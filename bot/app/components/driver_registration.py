"""
This module contains all the callbacks necessary to register drivers to the database.
"""
import os

from app.components import config
from app.components.queries import get_driver, get_similar_driver
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SQLASession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, User
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.app.components.models import Driver

CHECK_ID, ID, RACE_NUMBER = range(3)
OWNER = User(id=config.OWNER, first_name="Alexander Cingolani", is_bot=False)


engine = create_engine(os.environ.get("DB_URL"))
_Session = sessionmaker(bind=engine, autoflush=False)


async def driver_registration_entry_point(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Asks the user for his PSN ID"""

    session = _Session()
    context.user_data["sqla_session"] = session

    driver = get_driver(session, telegram_id=update.effective_user.id)
    if not driver:
        text = "Per registrarti scrivimi il tuo <i>PlayStation ID</i>:"
        await update.message.reply_text(text)
    else:
        text = f"Sei già registrato/a come <code>{driver.psn_id}</code>, sei tu?"
        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Sì, sono io.", callback_data="correct_id"),
                    InlineKeyboardButton("No, non sono io.", callback_data="change_id"),
                ],
            ]
        )
        context.user_data["driver_obj"] = driver
        await update.message.reply_text(text=text, reply_markup=reply_markup)
    return CHECK_ID


async def check_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Checks if the given psn_id is correct and saves the user's telegram_id if an exact
    match is found. If no exact match is found the bot provides the user with a similar
    ID and asks if that is the right one.
    """
    user_data = context.user_data
    sqla_session: SQLASession = user_data["sqla_session"]
    if getattr(update.callback_query, "data", ""):
        if update.callback_query.data == "change_id":
            driver: Driver = user_data["driver_obj"]
            driver.telegram_id = None
            sqla_session.commit()
            text = "Scrivimi il tuo <i>PlayStation ID</i>:"
            await update.callback_query.edit_message_text(text)
            return CHECK_ID

        if update.callback_query.data == "correct_id":
            await update.callback_query.edit_message_text("👌")
            sqla_session.close()
            user_data.clear()
            return ConversationHandler.END

    if driver := get_driver(sqla_session, psn_id=update.message.text):
        # Checks that no other user is registered to the requested psn_id
        if driver.telegram_id:
            text = (
                "Oh oh. Sembra che qualcuno si sia già registrato a questo ID.\n"
                "Se sei sicuro che questo si tratti del tuo ID PSN contatta "
                f"{OWNER.mention_html(OWNER.full_name)} per risolvere il problema."
            )
        else:
            driver.telegram_id = update.effective_user.id
            sqla_session.commit()
            text = (
                "Ok!\n"
                "In futuro potrai utilizzare il comando /stats per vedere le tue statistiche.\n"
                "Al momento questa funzione non è disponibile, in quanto i dati che ho"
                " a disposizione non sono sufficienti."
            )
        await update.message.reply_text(text)
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    if suggested_driver := get_similar_driver(sqla_session, psn_id=update.message.text):
        if not suggested_driver.telegram_id:
            user_data["suggested_driver"] = suggested_driver.psn_id
            text = f'Ho trovato "<code>{suggested_driver.psn_id}</code>", sei tu?'
            reply_markup = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("Sì", callback_data="y"),
                        InlineKeyboardButton("No", callback_data="n"),
                    ]
                ]
            )
            await update.message.reply_text(text=text, reply_markup=reply_markup)
            return ID

        if suggested_driver.telegram_id == update.effective_user.id:
            text = f"Sei già registrato con <code>{suggested_driver.psn_id}</code>.\n"
            await update.message.reply_text(text)
            sqla_session.close()
            user_data.clear()
            return ConversationHandler.END

    text = "Non ho trovato un ID corrispondente, riprova perfavore:"
    await update.message.reply_text(text=text)
    return CHECK_ID


async def verify_correction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """This callback is activated when the previous callback (check_id) didn't find an
    exact match to the ID provided by the user, in which case it gave the option to select
    a similar ID. This callback therefore handles the user's choice (if to accept the option
    or not)."""

    user_data = context.user_data
    sqla_session: SQLASession = user_data["sqla_session"]

    if update.callback_query.data == "y":
        driver = get_driver(sqla_session, psn_id=user_data["suggested_driver"])
        if driver.telegram_id:
            text = (
                "Oh oh. Sembra che qualcuno si sia già registrato a questo ID."
                f"Se questo è il tuo ID PSN contatta {OWNER.mention_html(OWNER.full_name)}"
            )
            sqla_session.close()
            user_data.clear()
            return ConversationHandler.END

        driver.telegram_id = update.effective_user.id
        sqla_session.commit()
        text = (
            "Bene!\n"
            "Ora potrai usare i comandi /classifica e /ultima_gara durante i campionati.\n"
        )
        await update.callback_query.edit_message_text(text)
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    text = "Ok, se vuoi riprova digitando l'ID PSN, altrimenti /annulla."
    await update.callback_query.edit_message_text(text)
    return CHECK_ID


async def cancel_registration(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """This callback is activated when the user decides to cancel the registration."""

    await update.message.reply_text("👌")
    context.user_data["sqla_session"].close()
    context.user_data.clear()
    return ConversationHandler.END


async def invalid_psn_id(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
    """This callback is activated when the user inputs an invalid psn_id,
    telling him to try again."""

    await update.message.reply_text("L'ID PlayStation inserito non è valido, riprova:")
    return CHECK_ID


driver_registration = ConversationHandler(
    entry_points=[
        CommandHandler(
            "registrami", driver_registration_entry_point, filters.ChatType.PRIVATE
        )
    ],
    states={
        CHECK_ID: [
            MessageHandler(filters.Regex(r"^[A-Za-z][A-Za-z0-9-_]{2,15}$"), check_id),
            CallbackQueryHandler(check_id, r"incorrect_id|correct_id|change_id"),
        ],
        ID: [CallbackQueryHandler(verify_correction, r"y|n")],
    },
    fallbacks=[
        CommandHandler("annulla", cancel_registration),
        CommandHandler("registrami", driver_registration_entry_point),
        MessageHandler(filters.TEXT, invalid_psn_id),
    ],
    allow_reentry=True,
)
