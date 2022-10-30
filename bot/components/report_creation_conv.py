import os
from datetime import datetime, timedelta

from more_itertools import chunked
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from components import config
from components.models import Category, Driver, Report
from components.queries import (
    delete_report,
    get_championship,
    get_driver,
    get_last_report_by,
    get_latest_report_number,
    get_reports,
    save_object,
    update_object,
)
from components.reportdoc import ReportDocument

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
) = range(6, 15)


async def create_late_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user which category he wants to create a report in."""
    championship = get_championship()
    user_data = context.user_data
    user_data["championship"] = championship
    user_data["categories"] = {}
    reply_markup = []

    user_data["leader"] = get_driver(telegram_id=update.effective_user.id)
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
        return ConversationHandler.END

    text = "Scegli la categoria dove vuoi creare la segnalazione:"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

    context.user_data["late_report"] = True
    return CATEGORY


async def save_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the category and asks what session the accident happened in."""

    user_data = context.user_data
    if not update.callback_query.data.isdigit():
        category: Category = context.user_data["categories"][update.callback_query.data]
        user_data["category"] = category
    user_data["sessions"] = {}
    user_data["sessions"] = {}
    reply_markup = []
    for i, session in enumerate(user_data["category"].sessions):
        session = session.session
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

    circuit = user_data["category"].first_non_completed_round().circuit
    text = f"""
<b>{user_data["category"].name}</b> - {circuit} 
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

    user_data["leader"] = get_driver(telegram_id=user.id)
    if not user_data["leader"]:
        await update.message.reply_text(
            "Non sei ancora registrato, puoi farlo tramite /registrami"
        )
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
        return ConversationHandler.END

    user_data["championship"] = get_championship()
    if not user_data["championship"]:
        text = "Il campionato è terminato! Non puoi più fare segnalazioni."
        await update.message.reply_text(text)
        return ConversationHandler.END

    user_data["category"] = user_data["championship"].reporting_category()
    if not user_data["category"]:
        text = """
Il periodo per le segnalazioni è terminato. Se necessario, puoi chiedere il permesso a un admin.
Dopo aver ottenuto il permesso crea la segnalazione con /segnalazione_ritardataria.
"""
        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Chiedi il permesso", url=f"https://t.me/+6Ksa63FEKTNkYmI0"
                    )
                ]
            ]
        )
        await update.message.reply_text(text, reply_markup=reply_markup)
        return ConversationHandler.END

    round = user_data["category"].first_non_completed_round()
    text = f"{round.number}ª Tappa {user_data['category'].name}\nIn che sessione è avvenuto l'incidente?"
    user_data["sessions"] = {}
    reply_markup = []
    for i, session in enumerate(user_data["category"].sessions):
        session = session.session
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
        if "qualific" not in user_data["report"].session.name.lower():
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
                str(SESSION) if user_data.get("late_report") else "create_report"
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

        text = "Non essendo disponibili i replay delle qualifiche è necessario fornire un video dell'episodio. Incolla il link qui sotto."
        callback_function = (
            str(SESSION) if user_data.get("late_report") else "create_report"
        )
        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "« Modifica sessione", callback_data=callback_function
                    )
                ]
            ]
        )
        if user_data["report"].video_link:
            reply_markup[-1].append(
                InlineKeyboardButton("Pilota vittima »", callback_data=str(LINK))
            )
        await update.callback_query.edit_message_text(
            text=text, reply_markup=reply_markup
        )
        return LINK


async def save_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data

    if (
        not getattr(update.callback_query, "data", "").isdigit()
        and "qualific" in user_data["report"].session.name.lower()
    ):
        user_data["report"].video_link = update.message.text
    text = "Chi è la vittima?"
    reply_markup = []
    for i, driver in enumerate(user_data["category"].drivers):
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
                if context.user_data.get("late_report")
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
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(reply_markup)
        )
    else:
        await update.message.reply_text(
            text=text, reply_markup=InlineKeyboardMarkup(reply_markup)
        )
    return REPORTING_DRIVER


async def reporting_driver(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the reporting driver and asks for the reported driver"""
    user_data = context.user_data
    if not update.callback_query.data.isdigit():
        context.user_data["report"].reporting_driver = user_data["drivers"][
            update.callback_query.data
        ]
    text = "Chi ritieni essere il colpevole?"
    reply_markup = []
    user_data["drivers"] = {}
    for i, driver in enumerate(user_data["category"].drivers):
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
    """Saves the reported driver and asks for the minute"""

    user_data = context.user_data
    if not update.callback_query.data.isdigit():
        user_data["report"].reported_driver = user_data["drivers"][
            update.callback_query.data
        ]
    text = "Quando è avvenuto l'incidente? (mm:ss)"

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
    """Saves the minute and asks for the reason"""

    if not update.callback_query:
        context.user_data["report"].incident_time = update.message.text

    text = """
<b>Seleziona una motivazione per la segnalazione:</b>
(alternativamente scrivine una qui sotto)
"""

    user_data = context.user_data
    reply_markup = [[]]

    for i, reason in enumerate(config.REASONS):
        i += 1
        reason = reason.format(
            a=user_data["report"].reporting_driver.psn_id,
            b=user_data["report"].reported_driver.psn_id,
        )
        text += f"\n{i} - <i>{reason}</i>"
        reply_markup[0].append(
            InlineKeyboardButton(text=str(i), callback_data=f"reason{i}")
        )
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
    if not update.callback_query:
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(reply_markup)
        )
    else:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(reply_markup)
        )
    return REPORT_REASON


async def save_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Saves the reason and asks if to send or not"""
    user_data = context.user_data
    if update.callback_query:
        if not update.callback_query.data.isdigit():
            user_data["report"].report_reason = config.REASONS[
                int(update.callback_query.data.replace("reason", "")) - 1
            ].format(
                a=user_data["report"].reporting_driver.psn_id,
                b=user_data["report"].reported_driver.psn_id,
            )
    else:
        user_data["report"].report_reason = update.message.text
    report: Report = user_data["report"]
    text = f"""Dopo aver controllato che i dati inseriti siano corretti, premi "conferma e invia" per inviare la segnalazione.
Dopo aver inviato la segnalazione avrai la possibilità di ritirarla entro 30 min.

<b>Sessione</b>: <i>{report.session.name}</i>
<b>Pilota Vittima</b>: <i>{report.reporting_driver.psn_id}</i>
<b>Pilota Colpevole</b>: <i>{report.reported_driver.psn_id}</i>
<b>Minuto Incidente</b>: <i>{report.incident_time}</i>
<b>Motivo Segnalazione</b>: <i>{report.report_reason}</i>
{f'<b>Video</b>: <i>{report.video_link}</i>' if report.video_link else ''}
 """
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

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=text, reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)
    return SEND


async def send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the report to the report channel and saves it in the database."""

    user_data = context.user_data
    if update.callback_query.data == "confirm":
        category: Category = user_data["category"]
        report: Report = user_data["report"]
        report.category = category
        report.round = (
            user_data["round"]
            if user_data.get("round")
            else category.first_non_completed_round()
        )
        report.reported_team = report.reported_driver.current_team()
        report.reporting_team = report.reporting_driver.current_team()
        report.number = get_latest_report_number(category.category_id) + 1

        channel = (
            config.TEST_CHANNEL
            if user_data.get("late_report")
            else config.REPORT_CHANNEL
        )

        report_document_name = ReportDocument(report).generate_document()
        with open(report_document_name, "rb") as document:
            message = await context.bot.send_document(
                chat_id=channel, document=document
            )

        report.channel_message_id = message.message_id
        update_object()

        os.remove(report_document_name)

        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Ritira segnalazione ↩", callback_data="withdraw_report"
                    )
                ]
            ]
        )
        await update.callback_query.edit_message_text(
            text="""
La segnalazione è stata inviata, se hai notato un errore, puoi ritirarla entro 30 minuti.
Ricorda che creando una nuova segnalazione perderai la possibilità di ritirare quella precedente.
""",
            reply_markup=reply_markup,
        )
    elif update.callback_query.data == "cancel":
        user_data.clear()
    save_object(report)
    return UNSEND


async def change_state_rep_creation(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handles "go back" and "go forwards" buttons in the report_creation conversation.

    This function is called by the dispatcher whenever callback_query.data contains a number
    between 6 and 14.

    It works by calling the callback function associated to the step of the conversation
    (each step is represented by an integer between 6 and 14) contained in callback_query.data.
    After the callback function has finished executing it returns the step in callbackquery.data + 1
    in order to allow the conversation to continue.
    """
    category_handler = (
        create_late_report if context.user_data.get("late_report") else create_report
    )
    session_handler = (
        save_category if context.user_data.get("late_report") else create_report
    )
    callbacks = {
        CATEGORY: category_handler,
        SESSION: session_handler,
        LINK: save_link,
        REPORTING_DRIVER: reporting_driver,
        REPORTED_DRIVER: reported_driver,
        MINUTE: save_minute,
        REPORT_REASON: save_reason,
        SEND: send,
    }
    state = int(update.callback_query.data)
    await callbacks.get(state)(update, context)
    return (
        state
        if context.user_data.get("late_report") and (state == 7 or state is None)
        else state + 1
    )


async def exit_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Clears user_data and ends the conversation"""
    context.user_data.clear()
    text = "Segnalazione annullata."
    if update.message:
        await update.message.reply_text(text)
    else:
        await update.callback_query.edit_message_text(text)
    return ConversationHandler.END


async def withdraw_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Withdraws the last report made by the user if made less than 30 minutes ago."""

    reporting_team_id = (
        get_driver(telegram_id=update.effective_user.id).current_team().team_id
    )
    report = get_last_report_by(reporting_team_id)
    if report:
        if (report.report_time - datetime.now()) < timedelta(minutes=30):

            await context.bot.delete_message(
                chat_id=config.REPORT_CHANNEL, message_id=report.channel_message_id
            )
            text = "Segnalazione ritirata."

            delete_report(report)
        else:
            text = "Troppo tardi, adesso ti attacchi!"
        await update.callback_query.edit_message_text(text)


report_creation = ConversationHandler(
    allow_reentry=True,
    entry_points=[
        CommandHandler(
            "nuova_segnalazione", create_report, filters=filters.ChatType.PRIVATE
        ),
        CommandHandler(
            "segnalazione_ritardataria",
            create_late_report,
            filters=filters.ChatType.PRIVATE,
        ),
        CallbackQueryHandler(create_report, "create_report"),
        CallbackQueryHandler(create_late_report, "create_late_report"),
        CallbackQueryHandler(change_state_rep_creation, r"^[6-9]|1[0-2]$"),
    ],
    states={
        CATEGORY: [CallbackQueryHandler(save_category, r"c0|c1|c2")],
        SESSION: [CallbackQueryHandler(save_session, r"s0|s1|s2")],
        LINK: [
            MessageHandler(
                filters.Regex(
                    r"^((?:https?:)?\/\/)?((?:www|m)\.)?((?:youtube(-nocookie)?\.com|youtu.be))(\/(?:[\w\-]+\?v=|embed\/|v\/)?)([\w\-]+)(\S+)?$"
                ),
                save_link,
            ),
            CallbackQueryHandler(save_link, r"^[6-9]|1[0-2]$"),
        ],
        REPORTING_DRIVER: [
            CallbackQueryHandler(
                reporting_driver, r"|".join(f"d{num}" for num in range(20))
            )
        ],
        REPORTED_DRIVER: [
            CallbackQueryHandler(
                reported_driver, r"|".join(f"d{num}" for num in range(20))
            )
        ],
        MINUTE: [
            MessageHandler(
                filters.Regex(r"^(?:(?:([01]?\d|2[0-3]):)?([0-5]?\d):)?([0-5]?\d)$"),
                save_minute,
            )
        ],
        REPORT_REASON: [
            MessageHandler(filters.Regex(r"^.{20,}$"), save_reason),
            CallbackQueryHandler(
                save_reason,
                r"|".join(map(lambda x: f"reason{x}", range(len(config.REASONS) + 1))),
            ),
        ],
        SEND: [CallbackQueryHandler(send, "confirm")],
        UNSEND: [CallbackQueryHandler(withdraw_report, "withdraw_report")],
    },
    fallbacks=[
        CommandHandler("esci", exit_conversation),
        CallbackQueryHandler(exit_conversation, "cancel"),
    ],
)
