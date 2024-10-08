"""
This module contains all the callbacks necessary to allow users to create protests
"""

import os
from datetime import datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

from app import config
from documents import ProtestDocument
from app.components.utils import send_or_edit_message
from more_itertools import chunked
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as SQLASession
from sqlalchemy.orm import sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from models import Category, Protest, Round, Team
from queries import (
    delete_protest,
    get_championship,
    get_driver,
    get_last_protest_number,
    get_protest,
)

(
    CATEGORY,
    SESSION,
    LINK,
    PROTESTING_DRIVER,
    PROTESTED_DRIVER,
    MINUTE,
    PROTEST_REASON,
    SEND,
    UNSEND,
) = range(5, 14)


engine = create_engine(os.environ["DB_URL"])

DBSession = sessionmaker(bind=engine, autoflush=False)


async def create_late_protest(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Asks the user which category he wants to create a protest in."""

    user_data = cast(dict[str, Any], context.user_data)
    chat_data = cast(dict[str, Any], context.chat_data)
    user_data.clear()

    sqla_session = DBSession()
    championship = get_championship(sqla_session)

    user_data["sqla_session"] = sqla_session
    user_data["championship"] = championship
    user_data["categories"] = {}

    driver = get_driver(sqla_session, telegram_id=update.effective_user.id)
    if not driver:
        await update.message.reply_text(
            "Come utente non registrato, non hai accesso a questa funzione."
        )
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    current_contract = driver.current_contract()
    if not current_contract:
        await update.message.reply_text(
            "Per usare questa funzione devi far parte di una scuderia."
        )
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    if not current_contract.has_permission(config.FILE_PROTEST):
        await update.message.reply_text(
            text="Non hai il permesso necessario per fare una segnalazione."
        )
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    user_data["protester"] = driver
    user_data["protesting_team"] = current_contract.team
    if not championship:
        await update.message.reply_text(
            "Il campionato è terminato, non è più possibile effettuare segnalazioni."
        )
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    today = datetime.now().date()
    buttons: list[InlineKeyboardButton] = []
    user_data["category_round"] = {}
    for i, category in enumerate(championship.categories):
        if datetime.now().weekday() == 6:
            break

        for championship_round in category.rounds:

            if championship_round.date > today:
                continue

            if championship_round.date.isocalendar()[1] == today.isocalendar()[1]:
                category_alias = f"c{i}"
                buttons.append(
                    InlineKeyboardButton(category.name, callback_data=category_alias)
                )
                user_data["categories"][category_alias] = category
                user_data["category_round"][category_alias] = championship_round
                break

    if not buttons:
        text = (
            "Troppo tardi perfino per le segnalazioni ritardatarie.."
            "\nI risultati di gara sono già stati confermati."
        )
        await update.message.reply_text(text)
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    text = "Scegli la categoria dove vuoi creare la segnalazione:"
    reply_markup = InlineKeyboardMarkup(list(chunked(buttons, 3)))
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

    chat_data["late_protest"] = True
    return CATEGORY


async def save_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the category and asks what session the accident happened in."""

    user_data = cast(dict[str, Any], context.user_data)

    if not update.callback_query.data.isdigit():
        user_data["category"] = user_data["categories"][update.callback_query.data]

    user_data["sessions"] = {}
    user_data["sessions"] = {}

    category: Category = user_data["category"]
    championship_round = cast(
        Round, user_data["category_round"][update.callback_query.data]
    )

    user_data["round"] = championship_round
    buttons: list[InlineKeyboardButton] = []
    for i, session in enumerate(championship_round.sessions):
        session_alias = f"s{i}"
        user_data["sessions"][session_alias] = session
        buttons.append(InlineKeyboardButton(session.name, callback_data=session_alias))
    chunked_buttons = list(chunked(buttons, 3))
    chunked_buttons.append(
        [
            InlineKeyboardButton(
                "« Modifica Categoria", callback_data="create_late_protest"
            )
        ]
    )

    round_number = championship_round.number
    text = f"""
<b>{category.name}</b> - Tappa {round_number} 
Scegli la sessione dove è avvenuto l'incidente:"""

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(chunked_buttons)
        )
    else:
        await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(chunked_buttons)
        )
    return SESSION


async def create_protest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user the session in which the accident happened."""
    user = update.effective_user
    user_data = cast(dict[str, Any], context.user_data)
    chat_data = cast(dict[str, Any], context.chat_data)
    user_data.clear()
    sqla_session = DBSession()
    driver = get_driver(sqla_session, telegram_id=user.id)
    chat_data["late_protest"] = False
    if not driver:
        await update.message.reply_text(
            "Non sei ancora registrato, puoi farlo tramite /registrami"
        )
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    current_contract = driver.current_contract()
    if not current_contract:
        await update.message.reply_text(
            "Per usare questa funzione devi far parte di una scuderia."
        )
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    if not current_contract.has_permission(config.FILE_PROTEST):
        text = "Non hai il permesso per fare una segnalazione."

        await update.message.reply_text(text=text)
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    user_data["protester"] = driver
    user_data["protesting_team"] = current_contract.team
    user_data["sqla_session"] = sqla_session

    championship = get_championship(sqla_session)

    if not championship:
        text = "Il campionato è terminato! Non puoi più fare segnalazioni."
        await update.message.reply_text(text)
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    user_data["championship"] = championship

    championship_rounds = championship.protesting_rounds()
    if not championship_rounds:
        text = (
            "Il periodo per le segnalazioni è terminato. Se necessario, puoi chiedere "
            "il permesso a un admin.\n"
            "Dopo aver ottenuto il permesso crea la segnalazione con "
            "/segnalazione_ritardataria."
        )
        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Chiedi il permesso", url="https://t.me/+6Ksa63FEKTNkYmI0"
                    )
                ]
            ]
        )
        await update.message.reply_text(text, reply_markup=reply_markup)
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    category = championship_rounds[0].category

    championship_round = None
    for rnd in championship_rounds:
        if rnd.category == category:
            championship_round = rnd
            break
    else:
        raise ValueError(
            "This shouldn't have happened. The current protesting round didn't match its category."
        )

    user_data["category"] = category
    user_data["round"] = championship_round
    text = (
        f"{championship_round.number}ª Tappa {category.name}"
        "\nIn che sessione è avvenuto l'incidente?"
    )

    user_data["sessions"] = {}
    buttons: list[InlineKeyboardButton] = []
    for i, session in enumerate(championship_round.sessions):
        session_alias = f"s{i}"
        user_data["sessions"][session_alias] = session
        buttons.append(InlineKeyboardButton(session.name, callback_data=session_alias))
    chunked_buttons = list(chunked(buttons, 3))
    chunked_buttons.append([InlineKeyboardButton("Annulla", callback_data="cancel")])

    if not update.callback_query:
        user_data["message"] = await update.message.reply_text(
            text, reply_markup=InlineKeyboardMarkup(chunked_buttons)
        )
    else:
        await update.callback_query.edit_message_text(
            text, reply_markup=InlineKeyboardMarkup(chunked_buttons)
        )
    return SESSION


async def save_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the session and asks for the protesting driver."""

    chat_data = cast(dict[str, Any], context.chat_data)
    user_data = cast(dict[str, Any], context.user_data)
    if not update.callback_query.data.isdigit():
        user_data["protest"] = Protest()
        user_data["protest"].session = user_data["sessions"][update.callback_query.data]
        user_data["drivers"] = {}

    if user_data["protest"].session.is_quali:
        text = (
            "Non essendo disponibili i replay delle qualifiche, è necessario "
            "fornire un video dell'episodio. Incolla il link al video su YouTube qui sotto."
        )
        callback_function = (
            str(SESSION) if chat_data.get("late_protest") else "create_protest"
        )
        chunked_buttons = [
            [
                InlineKeyboardButton(
                    "« Modifica sessione", callback_data=callback_function
                )
            ]
        ]

        if user_data["protest"].video_link:
            chunked_buttons[-1].append(
                InlineKeyboardButton("Pilota vittima »", callback_data=str(LINK))
            )

        await update.callback_query.edit_message_text(
            text=text, reply_markup=InlineKeyboardMarkup(chunked_buttons)
        )
        return LINK

    text = "Chi è la vittima?"
    buttons: list[InlineKeyboardButton] = []
    for i, driver in enumerate(user_data["protesting_team"].active_drivers):
        driver = driver.driver
        driver_alias = f"d{i}"
        # Only list the drivers who are in the specified category
        if driver_category := driver.current_category():
            if driver_category.category_id == user_data["category"].id:
                user_data["drivers"][driver_alias] = driver
                buttons.append(
                    InlineKeyboardButton(
                        driver.psn_id_or_abbreviated_name, callback_data=driver_alias
                    )
                )
    chunked_buttons = list(chunked(buttons, 2))
    callback_function = (
        str(SESSION) if chat_data.get("late_protest") else "create_protest"
    )
    chunked_buttons.append(
        [InlineKeyboardButton("« Modifica sessione", callback_data=callback_function)]
    )

    if user_data["protest"].protesting_driver:
        chunked_buttons[-1].append(
            InlineKeyboardButton("Link video »", callback_data=LINK)
        )

    await update.callback_query.edit_message_text(
        text=text, reply_markup=InlineKeyboardMarkup(chunked_buttons)
    )
    return PROTESTING_DRIVER


async def save_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the link provided by the user and asks who is considered to be the victim."""
    chat_data = cast(dict[str, Any], context.chat_data)
    user_data = cast(dict[str, Any], context.user_data)

    protesting_team = cast(Team, user_data["protesting_team"])

    if (
        not getattr(update.callback_query, "data", "").isdigit()
        and user_data["protest"].session.is_quali
    ):
        user_data["protest"].video_link = update.message.text

    text = "Chi è la vittima?"
    buttons: list[InlineKeyboardButton] = []
    for i, driver_contract in enumerate(protesting_team.active_drivers):
        driver = driver_contract.driver
        driver_alias = f"d{i}"
        user_data["drivers"][driver_alias] = driver
        buttons.append(
            InlineKeyboardButton(
                driver.psn_id_or_abbreviated_name, callback_data=driver_alias
            )
        )

    chunked_buttons = list(chunked(buttons, 2))
    chunked_buttons.append(
        [
            InlineKeyboardButton(
                "« Sessione",
                callback_data=(
                    str(SESSION) if chat_data.get("late_protest") else "create_protest"
                ),
            )
        ]
    )

    if user_data["protest"].protesting_driver:
        chunked_buttons[-1].append(
            InlineKeyboardButton(
                "Pilota colpevole »", callback_data=str(PROTESTING_DRIVER)
            )
        )

    await send_or_edit_message(
        update=update, message=text, reply_markup=InlineKeyboardMarkup(chunked_buttons)
    )

    return PROTESTING_DRIVER


async def protesting_driver(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the victim and asks for the protested driver."""
    user_data = cast(dict[str, Any], context.user_data)
    category = cast(Category, user_data["category"])

    # Save victim
    if not update.callback_query.data.isdigit():
        user_data["protest"].protesting_driver = user_data["drivers"][
            update.callback_query.data
        ]

    # Ask which driver to protest
    text = "Chi ritieni essere il colpevole?"
    buttons: list[InlineKeyboardButton] = []
    user_data["drivers"] = {}
    for i, driver in enumerate(category.active_drivers()):
        driver = driver.driver
        driver_alias = f"d{i}"
        if driver.current_team() != user_data["protesting_team"]:
            user_data["drivers"][driver_alias] = driver
            buttons.append(
                InlineKeyboardButton(
                    driver.psn_id_or_abbreviated_name, callback_data=driver_alias
                )
            )

    chunked_buttons = list(chunked(buttons, 2))
    chunked_buttons.append(
        [InlineKeyboardButton("« Pilota Vittima", callback_data=str(LINK))]
    )

    if user_data["protest"].protested_driver:
        chunked_buttons[-1].append(
            InlineKeyboardButton(
                "Minuto incidente »", callback_data=str(PROTESTED_DRIVER)
            )
        )

    await update.callback_query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(chunked_buttons)
    )
    return PROTESTED_DRIVER


async def protested_driver(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the protested driver and asks for the minute."""

    user_data = cast(dict[str, Any], context.user_data)
    if not update.callback_query.data.isdigit():
        user_data["protest"].protested_driver = user_data["drivers"][
            update.callback_query.data
        ]
    text = "In che minuto è avvenuto l'incidente?"

    reply_markup = [
        [
            InlineKeyboardButton(
                "« Pilota Colpevole",
                callback_data=str(PROTESTING_DRIVER),
            )
        ]
    ]
    if user_data["protest"].incident_time:
        reply_markup[-1].append(
            InlineKeyboardButton("Avanti »", callback_data=str(MINUTE))
        )

    await update.callback_query.edit_message_text(
        text, reply_markup=InlineKeyboardMarkup(reply_markup)
    )
    return MINUTE


async def save_minute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the minute and asks for the reason."""

    user_data = cast(dict[str, Any], context.user_data)
    if not update.callback_query:
        user_data["protest"].incident_time = update.message.text

    text = (
        "<b>Seleziona una motivazione per la segnalazione:</b>\n"
        "(se nessuna si addice, scrivine una tu)"
    )

    buttons: list[list[InlineKeyboardButton]] = [[]]
    for i, reason in enumerate(config.REASONS):
        i += 1
        reason = reason.format(
            a=user_data["protest"].protesting_driver.abbreviated_name_and_psn_id,
            b=user_data["protest"].protested_driver.abbreviated_name_and_psn_id,
        )
        text += f"\n{i} - <i>{reason}</i>"
        buttons[0].append(InlineKeyboardButton(text=str(i), callback_data=f"r{i}"))
    buttons.append(
        [
            InlineKeyboardButton(
                "« Minuto Incidente ", callback_data=str(PROTESTED_DRIVER)
            )
        ]
    )
    if user_data["protest"].reason:
        buttons[-1].append(
            InlineKeyboardButton("Avanti »", callback_data=str(PROTEST_REASON))
        )

    await send_or_edit_message(
        update=update, message=text, reply_markup=InlineKeyboardMarkup(buttons)
    )

    return PROTEST_REASON


async def save_reason(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the reason and asks if to send the protest or not."""
    user_data = cast(dict[str, Any], context.user_data)
    if update.callback_query:
        if not update.callback_query.data.isdigit():
            user_data["protest"].reason = config.REASONS[
                int(update.callback_query.data.removeprefix("r")) - 1
            ].format(
                a=user_data["protest"].protesting_driver.abbreviated_name_and_psn_id,
                b=user_data["protest"].protested_driver.abbreviated_name_and_psn_id,
            )
    else:
        user_data["protest"].reason = update.message.text
    protest: Protest = user_data["protest"]
    text = (
        f"Dopo aver controllato che i dati siano corretti, premi "
        '"conferma e invia" per inviare la segnalazione.\n'
        "Se cambi idea o noti un errore, hai comunque la possibilità di ritirarla entro 45 min."
        f"\n\n<b>Sessione</b>: <i>{protest.session.name}</i>"
        f"\n<b>Vittima</b>: <i>{protest.protesting_driver.abbreviated_name_and_psn_id}</i>"
        f"\n<b>Colpevole</b>: <i>{protest.protested_driver.abbreviated_name_and_psn_id}</i>"
        f"\n<b>Minuto Incidente</b>: <i>{protest.incident_time}</i>"
        f"\n<b>Motivo Segnalazione</b>: <i>{protest.reason}</i>"
        f"\n{f'<b>Video</b>: <i>{protest.video_link}</i>' if protest.video_link else ''}"
    )

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("Annulla  ❌", callback_data="cancel"),
                InlineKeyboardButton("Conferma e invia  ✅", callback_data="confirm"),
            ],
            [
                InlineKeyboardButton(
                    "« Motivo Segnalazione", callback_data=str(MINUTE)
                ),
            ],
        ]
    )

    await send_or_edit_message(update=update, message=text, reply_markup=reply_markup)
    return SEND


async def send_protest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Sends the protest to the protest channel and saves it to the database."""

    chat_data = cast(dict[str, Any], context.chat_data)
    user_data = cast(dict[str, Any], context.user_data)
    sqla_session: SQLASession = user_data["sqla_session"]
    category = cast(Category, user_data["category"])
    championship_round = cast(Round, user_data["round"])
    protest = cast(Protest, user_data["protest"])

    if (
        championship_round not in category.championship.protesting_rounds()
        and not chat_data.get("late_protest")
    ):
        text = (
            "Troppo tardi! Le segnalazioni vanno inviate prima delle 23:59.\n"
            "Se hai necessità di effettuare questa segnalazione, chiedi prima il "
            "permesso sul gruppo capi, una volta ottenuto, potrai fare la segnalazione "
            "usando il comando /segnalazione_ritardataria. Successivamente un admin inoltrerà "
            "la tua segnalazione sul canale pubblico."
        )
        await update.callback_query.edit_message_text(text=text)
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    if update.callback_query.data == "cancel":
        await update.callback_query.edit_message_text("Segnalazione annullata!")
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    protest.category = category
    protest.round = championship_round
    protest.protested_team = protest.protested_driver.current_team()  # type: ignore
    protest.protesting_team = user_data["protesting_team"]
    protest.number = get_last_protest_number(sqla_session, protest.round.id) + 1
    channel = (
        config.LATE_PROTEST_CHAT
        if chat_data.get("late_protest")
        else config.PROTEST_CHANNEL
    )
    document, filename = ProtestDocument(protest).generate_document()

    message = await context.bot.send_document(
        chat_id=channel, document=document, filename=filename
    )
    protest.channel_message_id = message.message_id

    try:
        sqla_session.add(protest)
        sqla_session.commit()
    except IntegrityError:
        await message.delete()
        await update.callback_query.edit_message_text(
            "Problemi, problemi, problemi! 😓\n"
            f"Si è verificato un errore inaspettato.."
        )
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END

    callback_data = (
        f"withdraw_late_protest_{protest.id}"
        if chat_data.get("late_protest")
        else f"withdraw_late_protest_{protest.id}"
    )
    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "Ritira segnalazione ↩",
                    callback_data=callback_data,
                )
            ]
        ]
    )
    text = (
        "Segnalazione inviata!"
        "\nSe noti un errore, hai 45 minuti di tempo per ritirarla."
        "\nRicorda che creando una nuova segnalazione perderai "
        "la possibilità di ritirare quella precedente."
    )
    await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
    return UNSEND


async def change_state_rep_creation(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Handles "go back" and "go forwards" buttons in the protest_creation conversation.

    This function is called by the dispatcher whenever callback_query.data contains a number
    between 6 and 14.

    It works by calling the callback function associated to the step of the
    conversation (each step is represented by an integer between 6 and 14)
    contained in callback_query.data. After the callback function has finished
    executing it returns the step in callbackquery.data + 1 in order to allow the
    conversation to continue.
    """
    chat_data = cast(dict[str, Any], context.chat_data)
    category_handler = (
        create_late_protest if chat_data.get("late_protest") else create_protest
    )
    session_handler = save_category if chat_data.get("late_protest") else create_protest
    callbacks = {
        CATEGORY: category_handler,
        SESSION: session_handler,
        LINK: save_link,
        PROTESTING_DRIVER: protesting_driver,
        PROTESTED_DRIVER: protested_driver,
        MINUTE: save_minute,
        PROTEST_REASON: save_reason,
        SEND: send_protest,
    }
    state = int(update.callback_query.data)

    await callbacks[state](update, context)

    return state if chat_data.get("late_protest") and state == 7 else state + 1


async def exit_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Clears user_data and ends the conversation"""

    text = "Segnalazione annullata."
    await send_or_edit_message(update, text)

    user_data = cast(dict[str, Any], context.user_data)
    user_data["sqla_session"].close()
    user_data.clear()

    return ConversationHandler.END


async def withdraw_protest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Withdraws the last protest made by the user if made less than 30 minutes ago."""

    user_data = cast(dict[str, Any], context.user_data)
    sqla_session: SQLASession = cast(SQLASession, user_data["sqla_session"])

    if "late" in update.callback_query.data:
        protest_id = update.callback_query.data.removeprefix("withdraw_late_protest_")
    else:
        protest_id = update.callback_query.data.removeprefix("withdraw_protest_")

    protest = get_protest(sqla_session, protest_id)
    if protest:
        if (
            datetime.now(tz=ZoneInfo("Europe/Rome")) - protest.protest_time
        ) < timedelta(minutes=45):
            try:
                await context.bot.delete_message(
                    chat_id=config.PROTEST_CHANNEL,
                    message_id=protest.channel_message_id,
                )

            except BadRequest:
                await context.bot.delete_message(
                    chat_id=config.LATE_PROTEST_CHAT,
                    message_id=protest.channel_message_id,
                )

            text = "Segnalazione ritirata."

            delete_protest(sqla_session, protest_id)
        else:
            text = "Non puoi più ritirare questa segnalazione."
        await update.callback_query.edit_message_text(text)
    cast(dict[str, Any], context.chat_data).clear()
    return ConversationHandler.END


protest_creation = ConversationHandler(
    allow_reentry=True,
    entry_points=[
        CommandHandler("segnala", create_protest, filters=filters.ChatType.PRIVATE),
        CommandHandler(
            "segnalazione_ritardataria",
            create_late_protest,
            filters=filters.ChatType.PRIVATE,
        ),
        CallbackQueryHandler(create_protest, r"^create_protest$"),
        CallbackQueryHandler(create_late_protest, r"^create_late_protest$"),
    ],
    states={
        CATEGORY: [CallbackQueryHandler(save_category, r"^c[0-9]{1,}$")],
        SESSION: [CallbackQueryHandler(save_session, r"^s[0-9]{1,}$")],
        LINK: [
            MessageHandler(
                filters.Regex(
                    r"^((?:https?:)?\/\/)?((?:www|m)\.)?"
                    r"((?:youtube(-nocookie)?\.com|youtu.be))"
                    r"(\/(?:[\w\-]+\?v=|embed\/|v\/)?)([\w\-]+)(\S+)?$"
                ),
                save_link,
            ),
            CallbackQueryHandler(save_link, r"^[6-9]|1[0-2]$"),
        ],
        PROTESTING_DRIVER: [CallbackQueryHandler(protesting_driver, r"^d[0-9]{1,}$")],
        PROTESTED_DRIVER: [CallbackQueryHandler(protested_driver, r"^d[0-9]{1,}$")],
        MINUTE: [
            MessageHandler(
                filters.Regex(r"^.{2,50}$"),
                save_minute,
            )
        ],
        PROTEST_REASON: [
            MessageHandler(filters.Regex(r"^.{20,}$"), save_reason),
            CallbackQueryHandler(
                save_reason,
                r"^r[0-9]{1,}$",
            ),
        ],
        SEND: [CallbackQueryHandler(send_protest, r"^confirm$")],
        UNSEND: [
            CallbackQueryHandler(
                withdraw_protest,
                r"^withdraw_(late_)?protest_"
                r"[0-9a-fA-F]{8}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b-[0-9a-fA-F]{4}\b"
                r"-[0-9a-fA-F]{12}$",
            )
        ],
    },
    fallbacks=[
        CommandHandler("esci", exit_conversation),
        CallbackQueryHandler(exit_conversation, r"^cancel$"),
        CallbackQueryHandler(change_state_rep_creation, r"^[3-9]$|^1[0-1]$"),
    ],
)
