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
from app.components.conversations.driver_registration import driver_registration
from app.components.conversations.penalty_creation import penalty_creation
from app.components.conversations.report_creation import report_creation
from app.components.conversations.result_recognition import save_results
from app.components.models import Team
from app.components.queries import get_championship, get_driver, get_team_leaders
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
from telegram.error import BadRequest, NetworkError
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
            if not driver.telegram_id:
                continue
            try:
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


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Writes full error traceback to a file and sends it to the dev channel.
    If the error was caused by a user a message will be displayed informing him
    about the error.
    """

    if isinstance(context.error, NetworkError):
        return

    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    try:
        if update.message.chat.type == ChatType.PRIVATE:
            await cast(User, update.effective_user).send_message(
                text=(
                    "⚠️ Si è verificato un errore!\n\n"
                    "Lo sviluppatore è stato informato del problema e cercherà "
                    "di risolverlo al più presto.\n"
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

    session = DBSession()
    user = cast(User, update.effective_user)
    text = (
        f"Ciao {user.first_name}!\n\n"
        "Sono il bot di Racing Team Italia 🇮🇹 e mi occupo delle <i>segnalazioni</i>, <i>statistiche</i> "
        "e <i>classifiche</i> dei nostri campionati.\n\n"
    )

    driver = get_driver(session, telegram_id=user.id)
    if not driver:
        text += (
            f"Se sei nuovo e vorresti entrare nel team puoi iscriverti sul nostro "
            "<i><a href='https://racingteamitalia.it/#user-registration-form-1115'>sito web</a></i>."
        )
    elif team := driver.current_team():
        if getattr(team.leader, "telegram_id") == user.id:
            await context.bot.set_my_commands(
                commands=config.LEADER_COMMANDS, scope=BotCommandScopeChat(user.id)
            )

    await update.message.reply_text(
        text=text,
        reply_markup=ForceReply(selective=True),
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


async def stats_info(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Tells the user how the statistics are calculated."""

    text = (
        "Di seguito sono riportate le formule utilizzate per il calcolo delle statistiche:\n\n"
        "- <b>Driver Rating</b>:\n"
        "Il driver rating è calcolato utilizzando l'algoritmo "
        "<a href='https://www.microsoft.com/en-us/research/project/trueskill-ranking-system/'>TrueSkill™</a> "
        "sviluppato da Microsoft, si basa sulle posizioni di arrivo in gara, tenendo anche conto "
        "del livello di abilità degli avversari.\n"
        "Non coinvolgendo altri fattori come il tempo totale di gara o il tempo di qualificazione, "
        "che possono variare a seconda delle impostazioni del campionato, permette di confrontare "
        "tutti i piloti di RTI indipendentemente dalla categoria di cui fanno parte.\n\n"
        "- <b>Affidabilità</b>:\n"
        "L'affidabilità misura la tendenza di un pilota a guadagnare lo stesso numero di punti "
        "in ogni gara, viene quindi in primis preso in considerazione il rapporto tra le"
        "<i>gare effettivamente completate dal pilota (gc)</i> e le <i>gare a cui avrebbe dovuto partecipare (g)</i>."
        "Questo rapporto assume sempre un valore compreso tra 0 (nessuna gara completata) e 1 (tutte le gare completate). "
        "In secondo luogo si considera lo <i>scarto quadratico medio dei piazzamenti in gara (σ)</i>. "
        "La formula risulta quindi: \n"
        "<code>A = 100(gc/g) - 3σ</code>\n\n"
        "- <b>Sportività</b>:\n"
        "La sportività misura la tendenza di un pilota a non ricevere penalità in gara. Vengono "
        "quindi considerati i <i>secondi (s), punti di penalità (p), warning (w)</i> ricevuti e "
        "<i>punti licenza (pl)</i> detratti lungo l'arco delle gare (g) del campionato. "
        "Per calcolare il valore viene quindi utilizzata la seguente formula:\n"
        "<code>S = 100-(3(s/1.5+p+w+4(pl))/g) </code>\n\n"
        "- <b>Qualifica</b>:\n"
        "Misura la velocità in qualifica del pilota. Per questa "
        "statistica vengono presi in considerazione solamente i distacchi in percentuale "
        "rispetto al poleman. La formula viene un po' un casino su telegram, se sei curioso "
        "puoi vedere l'implementazione "
        "<a href='https://github.com/alexander-cingolani/bot-rti/blob/53aa191387a1d9182a533d0c228a4f9e7cb926e0/bot/app/components/models.py#L521'>qui</a>\n\n"
        "- <b>Passo Gara</b>:\n"
        "Come per la qualifica, solo che prende come riferimento il tempo di gara del vincitore. "
        "L'implementazione di questa statistica invece è "
        "<a href='https://github.com/alexander-cingolani/bot-rti/blob/53aa191387a1d9182a533d0c228a4f9e7cb926e0/bot/app/components/models.py#L586'>qui</a>. "
    )
    await update.message.reply_text(text, disable_web_page_preview=True)
    return


async def inline_query(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the inline query. This callback provides the user with a complete
    list of drivers saved in the database, and enables him to view the statistics
    of each of them.
    """

    query = update.inline_query.query
    session = DBSession()
    results = []
    championship = get_championship(session)

    if not championship:
        return

    for driver in championship.driver_list:
        if query.lower() in driver.psn_id.lower():
            statistics = driver.stats()

            unique_teams = ",".join(set(map(lambda team: team.team.name, driver.teams)))
            current_team = driver.current_team()
            if not current_team:
                team_text = "/"
            else:
                team_text = current_team.name

            unique_teams = unique_teams.replace(team_text, f"{team_text} [Attuale]")

            if not unique_teams:
                unique_teams = "/"

            result_article = InlineQueryResultArticle(
                id=str(uuid4()),
                title=driver.psn_id,
                input_message_content=InputTextMessageContent(
                    (
                        f"<i><b>PROFILO PILOTA: {driver.psn_id.upper()}</b></i>\n\n"
                        f"<b>Driver Rating</b>: <i>{round(driver.rating, 2) if driver.rating else 'N.D.'}</i>\n"
                        f"<b>Affidabilità</b>: <i>{driver.consistency()}</i>\n"
                        f"<b>Sportività</b>: <i>{driver.sportsmanship()}</i>\n"
                        f"<b>Qualifica</b>: <i>{driver.speed()}</i>\n"
                        f"<b>Passo gara</b>: <i>{driver.race_pace()}</i>\n\n"
                        f"<b>Vittorie</b>: <i>{statistics['wins']}</i>\n"
                        f"<b>Podi</b>: <i>{statistics['podiums']}</i>\n"
                        f"<b>Pole</b>: <i>{statistics['poles']}</i>\n"
                        f"<b>Giri veloci</b>: <i>{statistics['fastest_laps']}</i>\n"
                        f"<b>Gare disputate</b>: <i>{statistics['races_completed']}</i>\n"
                        f"<b>Piazz. medio gara</b>: <i>{statistics['avg_race_position']}</i>\n"
                        f"<b>Piazz. medio quali</b>: <i>{statistics['avg_quali_position']}</i>\n"
                        f"<b>Punti licenza</b>: <i>{driver.licence_points}</i>\n"
                        f"<b>Warning</b>: <i>{driver.warnings}</i>\n"
                        f"<b>Team</b>: <i>{unique_teams}</i>"
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
    user_driver = get_driver(session, telegram_id=user.id)
    if not user_driver:
        await update.message.reply_text(
            "Per usare questa funzione devi essere registrato.\n"
            "Puoi farlo con /registrami."
        )
        return

    category = user_driver.current_category()

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
            diff_text = f" ↓{abs(diff)}"
        elif diff < 0:
            diff_text = f" ↑{abs(diff)}"
        else:
            diff_text = ""

        if driver == user_driver:
            driver_name = f"<b>{driver.psn_id}</b>"
        else:
            driver_name = driver.psn_id
        message += f"{pos} - {driver_name} <i>{points}{diff_text} </i>\n"

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
    user_driver = get_driver(session=sqla_session, telegram_id=update.effective_user.id)
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
                diff_text = f" ↓{abs(diff)}"
            elif diff < 0:
                diff_text = f" ↑{abs(diff)}"
            else:
                diff_text = ""

            team = driver.current_team()
            if team:
                team_name = team.name
            else:
                team_name = ""

            if driver == user_driver:
                driver_name = f"<b>{driver.psn_id}</b>"
            else:
                driver_name = driver.psn_id

            message += f"{pos} - {team_name} {driver_name} <i>{points}{diff_text}</i>\n"

            if (
                team_obj := driver.current_team()
            ):  # Checks if the driver has left the team
                teams[team_obj] += points

    for team_obj, points in teams.items():
        points += float(team_obj.current_championship().penalty_points)

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
            f"#{championship.abbreviated_name}Tappa{championship_round.number}"
            f" #{championship_round.category.name}"
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
        if championship_round := championship.reporting_round():
            if not championship_round.reports:
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
        time=time(hour=0, minute=15, second=35),
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
    application.add_handler(penalty_creation)
    application.add_handler(report_creation)
    application.add_handler(save_results)

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
    application.add_handler(CommandHandler("info_stats", stats_info))

    application.add_error_handler(error_handler)

    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
