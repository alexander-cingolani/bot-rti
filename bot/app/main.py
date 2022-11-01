"""
This telegram bot manages racingteamitalia's leaderboards, statistics and penalties.
"""
import json
import logging
import os
import traceback
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
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest
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

from app.components import config
from app.components.driver_registration import driver_registration
from app.components.queries import (
    get_category,
    get_championship,
    get_driver,
    get_max_races,
)
from app.components.report_creation_conv import report_creation
from app.components.report_processing_conv import report_processing
from app.components.result_recognition_conv import save_results_conv
from app.components.stats import (
    consistency,
    experience,
    race_pace,
    sportsmanship,
    stats,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")


async def set_admin_chat_commands(bot):
    try:
        await bot.set_my_commands(
            config.ADMIN_CHAT_COMMANDS,
            BotCommandScopeChatAdministrators(chat_id=config.GROUP_CHAT),
        )
    except BadRequest:
        pass


async def set_admin_commands(bot):
    for admin in config.ADMINS:
        try:
            await bot.set_my_commands(config.ADMIN_COMMANDS, BotCommandScopeChat(admin))
        except BadRequest:
            pass


async def post_init(application: Application) -> None:

    bot = application.bot

    await bot.set_my_commands(
        config.PRIVATE_CHAT_COMMANDS, BotCommandScopeAllPrivateChats()
    )

    await set_admin_chat_commands(bot)

    await set_admin_commands(bot)


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
        "⚠️ Si è verificato un errore inaspettato!\n\n"
        "Lo sviluppatore è stato informato del problema e cercherà"
        " di risolverlo al più presto.\n"
        "Nel frattempo si sconsiglia di ripetere l'operazione, in quanto "
        "avrebbe scarsa probabilità di successo."
    )

    try:
        if update.message.chat.type == ChatType.PRIVATE:
            await update.effective_user.send_message(user_message)
    except AttributeError:
        pass

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

    with open("traceback.txt", "rb") as doc:
        await context.bot.send_document(
            chat_id=config.DEVELOPER_CHAT, caption=caption, document=doc
        )
    os.remove("traceback.txt")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""

    owner_mention = config.OWNER.mention_html(config.OWNER.full_name)

    await update.message.reply_text(
        f"Ciao {update.effective_user.first_name}!\n"
        "Sono il bot di Racing Team Italia, mi occupo delle segnalazioni, comunicazioni"
        "penalità e statistiche dei nostri campionati.\n"
        f"Per qualsiasi problema o idea per migliorarmi puoi contattare {owner_mention}.",
        reply_markup=ForceReply(selective=True),
    )

    if update.effective_user.id in config.ADMINS:
        await context.bot.set_my_commands(
            config.ADMIN_COMMANDS, BotCommandScopeChat(update.effective_user.id)
        )

    driver = get_driver(get_driver(telegram_id=update.effective_user.id))

    if not driver:
        await update.message.reply_text(
            "Pare che non ti sia ancora registrato, puoi farlo con /registrami.\n\n"
            "Questa operazione va fatta solo una volta, a meno che tu non decida"
            " di usare un account Telegram diverso in futuro."
        )
    elif driver.current_team().leader.driver_id == update.effective_user.id:
        await context.bot.set_my_commands(
            config.LEADER_COMMANDS, BotCommandScopeChat(update.effective_user.id)
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

    results = []

    max_races = get_max_races()

    drivers = get_championship().driver_list

    for driver in drivers:

        if query.lower() in driver.psn_id.lower():

            wins, podiums, poles = stats(driver)
            current_team = driver.current_team().name
            unique_teams = ",".join(set(map(lambda team: team.team.name, driver.teams)))
            unique_teams = unique_teams.replace(
                current_team, f"{current_team} [Attuale]"
            )

            if const := consistency(driver) < 0:
                const = "N.D."
            if exp := experience(driver, max_races) <= 0:
                exp = "N.D."
            if sprt := sportsmanship(driver) <= 0:
                sprt = "N.D."
            if pace := race_pace(driver) <= 0:
                pace = "N.D."

            result_article = InlineQueryResultArticle(
                id=str(uuid4()),
                title=driver.psn_id,
                input_message_content=InputTextMessageContent(
                    (
                        f"<i><b>PROFILO {driver.psn_id.upper()}</b></i>\n\n"
                        f"<b>Costanza:</b> <i>{const}</i>\n"
                        f"<b>Esperienza:</b> <i>{exp}</i>\n"
                        f"<b>Sportività:</b> <i>{sprt}</i>\n"
                        f"<b>Passo:</b> <i>{pace}</i>\n\n"
                        f"<b>Vittorie:</b> <i>{wins}</i>\n"
                        f"<b>Podi:</b> <i>{podiums}</i>\n"
                        f"<b>Pole/Giri veloci:</b> <i>{poles}</i>\n"
                        f"<b>Gare disputate:</b> <i>{len(driver.race_results)}</i>\n"
                        f"<b>Team:</b> <i>{unique_teams}</i>"
                    ),
                ),
            )
            results.append(result_article)

    await update.inline_query.answer(results)


async def announce_reports(context: ContextTypes.DEFAULT_TYPE) -> None:
    championship = get_championship()
    if category := championship.reporting_category():
        round = category.first_non_completed_round()
        text = (
            f"<b>Segnalazioni Categoria {category.name}</b>\n"
            f"{round.number}ª Tappa / {round.circuit}\n"
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
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:

    try:
        await update.message.delete()
    except:
        pass
    context.bot_data["called_manually_by"] = update.effective_chat.id
    await send_participation_list(context)
    return


async def send_participation_list(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the list of drivers who are supposed to participate to a race."""

    championship = get_championship()
    chat_data = context.chat_data
    
    if not (category := championship.current_racing_category()):
        return ConversationHandler.END

    if not (round := category.first_non_completed_round()):
        return ConversationHandler.END

    drivers = category.drivers
    text = (
        f"<b>{round.number}ᵃ Tappa {category.name}</b>\n"
        f"Circuito: <b>{round.circuit}</b>"
    )

    chat_data["participation_list_text"] = text
    text += f"\n0/{len(drivers)}\n"
    chat_data["participants"] = {}  # dict[telegram_id, status]
    for driver in drivers:
        driver = driver.driver

        chat_data["participants"][driver.psn_id] = [
            driver.telegram_id,
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

    if chat_data.get("called_via_command_by"):
        chat_id = context.bot_data.pop("called_via_command_by")
    else:
        chat_id = config.GROUP_CHAT
        
    message = await context.bot.send_message(
        chat_id=chat_id, text=text, reply_markup=reply_markup
    )

    await context.bot.pin_chat_message(
        message_id=message.message_id,
        chat_id=message.chat_id,
        disable_notification=True,
    )


async def update_participation_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Manages updates to the list of drivers supposed to participate to a race."""
    
    if not context.chat_data.get("participants"):
        return
    
    user_id = update.effective_user.id
    user_psn_id = None

    chat_data = context.chat_data
    # Checks for non-registered users and queries the database to verify if
    # the user has registered since the participation list was last sent
    for psn_id, (tg_id, status) in context.chat_data["participants"].items():
        if not tg_id:
            driver = get_driver(psn_id=psn_id)
            chat_data["participants"][psn_id] = [
                driver.telegram_id,
                status,
            ]
            tg_id = chat_data["participants"][psn_id][0]

        if tg_id == user_id:
            user_psn_id = psn_id

    received_status = update.callback_query.data == "participating"
    # Checks if the user is allowed to answer and if his answer is the same as the previous one.
    if user_psn_id not in chat_data["participants"]:
        return
    if received_status == chat_data["participants"].get(user_psn_id, [0, 0])[1]:
        return

    chat_data["participants"][user_psn_id][1] = received_status

    text: str = chat_data["participation_list_text"]
    text += "\n{confirmed}/{total}\n"
    confirmed = 0
    total_drivers = 0
    for driver, (_, status) in chat_data["participants"].items():
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
    return


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
        time=time(hour=11, minute=45),
        chat_id=config.GROUP_CHAT,
    )

    application.job_queue.run_daily(
        callback=announce_reports,
        time=time(0),
        chat_id=config.REPORT_CHANNEL,
    )

    application.job_queue.run_daily(
        callback=close_report_column,
        time=time(hour=23, minute=59, second=40),
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
