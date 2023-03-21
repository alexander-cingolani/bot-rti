"""
This module contains the callbacks that make up the result recognition conversation.
This conversation allows users (admins) to save race and qualifying results to the database
by sending screenshots captured from the game or live stream.
"""


import os
from collections import defaultdict
from io import BytesIO
from typing import cast

import app.components.config as config
from app.components.results_processing import (
    Result,
    image_to_results,
    results_to_text,
    text_to_results,
)
from more_itertools import chunked
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SQLASession
from sqlalchemy.orm import sessionmaker
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, User
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from models import CarClass, Category, DriverCategory, Round, Session
from queries import get_championship

engine = create_engine(os.environ["DB_URL"])
DBSession = sessionmaker(bind=engine, autoflush=False)

# Defines the states of this conversation.
(
    SAVE_CATEGORY,
    SAVE_SESSION,
    SAVE_RESULTS,
    SAVE_CHANGES,
    SAVE_FASTEST_LAP,
    PERSIST_RESULTS,
) = range(6)


async def entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Checks if the user is authorized to use this command (admins only), if so asks
    the admin for the category he wants to add results to."""

    user_data = cast(dict, context.user_data)
    user_data.clear()

    # Checks that the user is part of the admin team, if not, tells the
    # user he can't use this command and returns.
    if cast(User, update.effective_user).id not in config.ADMINS:
        await update.message.reply_text(
            "Non sei autorizzato ad usare in questa funzione,"
            f" se credi di doverlo essere, contatta {config.OWNER}"
        )
        return ConversationHandler.END

    sqla_session: SQLASession = DBSession()
    championship = get_championship(sqla_session)

    # Checks if it's possible to save results.
    if not championship.is_active():
        await update.message.reply_text(
            "Il campionato è finito! Non ci sono più risultati da aggiungere."
        )
        return ConversationHandler.END

    user_data["sqla_session"] = sqla_session
    user_data["championship"] = championship
    user_data["results"] = {}

    # Creates keyboard with the available categories in the championship.
    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(category.name, callback_data=f"C{i}")
                for i, category in enumerate(championship.categories)
                if category.first_non_completed_round()
            ],
        ]
    )
    text = "Seleziona la categoria dove vuoi inserire o controllare i risultati:"

    await update.message.reply_text(text=text, reply_markup=reply_markup)

    return SAVE_CATEGORY


async def __ask_session(update: Update, round: Round, results: dict) -> None:
    session_buttons = []
    completed_sessions = 0
    for session in round.sessions:
        session_buttons.append(
            InlineKeyboardButton(
                text=session.name, callback_data=f"S{session.session_id}"
            )
        )
        if not results.get(session):
            results[session] = {
                "results": [],
                "fastest_lap_drivers": {
                    car_class.car_class: None
                    for car_class in round.category.car_classes
                },
            }
        else:
            completed_sessions += 1

    chunked_session_buttons = list(chunked(session_buttons, 3))
    text = "Scegli la sessione dove vuoi inserire o controllare i risultati."

    if completed_sessions == len(round.sessions):
        chunked_session_buttons.append(
            [InlineKeyboardButton("Salva Risultati", callback_data="persist-results")]
        )
        text = "Puoi controllare i risultati o salvarli."

    reply_markup = InlineKeyboardMarkup(chunked_session_buttons)

    await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)

    return


async def save_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user in which session he wants to enter the results.
    Once the user has entered the results for all the session he is brought given
    the option to save the results and check that what he has entered is correct."""

    user_data = cast(dict, context.user_data)
    cast(dict, user_data["results"])

    # Saves the category selected by the user.
    category = cast(
        Category,
        user_data["championship"].categories[
            int(update.callback_query.data.removeprefix("C"))
        ],
    )
    user_data["category"] = category

    # Can't be None, checked in previous callback.
    current_round = cast(Round, category.first_non_completed_round())
    user_data["round"] = current_round

    await __ask_session(update, current_round, user_data["results"])

    return SAVE_SESSION


async def save_session(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the session and asks the user for an image containing the qualifying or race results."""

    user_data = cast(dict, context.user_data)
    round = cast(Round, user_data["round"])
    session_id = int(update.callback_query.data.removeprefix("S"))
    # Saves the session selected by the user.
    for session in round.sessions:
        if session.session_id == session_id:
            current_session = session
            break

    user_data["current_session"] = current_session

    # Asks the user for the text/screenshot of the results from the selected session.
    text = f"Inviami il testo o lo screenshot contenente i risultati di <b>{current_session.name}</b>."
    await update.callback_query.edit_message_text(text)
    return SAVE_RESULTS


async def recognise_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the results (text or image) sent by the user, then asks him if what was saved
    is correct."""

    user_data = cast(dict, context.user_data)
    category = cast(Category, user_data["category"])
    expected_drivers = category.active_drivers()

    # Saves image or text depending on what the user decided to send.
    if getattr(update.message, "document"):
        file = await update.message.document.get_file()
        image = BytesIO(await file.download_as_bytearray())

        results = image_to_results(image, expected_drivers)
    elif update.message.text:
        text = update.message.text
        results = text_to_results(text, expected_drivers)
    user_data["results"][user_data["current_session"]]["results"] = results

    # Sends the user the recognised results.
    results_text = results_to_text(results)
    await update.message.reply_text(results_text)

    # Asks the user if the recognized results are correct.
    if "NON_RICONOSCIUTO" in results_text or "/" in results_text:
        check_results_text = (
            "Non sono riuscito a leggere tutto, correggi ciò che non va perfavore."
        )
        await update.message.reply_text(check_results_text)
    else:
        check_results_text = (
            "Mi pare di aver letto tutto correttamente, "
            "verifica rapidamente che i distacchi siano giusti perfavore."
        )
        reply_markup = InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="✅", callback_data="results-ok")]]
        )
        await update.message.reply_text(check_results_text, reply_markup=reply_markup)
    return SAVE_CHANGES


async def save_changes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Applies the changes (if any) made to the results by the user, then asks the
    user for the fastest driver."""

    user_data = cast(dict, context.user_data)
    category = cast(Category, user_data["category"])
    session = cast(Session, user_data["current_session"])
    results = cast(list[Result], user_data["results"][session]["results"])
    expected_drivers = category.active_drivers()

    # Saves any corrections made to the results.
    if update.message:
        results = text_to_results(update.message.text, expected_drivers)
        user_data["results"][session]["results"] = results

    # The fastest lap driver is not needed for qualifying sessions.
    if session.is_quali:
        await __ask_session(update, session.round, user_data["results"])
        return SAVE_SESSION

    # Asks the fastest lap driver for each car class in the selected category.
    drivers_by_carclass = defaultdict(list)
    for result in results:
        if result.seconds:
            drivers_by_carclass[result.driver.car_class].append(result.driver)

    await __ask_fastest_lap_driver(
        update, list(drivers_by_carclass[category.car_classes[0].car_class])
    )
    return SAVE_FASTEST_LAP


async def __ask_fastest_lap_driver(
    update: Update, drivers: list[DriverCategory]
) -> None:
    """This function updates the current message to ask which driver scored the fastest lap of the session."""
    text = f"Inserisci il pilota che ha segnato il giro più veloce in {drivers[0].car_class.name}"

    driver_buttons = []
    for driver in drivers:
        driver_buttons.append(
            InlineKeyboardButton(
                text=driver.driver.psn_id, callback_data=f"FL{driver.driver_id}"
            )
        )
    chunked_driver_buttons = list(chunked(driver_buttons, 2))

    reply_markup = InlineKeyboardMarkup(chunked_driver_buttons)

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    return


async def save_fastest_driver(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int | None:
    """Saves one of the (or the only in case of a single-class category) fastest drivers."""

    user_data = cast(dict, context.user_data)
    category = cast(Category, user_data["category"])
    session = cast(Session, user_data["current_session"])
    expected_drivers = category.active_drivers()
    fastest_lap_drivers = cast(
        dict[CarClass, DriverCategory],
        user_data["results"][session]["fastest_lap_drivers"],
    )

    # Saves the given driver.
    driver_id = int(update.callback_query.data.removeprefix("FL"))
    for driver_category in expected_drivers:
        if driver_id == driver_category.driver_id:
            fastest_lap_drivers[driver_category.car_class] = driver_category
            break

    drivers_by_carclass = defaultdict(list)
    for result in user_data["results"][session]["results"]:
        if result.seconds:
            drivers_by_carclass[result.driver.car_class].append(result.driver)

    # Checks if all car classes have a fastest lap driver, if not,
    # calls __ask_fastest_lap_driver on the first class without one.
    for car_class, driver_category in fastest_lap_drivers.items():
        if not driver_category:
            breakpoint()
            await __ask_fastest_lap_driver(update, list(drivers_by_carclass[car_class]))
            return None
    else:
        await __ask_session(update, user_data["round"], user_data["results"])
        return SAVE_CATEGORY


async def persist_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the results to the database."""

    return SAVE_CATEGORY


save_results = ConversationHandler(
    entry_points=[
        CommandHandler(
            "salva_risultati",
            entry_point,
            filters=filters.ChatType.PRIVATE,
        )
    ],
    states={
        SAVE_CATEGORY: [CallbackQueryHandler(save_category, r"^C[0-9]{1,}$")],
        SAVE_SESSION: [
            CallbackQueryHandler(save_session, r"S[0-9]{1,}"),
        ],
        SAVE_RESULTS: [
            CallbackQueryHandler(recognise_results, r"^confirm_quali_results$"),
            MessageHandler(filters.ATTACHMENT, recognise_results),
            MessageHandler(filters.Regex(r"^[^/][\s\S]{70,}$"), recognise_results),
        ],
        SAVE_CHANGES: [
            CallbackQueryHandler(save_changes, r"^results-ok$"),
            MessageHandler(filters.Regex(r"[^/]{60,}"), save_changes),
        ],
        SAVE_FASTEST_LAP: [CallbackQueryHandler(save_fastest_driver, r"^FL[0-9]{1,}$")],
        PERSIST_RESULTS: [CallbackQueryHandler(persist_results, "persist-results")],
    },
    fallbacks=[
        CommandHandler(
            "salva_risultati",
            entry_point,
        ),
        # CallbackQueryHandler(change_conversation_state, r"^2[7-9]$|^3[0-8]$"),
    ],
)
