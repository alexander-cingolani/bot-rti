from typing import cast
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, User
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from components.models import Driver
from components.queries import get_driver, get_similar_driver, update_object
from components import config

CHECK_ID, ID, RACE_NUMBER = range(3)
OWNER = User(id=config.OWNER, first_name="Alexander Cingolani", is_bot=False)


async def driver_registration_entry_point(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Asks the user for his PSN ID"""
    driver = get_driver(telegram_id=update.effective_user.id)
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
    match is found.
    """

    if getattr(update.callback_query, "data", ""):
        if update.callback_query.data == "change_id":
            driver = cast(Driver, context.user_data["driver_obj"])
            driver.telegram_id = None
            update_object()
        elif update.callback_query.data == "correct_id":
            await update.callback_query.edit_message_text("Perfetto!")
            return ConversationHandler.END
        text = "Scrivimi il tuo <i>PlayStation ID</i>:"
        await update.callback_query.edit_message_text(text)
        return CHECK_ID

    if driver := get_driver(psn_id=update.message.text):
        # Checks that no other telegram_id is already registered to that driver.
        if driver.telegram_id:
            text = (
                "Oh oh. Sembra che qualcuno si sia già registrato a questo ID."
                f"Se questo è il tuo ID PSN contatta {OWNER.mention_html(OWNER.full_name)}"
            )
            context.user_data.clear()
            return ConversationHandler.END
        driver.telegram_id = str(update.effective_user.id)
        update_object()
        text = "Ok! Puoi utilizzare il comando /stats per vedere le tue statistiche."
        await update.message.reply_text(text)
        context.user_data.clear()
        return ConversationHandler.END
    elif suggested_driver := get_similar_driver(psn_id=update.message.text):

        if not suggested_driver.telegram_id:
            context.user_data["suggested_driver"] = suggested_driver.psn_id
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
            text = "Sei già registrato con questo ID PSN."
            await update.message.reply_text(text)
            context.user_data.clear()
            return ConversationHandler.END
        text = (
            "Oh oh. Sembra che qualcuno si sia già registrato a questo ID."
            f"Se questo è il tuo ID PSN contatta {OWNER.mention_html(OWNER.full_name)}"
        )
        context.user_data.clear()
        return ConversationHandler.END

    text = "Non ho trovato un ID corrispondente, riprova perfavore:"
    await update.message.reply_text(text=text)
    return CHECK_ID


async def verify_correction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.callback_query.data == "y":
        driver = get_driver(psn_id=context.user_data["suggested_driver"])
        if driver.telegram_id:
            text = (
                "Oh oh. Sembra che qualcuno si sia già registrato a questo ID."
                f"Se questo è il tuo ID PSN contatta {OWNER.mention_html(OWNER.full_name)}"
            )
            context.user_data.clear()
            return ConversationHandler.END
        driver.telegram_id = str(update.effective_user.id)
        update_object()
        text = "Perfetto! Ora potrai utilizzare /stats in questa chat per vedere le tue statistiche."
        await update.callback_query.edit_message_text(text)

        context.user_data.clear()
        return ConversationHandler.END

    text = "Ok, se vuoi riprova digitando l'ID PSN, altrimenti /annulla."
    await update.callback_query.edit_message_text(text)
    return CHECK_ID


async def cancel_registration(update: Update, _: ContextTypes) -> int:
    if update.message:
        await update.message.reply_text("👌")
    else:
        await update.callback_query.edit_message_text("👌")
    return ConversationHandler.END


async def invalid_psn_id(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:
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
        CallbackQueryHandler(cancel_registration, "exit"),
        CommandHandler("registrami", driver_registration_entry_point),
        MessageHandler(filters.TEXT, invalid_psn_id),
    ],
    allow_reentry=True,
)
