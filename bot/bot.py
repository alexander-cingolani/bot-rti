"""
This telegram bot manages racingteamitalia's leaderboards, statistics and penalties.
"""
import json
import logging
import os
from datetime import time
from uuid import uuid4

import pytz
from telegram import (
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    BotCommandScopeChatAdministrators,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    Defaults,
    InlineQueryHandler,
    filters,
)

from components import config
from components.driver_registration import driver_registration
from components.models import Category
from components.queries import get_championship, get_driver, get_max_races
from components.report_creation_conv import report_creation
from components.report_processing_conv import report_processing
from components.result_recognition_conv import save_results_conv
from components.stats import consistency, experience, race_pace, sportsmanship, stats

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = config.TOKEN
CHAMPIONSHIP = get_championship()
CATEGORIES: list[Category] = CHAMPIONSHIP.categories

CATEGORY_NAMES: list[str] = [category.name for category in CATEGORIES]


async def post_init(application: Application) -> None:

    bot = application.bot

    await bot.set_my_commands(
        config.ADMIN_CHAT_COMMANDS,
        BotCommandScopeChatAdministrators(chat_id=config.GROUP_CHAT),
    )

    await bot.set_my_commands(
        config.PRIVATE_CHAT_COMMANDS, BotCommandScopeAllPrivateChats()
    )

    for admin in config.ADMINS:
        await bot.set_my_commands(config.ADMIN_COMMANDS, BotCommandScopeChat(admin))


async def post_shutdown(_: Application) -> None:
    if os.path.exists("results.jpg"):
        os.remove("results.jpg")
    if os.path.exists("results_1.jpg"):
        os.remove("results_1.jpg")
    if os.path.exists("results_2.jpg"):
        os.remove("results_2.jpg")


async def error_handler(update: Update, context: ContextTypes) -> None:
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    user_message = (
        "⚠️ Si è verificato un errore inaspettato! Lo sviluppatore è stato informato"
        " del problema e cercherà di risolverlo al più presto."
    )

    await update.effective_user.send_message(user_message)

    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
    )
    tb_string = "".join(tb_list)
    update_str = update.to_dict() if isinstance(update, Update) else str(update)

    message = (
        "An exception was raised while handling an update\n"
        f"update = {json.dumps(update_str, indent=2, ensure_ascii=False)}"
        "\n\n"
        f"context.chat_data = {str(context.chat_data)}\n\n"
        f"context.user_data = {str(context.user_data)}\n\n"
        f"{tb_string}"
    )

    with open("traceback.txt", "w") as file:
        file.write(message)
        caption = "An error occured."

    with open("traceback.txt", "r") as traceback:
        await context.bot.send_document(
            chat_id=config.DEVELOPER_CHAT, caption=caption, document=traceback
        )
    os.remove("traceback.txt")


async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    await update.message.reply_text(
        f"""
Ciao {user.first_name}!
Sono il bot di racingteamitalia, mi occupo delle segnalazioni, comunicazioni penalità e statistiche dei nostri campionati.

Per qualsiasi problema o idea per migliorarmi puoi contattare {config.OWNER.mention_html(config.OWNER.full_name)}.
        """,
        reply_markup=ForceReply(selective=True),
    )


async def help_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    text = f"Questo bot è gestito da {config.OWNER.mention_html(config.OWNER.full_name)}, se hai problemi non esitare a contattarlo."
    await update.message.reply_text(text)


async def exit_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clears user_data and ends the conversation"""
    context.user_data.clear()
    text = "Segnalazione annullata."
    if update.message:
        await update.message.reply_text(text)
    else:
        await update.callback_query.edit_message_text(text)
    return ConversationHandler.END


async def inline_query(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the inline query. This callback is executed when the user types: @botusername <query>"""
    query = update.inline_query.query

    if query == "":
        return

    race_results = []
    # InlineQueryResultArticle(
    #     id=str(1),
    #     title="Linee guida per i sorpassi",
    #     input_message_content=InputTextMessageContent(
    #         "In order for a car being overtaken to be required to give sufficient room to an overtaking car, the overtaking car needs to have a significant portion of the car alongside the car being overtaken and the overtaking manoeuvre must be done in a safe and controlled manner, while enabling the car to clearly remain within the limits of the track. When considering what is a ‘significant portion’ for an overtaking on the inside of a corner, among the various factors that will be looked at by the stewards when exercising their discretion, the stewards will consider if the overtaking car’s front tyres are alongside the other car by no later than the apex of the corner"        #     ),
    #     thumb_url="https://modales-project.eu/wp-content/uploads/2019/11/06-fia.png",
    # ),

    max_races = get_max_races()
    for driver in get_championship().drivers:
        driver = driver.driver
        if query.lower() in driver.psn_id.lower():
            wins, podiums, poles = stats(driver)
            current_team = driver.current_team().name
            race_results.append(
                InlineQueryResultArticle(
                    id=str(uuid4()),
                    title=f"{driver.psn_id}",
                    input_message_content=InputTextMessageContent(
                        f"""

<i><b>Statistiche {driver.psn_id}</b></i>

<b>Costanza:</b> <i>{consistency(driver)}</i>
<b>Esperienza:</b> <i>{experience(driver, max_races)}</i>
<b>Sportività:</b> <i>{sportsmanship(driver)}</i>
<b>Passo:</b> <i>{race_pace(driver)}

<b>Team:</b> <i>{(",".join(set(map(lambda x: x.team_name, driver.teams))).replace(current_team, f"{current_team} [Attuale]"))}</i>
<b>Vittorie:</b> <i>{wins}</i>
<b>Podi:</b> <i>{podiums}</i>
<b>Pole/Giri veloci:</b> <i>{poles}</i>
"""
                    ),
                )
            )

    await update.inline_query.answer(race_results)


async def announce_reports(context: ContextTypes.DEFAULT_TYPE) -> None:
    championship = get_championship()
    if category := championship.reporting_category():
        round = category.first_non_completed_round()
        text = (
            f"Penalità Categoria {category.name}"
            f"{round.number}ª Tappa / {round.circuit}"
            f"#{championship.abbreviated_name}Tappa{round.number} #{category.name}"
        )
        await context.bot.send_message(
            chat_id=config.REPORT_CHANNEL, text=text, disable_notification=True
        )


async def close_report_column(context: ContextTypes.DEFAULT_TYPE) -> None:
    championship = get_championship()
    if championship.reporting_category():
        with open("./images/sticker.webp") as sticker:
            await context.bot.send_sticker(
                chat_id=config.REPORT_CHANNEL,
                sticker=sticker,
                disable_notification=True,
            )


async def send_participation_list_command(
    _: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    await send_participation_list(context)
    return


async def send_participation_list(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the list of drivers who are supposed to participate to a race."""

    championship = get_championship()

    if not (category := championship.current_racing_category()):
        return ConversationHandler.END

    if not (round := category.first_non_completed_round()):
        return ConversationHandler.END

    drivers = category.drivers
    text = f"""
<b>{round.number + 1}ᵃ Tappa {category.name}</b>
Circuito: <b>{round.circuit}</b>
"""

    context.chat_data["participation_list_text"] = text
    text += f"0/{len(drivers)}\n"
    context.chat_data["participants"] = {}  # dict[psn_id, status]
    for driver in drivers:
        driver = driver.driver
        if driver.telegram_id:
            context.chat_data["participants"][driver.telegram_id] = [
                driver.psn_id,
                None,
            ]
            text += f"\n{driver.psn_id}"

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Presente ✅", callback_data="participating"),
                InlineKeyboardButton("Assente ❌", callback_data="not_participating"),
            ]
        ]
    )

    message = await context.bot.send_message(
        chat_id=config.GROUP_CHAT, text=text, reply_markup=reply_markup
    )

    await context.bot.pin_chat_message(
        message_id=message.message_id,
        chat_id=message.chat_id,
        disable_notification=True,
    )


async def update_participation_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Sends the list of drivers who are supposed to participate to a race."""
    user_id = update.effective_user.id
    driver = get_driver(telegram_id=user_id)

    received_status = update.callback_query.data == "participating"
    # Checks if the user is allowed to answer and if his answer is the same as the previous one.
    if user_id not in context.chat_data[
        "participants"
    ] or received_status in context.chat_data["participants"].get(user_id, []):
        return

    context.chat_data["participants"][user_id][1] = received_status

    text: str = context.chat_data["participation_list_text"]
    text += "{confirmed}/{total}\n"
    confirmed = 0
    total_drivers = 0
    for driver, status in context.chat_data["participants"].values():
        total_drivers += 1
        if status is None:
            text_status = ""
        elif status:
            text_status = "✅"
            confirmed += 1
        else:
            text_status = "❌"
        text += f"\n{driver} {text_status}"

    text = text.format(confirmed=confirmed, total=total_drivers)
    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Presente ✅", callback_data="participating"),
                InlineKeyboardButton("Assente ❌", callback_data="not_participating"),
            ]
        ]
    )
    await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)


def main() -> None:
    """Starts the bot."""

    defaults = Defaults(parse_mode=ParseMode.HTML, tzinfo=pytz.timezone("Europe/Rome"))
    application = (
        Application.builder()
        .token(TOKEN)
        .defaults(defaults)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .defaults(defaults)
        .build()
    )

    application.job_queue.run_daily(
        callback=send_participation_list,
        time=time(0),
        chat_id=config.GROUP_CHAT,
    )

    application.job_queue.run_daily(
        callback=announce_reports,
        time=time(0),
        chat_id=config.REPORT_CHANNEL,
    )

    application.job_queue.run_daily(
        callback=close_report_column,
        time=time(hour=23, minute=59),
        chat_id=config.REPORT_CHANNEL,
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))

    application.add_handler(
        CommandHandler(
            "lista_presenze",
            send_participation_list_command,
            filters=filters.ChatType.GROUPS,
        )
    )
    application.add_handler(
        CallbackQueryHandler(
            update_participation_list, r"participating|not_participating"
        )
    )
    application.add_handler(driver_registration)
    application.add_handler(report_processing)
    application.add_handler(report_creation)
    application.add_handler(save_results_conv)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(InlineQueryHandler(inline_query))

    application.add_error_handler(error_handler)

    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
