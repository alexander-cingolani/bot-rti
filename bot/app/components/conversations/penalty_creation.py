"""
This module contains the necessary callbacks to allow admins to proccess reports
made by users.
"""

import logging
import os
from collections import defaultdict
from typing import Any, DefaultDict, cast

from app import config
from app.components.documents import PenaltyDocument
from app.components.utils import send_or_edit_message
from more_itertools import chunked
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SQLASession
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

from models import Category, Championship, Driver, Penalty, Report
from queries import (
    get_championship,
    get_driver,
    get_last_penalty_number,
    get_reports,
    get_reprimand_types,
    save_and_apply_penalty,
)

(
    ASK_ROUND,
    ASK_SESSION,
    ASK_DRIVER,
    ASK_INCIDENT_TIME,
    ASK_INFRACTION,
    ASK_CATEGORY,
    ASK_FACT,
    ASK_POINTS_PENALTY,
    ASK_REPRIMAND,
    ASK_PENALTY_REASON,
    ASK_CONFIRMATION,
    ASK_IF_NEXT,
) = range(14, 26)


engine = create_engine(os.environ["DB_URL"])

DBSession = sessionmaker(bind=engine, autoflush=False)


async def create_penalty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Allows admins to create penalties without a pre-existing report made by a leader."""

    sqla_session = DBSession()
    driver = get_driver(sqla_session, telegram_id=update.effective_user.id)
    if not driver:
        await update.message.reply_text(
            text="Non hai il permesso per usare questa funzione."
        )
        return ConversationHandler.END

    if not driver.has_permission(config.MANAGE_PENALTIES):
        await update.message.reply_text(
            text="Non hai il permesso per usare questa funzione."
        )
        return ConversationHandler.END

    user_data = cast(dict[str, Any], context.user_data)
    user_data["sqla_session"] = sqla_session

    championship = get_championship(sqla_session)
    if not championship:
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    user_data["championship"] = championship

    if update.message:
        user_data["penalty"] = Penalty()
    text = "In quale categoria è avvenuta l'infrazione?"

    buttons: list[InlineKeyboardButton] = []
    for i, category in enumerate(championship.categories):
        buttons.append(InlineKeyboardButton(category.name, callback_data=f"C{i}"))

    chunked_buttons = list(chunked(buttons, 3))
    chunked_buttons.append(
        [
            InlineKeyboardButton(text="Annulla", callback_data="cancel"),
        ]
    )
    if user_data.get("category"):
        chunked_buttons[-1].append(
            InlineKeyboardButton(text="Seleziona tappa »", callback_data=str(ASK_ROUND))
        )

    await send_or_edit_message(update, text, InlineKeyboardMarkup(chunked_buttons))

    return ASK_ROUND


async def ask_round(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = cast(dict[str, Any], context.user_data)
    if not update.callback_query.data.isnumeric():
        user_data["category"] = user_data["championship"].categories[
            int(update.callback_query.data.removeprefix("C"))
        ]
        user_data["penalty"].category = user_data["category"]

    category: Category = user_data["category"]

    buttons: list[InlineKeyboardButton] = []
    for i, championship_round in enumerate(category.rounds):
        if championship_round.is_completed:
            buttons.append(
                InlineKeyboardButton(
                    f"Tappa {championship_round.number}", callback_data=f"R{i}"
                )
            )

    chunked_buttons = list(chunked(buttons, 3))

    chunked_buttons.append(
        [
            InlineKeyboardButton("« Categoria", callback_data=str("create_penalty")),
            InlineKeyboardButton("Sessione »", callback_data=str(ASK_SESSION)),
        ]
    )

    reply_markup = InlineKeyboardMarkup(chunked_buttons)
    text = "Seleziona la tappa in cui è avvenuta l'infrazione:"
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    return ASK_SESSION


async def ask_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the championship round and asks what session the accident happened in."""

    user_data = cast(dict[str, Any], context.user_data)
    category: Category = cast(Category, user_data["category"])
    sqla_session = cast(SQLASession, user_data["sqla_session"])
    penalty = cast(Penalty, user_data["penalty"])

    if not update.callback_query.data.isnumeric():
        penalty.round = category.rounds[
            int(update.callback_query.data.removeprefix("R"))
        ]
        penalty.number = (
            get_last_penalty_number(
                sqla_session,
                round_id=penalty.round.id,
            )
            + 1
        )

    text = "In quale sessione è avvenuta l'infrazione?"

    buttons: list[InlineKeyboardButton] = []
    for i, session in enumerate(penalty.round.sessions):
        buttons.append(InlineKeyboardButton(session.name, callback_data=f"S{i}"))

    chunked_buttons = list(chunked(buttons, 3))
    chunked_buttons.append(
        [
            InlineKeyboardButton("« Tappa", callback_data=str(ASK_ROUND)),
            InlineKeyboardButton("Minuto »", callback_data=str(ASK_INCIDENT_TIME)),
        ]
    )

    reply_markup = InlineKeyboardMarkup(chunked_buttons)
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    return ASK_INCIDENT_TIME


async def ask_incident_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the championship round and asks when the accident happened."""

    user_data = cast(dict[str, Any], context.user_data)

    if not update.callback_query.data.isnumeric():
        user_data["penalty"].session = user_data["penalty"].round.sessions[
            int(update.callback_query.data.removeprefix("S"))
        ]

    text = "In che minuto è stata commessa l'infrazione?"
    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("« Sessione", callback_data=str(ASK_SESSION)),
                InlineKeyboardButton(
                    "Pilota colpevole »", callback_data=str(ASK_DRIVER)
                ),
            ]
        ]
    )
    await send_or_edit_message(update, text, reply_markup)
    return ASK_DRIVER


async def ask_driver(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the championship round and asks who the driver to report is."""

    user_data = cast(dict[str, Any], context.user_data)

    if update.message:
        user_data["penalty"].incident_time = update.message.text

    text = "Quale pilota ha commesso l'infrazione?"

    buttons: list[InlineKeyboardButton] = []
    for i, driver in enumerate(user_data["penalty"].session.participating_drivers()):
        buttons.append(InlineKeyboardButton(driver.full_name, callback_data=f"D{i}"))

    chunked_buttons = list(chunked(buttons, 2))
    chunked_buttons.append(
        [
            InlineKeyboardButton("« Minuto", callback_data=str(ASK_INCIDENT_TIME)),
            InlineKeyboardButton(
                "Infrazione commessa »", callback_data=str(ASK_INFRACTION)
            ),
        ]
    )

    await send_or_edit_message(update, text, InlineKeyboardMarkup(chunked_buttons))

    return ASK_INFRACTION


async def ask_infraction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the driver and asks what infraction he committed."""

    user_data = cast(dict[str, Any], context.user_data)
    penalty = cast(Penalty, user_data["penalty"])

    if not update.callback_query.data.isnumeric():
        driver: Driver = penalty.session.participating_drivers()[
            int(update.callback_query.data.removeprefix("D"))
        ]
        # Driver always has a team here.
        penalty.team = driver.current_team()  # type: ignore
        penalty.driver = driver

    buttons: list[list[InlineKeyboardButton]] = []
    for i, infraction in enumerate(config.INFRACTIONS):
        buttons.append([InlineKeyboardButton(infraction, callback_data=f"i{i}")])

    buttons.append(
        [
            InlineKeyboardButton("« Pilota colpevole", callback_data=str(ASK_DRIVER)),
            InlineKeyboardButton(
                "Secondi di penalità »", callback_data=str(ASK_POINTS_PENALTY)
            ),
        ]
    )

    text = "Qual'è l'infrazione commessa?"
    await update.callback_query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons)
    )

    return ASK_POINTS_PENALTY


async def report_processing_entry_point(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Asks the user which category he wants to view reports from,
    after the /start_reviewing command is issued."""

    sqla_session = DBSession()
    championship = get_championship(sqla_session)

    user_data = cast(dict[str, Any], context.user_data)
    user_data["sqla_session"] = sqla_session
    user_data["championship"] = championship

    if not championship:
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    driver = get_driver(sqla_session, telegram_id=update.effective_user.id)
    if not driver:
        await update.message.reply_text(
            text="Non hai il permesso per usare questa funzione."
        )
        return ConversationHandler.END

    if not driver.has_permission(config.MANAGE_PENALTIES):
        await update.message.reply_text(
            text="Non hai il permesso per usare questa funzione."
        )
        return ConversationHandler.END

    reports = get_reports(sqla_session, is_reviewed=False)

    if not reports:
        text = "Non ci sono segnalazioni da processare."
        await send_or_edit_message(update, text)
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    user_data["unreviewed_reports"] = reports
    report_categories: DefaultDict[str, int] = defaultdict(int)
    for report in reports:
        report_categories[report.round.category.name] += 1

    total = sum(report_categories.values())

    if total == 1:
        text = f"C'è solo una segnalazione in {reports[0].category.name}"
    elif len(report_categories) == 1:
        text = f"Ci sono {total} segnalazioni in {reports.pop().round.category.name}."
    else:
        text = f"Hai {total} segnalazioni da processare, di cui:\n"
        for category, number in report_categories.items():
            text += f"{number} in {category}\n"
    text += "\nSeleziona la categoria dove vuoi giudicare le segnalazioni:"

    buttons: list[InlineKeyboardButton] = []
    for i, category_obj in enumerate(championship.categories):
        if report_categories.get(category_obj.name):
            buttons.append(
                InlineKeyboardButton(category_obj.name, callback_data=f"C{i}")
            )

    category_buttons = list(chunked(buttons, 3))
    category_buttons.append([InlineKeyboardButton("Annulla", callback_data="cancel")])
    reply_markup = InlineKeyboardMarkup(category_buttons)

    await send_or_edit_message(update, text, reply_markup)
    return ASK_CATEGORY


async def ask_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Shows the user the first unreviewed report in the selected category."""

    user_data = cast(dict[str, Any], context.user_data)
    sqla_session = cast(SQLASession, user_data["sqla_session"])
    reports = cast(list[Report], user_data["unreviewed_reports"])
    championship = cast(Championship, user_data["championship"])

    if not update.callback_query.data.isnumeric():
        user_data["selected_category"] = championship.categories[
            int(update.callback_query.data.removeprefix("C"))
        ]

    selected_category = cast(Category, user_data["selected_category"])

    text = "Non risultano esserci segnalazioni "

    for report in reports:
        if not report.category.id == selected_category.id:
            continue

        text = (
            f"<b>{report.category.name}</b>\n"
            f"<i>Tappa {report.round.number}</i> ({report.round.circuit.abbreviated_name}) - Segnalazione no.{report.number}\n\n"
            f"<b>Piloti coinvolti</b>: {report.reported_driver.full_name}, "
            f"{report.reporting_driver.full_name}\n"
            f"<b>Sessione</b>: {report.session.name}\n"
            f"<b>Minuto incidente</b>: {report.incident_time}\n"
            f"<b>Motivo segnalazione</b>: {report.reason}"
        )
        penalty = Penalty.from_report(report)
        penalty.number = (
            get_last_penalty_number(
                sqla_session,
                round_id=penalty.round.id,
            )
            + 1
        )
        user_data["penalty"] = penalty
        user_data["current_report"] = report
        reply_markup: list[InlineKeyboardButton] = [
            InlineKeyboardButton("« Categoria", callback_data="start_reviewing"),
            InlineKeyboardButton("Fatto »", callback_data=str(ASK_FACT)),
        ]
        break

    await update.callback_query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup([reply_markup])
    )

    return ASK_FACT


async def ask_fact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the admin for the fact when callback_data containing "ask_fact" is received."""

    user_data = cast(dict[str, Any], context.user_data)
    report: Report = user_data["current_report"]
    text = "Seleziona il fatto accaduto, oppure scrivine uno tu.\n"

    buttons: list[InlineKeyboardButton] = []

    for i, fact in enumerate(config.FACTS):
        callback_data = f"qf{i}" if report.session.is_quali else f"f{i}"
        buttons.append(
            InlineKeyboardButton(
                text=f"{i + 1}",
                callback_data=callback_data,
            )
        )
        text += f"\n{i + 1} - {fact}".format(
            a=report.reporting_driver.current_race_number
        )

    chunked_buttons = list(chunked(buttons, 4))

    next_step = ASK_POINTS_PENALTY
    next_step_button = InlineKeyboardButton(
        "Punti penalità »", callback_data=str(next_step)
    )
    chunked_buttons.append(
        [
            InlineKeyboardButton(
                "« Vedi segnalazione", callback_data=str(ASK_CATEGORY)
            ),
            next_step_button,
        ]
    )

    await update.callback_query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(chunked_buttons)
    )
    return next_step


async def ask_points_penalty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the time penalty and asks user for the decision, after a valid fact has been entered."""
    user_data = cast(dict[str, Any], context.user_data)

    if update.callback_query:
        # Save infraction if the report was made via the alternative command "penalizza"
        if update.callback_query.data[0] == "i":
            user_data["penalty"].fact = config.INFRACTIONS[
                int(update.callback_query.data.removeprefix("i"))
            ]
        elif not update.callback_query.data.isdigit():
            if user_data["current_report"].session.is_quali:
                user_data["penalty"].fact = config.FACTS[
                    int(update.callback_query.data.removeprefix("qf"))
                ].format(a=user_data["penalty"].driver.current_race_number)
                await ask_reprimand(update, context)
                return ASK_REPRIMAND

            user_data["penalty"].fact = config.FACTS[
                int(update.callback_query.data.removeprefix("f"))
            ].format(a=user_data["current_report"].reporting_driver.current_race_number)

    else:
        user_data["penalty"].fact = update.message.text

    text = "Seleziona i punti di penalità inflitti:"
    buttons: list[list[InlineKeyboardButton]] = [[]]
    for points in ("3", "6", "12"):
        buttons[0].append(
            InlineKeyboardButton(
                f"{points}",
                callback_data=f"pp{points}",
            )
        )

    buttons.append(
        [InlineKeyboardButton("Nessuna penalità in punti", callback_data="no_penalty")]
    )

    previous_step = (
        ASK_FACT if not user_data.get("alternative_entry_point") else ASK_INFRACTION
    )
    buttons.append(
        [
            InlineKeyboardButton("« Fatto", callback_data=str(previous_step)),
            InlineKeyboardButton("Reprimende »", callback_data=str(ASK_REPRIMAND)),
        ]
    )
    reply_markup = InlineKeyboardMarkup(buttons)

    await send_or_edit_message(update, text, reply_markup)

    return ASK_REPRIMAND


async def ask_reprimand(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves warnings (if given) and asks if any reprimands are to be given."""

    user_data = cast(dict[str, Any], context.user_data)
    sqla_session: SQLASession = user_data["sqla_session"]

    if update.callback_query:
        if (
            not update.callback_query.data.isdigit()
            and "qf" not in update.callback_query.data
        ):
            if "no_penalty" in update.callback_query.data:
                user_data["penalty"].points = 0
                user_data["point_penalty_text"] = None
            else:
                points = int(update.callback_query.data.removeprefix("pp"))
                user_data["penalty"].points = points
                user_data["point_penalty_text"] = (
                    f"Sottratti {points} punti in campionato"
                )

    else:
        points = int(update.message.text.split()[0])
        user_data["penalty"].points = points

    text = "Se data, seleziona la reprimenda:"
    reprimand_types = get_reprimand_types(sqla_session)
    user_data["reprimand_descriptions"] = {r.id: r.description for r in reprimand_types}
    buttons: list[list[InlineKeyboardButton]] = []
    for reprimand in reprimand_types:
        buttons.append(
            [
                InlineKeyboardButton(
                    reprimand.description, callback_data=f"rep{reprimand.id}"
                )
            ]
        )

    buttons.append(
        [InlineKeyboardButton("Nessuna reprimenda", callback_data="no_reprimand")]
    )

    buttons.append(
        [
            InlineKeyboardButton(
                "« Punti di penalità", callback_data=str(ASK_POINTS_PENALTY)
            ),
            InlineKeyboardButton(
                "Motivazione »", callback_data=str(ASK_PENALTY_REASON)
            ),
        ],
    )

    reply_markup = InlineKeyboardMarkup(buttons)

    await send_or_edit_message(update, text, reply_markup)

    return ASK_PENALTY_REASON


async def ask_penalty_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """If given, saves the reprimand and asks for the penalty reason."""

    user_data = cast(dict[str, Any], context.user_data)
    if update.callback_query:
        if not update.callback_query.data.isnumeric():
            if update.callback_query.data == "no_reprimand":
                user_data["reprimand_text"] = ""
            else:
                description = user_data["reprimand_descriptions"][
                    int(update.callback_query.data.removeprefix("rep"))
                ]
                user_data["reprimand_text"] = f"Reprimenda per {description}"

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("« Reprimende", callback_data=str(ASK_REPRIMAND)),
                InlineKeyboardButton(
                    "Controlla »", callback_data=str(ASK_CONFIRMATION)
                ),
            ]
        ]
    )

    text = "Scrivi la motivazione:"
    await send_or_edit_message(update, text, reply_markup)

    return ASK_CONFIRMATION


async def ask_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the reason and asks for confirmation."""

    user_data = cast(dict[str, Any], context.user_data)

    if not update.callback_query:
        user_data["penalty"].reason = update.message.text

    penalty: Penalty = user_data["penalty"]
    # Driver always has a team here.
    penalty.team = penalty.driver.current_team()  # type: ignore
    penalty.decision = ", ".join(
        filter(
            None,
            (
                user_data.get("point_penalty_text", None),
                user_data.get("reprimand_text", None),
            ),
        )
    )
    if not penalty.decision:
        penalty.decision = "Nessun'azione"
    if penalty.decision:
        penalty.decision += "."
    text = (
        f"<b>Segnalazione no.{penalty.number}</b> - Recap dati inseriti\n\n"
        f"<b>Tappa</b>: {penalty.round.number if penalty.round else '-'}\n"
        f"<b>Sessione</b>: {penalty.session.name}\n"
        f"<b>Pilota</b>: {penalty.driver.full_name if penalty.driver else '-'}\n"
        f"<b>Fatto</b>: {penalty.fact if penalty.fact else '-'}\n"
        f"<b>Decisione</b>: {penalty.decision if penalty.decision else '-'}\n"
        f"<b>Motivazione</b>: {penalty.reason if penalty.reason else '-'}"
    )
    reply_markup = [
        [InlineKeyboardButton("« Motivazione", callback_data=str(ASK_PENALTY_REASON))],
    ]

    if penalty.is_complete():
        reply_markup.append(
            [
                InlineKeyboardButton("Conferma decisione", callback_data="send_now"),
            ],
        )
    else:
        text += (
            "\n⚠️ Prima di inviare il report è necessario aver compilato tutti i campi."
        )

    await send_or_edit_message(update, text, InlineKeyboardMarkup(reply_markup))

    return ASK_IF_NEXT


async def send_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send the report and ends the conversation"""

    user_data = cast(dict[str, Any], context.user_data)
    sqla_session: SQLASession = user_data["sqla_session"]
    if user_data.get("current_report"):
        report = user_data["current_report"]
        report.is_reviewed = True
        sqla_session.commit()

    penalty: Penalty = user_data["penalty"]

    save_and_apply_penalty(sqla_session, penalty)
    file = PenaltyDocument(penalty).generate_document()
    await context.bot.send_document(
        chat_id=config.REPORT_CHANNEL,
        document=open(file, "rb"),
    )
    text = "Penalità applicata e inviata."

    await send_or_edit_message(update, text)
    sqla_session.close()
    user_data.clear()
    return ConversationHandler.END


async def go_back_handler_report_processing(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handles "go back" and "go forwards" buttons in the report_processing conversation.

    This function is called by the dispatcher whenever callback_query.data contains a number
    between 0 and 5.

    It works by calling the callback function associated to the step of the conversation
    (each step is represented by an integer between 0 and 5) contained in callback_query.data.
    After the callback function has finished executing it returns the step in callbackquery.data + 1
    in order to allow the conversation to continue.
    """

    callbacks = {
        ASK_ROUND: ask_round,
        ASK_SESSION: ask_session,
        ASK_INCIDENT_TIME: ask_incident_time,
        ASK_DRIVER: ask_driver,
        ASK_INFRACTION: ask_infraction,
        ASK_CATEGORY: ask_category,
        ASK_FACT: ask_fact,
        ASK_POINTS_PENALTY: ask_points_penalty,
        ASK_REPRIMAND: ask_reprimand,
        ASK_PENALTY_REASON: ask_penalty_reason,
        ASK_CONFIRMATION: ask_confirmation,
    }
    state = int(update.callback_query.data)
    await callbacks[state](update, context)

    return state + (1 if state != 17 else 3)


async def exit_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clears user_data and ends the conversation"""
    text = "Penalità annullata."
    await send_or_edit_message(update, text)

    user_data = cast(dict[str, Any], context.user_data)
    user_data["sqla_session"].close()
    user_data.clear()
    return ConversationHandler.END


penalty_creation = ConversationHandler(
    allow_reentry=True,
    entry_points=[
        CommandHandler(
            "segnalazioni",
            report_processing_entry_point,
            filters=filters.ChatType.PRIVATE,
        ),
        CommandHandler("penalizza", create_penalty, filters=filters.ChatType.PRIVATE),
        CallbackQueryHandler(report_processing_entry_point, r"^start_reviewing$"),
        CallbackQueryHandler(create_penalty, r"^create_penalty$"),
    ],
    states={
        ASK_ROUND: [CallbackQueryHandler(ask_round, r"^C[0-9]{1,}$")],
        ASK_SESSION: [CallbackQueryHandler(ask_session, r"^R[0-9]{1,}$")],
        ASK_INCIDENT_TIME: [CallbackQueryHandler(ask_incident_time, r"^S[0-9]{1,}$")],
        ASK_DRIVER: [MessageHandler(filters.TEXT, ask_driver)],
        ASK_INFRACTION: [CallbackQueryHandler(ask_infraction, r"^D[0-9]{1,}$")],
        ASK_CATEGORY: [
            CallbackQueryHandler(
                ask_category,
                r"^C[0-9]{1,}$",
            )
        ],
        ASK_FACT: [CallbackQueryHandler(ask_fact, r"^continue$")],
        ASK_POINTS_PENALTY: [
            CallbackQueryHandler(
                ask_points_penalty, r"^f[0-9]{1,}$|^i[0-9]{1,}$|^qf[0-9]{1,}$"
            ),
            MessageHandler(
                filters.Regex(r"^[^/]{2,}$"),
                ask_points_penalty,
            ),
        ],
        ASK_REPRIMAND: [
            CallbackQueryHandler(ask_reprimand, r"^pp[0-9]{1,}$|^no_penalty$")
        ],
        ASK_PENALTY_REASON: [
            CallbackQueryHandler(ask_penalty_reason, r"rep[0-9]{1,}|no_reprimand")
        ],
        ASK_CONFIRMATION: [
            MessageHandler(filters.Regex(r"^[^/]{20,}$"), ask_confirmation)
        ],
        ASK_IF_NEXT: [CallbackQueryHandler(send_report, r"^send_now$")],
    },
    fallbacks=[
        CommandHandler("esci", exit_conversation),
        CallbackQueryHandler(exit_conversation, r"^cancel$"),
        CallbackQueryHandler(go_back_handler_report_processing, r"^1[2-9]$|^2[0-7]$"),
    ],
)
