"""
This telegram bot manages racingteamitalia's leaderboards, statistics and penalties.
"""
import json
import logging
import os
import traceback
from collections import defaultdict
from datetime import time
from typing import DefaultDict, cast
from uuid import uuid4

import pytz
from app.components import config
from app.components.driver_registration import driver_registration
from app.components.queries import get_championship, get_driver, get_team_leaders
from app.components.report_creation_conv import report_creation
from app.components.report_processing_conv import report_processing
from app.components.result_recognition_conv import save_results_conv
from app.components.models import Team
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from telegram import (
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
    Update,
    User,
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
    PersistenceInput,
    PicklePersistence,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)
TOKEN = os.environ["BOT_TOKEN"]


if os.environ.get("DB_URL"):
    engine = create_engine(os.environ["DB_URL"])
else:
    raise RuntimeError("No DB_URL in environment variables, can't connect to database.")

DBSession = sessionmaker(bind=engine, autoflush=False)


async def post_init(application: Application) -> None:
    """Sets commands for every user."""

    session = DBSession()
    leaders = get_team_leaders(session)
    session.close()

    # Set base user commands
    await application.bot.set_my_commands(
        config.BASE_COMMANDS, BotCommandScopeAllPrivateChats()
    )

    # Set leader commands
    if leaders:
        for driver in leaders:
            try:
                if not driver.telegram_id:
                    continue
                await application.bot.set_my_commands(
                    config.LEADER_COMMANDS, BotCommandScopeChat(driver.telegram_id)
                )
            except BadRequest:
                pass

    # Set admin commands in group and private chats
    for admin_id in config.ADMINS:
        try:
            await application.bot.set_my_commands(
                config.ADMIN_COMMANDS, BotCommandScopeChat(admin_id)
            )
        except BadRequest:
            pass


async def post_shutdown(_: Application) -> None:
    """Deletes any leftover race result images"""
    if os.path.exists("./app/results.jpg"):
        os.remove("./app/results.jpg")

    if os.path.exists("./app/results_1.jpg"):
        os.remove("./app/results_1.jpg")

    if os.path.exists("./app/results_2.jpg"):
        os.remove("./app/results_2.jpg")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Writes full error traceback to a file and sends it to the dev channel.
    If the error was caused by a user a message will be displayed informing him
    to not repeat the action which caused the error.
    """
    logger.error(msg="Exception while handling an update:", exc_info=context.error)

    try:
        if update.message.chat.type == ChatType.PRIVATE:
            await cast(User, update.effective_user).send_message(
                text=(
                    "⚠️ Si è verificato un errore inaspettato!\n\n"
                    "Lo sviluppatore è stato informato del problema e cercherà"
                    " di risolverlo al più presto.\n"
                    "Nel frattempo si sconsiglia di ripetere l'operazione, in quanto "
                    "avrebbe scarsa probabilità di successo."
                )
            )
    except AttributeError:
        pass

    traceback_list = traceback.format_exception(
        None, context.error, context.error.__traceback__  # type: ignore
    )
    traceback_string = "".join(traceback_list)
    update_str = update.to_dict() if isinstance(update, Update) else str(update)

    message = (
        "An exception was raised while handling an update\n"
        f"update = {json.dumps(update_str, indent=2, ensure_ascii=False)}"
        "\n\n"
        f"context.chat_data = {str(context.chat_data)}\n\n"
        f"context.user_data = {str(context.user_data)}\n\n"
        f"{traceback_string}"
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
    user = cast(User, update.effective_user)
    await update.message.reply_text(
        f"Ciao {user.first_name}!\n"
        "Sono il bot di Racing Team Italia, mi occupo delle segnalazioni, comunicazioni"
        "penalità e statistiche dei nostri campionati.\n"
        f"Per qualsiasi problema o idea per migliorarmi puoi contattare {owner_mention}.",
        reply_markup=ForceReply(selective=True),
    )

    session = DBSession()
    driver = get_driver(session, telegram_id=user.id)

    if not driver:
        await update.message.reply_text(
            "Pare che non ti sia ancora registrato, puoi farlo con /registrami.\n\n"
            "Questa operazione va fatta solo una volta, a meno che tu non decida "
            "di cambiare account Telegram in futuro."
        )
    elif team := driver.current_team():
        if getattr(team.leader, "telegram_id") == user.id:
            await context.bot.set_my_commands(
                commands=config.LEADER_COMMANDS, scope=BotCommandScopeChat(user.id)
            )
    session.close()


async def help_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message providing the developer's contact details for help."""
    text = (
        f"Questo bot è gestito da {config.OWNER.mention_html(config.OWNER.full_name)},"
        " se stai riscontrando un problema non esitare a contattarlo."
    )
    await update.message.reply_text(text)


async def exit_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clears user_data and ends the conversation"""
    cast(dict, context.user_data).clear()
    text = "Segnalazione annullata."
    if update.message:
        await update.message.reply_text(text)
    else:
        await update.callback_query.edit_message_text(text)
    return ConversationHandler.END


async def next_event(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Command which sends the event info for the next round."""
    session = DBSession()
    user = cast(User, update.effective_user)
    driver = get_driver(session, telegram_id=user.id)

    if not driver:
        message = "Per usare questa funzione devi essere registrato. Puoi farlo con /registrami."
        await update.message.reply_text(message)
        return

    if not (current_category := driver.current_category()):
        msg = "Al momento non fai parte di alcuna categoria."
    elif not (championship_round := current_category.next_round()):
        msg = "Il campionato è terminato, non ci sono più gare da completare."
    else:
        msg = championship_round.generate_info_message()

    await update.message.reply_text(msg)
    session.close()
    return


async def inline_query(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the inline query. This callback provides the user with a complete
    list of drivers saved in the database, and enables him to view the statistics
    of each of them.
    """

    query = update.inline_query.query
    session = DBSession()
    results = []
    for driver in get_championship(session).driver_list:
        if query.lower() in driver.psn_id.lower():
            (
                wins,
                podiums,
                poles,
                fastest_laps,
                races_disputed,
                avg_position,
                avg_quali_position,
            ) = driver.stats()

            unique_teams = ",".join(set(map(lambda team: team.team.name, driver.teams)))
            current_team = driver.current_team()
            if not current_team:
                current_team = "/"
            else:
                current_team = current_team.name

            unique_teams = unique_teams.replace(
                current_team, f"{current_team} [Attuale]"
            )

            if not unique_teams:
                unique_teams = "/"

            consistency = driver.consistency()
            sportsmanship = driver.sportsmanship()
            race_pace = driver.race_pace()
            quali_pace = driver.speed()

            overall = (
                sum(
                    map(
                        int,
                        filter(
                            lambda x: x != "dati insufficienti",
                            (consistency, sportsmanship, race_pace, quali_pace),
                        ),
                    )
                )
                // 4
            )

            result_article = InlineQueryResultArticle(
                id=str(uuid4()),
                title=driver.psn_id,
                input_message_content=InputTextMessageContent(
                    (
                        f"<i><b>PROFILO PILOTA: {driver.psn_id.upper()}</b></i>\n\n"
                        f"<b>Overall:</b> <i>{overall}</i>\n"
                        f"<b>Affidabilità:</b> <i>{consistency}</i>\n"
                        f"<b>Sportività:</b> <i>{sportsmanship}</i>\n"
                        f"<b>Qualifica:</b> <i>{quali_pace}</i>\n"
                        f"<b>Passo gara:</b> <i>{race_pace}</i>\n\n"
                        f"<b>Vittorie:</b> <i>{wins}</i>\n"
                        f"<b>Podi:</b> <i>{podiums}</i>\n"
                        f"<b>Pole:</b> <i>{poles}</i>\n"
                        f"<b>Giri veloci:</b> <i>{fastest_laps}</i>\n"
                        f"<b>Gare disputate:</b> <i>{races_disputed}</i>\n"
                        f"<b>Piazzamento medio (Gara):</b> <i>{avg_position}</i>\n"
                        f"<b>Piazzamento medio (Qualifica)</b>: <i>{avg_quali_position}</i>\n"
                        f"<b>Team:</b> <i>{unique_teams}</i>"
                    ),
                ),
            )
            results.append(result_article)

    await update.inline_query.answer(results)


async def championship_standings(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """When activated via the /classifica command, it sends a message containing
    the current championship standings for the category the user is in.
    """
    session = DBSession()
    user = cast(User, update.effective_user)
    driver = get_driver(session, telegram_id=user.id)
    if not driver:
        await update.message.reply_text(
            "Per usare questa funzione devi essere registrato.\n"
            "Puoi farlo con /registrami."
        )
        return

    category = driver.current_category()

    if not category:
        text = (
            "Non fai parte di alcuna categoria al momento, quando ti iscriverai "
            "ad un nostro campionato potrai utilizzare questo comando per vedere "
            "la classifica della tua categoria."
        )
        await update.message.reply_text(text)
        return

    message = f"<b><i>CLASSIFICA {category.name}</i></b>\n\n"
    standings = category.standings()

    for pos, (driver, (points, diff)) in enumerate(standings.items(), start=1):

        if diff > 0:
            diff = f" ↓{abs(diff)}"
        elif diff < 0:
            diff = f" ↑{abs(diff)}"
        else:
            diff = ""

        message += f"{pos} - {driver.psn_id} <i>{points}{diff} </i>\n"

    message = message.replace(driver.psn_id, f"<b>{driver.psn_id}</b>")

    await update.message.reply_text(text=message)


async def complete_championship_standings(
    update: Update, _: ContextTypes.DEFAULT_TYPE
) -> None:
    """When activated via the /classifica command, it sends a message containing
    the current championship standings for the category the user is in.
    """
    sqla_session = DBSession()
    teams: DefaultDict[Team, float] = defaultdict(float)
    championship = get_championship(sqla_session)

    if not championship:
        return

    message = f"<b>CLASSIFICHE #{championship.abbreviated_name}</b>"
    if not championship:
        await update.message.reply_text("Il campionato è finito.")
        sqla_session.close()
        return

    for category in championship.categories:

        standings = category.standings(-1)
        message += f"\n\n<b><i>CLASSIFICA PILOTI {category.name}</i></b>\n\n"

        for pos, (driver, (points, diff)) in enumerate(standings.items(), start=1):

            if diff > 0:
                diff = f" ↓{abs(diff)}"
            elif diff < 0:
                diff = f" ↑{abs(diff)}"
            else:
                diff = ""

            team = driver.current_team()
            if team:
                team_name = team.name
            else:
                team_name = ""
            message += f"{pos} - {team_name} {driver.psn_id} <i>{points}{diff}</i>\n"

            if (
                team_obj := driver.current_team()
            ):  # Check if the driver has left the team
                teams[team_obj] += points

    for team_obj, points in teams.items():
        points += team_obj.current_championship().penalty_points  # type: ignore

    message += "\n\n<i><b>CLASSIFICA COSTRUTTORI</b></i>\n\n"
    for pos, (team_obj, points) in enumerate(
        sorted(list(teams.items()), key=lambda x: x[1], reverse=True), start=1
    ):
        message += f"{pos}- {team_obj.name} <i>{points}</i>\n"
    await update.message.reply_text(message)
    sqla_session.close()


async def last_race_results(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """When activated via the /ultima_gara command, it sends a message containing
    the results of the user's last race."""

    sqla_session = DBSession()
    user = cast(User, update.effective_user)
    driver = get_driver(sqla_session, telegram_id=user.id)

    if not driver:
        await update.message.reply_text(
            "Per usare questo comando è necessario essere registrati."
            " Puoi farlo tramite /registrami."
        )
        return

    category = driver.current_category()
    if not category:
        await update.message.reply_text(
            "Pare che tu non faccia parte di alcuna categoria al momento."
        )
        return

    championship_round = category.last_completed_round()

    if not championship_round:
        await update.message.reply_text(
            "I risultati non sono ancora stati caricati, solitamente "
            "diventano disponibili dopo che ogni categoria ha completato la sua gara."
        )
        return

    message = f"<i><b>RISULTATI {championship_round.number}ª TAPPA</b></i>\n\n"

    for session in championship_round.sessions:
        message += session.results_message()

    await update.message.reply_text(text=message)
    sqla_session.close()
    return


async def complete_last_race_results(
    update: Update, _: ContextTypes.DEFAULT_TYPE
) -> None:
    """Sends a message containing the race and qualifying results of the last completed
    round in each category of the current championship."""
    sqla_session = DBSession()
    championship = get_championship(sqla_session)
    message = ""
    if not championship:
        return

    for category in championship.categories:
        championship_round = category.last_completed_round()

        if not championship_round:
            continue

        message += (
            f"<i><b>RISULTATI {championship_round.number}ª "
            f"TAPPA #{championship.abbreviated_name}</b></i>\n\n"
        )

        for session in championship_round.sessions:
            message += session.results_message()

    await update.message.reply_text(text=message)
    sqla_session.close()


async def announce_reports(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message to the report channel announcing that the report window
    has opened for a specific category.
    """
    sqla_session = DBSession()
    championship = get_championship(sqla_session)

    if not championship:
        sqla_session.close()
        return

    if championship_round := championship.reporting_round():
        text = (
            f"<b>Segnalazioni Categoria {championship_round.category.name}</b>\n"
            f"{championship_round.number}ª Tappa / {championship_round.circuit}\n"
            f"#{championship.abbreviated_name}Tappa{championship_round.number} #{championship_round.category.name}"
        )

        await context.bot.send_message(
            chat_id=config.REPORT_CHANNEL, text=text, disable_notification=True
        )
    sqla_session.close()


async def close_report_window(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a sticker to the report channel indicating that the time window for making
    reports has closed.
    """

    sqla_session = DBSession()
    championship = get_championship(sqla_session)

    if championship:
        if round := championship.reporting_round():
            if not round.reports:
                await context.bot.send_message(
                    chat_id=config.REPORT_CHANNEL, text="Nessuna segnalazione ricevuta."
                )

            await context.bot.send_sticker(
                chat_id=config.REPORT_CHANNEL,
                sticker=open("./app/images/sticker.webp", "rb"),
                disable_notification=True,
            )
    sqla_session.close()


async def freeze_participation_list(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Freezes the participation list sent earlier during the day."""
    chat_data = cast(dict, context.chat_data)
    message: Message | None = chat_data.get("participation_list_message")
    if message:
        await message.edit_reply_markup()  # Deletes the buttons.
    chat_data.clear()


async def send_participation_list(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the list of drivers supposed to participate to a race."""

    sqla_session = DBSession()
    championship = get_championship(sqla_session)
    chat_data = cast(dict, context.chat_data)
    chat_data["participation_list_sqlasession"] = sqla_session

    if not championship:
        sqla_session.close()
        return

    if not (category := championship.current_racing_category()):
        sqla_session.close()
        return

    if not (championship_round := category.first_non_completed_round()):
        sqla_session.close()
        return

    drivers = category.active_drivers()
    text = (
        f"<b>{championship_round.number}ᵃ Tappa {category.name}</b>\n"
        f"Circuito: <b>{championship_round.circuit}</b>"
    )

    chat_data["participation_list_text"] = text
    text += f"\n0/{len(drivers)}\n"
    chat_data["participants"] = {}  # dict[telegram_id, status]
    for driver in drivers:
        driver_obj = driver.driver

        chat_data["participants"][driver_obj.psn_id] = [
            driver_obj.telegram_id,
            None,
        ]
        text += f"\n{driver_obj.psn_id}"

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Presente ✅", callback_data="participating"),
                InlineKeyboardButton("Assente ❌", callback_data="not_participating"),
            ]
        ]
    )

    if context.bot_data.get("called_manually_by"):
        chat_id = context.bot_data.pop("called_manually_by")
    else:
        chat_id = config.GROUP_CHAT

    message = await context.bot.send_message(
        chat_id=chat_id, text=text, reply_markup=reply_markup
    )

    chat_data["participation_list_message"] = message

    await context.bot.pin_chat_message(
        message_id=message.message_id,
        chat_id=message.chat_id,
        disable_notification=True,
    )


async def update_participation_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Manages updates to the list of drivers supposed to participate to a race."""

    chat_data = cast(dict, context.chat_data)

    if not chat_data.get("participants"):
        return

    session = chat_data.get("participation_list_sqlasession")
    if not session:
        return

    user = cast(User, update.effective_user)
    user_psn_id = None

    # Checks for non-registered users and queries the database to verify if
    # the user has registered since the participation list was last sent
    for psn_id, (tg_id, status) in chat_data["participants"].items():
        if not tg_id:
            driver = get_driver(session, psn_id=psn_id)
            if driver:
                chat_data["participants"][psn_id] = [
                    driver.telegram_id,
                    status,
                ]
            tg_id = chat_data["participants"][psn_id][0]

        if tg_id == user.id:
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

    persistence = PicklePersistence(
        filepath="bot_context",
        store_data=PersistenceInput(bot_data=True, chat_data=False, user_data=False),
    )

    defaults = Defaults(parse_mode=ParseMode.HTML, tzinfo=pytz.timezone("Europe/Rome"))
    application = (
        Application.builder()
        .token(TOKEN)
        .defaults(defaults)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .persistence(persistence)
        .build()
    )

    application.job_queue.run_daily(
        callback=announce_reports,
        time=time(0),
        chat_id=config.REPORT_CHANNEL,
    )
    application.job_queue.run_daily(
        callback=send_participation_list,
        time=time(hour=7),
        chat_id=config.GROUP_CHAT,
    )
    application.job_queue.run_daily(
        callback=close_report_window,
        time=time(hour=23, minute=59, second=59),
        chat_id=config.REPORT_CHANNEL,
    )
    application.job_queue.run_daily(
        callback=freeze_participation_list,
        time=time(hour=21, minute=45),
        chat_id=config.REPORT_CHANNEL,
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(driver_registration)
    application.add_handler(report_processing)
    application.add_handler(report_creation)
    application.add_handler(save_results_conv)

    application.add_handler(
        CallbackQueryHandler(
            update_participation_list, r"participating|not_participating"
        )
    )

    application.add_handler(CommandHandler("start", start, filters=ChatType.PRIVATE))  # type: ignore
    application.add_handler(InlineQueryHandler(inline_query))
    application.add_handler(CommandHandler("prossima_gara", next_event))
    application.add_handler(CommandHandler("classifica", championship_standings))
    application.add_handler(
        CommandHandler("classifica_completa", complete_championship_standings)
    )
    application.add_handler(CommandHandler("ultima_gara", last_race_results))
    application.add_handler(CommandHandler("ultime_gare", complete_last_race_results))
    application.add_error_handler(error_handler)

    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
