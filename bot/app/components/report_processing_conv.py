import os
from collections import defaultdict

from app.components import config
from app.components.models import Report
from app.components.queries import get_championship, get_reports, save_and_apply_report
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

CATEGORY, ASK_FACT, FACT, PENALTY, PENALTY_REASON, ADD_TO_QUEUE = range(6)


async def report_processing_entry_point(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Asks the user which category he wants to view reports from,
    after the /start_reviewing command is issued"""

    user = update.effective_user
    if user.id not in config.ADMINS:
        text = "Non sei autorizzato ad utilizzare questa funzione."
        reply_markup = InlineKeyboardMarkup(
            [
                InlineKeyboardButton(
                    text="Chiedi l'autorizzazione",
                    url=f"tg://user?id=<{config.OWNER_ID}>",
                )
            ]
        )
        await update.message.reply_text(text, reply_markup=reply_markup)
        return ConversationHandler.END

    reports = get_reports(is_reviewed=False)

    context.user_data["unreviewed_reports"] = reports
    report_categories = defaultdict(int)
    for report in reports:
        report_categories[report.round.category.name] += 1
    total = sum(report_categories.values())

    if total == 0:
        text = "Non ci sono segnalazioni da processare in alcuna categoria."
        if update.callback_query:
            await update.callback_query.edit_text(text)
        else:
            await update.message.reply_text(text)
        return ConversationHandler.END

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
    for i, category in enumerate(get_championship().categories):
        if report_categories.get(category.name):
            reply_markup.append(
                InlineKeyboardButton(category.name, callback_data=f"c{i}")
            )
    category_buttons = list(chunked(reply_markup, 3))
    category_buttons.append(
        [InlineKeyboardButton("Annulla", callback_data="cancel_processing")]
    )
    reply_markup = InlineKeyboardMarkup(category_buttons)

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=text, reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(text=text, reply_markup=reply_markup)
    return CATEGORY


async def show_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Shows the user the first unreviewed report in the selected category."""

    user_data = context.user_data
    reports: list[Report] = user_data["unreviewed_reports"]
    if not user_data.get("selected_category"):
        for i, category in enumerate(get_championship().categories):

            if i == int(update.callback_query.data[1]):
                user_data["selected_category"] = category

    for report in reports:
        if report.category.category_id == user_data["selected_category"].category_id:
            text = (
                f"<b>{report.category.name}</b> / Segnalazione no.{report.number}\n\n"
                f"<b>Piloti coinvolti</b>: {report.reported_driver.psn_id}, {report.reporting_driver.psn_id}\n"
                f"<b>Sessione</b>: {report.session.name}\n"
                f"<b>Minuto incidente</b>: {report.incident_time}\n"
                f"<b>Motivo segnalazione</b>: {report.report_reason}"
            )
            context.user_data["current_report"] = report
            reports.remove(report)
            reply_markup = [
                InlineKeyboardButton("« Categoria", callback_data="start_reviewing"),
                InlineKeyboardButton("Procedi »", callback_data="continue"),
            ]
            break

    await update.callback_query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup([reply_markup])
    )

    return ASK_FACT


async def ask_fact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the admin for the fact when callback_data containing "ask_fact" is received."""

    report = context.user_data["current_report"]
    text = "Seleziona il fatto accaduto, oppure scrivine uno tu."
    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"Collisione con vettura no.{report.reporting_driver.race_number} 💥",
                    callback_data=f"Collisione con vettura no.{report.reporting_driver.race_number}"
                    f"{report.reporting_driver.race_number}",
                ),
            ],
            [
                InlineKeyboardButton(
                    f"Bandiere blu non rispettate nei confronti di {report.reporting_driver.race_number}  🟦",
                    callback_data=f"Bandiere blu non rispettate nei confronti di {report.reporting_driver.race_number}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "« Vedi segnalazione", callback_data=str(CATEGORY)
                ),
                InlineKeyboardButton("Decisione »", callback_data=str(FACT)),
            ],
        ],
    )

    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    return FACT


async def save_fact(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the fact an asks user for the decision, after a valid fact has been entered."""
    user_data = context.user_data

    if update.callback_query:
        if not update.callback_query.data.isdigit():
            user_data["current_report"].fact = update.callback_query.data
    else:
        user_data["current_report"].fact = update.message.text

    text = "Seleziona la penalità inflitta:"
    reply_markup = []
    for seconds in ("3", "5", "10", "15", "20", "30"):
        reply_markup.append(
            InlineKeyboardButton(
                f"{seconds}s",
                callback_data=f"{seconds} seconds",
            )
        )
    reply_markup = list(chunked(reply_markup, 3))
    reply_markup.append(
        [InlineKeyboardButton("Nessun'azione", callback_data="0 seconds")]
    )
    reply_markup.append(
        [
            InlineKeyboardButton("« Fatto", callback_data=str(ASK_FACT)),
            InlineKeyboardButton("Motivazione »", callback_data=str(PENALTY)),
        ]
    )
    reply_markup = InlineKeyboardMarkup(reply_markup)

    if not update.callback_query:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    return PENALTY


async def save_penalty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the decision and asks for the reason"""

    user_data = context.user_data

    if update.callback_query:
        if not update.callback_query.data.isdigit():
            user_data["current_report"].time_penalty = int(
                update.callback_query.data.split()[0]
            )
    else:
        user_data["current_report"].time_penalty = int(update.message.text.split(""))

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("« Torna indietro", callback_data=str(FACT)),
                InlineKeyboardButton(
                    "Verifica dati »", callback_data=str(PENALTY_REASON)
                ),
            ]
        ]
    )

    text = "Scrivi la motivazione:"
    if not update.callback_query:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    return PENALTY_REASON


async def save_penalty_reason(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Saves the reason and asks if to send the report immediately or add it to the queue"""

    user_data = context.user_data
    if update.callback_query:
        if not update.callback_query.data.isdigit():
            user_data["current_report"].penalty_reason = update.callback_query.data
    else:
        user_data["current_report"].penalty_reason = update.message.text
    report = user_data["current_report"]

    text = (
        f"Recap dati inseriti per la segnalazione no.{report.number}\n\n"
        f"<b>Fatto</b>: {report.fact if report.fact else '-'}\n"
        f"<b>Decisione</b>: {report.time_penalty if report.time_penalty else '-'}\n"
        f"<b>Motivazione</b>: {report.penalty_reason if report.penalty_reason else '-'}"
    )
    reply_markup = [
        [InlineKeyboardButton("« Torna indietro", callback_data=str(PENALTY))],
    ]

    if report.fact and report.time_penalty and report.penalty_reason:
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
    return ADD_TO_QUEUE


async def add_to_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Adds the report to the queue or sends it, then ends the conversation"""

    user_data = context.user_data
    report = user_data["current_report"]

    if update.callback_query.data == "send_now":
        report.is_reviewed = True
        save_and_apply_report(report)

        text = "Penalità salvata e inviata."
    elif update.callback_query.data == "add_to_queue":
        report.is_reviewed = True
        report.is_queued = True
        text = "Penalità salvata e aggiunta alla coda"
        save_and_apply_report(report)

    text += f"\nOra ne rimangono {len(user_data['unreviewed_reports'])}."
    reply_markup = [
        [
            InlineKeyboardButton(
                "Prossima segnalazione",
                callback_data=str(CATEGORY)
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


async def cancel_review(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Deletes the current report."""
    context.user_data["current_report"] = None
    update.message.reply_text("Ok! Revisione cancellata.")
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
        CATEGORY: show_report,
        ASK_FACT: ask_fact,
        FACT: save_fact,
        PENALTY: save_penalty,
        PENALTY_REASON: save_penalty_reason,
    }
    state = int(update.callback_query.data)
    await callbacks.get(state)(update, context)
    return state + 1


async def exit_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clears user_data and ends the conversation"""
    context.user_data.clear()
    text = "Segnalazione annullata."
    if update.message:
        await update.message.reply_text(text)
    else:
        if update.callback_query.data == "cancel_processing":
            text = "Processo di segnalazione annullato."
        await update.callback_query.edit_message_text(text)
    return ConversationHandler.END


report_processing = ConversationHandler(
    allow_reentry=True,
    entry_points=[
        CommandHandler("segnalazioni", report_processing_entry_point),
        CallbackQueryHandler(go_back_handler_report_processing, r"^[0-5]$"),
        CallbackQueryHandler(report_processing_entry_point, "start_reviewing"),
    ],
    states={
        CATEGORY: [
            CallbackQueryHandler(
                show_report,
                r"c0|c1|c2|c3",
            )
        ],
        ASK_FACT: [CallbackQueryHandler(ask_fact, "continue")],
        FACT: [
            CallbackQueryHandler(save_fact, r"."),
            MessageHandler(filters.Regex(r"^[^/]{2,}$"), save_fact),
        ],
        PENALTY: [
            CallbackQueryHandler(save_penalty, r"\d{1,3} seconds"),
            MessageHandler(
                filters.Regex(r"punti di penalità|sospensione"), save_penalty
            ),
        ],
        PENALTY_REASON: [
            MessageHandler(filters.Regex(r"^[^/]{2,}$"), save_penalty_reason)
        ],
        ADD_TO_QUEUE: [CallbackQueryHandler(add_to_queue, r"add_to_queue|send_now")],
    },
    fallbacks=[
        CommandHandler("esci", exit_conversation),
        CallbackQueryHandler(exit_conversation, "cancel_processing"),
    ],
)
