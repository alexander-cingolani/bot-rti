"""
This module contains all the callbacks necessary to allow users to create reports
"""

import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.components import config
from app.components.docs import ReportDocument
from app.components.models import Category, Driver, Report
from app.components.queries import (
    delete_report,
    get_championship,
    get_driver,
    get_last_report_number,
    get_report,
    save_object,
)
from app.components.utils import send_or_edit_message
from more_itertools import chunked
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

(
    CATEGORY,
    SESSION,
    LINK,
    REPORTING_DRIVER,
    REPORTED_DRIVER,
    MINUTE,
    REPORT_REASON,
    SEND,
    UNSEND,
) = range(3, 12)

from telegram.error import BadRequest

engine = create_engine(os.environ.get("DB_URL"))
_Session = sessionmaker(bind=engine, autoflush=False)


async def create_late_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user which category he wants to create a report in."""

    user_data = context.user_data
    user_data.clear()

    session = _Session()
    championship = get_championship(session)

    user_data["sqla_session"] = session
    user_data["championship"] = championship
    user_data["categories"] = {}
    reply_markup = []

    user_data["leader"] = get_driver(session, telegram_id=update.effective_user.id)
    if user_data["leader"].current_team().leader != user_data["leader"]:

        text = "Solamente i capi scuderia possono effettuare segnalazioni."
        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="Chiedi il permesso",
                        url=f"tg://user?id={config.OWNER}",
                    )
                ]
            ]
        )
        await update.message.reply_text(text=text, reply_markup=reply_markup)
        user_data["sqla_session"].close()
        user_data.clear()
        return ConversationHandler.END

    for i, category in enumerate(championship.categories):
        if category.first_non_completed_round():
            category_alias = f"c{i}"
            reply_markup.append(
                InlineKeyboardButton(category.name, callback_data=category_alias)
            )
            user_data["categories"][category_alias] = category
    reply_markup = InlineKeyboardMarkup(list(chunked(reply_markup, 3)))
    if not reply_markup:
        text = "Il campionato è terminato! Non è più possibile effettuare segnalazioni."
        await update.message.reply_text(text)
        user_data["sqla_session"].close()
        user_data.clear()
        return ConversationHandler.END

    text = "Scegli la categoria dove vuoi creare la segnalazione:"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

    context.chat_data["late_report"] = True
    return CATEGORY


async def save_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the category and asks what session the accident happened in."""

    user_data = context.user_data
    if not update.callback_query.data.isdigit():
        user_data["category"] = context.user_data["categories"][
            update.callback_query.data
        ]

    user_data["sessions"] = {}
    user_data["sessions"] = {}
    category: Category = user_data["category"]
    reply_markup = []

    for i, session in enumerate(category.first_non_completed_round().sessions):
        session_alias = f"s{i}"
        user_data["sessions"][session_alias] = session
        reply_markup.append(
            InlineKeyboardButton(session.name, callback_data=session_alias)
        )
    reply_markup = list(chunked(reply_markup, 3))
    reply_markup.append(
        [
            InlineKeyboardButton(
                "« Modifica Categoria", callback_data="create_late_report"
            )
        ]
    )

    round_number = category.first_non_completed_round().number
    text = f"""
<b>{user_data["category"].name}</b> - Tappa {round_number} 
Scegli la sessione dove è avvenuto l'incidente:"""

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(reply_markup)
        )
    else:
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(reply_markup)
        )
    return SESSION


async def create_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user the session in which the accident happened."""
    user = update.effective_user
    user_data = context.user_data
    user_data.clear()
    session = _Session()
    user_data["leader"] = get_driver(session, telegram_id=user.id)
    user_data["sqla_session"] = session

    if not user_data["leader"]:
        await update.message.reply_text(
            "Non sei ancora registrato, puoi farlo tramite /registrami"
        )
        user_data["sqla_session"].close()
        user_data.clear()
        return ConversationHandler.END

    if user_data["leader"].current_team().leader != user_data["leader"]:
        text = "Solamente i capi scuderia possono effettuare segnalazioni."
        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="Chiedi il permesso",
                        url=f"tg://user?id={config.OWNER}",
                    )
                ]
            ]
        )
        await update.message.reply_text(text=text, reply_markup=reply_markup)
        user_data["sqla_session"].close()
        user_data.clear()
        return ConversationHandler.END

    championship = get_championship(session)

    if not championship:
        text = "Il campionato è terminato! Non puoi più fare segnalazioni."
        await update.message.reply_text(text)
        user_data["sqla_session"].close()
        user_data.clear()
        return ConversationHandler.END

    user_data["championship"] = championship

    category: Category = championship.reporting_category()

    if not category:
        text = (
            "Il periodo per le segnalazioni è terminato. Se necessario, puoi chiedere "
            "il permesso a un admin.\n"
            "Dopo aver ottenuto il permesso crea la segnalazione con "
            "/segnalazione_ritardataria."
        )
        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Chiedi il permesso", url="https://t.me/+6Ksa63FEKTNkYmI0"
                    )
                ]
            ]
        )
        await update.message.reply_text(text, reply_markup=reply_markup)
        user_data["sqla_session"].close()
        user_data.clear()
        return ConversationHandler.END

    user_data["category"] = category
    championship_round = category.first_non_completed_round()

    text = (
        f"{championship_round.number}ª Tappa {category.name}"
        "\nIn che sessione è avvenuto l'incidente?"
    )

    user_data["sessions"] = {}
    reply_markup = []
    for i, session in enumerate(championship_round.sessions):
        session_alias = f"s{i}"
        user_data["sessions"][session_alias] = session
        reply_markup.append(
            InlineKeyboardButton(session.name, callback_data=session_alias)
        )
    reply_markup = list(chunked(reply_markup, 3))
    reply_markup.append([InlineKeyboardButton("Annulla", callback_data="cancel")])

    if not update.callback_query:
        context.user_data["message"] = await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(reply_markup)
        )
    else:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(reply_markup)
        )
    return SESSION


async def save_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the session and asks for the reporting driver."""

    user_data = context.user_data
    if not update.callback_query.data.isdigit():
        user_data["report"] = Report()
        user_data["report"].session = user_data["sessions"][update.callback_query.data]
        user_data["drivers"] = {}

    if not user_data["report"].session.is_quali:
        text = "Chi è la vittima?"
        reply_markup = []
        for i, driver in enumerate(user_data["leader"].current_team().drivers):
            driver: Driver = driver.driver
            driver_alias = f"d{i}"
            if driver.current_category() == user_data["category"]:
                user_data["drivers"][driver_alias] = driver
                reply_markup.append(
                    InlineKeyboardButton(driver.psn_id, callback_data=driver_alias)
                )
        reply_markup = list(chunked(reply_markup, 2))
        callback_function = (
            str(SESSION) if context.chat_data.get("late_report") else "create_report"
        )
        reply_markup.append(
            [
                InlineKeyboardButton(
                    "« Modifica sessione", callback_data=callback_function
                )
            ]
        )
        if user_data["report"].reporting_driver:
            reply_markup[-1].append(
                InlineKeyboardButton("Link video »", callback_data=LINK)
            )
        await update.callback_query.edit_message_text(
            text=text, reply_markup=InlineKeyboardMarkup(reply_markup)
        )
        return REPORTING_DRIVER

    text = (
        "Non essendo disponibili i replay delle qualifiche è necessario "
        "fornire un video dell'episodio. Incolla il link al video YouTube qui sotto."
    )
    callback_function = (
        str(SESSION) if context.chat_data.get("late_report") else "create_report"
    )
    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("« Modifica sessione", callback_data=callback_function)]]
    )

    if user_data["report"].video_link:
        reply_markup[-1].append(
            InlineKeyboardButton("Pilota vittima »", callback_data=str(LINK))
        )

    await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
    return LINK


async def save_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the link provided by the user and asks who is considered to be the victim."""
    user_data = context.user_data

    if (
        not getattr(update.callback_query, "data", "").isdigit()
        and user_data["report"].session.is_quali
    ):
        user_data["report"].video_link = update.message.text

    text = "Chi è la vittima?"
    reply_markup = []
    for i, driver in enumerate(user_data["category"].active_drivers()):
        driver: Driver = driver.driver
        driver_alias = f"d{i}"
        if driver.current_team().leader.driver_id == user_data["leader"].driver_id:
            user_data["drivers"][driver_alias] = driver
            reply_markup.append(
                InlineKeyboardButton(driver.psn_id, callback_data=driver_alias)
            )

    reply_markup = list(chunked(reply_markup, 2))
    reply_markup.append(
        [
            InlineKeyboardButton(
                "« Sessione",
                callback_data=str(SESSION)
                if context.chat_data.get("late_report")
                else "create_report",
            )
        ]
    )

    if user_data["report"].reporting_driver:
        reply_markup[-1].append(
            InlineKeyboardButton(
                "Pilota colpevole »", callback_data=str(REPORTING_DRIVER)
            )
        )

    await send_or_edit_message(
        update=update, message=text, reply_markup=InlineKeyboardMarkup(reply_markup)
    )

    return REPORTING_DRIVER


async def reporting_driver(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the victim and asks for the reported driver."""
    user_data = context.user_data
    if not update.callback_query.data.isdigit():
        context.user_data["report"].reporting_driver = user_data["drivers"][
            update.callback_query.data
        ]
    text = "Chi ritieni essere il colpevole?"
    reply_markup = []
    user_data["drivers"] = {}
    for i, driver in enumerate(user_data["category"].active_drivers()):
        driver: Driver = driver.driver
        driver_alias = f"d{i}"
        if driver.current_team().leader.driver_id != user_data["leader"].driver_id:
            user_data["drivers"][driver_alias] = driver
            reply_markup.append(
                InlineKeyboardButton(driver.psn_id, callback_data=driver_alias)
            )
    reply_markup = list(chunked(reply_markup, 2))
    reply_markup.append(
        [InlineKeyboardButton("« Pilota Vittima", callback_data=str(LINK))]
    )
    if user_data["report"].reported_driver:
        reply_markup[-1].append(
            InlineKeyboardButton(
                "Minuto incidente »", callback_data=str(REPORTED_DRIVER)
            )
        )

    await update.callback_query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(reply_markup)
    )
    return REPORTED_DRIVER


async def reported_driver(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the reported driver and asks for the minute."""

    user_data = context.user_data
    if not update.callback_query.data.isdigit():
        user_data["report"].reported_driver = user_data["drivers"][
            update.callback_query.data
        ]
    text = "In che minuto è avvenuto l'incidente?"

    reply_markup = [
        [
            InlineKeyboardButton(
                "« Pilota Colpevole",
                callback_data=str(REPORTING_DRIVER),
            )
        ]
    ]
    if user_data["report"].incident_time:
        reply_markup[-1].append(
            InlineKeyboardButton("Avanti »", callback_data=str(MINUTE))
        )

    await update.callback_query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(reply_markup)
    )
    return MINUTE


async def save_minute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the minute and asks for the reason."""

    if not update.callback_query:
        context.user_data["report"].incident_time = update.message.text

    text = (
        "<b>Seleziona una motivazione per la segnalazione:</b>\n"
        "(alternativamente scrivine una qui sotto)"
    )

    user_data = context.user_data
    reply_markup = [[]]

    for i, reason in enumerate(config.REASONS):
        i += 1
        reason = reason.format(
            a=user_data["report"].reporting_driver.psn_id,
            b=user_data["report"].reported_driver.psn_id,
        )
        text += f"\n{i} - <i>{reason}</i>"
        reply_markup[0].append(InlineKeyboardButton(text=str(i), callback_data=f"r{i}"))
    reply_markup.append(
        [
            InlineKeyboardButton(
                "« Minuto Incidente ", callback_data=str(REPORTED_DRIVER)
            )
        ]
    )
    if user_data["report"].report_reason:
        reply_markup[-1].append(
            InlineKeyboardButton("Avanti »", callback_data=str(REPORT_REASON))
        )

    await send_or_edit_message(
        update=update, message=text, reply_markup=InlineKeyboardMarkup(reply_markup)
    )

    return REPORT_REASON


async def save_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Saves the reason and asks if to send the report or not."""
    user_data = context.user_data
    if update.callback_query:
        if not update.callback_query.data.isdigit():
            user_data["report"].report_reason = config.REASONS[
                int(update.callback_query.data.removeprefix("r")) - 1
            ].format(
                a=user_data["report"].reporting_driver.psn_id,
                b=user_data["report"].reported_driver.psn_id,
            )
    else:
        user_data["report"].report_reason = update.message.text
    report: Report = user_data["report"]
    text = (
        f"Contolla che i dati inseriti siano corretti, poi premi "
        '"conferma e invia" per inviare la segnalazione.\n'
        "Dopo aver inviato la segnalazione avrai la possibilità di ritirarla entro 30 min."
        f"\n\n<b>Sessione</b>: <i>{report.session.name}</i>"
        f"\n<b>Pilota Vittima</b>: <i>{report.reporting_driver.psn_id}</i>"
        f"\n<b>Pilota Colpevole</b>: <i>{report.reported_driver.psn_id}</i>"
        f"\n<b>Minuto Incidente</b>: <i>{report.incident_time}</i>"
        f"\n<b>Motivo Segnalazione</b>: <i>{report.report_reason}</i>"
        f"\n{f'<b>Video</b>: <i>{report.video_link}</i>' if report.video_link else ''}"
    )

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Annulla  ❌", callback_data="cancel"),
                InlineKeyboardButton("Conferma e invia  ✅", callback_data="confirm"),
            ],
            [
                InlineKeyboardButton(
                    "« Motivo Segnalazione", callback_data=str(MINUTE)
                ),
            ],
        ]
    )

    await send_or_edit_message(update=update, message=text, reply_markup=reply_markup)
    return SEND


async def send_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the report to the report channel and saves it to the database."""

    user_data = context.user_data

    category: Category = user_data["category"]

    if not category.can_report_today() and not context.chat_data.get("late_report"):
        text = "Troppo tardi! La mezzanotte è già scoccata."
        await update.callback_query.edit_message_text(text=text)

    if update.callback_query.data == "confirm":

        report: Report = user_data["report"]
        report.category = category
        report.round = category.first_non_completed_round()
        report.reported_team = report.reported_driver.current_team()
        report.reporting_team = report.reporting_driver.current_team()
        report.number = (
            get_last_report_number(
                user_data["sqla_session"], category.category_id, report.round.round_id
            )
            + 1
        )

        channel = (
            config.LATE_REPORT_CHAT
            if context.chat_data.get("late_report")
            else config.REPORT_CHANNEL
        )

        report_document_name = ReportDocument(report).generate_document()

        message = await context.bot.send_document(
            chat_id=channel, document=open(report_document_name, "rb")
        )
        report.channel_message_id = message.message_id

        try:
            save_object(user_data["sqla_session"], report)
        except IntegrityError:
            os.remove(report_document_name)
            await message.delete()
            await update.callback_query.edit_message_text(
                "Problemi, problemi, problemi! 😓\n"
                f"Questo errore è dovuto all'incompetenza di {config.OWNER.mention_html()}.\n"
                "Non farti problemi ad insultarlo in chat."
            )
            user_data["sqla_session"].close()
            user_data.clear()
            return ConversationHandler.END

        callback_data = (
            f"withdraw_late_report_{report.report_id}"
            if context.chat_data.get("late_report")
            else f"withdraw_late_report{report.report_id}"
        )
        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Ritira segnalazione ↩",
                        callback_data=callback_data,
                    )
                ]
            ]
        )

        text = (
            "Segnalazione inviata!"
            "\nSe noti un errore hai 30 minuti di tempo per ritirarla."
            "\nRicorda che creando una nuova segnalazione perderai "
            "la possibilità di ritirare quella precedente."
        )
        await update.callback_query.edit_message_text(
            text=text, reply_markup=reply_markup
        )

        return UNSEND

    if update.callback_query.data == "cancel":
        await update.callback_query.edit_message_text("Segnalazione annullata!")
        user_data["sqla_session"].close()
        user_data.clear()
        return ConversationHandler.END


async def change_state_rep_creation(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handles "go back" and "go forwards" buttons in the report_creation conversation.

    This function is called by the dispatcher whenever callback_query.data contains a number
    between 6 and 14.

    It works by calling the callback function associated to the step of the
    conversation (each step is represented by an integer between 6 and 14)
    contained in callback_query.data. After the callback function has finished
    executing it returns the step in callbackquery.data + 1 in order to allow the
    conversation to continue.
    """
    category_handler = (
        create_late_report if context.chat_data.get("late_report") else create_report
    )
    session_handler = (
        save_category if context.chat_data.get("late_report") else create_report
    )
    callbacks = {
        CATEGORY: category_handler,
        SESSION: session_handler,
        LINK: save_link,
        REPORTING_DRIVER: reporting_driver,
        REPORTED_DRIVER: reported_driver,
        MINUTE: save_minute,
        REPORT_REASON: save_reason,
        SEND: send_report,
    }
    state = int(update.callback_query.data)

    await callbacks.get(state)(update, context)

    return (
        state
        if context.chat_data.get("late_report") and (state == 7 or state is None)
        else state + 1
    )


async def exit_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Clears user_data and ends the conversation"""

    text = "Segnalazione annullata."
    await send_or_edit_message(update, text)
    context.user_data["sqla_session"].close()
    context.user_data.clear()
    return ConversationHandler.END


async def withdraw_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Withdraws the last report made by the user if made less than 30 minutes ago."""
    if "late" in update.callback_query.data:
        report_id = update.callback_query.data.removeprefix("withdraw_late_report_")
    else:
        report_id = update.callback_query.data.removeprefix("withdraw_report_")

    report = get_report(context.user_data["sqla_session"], report_id)
    if report:
        if (datetime.now(tz=ZoneInfo("Europe/Rome")) - report.report_time) < timedelta(
            minutes=30
        ):

            text = f"<i><b>[segnalazione ritirata]</b></i>"
            try:
                await context.bot.edit_message_caption(
                    chat_id=config.REPORT_CHANNEL,
                    message_id=report.channel_message_id,
                    caption=text,
                )
            except BadRequest:
                await context.bot.edit_message_caption(
                    chat_id=config.LATE_REPORT_CHAT,
                    message_id=report.channel_message_id,
                    caption=text,
                )

            text = "Segnalazione ritirata."

            delete_report(context.user_data["sqla_session"], report_id)
        else:
            text = "Troppo tardi per ritirarla!"
        await update.callback_query.edit_message_text(text)
    context.chat_data.clear()


report_creation = ConversationHandler(
    allow_reentry=True,
    entry_points=[
        CommandHandler("segnala", create_report, filters=filters.ChatType.PRIVATE),
        CommandHandler(
            "segnalazione_ritardataria",
            create_late_report,
            filters=filters.ChatType.PRIVATE,
        ),
        CallbackQueryHandler(create_report, r"^create_report$"),
        CallbackQueryHandler(create_late_report, r"^create_late_report$"),
    ],
    states={
        CATEGORY: [CallbackQueryHandler(save_category, r"^c[0-9]{1,}$")],
        SESSION: [CallbackQueryHandler(save_session, r"^s[0-9]{1,}$")],
        LINK: [
            MessageHandler(
                filters.Regex(
                    r"^((?:https?:)?\/\/)?((?:www|m)\.)?"
                    r"((?:youtube(-nocookie)?\.com|youtu.be))"
                    r"(\/(?:[\w\-]+\?v=|embed\/|v\/)?)([\w\-]+)(\S+)?$"
                ),
                save_link,
            ),
            CallbackQueryHandler(save_link, r"^[6-9]|1[0-2]$"),
        ],
        REPORTING_DRIVER: [CallbackQueryHandler(reporting_driver, r"^d[0-9]{1,}$")],
        REPORTED_DRIVER: [CallbackQueryHandler(reported_driver, r"^d[0-9]{1,}$")],
        MINUTE: [
            MessageHandler(
                filters.Regex(r"^.{2,50}$"),
                save_minute,
            )
        ],
        REPORT_REASON: [
            MessageHandler(filters.Regex(r"^.{20,}$"), save_reason),
            CallbackQueryHandler(
                save_reason,
                r"^r[0-9]{1,}$",
            ),
        ],
        SEND: [CallbackQueryHandler(send_report, r"^confirm$")],
        UNSEND: [
            CallbackQueryHandler(
                withdraw_report,
                r"^withdraw_(late_)?report_"
                r"[0-9a-fA-F]{8}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b"
                r"-[0-9a-fA-F]{12}$",
            )
        ],
    },
    fallbacks=[
        CommandHandler("esci", exit_conversation),
        CallbackQueryHandler(exit_conversation, r"^cancel$"),
        CallbackQueryHandler(change_state_rep_creation, r"^[3-9]$|^1[0-1]$"),
    ],
)
