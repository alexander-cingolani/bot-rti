"""
Helper stuff.
"""
from telegram import InlineKeyboardMarkup, Update


async def send_or_edit_message(
    update: Update,
    message: str,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    if update.callback_query:
        if not reply_markup:
            await update.callback_query.edit_message_text(text=message)
            return
        await update.callback_query.edit_message_text(
            text=message, reply_markup=reply_markup
        )
        return

    if not reply_markup:
        await update.message.reply_text(message)
        return

    await update.message.reply_text(text=message, reply_markup=reply_markup)
    return
