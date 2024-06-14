"""
This module contains all the callbacks necessary to register drivers to the database.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from io import BytesIO
from app.components.watermark import add_watermark as add_water

RECEIVE_IMAGE = 50


engine = create_engine(os.environ["DB_URL"])

DBSession = sessionmaker(bind=engine, autoflush=False)


async def entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks user to send a group of images or a single image to add the watermark to."""

    text = "Ciao! Mandami pure la/le foto a cui devo aggiungere il watermark, quando hai finito di caricarle, scrivi /fine."
    await update.message.reply_text(text)

    context.chat_data["images"] = []

    return RECEIVE_IMAGE


async def receive_image(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends back the received image with the watermark."""

    original_filename = update.message.effective_attachment.file_name
    if original_filename:
        name, _ = original_filename.split(".")
        filename = f"{name} con watermark.jpg"
    else:
        filename = "immagine_con_watermark.jpg"

    update.message.effective_attachment

    file = await update.message.effective_attachment.get_file()
    binary_io = BytesIO()
    await file.download_to_memory(binary_io)

    context.chat_data["images"].append((binary_io, filename))

    return RECEIVE_IMAGE


async def finish_receiving(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    for stream, filename in context.chat_data["images"]:

        await update.message.reply_document(
            document=add_water(stream), filename=filename
        )

    await update.message.reply_text("Ecco qua!")

    return ConversationHandler.END


async def invalid_format(update: Update, _: ContextTypes.DEFAULT_TYPE) -> int:

    text = "Per inviarmi una foto su cui aggiungere il watermark, mandamela/e in formato file.\nRiprova: /aggiungi_watermark"
    await update.message.reply_text(text)

    return ConversationHandler.END


add_watermark_conv = ConversationHandler(
    entry_points=[
        CommandHandler("aggiungi_watermark", entry_point, filters.ChatType.PRIVATE),
    ],
    states={
        RECEIVE_IMAGE: [MessageHandler(filters.ATTACHMENT, receive_image)],
    },
    fallbacks=[
        CommandHandler("fine", finish_receiving),
        MessageHandler(filters.ALL, invalid_format),
    ],
    allow_reentry=True,
)
