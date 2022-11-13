"""
This module contains the necessary callbacks to allow admins to proccess reports
made by users.
"""

import os
from collections import defaultdict

from app.components import config
from app.components.models import Category, DriverCategory, Report
from app.components.queries import (
    get_championship,
    get_last_report_number,
    get_reports,
    save_and_apply_report,
)
from app.components.reportdoc import ReviewedReportDocument
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

(
    NEW_REPORT,
    ASK_ROUND,
    ASK_SESSION,
    ASK_DRIVER,
    ASK_INCIDENT_TIME,
    ASK_INFRACTION,
    ASK_CATEGORY,
    ASK_FACT,
    ASK_SECONDS,
    ASK_LICENCE_POINTS,
    ASK_WARNINGS,
    ASK_PENALTY_REASON,
    ASK_QUEUE_OR_SEND,
    ASK_IF_NEXT,
    END_REPORTING,
) = range(12, 27)


async def create_penalty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Allows admins to create reports without a pre-existing one made by a driver."""

    if update.effective_user.id not in config.ADMINS:
        await update.message.reply_text(text="Questo comando è riservato agli admin.")
        return ConversationHandler.END

    championship = get_championship()
    context.user_data["championship"] = championship

    if update.message:
        context.user_data["current_report"] = Report()

    text = "In quale categoria è avvenuta l'infrazione?"

    buttons = []
    for i, category in enumerate(championship.categories):

        buttons.append(InlineKeyboardButton(category.name, callback_data=f"C{i}"))
    buttons = list(chunked(buttons, 3))
    buttons.append(
        [
            InlineKeyboardButton(text="Annulla", callback_data="cancel"),
        ]
    )
    if context.user_data.get("category"):
        buttons[-1].append(
            InlineKeyboardButton(text="Seleziona tappa »", callback_data=str(ASK_ROUND))
        )
    reply_markup = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

    return ASK_ROUND


async def ask_round(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data
    if not update.callback_query.data.isnumeric():
        user_data["category"] = user_data["championship"].categories[
            int(update.callback_query.data.removeprefix("C"))
        ]
        user_data["current_report"].category = user_data["category"]

    category: Category = user_data["category"]

    buttons = []
    for i, championship_round in enumerate(category.rounds):
        if championship_round.completed:
            buttons.append(
                InlineKeyboardButton(
                    f"Tappa {championship_round.number}", callback_data=f"R{i}"
                )
            )

    buttons = list(chunked(buttons, 3))

    buttons.append(
        [
            InlineKeyboardButton("« Categoria", callback_data=str("create_penalty")),
            InlineKeyboardButton("Sessione »", callback_data=str(ASK_SESSION)),
        ]
    )

    reply_markup = InlineKeyboardMarkup(buttons)
    text = "Seleziona la tappa in cui è avvenuta l'infrazione:"
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    return ASK_SESSION


async def ask_session(update: Update, context: ContextTypes) -> int:
    """Saves the championship round and asks what session the accident happened in."""

    user_data = context.user_data
    category: Category = user_data["category"]
    if not update.callback_query.data.isnumeric():
        user_data["current_report"].round = category.rounds[
            int(update.callback_query.data.removeprefix("R"))
        ]
        user_data["current_report"].number = (
            get_last_report_number(
                category_id=user_data["current_report"].category.category_id,
                round_id=user_data["current_report"].round.round_id,
            )
            + 1
        )

    text = "In quale sessione è avvenuta l'infrazione?"

    buttons = []
    for i, session in enumerate(user_data["current_report"].round.sessions):
        buttons.append(InlineKeyboardButton(session.name, callback_data=f"S{i}"))
    buttons = list(chunked(buttons, 3))
    buttons.append(
        [
            InlineKeyboardButton("« Tappa", callback_data=str(ASK_ROUND)),
            InlineKeyboardButton("Minuto »", callback_data=str(ASK_INCIDENT_TIME)),
        ]
    )

    reply_markup = InlineKeyboardMarkup(buttons)
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    return ASK_INCIDENT_TIME


async def ask_incident_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the championship round and asks when the accident happened."""

    user_data = context.user_data

    if not update.callback_query.data.isnumeric():
        user_data["current_report"].session = user_data[
            "current_report"
        ].round.sessions[int(update.callback_query.data.removeprefix("S"))]

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
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=text, reply_markup=reply_markup
        )
    else:
        update.message.reply_text(text, reply_markup=reply_markup)
    return ASK_DRIVER


async def ask_driver(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the championship round and asks who the driver to report is."""

    user_data = context.user_data
    category: Category = user_data["category"]
    if update.message:
        user_data["current_report"].incident_time = update.message.text

    text = "Quale pilota ha commesso l'infrazione?"

    buttons = []
    for i, driver in enumerate(category.drivers):
        buttons.append(
            InlineKeyboardButton(driver.driver.psn_id, callback_data=f"D{i}")
        )
    buttons = list(chunked(buttons, 2))

    buttons.append(
        [
            InlineKeyboardButton("« Minuto", callback_data=str(ASK_INCIDENT_TIME)),
            InlineKeyboardButton(
                "Infrazione commessa »", callback_data=str(ASK_INFRACTION)
            ),
        ]
    )

    reply_markup = InlineKeyboardMarkup(buttons)

    if not update.message:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)
    return ASK_INFRACTION


async def ask_infraction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the driver and asks what infraction he committed."""

    user_data = context.user_data

    if not update.callback_query.data.isnumeric():
        driver: DriverCategory = user_data["category"].drivers[
            int(update.callback_query.data.removeprefix("D"))
        ]
        user_data["current_report"].reported_team = driver.driver.current_team()
        user_data["current_report"].reported_driver = driver.driver

    buttons = []
    for i, infraction in enumerate(config.INFRACTIONS):
        buttons.append([InlineKeyboardButton(infraction, callback_data=f"i{i}")])
    buttons.append(
        [
            InlineKeyboardButton("« Pilota colpevole", callback_data=str(ASK_DRIVER)),
            InlineKeyboardButton(
                "Secondi di penalità »", callback_data=str(ASK_SECONDS)
            ),
        ]
    )
    reply_markup = InlineKeyboardMarkup(buttons)
    text = "Qual'è l'infrazione commessa?"
    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    return ASK_SECONDS


async def report_processing_entry_point(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Asks the user which category he wants to view reports from,
    after the /start_reviewing command is issued"""

    championship = get_championship()
    context.user_data["championship"] = championship
    user = update.effective_user
    if user.id not in config.ADMINS:
        text = "Questa funzione è riservata agli admin di RTI.\n"
        button = InlineKeyboardButton(
            text="Chiedi l'autorizzazione", url=f"tg://user?id={config.OWNER_ID}"
        )
        reply_markup = InlineKeyboardMarkup([[button]])
        await update.message.reply_text(text, reply_markup=reply_markup)
        return ConversationHandler.END

    reports = get_reports(is_reviewed=False)

    if not reports:
        text = "Non ci sono segnalazioni da processare."
        if update.callback_query:
            await update.callback_query.edit_text(text)
        else:
            await update.message.reply_text(text)
        return ConversationHandler.END

    context.user_data["unreviewed_reports"] = reports
    report_categories = defaultdict(int)
    for report in reports:
        report_categories[report.round.category.name] += 1

    total = sum(report_categories.values())
    if total == 1:
        text = f"C'è solo una segnalazione in {reports[0].category.name}"
    elif len(report_categories) == 1:
        text = f"Ci {total} sono segnalazioni in {report.round.category.name}."
    else:
        text = f"Hai {total} segnalazioni da processare, di cui:\n"
        for category, number in report_categories.items():
            text += f"{number} in {category}\n"
    text += "\nSeleziona la categoria dove vuoi giudicare le segnalazioni:"

    reply_markup = []
    for i, category in enumerate(championship.categories):
        if report_categories.get(category.name):
            reply_markup.append(
                InlineKeyboardButton(category.name, callback_data=f"C{i}")
            )

    category_buttons = list(chunked(reply_markup, 3))
    category_buttons.append([InlineKeyboardButton("Annulla", callback_data="cancel")])
    reply_markup = InlineKeyboardMarkup(category_buttons)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=text, reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(text=text, reply_markup=reply_markup)
    return ASK_CATEGORY


async def ask_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the user the first unreviewed report in the selected category."""

    user_data = context.user_data
    reports: list[Report] = user_data["unreviewed_reports"]
    if not update.callback_query.data.isnumeric():
        user_data["selected_category"] = user_data["championship"].categories[
            int(update.callback_query.data.removeprefix("C"))
        ]

    for report in reports:
        if report.category.category_id == user_data["selected_category"].category_id:
            text = (
                f"<b>{report.category.name}</b> - Segnalazione no.{report.number}\n\n"
                f"<b>Piloti coinvolti</b>: {report.reported_driver.psn_id}, "
                f"{report.reporting_driver.psn_id}\n"
                f"<b>Sessione</b>: {report.session.name}\n"
                f"<b>Minuto incidente</b>: {report.incident_time}\n"
                f"<b>Motivo segnalazione</b>: {report.report_reason}"
            )
            context.user_data["current_report"] = report
            reply_markup = [
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

    report: Report = context.user_data["current_report"]
    text = "Seleziona il fatto accaduto, oppure scrivine uno tu.\n"

    buttons = []

    for i, fact in enumerate(config.FACTS):
        callback_data = (
            f"qf{i}"
            if context.user_data["current_report"].session.is_quali
            else f"f{i}"
        )
        buttons.append(
            InlineKeyboardButton(
                text=f"{i + 1}",
                callback_data=callback_data,
            )
        )

        text += f"\n{i + 1} - {fact}".format(
            a=report.reporting_driver.current_race_number
        )

    buttons = list(chunked(buttons, 4))

    if context.user_data["current_report"].session.is_quali:

        next_step = ASK_LICENCE_POINTS
        next_step_button = InlineKeyboardButton(
            "Punti licenza »", callback_data=str(next_step)
        )
    else:

        next_step = ASK_SECONDS
        next_step_button = InlineKeyboardButton(
            "Secondi »", callback_data=str(next_step)
        )
    buttons.append(
        [
            InlineKeyboardButton(
                "« Vedi segnalazione", callback_data=str(ASK_CATEGORY)
            ),
            next_step_button,
        ]
    )

    await update.callback_query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(buttons)
    )
    return next_step


async def ask_seconds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the fact an asks user for the decision, after a valid fact has been entered."""
    user_data = context.user_data

    if update.callback_query:
        # Save infraction if the report was made via the alternative command "penalizza"
        if update.callback_query.data[0] == "i":
            context.user_data["current_report"].fact = config.INFRACTIONS[
                int(update.callback_query.data.removeprefix("i"))
            ]
        elif not update.callback_query.data.isdigit():
            if user_data["current_report"].session.is_quali:
                user_data["current_report"].fact = config.FACTS[
                    int(update.callback_query.data.removeprefix("qf"))
                ].format(
                    a=user_data["current_report"].reported_driver.current_race_number
                )
                await ask_licence_points(update, context)
                return ASK_WARNINGS
            else:
                user_data["current_report"].fact = config.FACTS[
                    int(update.callback_query.data.removeprefix("f"))
                ].format(
                    a=user_data["current_report"].reporting_driver.current_race_number
                )

    else:
        user_data["current_report"].fact = update.message.text

    text = "Seleziona i secondi di penalità inflitti:"
    reply_markup = []
    for seconds in ("3", "5", "10", "15", "20", "30"):
        reply_markup.append(
            InlineKeyboardButton(
                f"{seconds}",
                callback_data=f"{seconds} secondi aggiunti sul tempo di gara",
            )
        )

    reply_markup = list(chunked(reply_markup, 3))
    reply_markup.append(
        [InlineKeyboardButton("Nessuna penalità in tempo", callback_data="no_penalty")]
    )

    previous_step = (
        ASK_FACT
        if not context.user_data.get("alternative_entry_point")
        else ASK_INFRACTION
    )
    reply_markup.append(
        [
            InlineKeyboardButton("« Fatto", callback_data=str(previous_step)),
            InlineKeyboardButton(
                "Punti licenza »", callback_data=str(ASK_LICENCE_POINTS)
            ),
        ]
    )
    reply_markup = InlineKeyboardMarkup(reply_markup)

    if not update.callback_query:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    return ASK_LICENCE_POINTS


async def ask_licence_points(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the decision and asks for the reason"""

    user_data = context.user_data

    if update.callback_query:
        if (
            not update.callback_query.data.isdigit()
            and "qf" not in update.callback_query.data
        ):
            if "no_penalty" in update.callback_query.data:
                user_data["current_report"].time_penalty = 0
                user_data["current_report"].penalty = None
                user_data["time_penalty_text"] = None
            else:
                time_penalty = int(update.callback_query.data.split()[0])
                user_data["current_report"].time_penalty = time_penalty
                user_data[
                    "time_penalty_text"
                ] = f"{time_penalty} secondi aggiunti sul tempo di gara"

    else:
        user_data["current_report"].time_penalty = int(update.message.text.split()[0])
        user_data[
            "time_penalty_text"
        ] = f"{time_penalty} secondi aggiunti sul tempo di gara"

    buttons = []
    for licence_points in range(5):
        buttons.append(
            InlineKeyboardButton(
                str(licence_points), callback_data=f"lp{licence_points}"
            )
        )
    buttons = list(chunked(buttons, 5))

    if user_data["current_report"].session.is_quali and user_data.get(
        "alternative_entry_point"
    ):
        previous_step_button = InlineKeyboardButton(
            "« Infrazione", callback_data=str(ASK_INFRACTION)
        )
    elif user_data["current_report"].session.is_quali:
        previous_step_button = InlineKeyboardButton(
            "« Fatto", callback_data=str(ASK_FACT)
        )
    else:
        previous_step_button = InlineKeyboardButton(
            "« Torna indietro", callback_data=str(ASK_SECONDS)
        )

    buttons.append(
        [
            previous_step_button,
            InlineKeyboardButton("Warning »", callback_data=str(ASK_WARNINGS)),
        ]
    )
    reply_markup = InlineKeyboardMarkup(buttons)
    text = (
        "Quanti punti licenza sono stati detratti? (Scrivi o scegli una tra le opzioni)"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

    return ASK_WARNINGS


async def ask_warnings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves penalty seconds (if given) and asks if any licence points are to be added."""

    user_data = context.user_data

    if update.callback_query:
        if not update.callback_query.data.isdigit():
            licence_points = int(update.callback_query.data.removeprefix("lp"))
            user_data["current_report"].licence_points = licence_points
            current_report: Report = user_data["current_report"]
            if licence_points > 1:
                user_data["licence_points_text"] = (
                    f"{licence_points} punti sulla licenza"
                    f"({current_report.reported_driver.licence_points - licence_points}/10)"
                )
            elif licence_points == 1:
                user_data["licence_points_text"] = (
                    "1 punto sulla licenza"
                    f"({current_report.reported_driver.licence_points - 1}/10)"
                )
            else:
                user_data["licence_points_text"] = ""
    else:
        licence_points = int(update.message.text.split()[0])
        user_data["current_report"].licence_points = licence_points
        user_data["licence_points_text"] = (
            f"{licence_points}punti sulla licenza"
            f"({user_data['current_report'].reported_driver.licence_points - licence_points}/10)"
        )
    text = "Quanti warning sono stati dati?"

    buttons = []
    for i in range(1, 13):
        buttons.append(InlineKeyboardButton(str(i), callback_data=f"w{i}"))
    buttons = list(chunked(buttons, 4))
    buttons.append(
        [InlineKeyboardButton("Nessuno", callback_data="w0")],
    )
    buttons.append(
        [
            InlineKeyboardButton(
                "« Punti patente", callback_data=str(ASK_LICENCE_POINTS)
            ),
            InlineKeyboardButton(
                "Motivazione »", callback_data=str(ASK_PENALTY_REASON)
            ),
        ],
    )

    reply_markup = InlineKeyboardMarkup(buttons)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)
    return ASK_PENALTY_REASON


async def ask_penalty_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves warnings given (if any) and asks for the penalty reason."""

    user_data = context.user_data
    if update.callback_query:

        if not update.callback_query.data.isnumeric():
            warnings = int(update.callback_query.data.removeprefix("w"))
            user_data["current_report"].warnings = warnings
            if warnings > 0:
                user_data["warnings_text"] = (
                    f"{warnings} warning"
                    f"({warnings + user_data['current_report'].reported_driver.warnings}/12)"
                )
            else:
                user_data["warnings_text"] = ""
    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("« Warning", callback_data=str(ASK_WARNINGS)),
                InlineKeyboardButton(
                    "Controlla »", callback_data=str(ASK_QUEUE_OR_SEND)
                ),
            ]
        ]
    )

    text = "Scrivi la motivazione:"
    if not update.callback_query:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    return ASK_QUEUE_OR_SEND


async def ask_queue_or_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the reason and asks if to send the report immediately or add it to the queue"""

    user_data = context.user_data

    if not update.callback_query:
        user_data["current_report"].penalty_reason = update.message.text

    report: Report = user_data["current_report"]

    report.penalty = ", ".join(
        filter(
            None,
            (
                user_data.get("time_penalty_text", None),
                user_data.get("warnings_text", None),
                user_data.get("licence_points_text", None),
            ),
        )
    )
    if not report.penalty:
        report.penalty = "Nessun'azione"
    if report.penalty:
        report.penalty += "."
    text = (
        f"<b>Segnalazione no.{report.number}</b> - Recap dati inseriti\n\n"
        f"<b>Tappa</b>: {report.round.number if report.round else '-'}\n"
        f"<b>Pilota</b>: {report.reported_driver.psn_id if report.reported_driver else '-'}\n"
        f"<b>Fatto</b>: {report.fact if report.fact else '-'}\n"
        f"<b>Decisione</b>: {report.penalty if report.penalty else '-'}\n"
        f"<b>Motivazione</b>: {report.penalty_reason if report.penalty_reason else '-'}"
    )
    reply_markup = [
        [InlineKeyboardButton("« Motivazione", callback_data=str(ASK_PENALTY_REASON))],
    ]

    if report.is_complete():
        reply_markup.append(
            [
                InlineKeyboardButton(
                    "Aggiungi in coda 📥", callback_data="add_to_queue"
                ),
                InlineKeyboardButton("Invia subito ✉️", callback_data="send_now"),
            ],
        )
    else:
        text += (
            "\n⚠️ Prima di inviare il report è necessario aver compilato tutti i campi."
        )

    if not update.callback_query:
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(reply_markup)
        )
    else:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(reply_markup)
        )
    return ASK_IF_NEXT


async def add_to_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Adds the report to the queue or sends it, then ends the conversation"""

    user_data = context.user_data
    report = user_data["current_report"]

    if update.callback_query.data == "send_now":
        save_and_apply_report(report)
        file = ReviewedReportDocument(report).generate_document()
        await context.bot.send_document(
            chat_id=config.REPORT_CHANNEL,
            document=open(file, "rb"),
        )

        text = "Penalità salvata e inviata."
    elif update.callback_query.data == "add_to_queue":
        report.is_reviewed = True
        report.is_queued = True
        text = "Penalità salvata e aggiunta alla coda"

    text += f"\nOra ne rimangono {len(user_data['unreviewed_reports'])}."
    reply_markup = [
        [
            InlineKeyboardButton(
                "Prossima segnalazione",
                callback_data=str(ASK_CATEGORY)
                if len(user_data["unreviewed_reports"]) == 0
                else "start_reviewing",
            ),
        ]
    ]

    if len(context.user_data["unreviewed_reports"]) == 1:
        reply_markup.append(
            [
                InlineKeyboardButton(
                    "Invia tutti i messaggi in coda", callback_data="send_all"
                )
            ]
        )

    await update.callback_query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(reply_markup)
    )
    return END_REPORTING


async def end_reporting_process(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Undoes previous action or restarts the conversation, if there is at least one report left.
    Otherwise it asks the user wether to send all the queued reports or not.
    """

    if update.callback_query.data == "send_all":
        for report in context.user_data["report_queue"]:
            with open(ReviewedReportDocument(report).filename, "rb") as doc:
                context.bot.send_document(config.REPORT_CHANNEL, document=doc)
                os.remove(doc)
                save_and_apply_report(report)


async def cancel_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Deletes the current report."""
    del context.user_data["current_report"]
    await update.message.reply_text(
        "Ok! I dati raccolti per quest'ultima segnalazione sono stati cancellati."
    )
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
        ASK_SECONDS: ask_seconds,
        ASK_LICENCE_POINTS: ask_licence_points,
        ASK_WARNINGS: ask_warnings,
        ASK_PENALTY_REASON: ask_penalty_reason,
        ASK_QUEUE_OR_SEND: ask_queue_or_send,
        END_REPORTING: end_reporting_process,
    }
    state = int(update.callback_query.data)
    await callbacks.get(state)(update, context)

    return state + (1 if state != 17 else 3)


async def exit_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clears user_data and ends the conversation"""
    context.user_data.clear()
    text = "Segnalazione annullata."
    if update.message:
        await update.message.reply_text(text)
    else:
        if update.callback_query.data == "cancel":
            text = "Processo di segnalazione annullato."
        await update.callback_query.edit_message_text(text)
    return ConversationHandler.END


report_processing = ConversationHandler(
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
        ASK_SECONDS: [
            CallbackQueryHandler(
                ask_seconds, r"^f[0-9]{1,}$|^i[0-9]{1,}$|^qf[0-9]{1,}$"
            ),
            MessageHandler(filters.Regex(r"^[^/]{2,}$"), ask_seconds),
        ],
        ASK_LICENCE_POINTS: [
            CallbackQueryHandler(
                ask_licence_points, r"^\d{1,3} secondi aggiunti|^no_penalty$"
            ),
            MessageHandler(
                filters.Regex(r"secondi|punti di penalità|sospensione"),
                ask_licence_points,
            ),
        ],
        ASK_WARNINGS: [CallbackQueryHandler(ask_warnings, r"lp[0-9]{1,}")],
        ASK_PENALTY_REASON: [CallbackQueryHandler(ask_penalty_reason, r"w[0-9]{1,}")],
        ASK_QUEUE_OR_SEND: [
            MessageHandler(filters.Regex(r"^[^/]{20,}$"), ask_queue_or_send)
        ],
        ASK_IF_NEXT: [CallbackQueryHandler(add_to_queue, r"^add_to_queue$|^send_now$")],
        END_REPORTING: [CallbackQueryHandler(end_reporting_process, r"send_all")],
    },
    fallbacks=[
        CommandHandler("esci", exit_conversation),
        CallbackQueryHandler(exit_conversation, r"^cancel$"),
        CallbackQueryHandler(go_back_handler_report_processing, r"^1[2-9]$|^2[0-7]$"),
    ],
)
