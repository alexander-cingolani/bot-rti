"""
This module contains the necessary callbacks to allow admins to delete a penalty
that has already been applied.
"""

# TODO: Update driver stats, link penalties to reports and mark related report as "unseen" when a penalty is deleted.
import os
from typing import Any, cast
from more_itertools import chunked

from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SQLASession
from sqlalchemy.orm import sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    CommandHandler,
)
from models import Championship, Penalty, Round

from queries import get_report, reverse_penalty, get_championship

engine = create_engine(os.environ["DB_URL"])

DBSession = sessionmaker(bind=engine, autoflush=False)

SAVE_CATEGORY, SAVE_ROUND, SAVE_PENALTY, CONFIRM, DELETE_PENALTY = range(28, 33)
EXIT = "e"
BACK = "b"
YES = "y"
CANCEL = "c"


async def entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Checks if there are penalties to delete, if there are, it then asks which category
    the penalty is in."""

    user_data = cast(dict[str, Any], context.user_data)

    sqla_session = DBSession()
    user_data["sqla_session"] = sqla_session

    championship = get_championship(sqla_session)

    if not championship:
        await update.message.reply_text(
            "Non sono presenti campionati nel database, "
            "quindi non ci sono penalità da poter eliminare."
        )
        user_data.clear()
        sqla_session.close()
        return ConversationHandler.END

    user_data["championship"] = championship

    if not championship.categories:
        await update.message.reply_text(
            "Non sono presenti categorie legate a questo campionato nel database, "
            "quindi non ci sono penalità da poter eliminare."
        )
        user_data.clear()
        sqla_session.close()
        return ConversationHandler.END

    buttons: list[InlineKeyboardButton] = []
    for i, category in enumerate(championship.categories):
        if category.last_completed_round():
            buttons.append(
                InlineKeyboardButton(text=f"{category.name}", callback_data=f"C{i}")
            )

    if not buttons:
        await update.message.reply_text(
            "Non ci sono round completati in alcuna categoria, "
            "quindi non ci sono nemmeno penalità da cancellare."
        )
        user_data.clear()
        sqla_session.close()
        return ConversationHandler.END

    user_data["category_buttons"] = buttons

    await __ask_category(update, buttons)

    return SAVE_CATEGORY


async def __ask_category(update: Update, category_buttons: list[InlineKeyboardButton]):
    """Asks which category the penalty was in."""
    text = """Seleziona la categoria dove si trova la penalità da eliminare:"""

    reply_markup = InlineKeyboardMarkup(
        [category_buttons, [InlineKeyboardButton("Annulla", callback_data=EXIT)]]
    )
    if update.message:
        await update.message.reply_text(text=text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(
            text=text, reply_markup=reply_markup
        )


async def save_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the category and asks which round the penalty was in."""

    user_data = cast(dict[str, Any], context.user_data)
    championship = cast(Championship, user_data["championship"])

    if update.callback_query.data == EXIT:
        await update.callback_query.edit_message_text("Ok! Non cancelliamo nulla.")
        user_data["sqla_session"].close()
        user_data.clear()
        return ConversationHandler.END

    index = int(update.callback_query.data.removeprefix("C"))
    category = championship.categories[index]
    user_data["category"] = category

    rnds: list[Round] = []
    for rnd in reversed(category.rounds):
        if rnd.is_completed:
            rnds.append(rnd)
        if len(rnds) == 3:
            break

    user_data["rounds"] = rnds

    await __ask_round(update, user_data["rounds"])

    return SAVE_ROUND


async def __ask_round(update: Update, rnds: list[Round]):
    """Asks which round the penalty was in."""

    buttons: list[InlineKeyboardButton] = []
    for i, rnd in enumerate(rnds):
        buttons.append(
            InlineKeyboardButton(text=f"{rnd.number}^ Tappa", callback_data=f"R{i}")
        )

    text = """Seleziona la tappa dove si trova la penalità da eliminare:"""
    reply_markup = InlineKeyboardMarkup(
        [buttons, [InlineKeyboardButton("« Torna alle categorie", callback_data=BACK)]]
    )
    await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)


async def save_round(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks which penalty the user wants to delete."""

    user_data = cast(dict[str, Any], context.user_data)
    rnds = cast(list[Round], user_data["rounds"])

    if update.callback_query.data == BACK:
        await __ask_category(update, user_data["category_buttons"])
        return SAVE_CATEGORY

    index = int(update.callback_query.data.removeprefix("R"))

    rnd = rnds[index]
    user_data["round"] = rnd

    await __ask_penalty(update, rnd)

    return SAVE_PENALTY


async def __ask_penalty(update: Update, rnd: Round):
    """Asks which penalty to delete."""

    text = (
        f"Queste sono le penalità della <b>{rnd.number}^ Tappa</b>.\n"
        "Quale vuoi eliminare?\n"
        "<i>(I numeri corrispondono a quelli dei documenti)</i>\n\n"
    )

    buttons: list[InlineKeyboardButton] = []
    for i, penalty in enumerate(rnd.penalties):
        text += f"{penalty.number} - {penalty.driver.abbreviated_name}, {int(penalty.points)} punti di penalità\n"
        buttons.append(
            InlineKeyboardButton(text=str(penalty.number), callback_data=f"P{i}")
        )

    if not buttons:
        text = "Non risultano essere state date penalità in questa tappa."

    chunked_buttons = list(chunked(buttons, 4))
    chunked_buttons.append(
        [InlineKeyboardButton("« Torna alle tappe", callback_data=BACK)]
    )
    reply_markup = InlineKeyboardMarkup(chunked_buttons)

    await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)


async def save_penalty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks if the user is certain he wants to delete the penalty."""

    user_data = cast(dict[str, Any], context.user_data)
    rnd = cast(Round, user_data["round"])

    if update.callback_query.data == BACK:
        await __ask_round(update, user_data["rounds"])
        return SAVE_ROUND

    index = int(update.callback_query.data.removeprefix("P"))
    penalty = rnd.penalties[index]
    user_data["penalty"] = penalty

    await __ask_confirmation(update, penalty)

    return CONFIRM


async def __ask_confirmation(update: Update, penalty: Penalty):
    """Asks the user if he is sure he wants to delete the penalty."""
    text = (
        "<u>Sei sicuro</u> di voler annullare questa penalità?\n\n"
        f"N° Documento: {penalty.number}\n"
        f"Pilota: {penalty.driver.abbreviated_name}\n"
        f"Punti penalità: {penalty.points}\n"
        f"Reprimende: {1 if penalty.reprimand else 0}"
    )

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(text="No, torna indietro.", callback_data=BACK),
                InlineKeyboardButton(text="Sì", callback_data=YES),
            ],
        ]
    )

    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)


async def confirm_again(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user to reconfirm that he wants to delete the penalty."""

    if update.callback_query.data == BACK:
        user_data = cast(dict[str, Any], context.user_data)
        rnd = cast(Round, user_data["round"])

        await __ask_penalty(update, rnd)
        return SAVE_PENALTY

    if update.callback_query.data == CANCEL:
        text = "Ok! Non cancelliamo nulla."
        await update.callback_query.edit_message_text(text)
        return ConversationHandler.END

    text = "Sei assolutamente sicuro? Quest'azione non è reversibile."

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(text="Sì, sono sicuro", callback_data=YES),
                InlineKeyboardButton(text="Annulla", callback_data=CANCEL),
            ],
            [
                InlineKeyboardButton(text="No, torna indietro.", callback_data=BACK),
            ],
        ]
    )

    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    return DELETE_PENALTY


async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Deletes the selected penalty, goes back to penalty selection or ends
    the conversation."""

    user_data = cast(dict[str, Any], context.user_data)
    sqla_session = cast(SQLASession, user_data["sqla_session"])
    penalty = cast(Penalty, user_data["penalty"])

    if update.callback_query.data == BACK:
        rnd = cast(Round, user_data["round"])
        await __ask_penalty(update, rnd)
        return SAVE_PENALTY

    if update.callback_query.data == CANCEL:
        text = "Ok! Non eliminiamo nulla."
        await update.callback_query.edit_message_text(text)
        return ConversationHandler.END

    reverse_penalty(sqla_session, penalty)

    p = penalty
    reprimand_text = (
        f"\nReprimenda per {p.reprimand.description} rimossa." if p.reprimand else ""
    )
    text = (
        "Penalità rimossa con successo!\n"
        f"\n<b>{p.points} punt{'o' if p.points == 1 else 'i'}</b> restituit{'o' if p.points == 1 else 'i'}"
        + reprimand_text
        + "\n\nClassfiche e statistiche sono state aggiornate di conseguenza."
    )

    await update.callback_query.edit_message_text(text)

    user_data.clear()
    return ConversationHandler.END


penalty_deletion = ConversationHandler(
    entry_points=[CommandHandler("annulla_penalita", entry_point)],
    states={
        SAVE_CATEGORY: [
            CallbackQueryHandler(save_category, pattern=r"C[0-9]{1,}|" + EXIT)
        ],
        SAVE_ROUND: [CallbackQueryHandler(save_round, pattern=r"R[0-9]{1,}|" + BACK)],
        SAVE_PENALTY: [
            CallbackQueryHandler(save_penalty, pattern=r"P[0-9]{1,}|" + BACK)
        ],
        CONFIRM: [
            CallbackQueryHandler(confirm_again, pattern=f"{BACK}|{CANCEL}|{YES}")
        ],
        DELETE_PENALTY: [
            CallbackQueryHandler(delete, pattern=f"{BACK}|{CANCEL}|{YES}")
        ],
    },
    fallbacks=[],
    allow_reentry=False,
)
