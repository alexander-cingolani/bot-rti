"""
This telegram bot manages racingteamitalia's leaderboards, statistics and penalties.
"""

import json
import logging
import os
import traceback
from datetime import datetime
from difflib import get_close_matches
from typing import Any, cast
from uuid import uuid4

import pytz
from app import config
from app.components.conversations.driver_registration import driver_registration
from app.components.conversations.penalty_creation import penalty_creation
from app.components.conversations.report_creation import report_creation
from app.components.conversations.result_recognition import save_results_conv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SQLASession
from sqlalchemy.orm import sessionmaker
from telegram import BotCommandScopeAllPrivateChats, BotCommandScopeChat
from telegram import Chat as TGChat
from telegram import (
    ChatMember,
    ChatMemberUpdated,
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
    ChatMemberHandler,
    CommandHandler,
    ContextTypes,
    Defaults,
    InlineQueryHandler,
    MessageHandler,
    filters,
)

from models import Chat, Driver, Participation, RoundParticipant
from queries import (
    delete_chat,
    get_all_drivers,
    get_championship,
    get_driver,
    get_participants_from_round,
    get_team_leaders,
    update_participant_status,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN: str = os.environ["BOT_TOKEN"]
if not TOKEN:
    raise RuntimeError("No bot token found in environment variables.")

if os.environ.get("DB_URL"):
    engine = create_engine(os.environ["DB_URL"])
else:
    raise RuntimeError("No DB_URL in environment variables, can't connect to database.")

DBSession = sessionmaker(bind=engine, autoflush=False)
session = DBSession()


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
            await update.effective_user.send_message(
                text=(
                    "Problemi, problemi, problemi! 😓\n"
                    f"Questo errore è dovuto all'incompetenza di {config.OWNER.mention_html()}.\n"
                    "Non farti problemi ad insultarlo in chat."
                )
            )
    except AttributeError:
        pass

    traceback_list = traceback.format_exception(
        None, context.error, context.error.__traceback__  # type: ignore
    )
    traceback_string = "".join(traceback_list)
    update_str = update.to_dict()

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


def extract_status_change(
    chat_member_update: ChatMemberUpdated,
) -> tuple[bool, bool] | None:
    """Takes a ChatMemberUpdated instance and extracts whether the 'old_chat_member' was a member

    of the chat and whether the 'new_chat_member' is a member of the chat. Returns None, if

    the status didn't change.

    """

    status_change = chat_member_update.difference().get("status")

    old_is_member, new_is_member = chat_member_update.difference().get(
        "is_member", (None, None)
    )

    if status_change is None:
        return None

    old_status, new_status = status_change

    was_member = old_status in (
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ) or (old_status == ChatMember.RESTRICTED and old_is_member is True)

    is_member = new_status in (
        ChatMember.MEMBER,
        ChatMember.OWNER,
        ChatMember.ADMINISTRATOR,
    ) or (new_status == ChatMember.RESTRICTED and new_is_member is True)

    return was_member, is_member


async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Tracks the chats the bot is in."""

    result = extract_status_change(update.my_chat_member)

    if result is None:
        return

    chat = update.effective_chat
    was_member, is_member = result
    session = DBSession()

    if was_member and not is_member:
        delete_chat(session, chat.id)
        return

    if chat.type == TGChat.CHANNEL and chat.id not in (
        config.TEST_CHANNEL,
        config.REPORT_CHANNEL,
    ):
        await chat.leave()
        return

    user = update.effective_user
    driver = get_driver(session, telegram_id=user.id)
    if not driver:
        website_link = "<a href='https://racingteamitalia.it/'>Racing Team Italia</a>"
        await chat.send_message(
            f"Questo bot è riservato esclusivamente ai gruppi di {website_link}.\n\n"
            f"L'utente che mi ha aggiunto, {user.mention_html()}, non risulta "
            f"essere un membro registrato del team, pertanto procederò a rimuovermi dal gruppo.\n"
        )
        await chat.leave()
        return

    await context.bot.set_my_commands(
        config.GROUP_COMMANDS, BotCommandScopeChat(chat.id)
    )

    is_group = True if chat.type in (TGChat.SUPERGROUP, TGChat.GROUP) else False
    session.add(Chat(chat_id=chat.id, is_group=is_group))
    session.commit()


async def greet_new_chat_members(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    result = extract_status_change(update.my_chat_member)
    if result is None:
        return

    chat = update.effective_chat
    user = update.effective_user
    was_member, is_member = result

    if was_member and not is_member:
        text = f"{user.mention_html()} ci ha lasciati 😔"
    elif not was_member and is_member:
        if not chat.id == config.GROUP_CHAT:
            return

        session = DBSession()
        driver = get_driver(session, telegram_id=user.id)
        session.close()

        if not driver:
            text = (
                f"Benvenuto {user.mention_html()}!\n\n"
                "Sono il bot di Racing Team Italia, per sfruttare a pieno le mie funzionalità, "
                "registrati scrivendomi /registrami in chat privata."
                f"Prima di fare ciò però assicurati di aver scritto il tuo ID PSN a {config.OWNER.mention_html()}."
            )
            button_row = [
                InlineKeyboardButton(
                    text="Vai alla chat ➡️", url=f"t.me/{context.bot.username}"
                )
            ]
            await chat.send_message(
                text, reply_markup=InlineKeyboardMarkup([button_row])
            )
            return

        text = f"Bentornato {user.mention_html()}!"
    else:
        return

    await chat.send_message(text)
    return


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the /start command is issued."""

    session = DBSession()
    user = update.effective_user
    text = (
        f"Ciao {user.first_name}!\n\n"
        "Sono il bot di Racing Team Italia 🇮🇹\nMi occupo delle <i>segnalazioni</i>, <i>statistiche</i> "
        "e <i>classifiche</i> dei nostri campionati."
    )

    driver = get_driver(session, telegram_id=user.id)
    if not driver:
        website_link = "<a href='https://racingteamitalia.it/#user-registration-form-1115'>sito</a>"
        instagram_link = "<a href='https://www.instagram.com/rti_racingteamitalia/'>rti_racingteamitalia</a>"
        text += (
            "\n\nSe sei nuovo nel team, l'ultimo step è completare la registrazione tramite il comando /registrami.\n\n"
            f"Se invece non fai ancora parte del team, puoi registrarti sul nostro {website_link}. "
            f"Per qualsiasi informazione puoi scriverci sul nostro profilo instagram, {instagram_link}."
        )
    elif team := driver.current_team():
        if getattr(team.leader, "telegram_id", 0) == user.id:
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
        f"Questo bot è gestito da {config.OWNER.mention_html()},"
        " se stai riscontrando un problema non esitare a contattarlo."
    )
    await update.message.reply_text(text)


async def next_event(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Command which sends the event info for the next round."""

    session = DBSession()
    user = update.effective_user
    driver = get_driver(session, telegram_id=user.id)

    if not driver:
        message = (
            "Per usare questa funzione devi essere registrato. Puoi farlo con /registrami "
            "in chat privata."
        )
        await update.message.reply_text(message)
        return

    if not (current_category := driver.current_category()):
        msg = "Al momento non fai parte di alcuna categoria."
    elif not (rnd := current_category.next_round()):
        msg = "Il campionato è terminato, non ci sono più gare da completare."
    else:
        msg = rnd.generate_info_message()

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
    results: list[InlineQueryResultArticle] = []
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

            current_category = driver.current_category()
            rnd = current_category.penultimate_completed_round()
            previous_rating = 0
            if rnd:
                for result in rnd.long_race.race_results:
                    if result.driver_id == driver.driver_id:
                        previous_rating = (
                            result.driver_mu - config.K * result.driver_sigma
                        )
                        break

            if previous_rating:
                diff = round(driver.rating - previous_rating, 2)
                diff_text = f"↓{abs(diff)}" if diff < 0 else f"↑{abs(diff)}"
                driver_rating_text = f"<b>Driver Rating</b>: <i>{round(driver.rating, 2)} {diff_text}</i>\n"
            elif driver.rating:
                driver_rating_text = (
                    f"<b>Driver Rating</b>: <i>{round(driver.rating, 2)}</i>\n"
                )
            else:
                driver_rating_text = f"<b>Driver Rating</b>: <i>N.D.</i>\n"

            consistency = driver.consistency()
            speed = driver.speed()
            sportsmanship = driver.sportsmanship()
            race_pace = driver.race_pace()

            result_article = InlineQueryResultArticle(
                id=str(uuid4()),
                title=driver.psn_id,
                input_message_content=InputTextMessageContent(
                    (
                        f"<i><b>PROFILO PILOTA: {driver.psn_id.upper()}</b></i>\n\n"
                        + driver_rating_text
                        + f"<b>Affidabilità</b>: <i>{consistency if consistency else 'Dati insufficienti'}</i>\n"
                        f"<b>Sportività</b>: <i>{sportsmanship if sportsmanship else 'Dati insufficienti'}</i>\n"
                        f"<b>Qualifica</b>: <i>{speed if speed else 'Dati insufficienti'}</i>\n"
                        f"<b>Passo gara</b>: <i>{race_pace if race_pace else 'Dati insufficienti.'}</i>\n\n"
                        f"<b>Vittorie</b>: <i>{statistics['wins']}</i>\n"
                        f"<b>Podi</b>: <i>{statistics['podiums']}</i>\n"
                        f"<b>Pole</b>: <i>{statistics['poles']}</i>\n"
                        f"<b>Giri veloci</b>: <i>{statistics['fastest_laps']:g}</i>\n"
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
    user = update.effective_user
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
    standings = category.standings(-1)

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
        message += f"{pos} - {driver_name} <i>{points:g}{diff_text} </i>\n"

    await update.message.reply_text(text=message)


async def complete_championship_standings(
    update: Update, _: ContextTypes.DEFAULT_TYPE
) -> None:
    """When activated via the /classifica command, it sends a message containing
    the current championship standings for the category the user is in.
    """
    sqla_session = DBSession()
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

            message += (
                f"{pos} - {team_name} {driver_name} <i>{points:g}{diff_text}</i>\n"
            )

    await update.message.reply_text(message)
    sqla_session.close()


async def constructors_standings(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message containing the constructors championship standings. The team of the driver
    who called this function is highlighted in bold."""

    sqla_session = DBSession()
    championship = get_championship(sqla_session)

    if not championship:
        return

    driver = get_driver(sqla_session, telegram_id=update.effective_user.id)

    teams = sorted(championship.teams, key=lambda t: t.points, reverse=True)

    message = f"<b>CLASSIFICA COSTRUTTORI #{championship.abbreviated_name}</b>\n\n"
    for pos, team in enumerate(teams, start=1):
        if driver:
            current_team = driver.current_team()
            if current_team and current_team.team_id == team.team_id:
                message += f"{pos} - <b>{team.team.name}</b> <i>{team.points:g}</i>\n"
                continue

        message += f"{pos} - {team.team.name} <i>{team.points:g}</i>\n"

    await update.message.reply_text(message)


async def last_race_results(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """When activated via the /ultima_gara command, it sends a message containing
    the results of the user's last race."""

    sqla_session = DBSession()
    user = update.effective_user
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

    rnd = category.last_completed_round()

    if not rnd:
        await update.message.reply_text(
            "I risultati non sono ancora stati caricati, solitamente "
            "diventano disponibili dopo che ogni categoria ha completato la sua gara."
        )
        return

    message = f"<i><b>RISULTATI {rnd.number}ª TAPPA</b></i>\n\n"

    for session in rnd.sessions:
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
        rnd = category.last_completed_round()

        if not rnd:
            continue

        message += f"{rnd.number}ª TAPPA {category.name}\n\n"

        for session in rnd.sessions:
            message += session.results_message()

    if not message:
        message = (
            "I risultati non sono ancora stati caricati, solitamente "
            "diventano disponibili dopo che ogni categoria ha completato la sua gara."
        )

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

    if rnd := championship.reporting_round():
        text = (
            f"<b>Segnalazioni Categoria {rnd.category.name}</b>\n"
            f"{rnd.number}ª Tappa - {rnd.circuit.abbreviated_name}\n"
            f"#{championship.abbreviated_name}Tappa{rnd.number}"
            f" #{rnd.category.tag}"
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
        if rnd := championship.reporting_round():
            if not rnd.reports:
                await context.bot.send_message(
                    chat_id=config.REPORT_CHANNEL, text="Nessuna segnalazione ricevuta."
                )

            await context.bot.send_sticker(
                chat_id=config.REPORT_CHANNEL,
                sticker=open("./app/assets/images/sticker.webp", "rb"),
                disable_notification=True,
            )
    sqla_session.close()


async def freeze_participation_list(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Freezes the participants list sent earlier during the day."""
    chat_data = cast(dict[str, Any], context.chat_data)
    message: Message | None = chat_data.get("participation_list_message")
    if message:
        await message.edit_reply_markup()  # Deletes the buttons.
    chat_data.clear()


async def send_participants_list(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the list of drivers supposed to participate to a race."""

    sqla_session = DBSession()
    championship = get_championship(sqla_session)
    chat_data = cast(dict[str, Any], context.chat_data)
    chat_data["participation_list_sqlasession"] = sqla_session

    if not championship:
        sqla_session.close()
        return

    if not (category := championship.current_racing_category()):
        sqla_session.close()
        return

    if not (rnd := category.next_round()):
        sqla_session.close()
        return

    drivers = category.active_drivers()
    drivers.sort(key=lambda d: d.driver.psn_id.lower())
    text = (
        f"<b>{rnd.number}ᵃ Tappa {category.name}</b>\n"
        f"<b>{rnd.circuit.abbreviated_name} - {rnd.circuit.variation}</b>"
    )

    chat_data["participation_list_text"] = text
    text += f"\n0/{len(drivers)}\n"

    participants: list[RoundParticipant] = []
    for driver in drivers:
        participant = RoundParticipant(
            round_id=rnd.round_id,
            driver_id=driver.driver_id,
        )
        participants.append(participant)
        sqla_session.add(participant)

        text += f"\n{driver.driver.psn_id}"

    sqla_session.commit()

    chat_data["participants"] = participants

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Presente ✅", callback_data="participating"),
                InlineKeyboardButton("Assente ❌", callback_data="not_participating"),
            ],
            [InlineKeyboardButton("Incerto ❓", callback_data="not_sure")],
        ]
    )

    message = await context.bot.send_message(
        chat_id=config.GROUP_CHAT, text=text, reply_markup=reply_markup
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
    chat_data = cast(dict[str, Any], context.chat_data)

    session: SQLASession | None = chat_data.get("participation_list_sqlasession")

    if not session:
        session = DBSession()

    championship = get_championship(session)
    if not championship:
        await update.callback_query.answer(
            "Il campionato a cui è legata questa lista è terminato.",
            show_alert=True,
        )
        return

    category = championship.current_racing_category()
    if not category:
        await update.callback_query.answer(
            "Questa lista è vecchia. La gara a cui si riferiva è gia passata.",
            show_alert=True,
        )
        return

    rnd = category.next_round()
    if not rnd:
        return

    if not chat_data.get("participants"):
        participants = get_participants_from_round(session, rnd.round_id)
        participants.sort(key=lambda p: p.driver.psn_id.lower())
        chat_data["participants"] = participants

    if not chat_data.get("participation_list_text"):
        chat_data["participation_list_text"] = (
            f"<b>{rnd.number}ᵃ Tappa {category.name}</b>\n"
            f"<b>{rnd.circuit.abbreviated_name} - {rnd.circuit.variation}</b>"
        )

    if not chat_data.get("participation_list_message"):
        chat_data["participation_list_message"] = update.message

    driver: Driver | None = get_driver(session, telegram_id=update.effective_user.id)
    if not driver:
        await update.callback_query.answer(
            "Non ti sei ancora registrato! Puoi farlo tramite il comando /registrami in privato.",
            show_alert=True,
        )
        return

    participants = cast(list[RoundParticipant], chat_data["participants"])
    for i, participant in enumerate(participants):
        if driver.driver_id == participant.driver_id:
            break
    else:
        await update.callback_query.answer(
            "Non risulti come partecipante a questa categoria. Se si tratta di un errore, "
            f"contatta @gino_pincopallo",
            show_alert=True,
        )
        return

    received_status = update.callback_query.data

    match received_status:
        case "participating":
            participant.participating = Participation.YES
        case "not_participating":
            participant.participating = Participation.NO
        case "not_sure":
            participant.participating = Participation.UNCERTAIN
        case _:
            pass

    update_participant_status(session, participant)

    participants[i] = participant

    text: str = chat_data["participation_list_text"]
    text += "\n{confirmed}/{total}\n"

    confirmed = 0
    total_drivers = 0

    for participant in participants:
        total_drivers += 1
        match participant.participating:
            case Participation.NO_REPLY:
                text_status = ""
            case Participation.YES:
                text_status = "✅"
                confirmed += 1
            case Participation.UNCERTAIN:
                text_status = "❓"
            case Participation.NO:
                text_status = "❌"

        text += f"\n{participant.driver.psn_id} {text_status}"

    text = text.format(confirmed=confirmed, total=total_drivers)
    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Presente ✅", callback_data="participating"),
                InlineKeyboardButton("Assente ❌", callback_data="not_participating"),
            ],
            [InlineKeyboardButton("Incerto ❓", callback_data="not_sure")],
        ]
    )
    await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
    return


async def participation_list_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message in the group chat mentioning drivers who forgot to reply to the
    participants list message."""
    chat_data = cast(dict[str, Any], context.chat_data)

    if not chat_data.get("participants"):
        championship = get_championship(session)
        if not championship:
            return

        category = championship.current_racing_category()
        if not category:
            return

        rnd = category.next_round()
        if not rnd:
            return
        participants = get_participants_from_round(session, rnd.round_id)
        participants.sort(key=lambda p: p.driver.psn_id.lower())
        chat_data["participants"] = participants

    participants = cast(list[RoundParticipant], chat_data["participants"])

    if participants[0].round.date != datetime.now().date():
        return

    mentions: list[str] = []
    for participant in participants:
        if participant.participating in (
            Participation.NO_REPLY,
            Participation.UNCERTAIN,
        ):
            if not participant.driver.telegram_id:
                continue

            mentions.append(
                f"{User(participant.driver.telegram_id, participant.driver.psn_id, is_bot=False).mention_html()}"
            )

    text = ""
    if len(mentions) == 1:
        text = f"Ehi {mentions[0]}! Manchi solo tu a confermare la presenza sulla lista dei partecipanti."
    else:
        text = f"{', '.join(mentions)}\n\nRicordatevi di confermare la vostra presenza nella lista dei partecipanti."

    await context.bot.send_message(chat_id=config.GROUP_CHAT, text=text)

    return


async def calendar(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends the list of rounds yet to be completed in the user's category.
    This command is only available for registered and currently active users."""
    session = DBSession()
    driver = get_driver(session, telegram_id=update.effective_user.id)

    message = ""

    if not driver:
        await update.message.reply_text(
            "Solo i piloti registrati possono usare questo comando."
        )
        return

    category = driver.current_category()

    if not category:
        await update.message.reply_text(
            "Solo i piloti che stanno partecipando ad un campionato possono usare questo comando."
        )
        return

    message += f"<b>Calendario {category.name}</b>\n\n"

    for rnd in category.rounds:
        if rnd.date > datetime.now().date():
            message += f"{rnd.number} - {rnd.circuit.abbreviated_name}\n"
        else:
            message += f"{rnd.number} - <s>{rnd.circuit.abbreviated_name}</s>\n"

    await update.message.reply_text(message)

    return


async def non_existant_command(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Tells the user that the given command does not exist and provides him with a complete
    list of commands."""

    command_given = update.message.text[1:]  # Remove the '/' in from the message.

    team_leader_commands = [i[0] for i in config.LEADER_ONLY_COMMANDS]
    all_commands = [i[0] for i in config.ADMIN_COMMANDS]
    if matches := get_close_matches(
        command_given, possibilities=all_commands, cutoff=0.5
    ):
        closest_match = matches[0]
        text = f"""Quel comando non esiste. Forse intendevi /{closest_match}?"""
        telegram_id = update.effective_user.id

        if telegram_id not in config.ADMINS:
            await update.message.reply_text(text)
            return

        session = DBSession()
        driver = get_driver(session, telegram_id=telegram_id)

        if not driver:
            text = "Quel comando non esiste"
        elif not driver.is_leader and closest_match in team_leader_commands:
            text = "Quel comando non esiste."

        await update.message.reply_text(text)


async def user_stats(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    sqla_session = DBSession()

    if not (driver := get_driver(sqla_session, telegram_id=update.effective_user.id)):
        await update.message.reply_text(
            "Per usare questo comando occorre prima essersi registrati."
        )
        return

    unique_teams = ",".join(set(map(lambda team: team.team.name, driver.teams)))
    current_team = driver.current_team()
    if not current_team:
        team_text = "/"
    else:
        team_text = current_team.name
    unique_teams = unique_teams.replace(team_text, f"{team_text} [Attuale]")
    if not unique_teams:
        unique_teams = "/"

    statistics = driver.stats()
    consistency = driver.consistency()
    speed = driver.speed()
    sportsmanship = driver.sportsmanship()
    race_pace = driver.race_pace()

    current_category = driver.current_category()
    rnd = current_category.penultimate_completed_round()
    previous_rating = 0
    if rnd:
        for result in rnd.long_race.race_results:
            if result.driver_id == driver.driver_id:
                previous_rating = result.driver_mu - config.K * result.driver_sigma
                break

    if previous_rating:
        diff = round(driver.rating - previous_rating, 2)
        diff_text = f"↓{abs(diff)}" if diff < 0 else f"↑{abs(diff)}"
        driver_rating_text = (
            f"<b>Driver Rating</b>: <i>{round(driver.rating, 2)} {diff_text}</i>\n"
        )
    elif driver.rating:
        driver_rating_text = f"<b>Driver Rating</b>: <i>{round(driver.rating, 2)}</i>\n"
    else:
        driver_rating_text = f"<b>Driver Rating</b>: <i>N.D.</i>\n"

    await update.message.reply_text(
        f"<i><b>PROFILO PILOTA: {driver.psn_id.upper()}</b></i>\n\n"
        + driver_rating_text
        + f"<b>Affidabilità</b>: <i>{consistency if consistency else 'Dati insufficienti'}</i>\n"
        f"<b>Sportività</b>: <i>{sportsmanship if sportsmanship else 'Dati insufficienti'}</i>\n"
        f"<b>Qualifica</b>: <i>{speed if speed else 'Dati insufficienti'}</i>\n"
        f"<b>Passo gara</b>: <i>{race_pace if race_pace else 'Dati insufficienti.'}</i>\n\n"
        f"<b>Vittorie</b>: <i>{statistics['wins']}</i>\n"
        f"<b>Podi</b>: <i>{statistics['podiums']}</i>\n"
        f"<b>Pole</b>: <i>{statistics['poles']}</i>\n"
        f"<b>Giri veloci</b>: <i>{statistics['fastest_laps']:g}</i>\n"
        f"<b>Gare disputate</b>: <i>{statistics['races_completed']}</i>\n"
        f"<b>Piazz. medio gara</b>: <i>{statistics['avg_race_position']}</i>\n"
        f"<b>Piazz. medio quali</b>: <i>{statistics['avg_quali_position']}</i>\n"
        f"<b>Punti licenza</b>: <i>{driver.licence_points}</i>\n"
        f"<b>Warning</b>: <i>{driver.warnings}</i>\n"
        f"<b>Team</b>: <i>{unique_teams}</i>"
    )


async def top_ten(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a list containing the top 10 drivers by rating."""
    session = DBSession()
    drivers = get_all_drivers(session)

    drivers.sort(key=lambda d: d.rating, reverse=True)

    n = 10
    if len(drivers) < n:
        n = len(drivers)

    message = "Top 10 Piloti per Driver Rating:\n\n"
    for driver in drivers[:n]:
        message += f"<b>{driver.psn_id}</b> <i>{driver.rating:.2f}</i>\n"

    await update.message.reply_text(message)


async def unpin_auto_forward(update: Update, _: ContextTypes.DEFAULT_TYPE):
    await update.message.unpin()
    if update.message.from_user.is_bot and not update.message.document:
        await update.message.delete()
    if update.message.sticker:
        await update.message.delete()
    return


def main() -> None:
    """Starts the bot."""

    defaults = Defaults(parse_mode=ParseMode.HTML, tzinfo=pytz.timezone("Europe/Rome"))
    application = (
        Application.builder()
        .token(TOKEN)
        .defaults(defaults)
        .post_init(post_init)
        .build()
    )

    application.job_queue.run_daily(  # type: ignore
        callback=announce_reports,
        time=config.REPORT_WINDOW_OPENING,
        chat_id=config.REPORT_CHANNEL,
    )
    application.job_queue.run_daily(  # type: ignore
        callback=send_participants_list,
        time=config.PARTICIPANT_LIST_OPENING,
        chat_id=config.GROUP_CHAT,
    )
    application.job_queue.run_daily(  # type: ignore
        callback=close_report_window,
        time=config.REPORT_WINDOW_CLOSURE,
        chat_id=config.REPORT_CHANNEL,
    )
    application.job_queue.run_daily(  # type: ignore
        callback=freeze_participation_list,
        time=config.PARTICIPANTS_LIST_CLOSURE,
        chat_id=config.REPORT_CHANNEL,
    )
    application.job_queue.run_daily(  # type: ignore
        callback=participation_list_reminder,
        time=config.PARTICIPATION_LIST_REMINDER,
        chat_id=config.GROUP_CHAT,
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("aiuto", help_command))
    application.add_handler(
        ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER)
    )
    application.add_handler(
        ChatMemberHandler(greet_new_chat_members, ChatMemberHandler.CHAT_MEMBER)
    )
    application.add_handler(driver_registration)
    application.add_handler(penalty_creation)
    application.add_handler(report_creation)
    application.add_handler(save_results_conv)

    application.add_handler(
        CallbackQueryHandler(
            update_participation_list, r"participating|not_participating|not_sure"
        )
    )
    application.add_handler(
        MessageHandler(filters.IS_AUTOMATIC_FORWARD, unpin_auto_forward)
    )
    application.add_handler(CommandHandler("start", start, filters=ChatType.PRIVATE))  # type: ignore
    application.add_handler(InlineQueryHandler(inline_query))
    application.add_handler(CommandHandler("prossima_gara", next_event))
    application.add_handler(CommandHandler("classifica_piloti", championship_standings))
    application.add_handler(CommandHandler("calendario", calendar))
    application.add_handler(
        CommandHandler("classifica_costruttori", constructors_standings)
    )
    application.add_handler(
        CommandHandler("classifiche_piloti", complete_championship_standings)
    )
    application.add_handler(CommandHandler("ultima_gara", last_race_results))
    application.add_handler(CommandHandler("ultime_gare", complete_last_race_results))
    application.add_handler(CommandHandler("my_stats", user_stats))
    application.add_handler(CommandHandler("top_ten", top_ten))

    application.add_handler(
        MessageHandler(filters.Regex(r"^\/.*"), non_existant_command)
    )

    application.add_error_handler(error_handler)

    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
