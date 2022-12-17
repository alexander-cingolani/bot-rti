"""
This module contains the callbacks that make up the result recognition conversation.
This conversation allows users (admins) to save race and qualifying results to the database
by sending screenshots captured from the game or live stream.
"""
from collections import defaultdict
import os
from decimal import Decimal
from difflib import get_close_matches
from typing import Any, Optional, cast

from app.components import config
from app.components.models import Category, QualifyingResult, RaceResult, Round
from app.components.ocr import Result, recognize_results, string_to_seconds
from app.components.queries import get_championship, get_driver
from app.components.utils import send_or_edit_message, separate_car_classes
from more_itertools import chunked
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SQLASession
from telegram import Chat, InlineKeyboardButton, InlineKeyboardMarkup, Update, User
from telegram.constants import ChatAction
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

(
    ASK_QUALI_RESULTS,
    DOWNLOAD_QUALI_RESULTS,
    SAVE_QUALI_RESULTS,
    DOWNLOAD_RACE_1_RESULTS,
    ASK_FASTEST_LAP_1,
    ASK_2ND_FASTEST_LAP_1,
    SAVE_RACE_1_RESULTS,
    DOWNLOAD_RACE_2_RESULTS,
    ASK_FASTEST_LAP_2,
    SAVE_RACE_2_RESULTS,
    PERSIST_RESULTS,
) = range(27, 38)


WRONG_FILE_FORMAT_MESSAGE = (
    "Il file dei risultati deve essere inviato in formato 16:9 senza compressione."
    "\nè consigliabile fare lo screenshot dei risultati da PC, in quanto "
    "il formato degli screenshot fatti da smartphone risulta dilatato rispetto al "
    "formato 16:9, rendendo impossibile la corretta identificazione dei giocatori "
    "e dei tempi di gara."
)


engine = create_engine(os.environ["DB_URL"])

DBSession = sessionmaker(bind=engine, autoflush=False)


def text_to_results(text: str, category: Category) -> list[Result]:
    """This is a helper function for ask_fastest_lap callbacks.
    It receives the block of text sent by the user to correct race/qualifying results
    and transforms it into a list of Result objects. Driver psn id's don't have to be
    spelt perfectly, this function automatically selects the closest driver to the one
    given in the message.

    Args:
        text (str): Text to convert into results.
        category (Category): Category the results are from.
        drivers

    Returns:
        list[Result]: Results obtained
    """
    recognized_text = list(chunked(text.split(), 2))
    driver_map = {
        driver.driver.psn_id: (driver.car_class, driver.driver)
        for driver in category.active_drivers()
    }
    results = []
    for given_driver_name, gap in recognized_text:

        driver_name = given_driver_name

        if given_driver_name not in driver_map:
            driver_name = get_close_matches(
                given_driver_name, driver_map.keys(), cutoff=0.2
            )[0]

        if driver_name:
            driver_obj = driver_map[given_driver_name][1]
            seconds = string_to_seconds(gap)
            result = Result(driver_obj.psn_id, seconds)
            result.car_class = driver_map.pop(driver_obj.psn_id)[0]
            results.append(result)

    # Add unrecognized drivers to the results list
    for given_driver_name in driver_map:
        driver_obj = driver_map[given_driver_name][1]
        result = Result(driver_obj.psn_id, 0)

        result.car_class = driver_map[driver_obj.psn_id][0]
        results.append(result)

    return results


async def results_input_entry_point(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Asks the admin for the category he wants to add results to."""
    user_data = cast(dict, context.user_data)
    user_data.clear()
    if cast(User, update.effective_user).id not in config.ADMINS:
        await update.message.reply_text(
            "Non sei autorizzato ad usare in questa funzione,"
            f" se credi di doverlo essere, contatta {config.OWNER}"
        )

    sqla_session: SQLASession = DBSession()
    championship = get_championship(sqla_session)

    if not championship:
        sqla_session.close()
        return ConversationHandler.END

    user_data["sqla_session"] = sqla_session
    user_data["championship"] = championship
    user_data["race_results"] = defaultdict(dict)

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(category.name, callback_data=f"c{i}")
                for i, category in enumerate(championship.categories)
                if category.first_non_completed_round()
            ],
            [InlineKeyboardButton("Annulla", callback_data="exit")],
        ]
    )
    text = "Seleziona la categoria dove vuoi inserire i risultati:"
    if not reply_markup:
        await update.message.reply_text(
            "Il campionato è finito! Non ci sono più risultati da aggiungere."
        )
        sqla_session.close()
        user_data.clear()
        return ConversationHandler.END
    await update.message.reply_text(text=text, reply_markup=reply_markup)
    return ASK_QUALI_RESULTS


async def ask_qualifying_results(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Saves the fastest lap and asks the user for the qualifying results screenshot."""

    user_data = cast(dict, context.user_data)

    if not getattr(update.callback_query, "data", "").isnumeric():

        user_data["category"] = user_data["championship"].categories[
            int(update.callback_query.data[1])
        ]

    category: Category = user_data["category"]

    current_round = category.first_non_completed_round()
    if not current_round:
        user_data.clear()
        user_data["sqla_session"].close()
        return ConversationHandler.END
    user_data["round"] = current_round
    text = (
        f"<b>{category.name}</b> - {current_round.number}ᵃ tappa {current_round.circuit}."
        "\nInviami l'immagine dei risultati della qualifica:"
    )
    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Salta", callback_data="skip_quali")]]
    )
    await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
    return DOWNLOAD_QUALI_RESULTS


def seconds_to_str(seconds: Decimal) -> str:
    """Converts seconds to a user-friendly string format.

    Args:
        seconds (Decimal): seconds to covert into string.
            Must contain at least one decimal number.

    Returns:
        str: User-friendly string.
    """

    minutes, seconds = divmod(seconds, 60)
    seconds, milliseconds = divmod(seconds, 1)
    milliseconds = int(milliseconds * 1000)
    return (
        f"{str(minutes) + ':' if minutes else ''}{int(seconds):02d}.{milliseconds:0<3}"
    )


async def download_quali_results(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Performs OCR on the received image and asks if the results are correct."""
    user_data = cast(dict, context.user_data)
    category: Category = user_data["category"]
    sqla_session: SQLASession = user_data["sqla_session"]

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "« Usa un'altra foto", callback_data=str(ASK_QUALI_RESULTS)
                ),
                InlineKeyboardButton(
                    "Screenshot gara »", callback_data="confirm_quali_results"
                ),
            ]
        ]
    )

    if getattr(update.callback_query, "data", "") == "skip_quali":
        user_data["skip_quali"] = True
        await update.callback_query.edit_message_text(
            "Ok, inviami i risultati di gara 1."
        )
        return DOWNLOAD_RACE_1_RESULTS
    if getattr(update.callback_query, "data", "").isnumeric():
        await update.callback_query.edit_message_text(
            "Invia i risultati corretti:", reply_markup=reply_markup
        )
        return SAVE_QUALI_RESULTS
    await cast(Chat, update.effective_chat).send_action(ChatAction.TYPING)

    # Save the photo containing the results.
    if update.message:
        if update.message.text:
            results = text_to_results(text=update.message.text, category=category)
            user_data["quali_results"] = results
            success = True
        else:

            try:
                file = await update.message.document.get_file()
            except AttributeError:
                await update.message.reply_text(WRONG_FILE_FORMAT_MESSAGE)
                sqla_session.close()
                user_data.clear()
                return ConversationHandler.END

            await file.download_to_drive("results.jpg")

            drivers = [driver.driver for driver in category.active_drivers()]
            success, user_data["quali_results"] = recognize_results(
                "results.jpg", drivers
            )

            os.remove("results.jpg")

    results = user_data["quali_results"]
    results_message_text = ""
    for result in results:
        if result.seconds:
            gap = seconds_to_str(result.seconds)
        else:
            gap = "ASSENTE"
        results_message_text += f"\n{result.driver} {gap}"
    await update.message.reply_text(results_message_text)

    if success:
        text_2 = (
            "Mi sembra di aver letto tutto correttamente, controlla che i tempi siano giusti."
            " Puoi correggere gli errori copiando e modificando il messaggio sopra."
        )
        await update.message.reply_text(text=text_2, reply_markup=reply_markup)

    else:
        results_message_text = (
            "Non sono riuscito a riconoscere tutti i nomi dei piloti e"
            "potrebbero esserci degli errori nei tempi, puoi correggerli?"
        )
        await update.message.reply_text(text=results_message_text)

    return SAVE_QUALI_RESULTS


async def save_quali_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the qualifying results"""

    user_data = cast(dict, context.user_data)
    category: Category = user_data["category"]
    if not update.callback_query:
        text = update.message.text
        results = text_to_results(text, category)
        user_data["quali_results"] = results
    buttons = [
        InlineKeyboardButton(
            "« Modifica risultati qualifica", callback_data=str(DOWNLOAD_QUALI_RESULTS)
        )
    ]

    if user_data["round"].has_sprint_race:
        text = "Inviami lo screenshot dei risultati di gara 1."
    else:
        text = "Inviami lo screenshot dei risultati di gara."

    await send_or_edit_message(update, text, InlineKeyboardMarkup([buttons]))
    return DOWNLOAD_RACE_1_RESULTS


async def download_race_1_results(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Downloads the screenshot sent by the user and passes it to the recognize_results
    function to analyze its contents. If results weren't recognized correctly,
    forces the user to correct them manually. Otherwise the user is asked to confirm
    that the recognized results are correct."""
    user_data = cast(dict, context.user_data)
    category: Category = user_data["category"]
    championship_round: Round = user_data["round"]
    sqla_session: SQLASession = user_data["sqla_session"]
    if update.callback_query:
        if championship_round.has_sprint_race:
            gara = " 1"
        else:
            gara = ""
        await update.callback_query.edit_message_text(
            f"Inviami i risultati di gara{gara} corretti:"
        )
        return SAVE_RACE_1_RESULTS

    drivers = [driver.driver for driver in category.active_drivers()]
    if update.message:
        if update.message.text:
            results = text_to_results(text=update.message.text, category=category)
        else:
            await cast(Chat, update.effective_chat).send_action(ChatAction.TYPING)
            try:
                file = await update.message.document.get_file()
            except AttributeError:
                await update.message.reply_text(WRONG_FILE_FORMAT_MESSAGE)
                sqla_session.close()
                user_data.clear()
                return ConversationHandler.END

            screenshot = await file.download_to_drive("results_1.jpg")

            _, results = recognize_results(screenshot, drivers)

    user_data["race_results"][championship_round.long_race]["results"] = results
    text = ""
    # Sends recognized results to the user
    for result in results:
        if result.seconds is None:
            racetime = "ASSENTE"
        elif not result.seconds:
            racetime = "/"
        else:
            racetime = seconds_to_str(result.seconds)

        text += f"\n{result.driver} {racetime}"

    await update.message.reply_text(text)

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "« Usa un'altra immagine", callback_data=str(SAVE_QUALI_RESULTS)
                ),
                InlineKeyboardButton(
                    "Giro veloce »", callback_data="race_1_results_ok"
                ),
            ]
        ]
    )

    text = (
        "Controlla che i risultati siano corretti."
        " Per correggere copia il messaggio sopra."
    )
    await update.message.reply_text(text, reply_markup=reply_markup)
    return ASK_FASTEST_LAP_1


async def ask_fastest_lap_1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks which driver scored the fastest lap in the first class of the first race."""
    user_data = cast(dict, context.user_data)
    category: Category = user_data["category"]
    championship_round: Round = user_data["round"]

    buttons: list[InlineKeyboardButton] = []
    car_class = category.car_classes[0].car_class
    for i, driver in enumerate(category.active_drivers()):
        if driver.car_class_id == car_class.car_class_id:
            buttons.append(
                InlineKeyboardButton(driver.driver.psn_id, callback_data=f"d{i}")
            )
    chunked_buttons: list[list[InlineKeyboardButton]] = list(chunked(buttons, 2))

    if not category.multi_class:
        text = "Chi ha segnato il giro più veloce?"
        if championship_round.has_sprint_race:
            button_text = "Salva risultati »"
            callback_data = "save_race_1_results"
        else:
            button_text = "Risultati gara 2 »"
            callback_data = "save_race_1_results"
    else:
        text = f"Chi ha segnato il giro più veloce in {car_class.name}?"
        if championship_round.has_sprint_race:
            button_text = f"G.V. classe {category.car_classes[1].car_class.name} »"
            callback_data = "ask_2nd_fastest_lap_1"
        else:
            button_text = "Risultati gara 2 »"
            callback_data = "save_race_1_results"

    chunked_buttons.append(
        [
            InlineKeyboardButton(
                "« Modifica risultati gara 1",
                callback_data=str(DOWNLOAD_RACE_1_RESULTS),
            ),
            InlineKeyboardButton(text=button_text, callback_data=callback_data),
        ]
    )

    reply_markup = InlineKeyboardMarkup(chunked_buttons)

    # Saves corrected results if a message was sent.
    if update.message:
        user_data["race_results"][championship_round.long_race][
            "results"
        ] = text_to_results(update.message.text, user_data["category"])

        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    if category.multi_class:
        return ASK_2ND_FASTEST_LAP_1

    return SAVE_RACE_1_RESULTS


async def ask_2nd_fastest_lap_1(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Asks which driver scored the fastest lap in the second class of the first race."""

    user_data = cast(dict, context.user_data)
    category: Category = user_data["category"]
    championship_round: Round = user_data["round"]

    # Saves driver who scored the fastest lap if callback data contains a driver.
    if update.callback_query.data != "save_race_1_results":
        if not user_data["race_results"][championship_round.long_race].get(
            "fastest_lap_drivers"
        ):
            user_data["race_results"][championship_round.long_race][
                "fastest_lap_drivers"
            ] = [
                category.active_drivers()[
                    int(update.callback_query.data[1])
                ].driver.psn_id
            ]
        else:
            user_data["race_results"][championship_round.long_race][
                "fastest_lap_drivers"
            ][0] = category.active_drivers()[
                int(update.callback_query.data[1])
            ].driver.psn_id

    buttons = []
    car_class = category.car_classes[1].car_class
    for i, driver in enumerate(category.active_drivers()):
        if driver.car_class_id == car_class.car_class_id:
            buttons.append(
                InlineKeyboardButton(driver.driver.psn_id, callback_data=f"d{i}")
            )
    chunked_buttons: list[list[InlineKeyboardButton]] = list(chunked(buttons, 2))

    if championship_round.has_sprint_race:
        button_text = "Salva risultati »"
        callback_data = "save_race_1_results"
    else:
        button_text = "Risultati gara 2 »"
        callback_data = "save_race_1_results"

    chunked_buttons.append(
        [
            InlineKeyboardButton(
                f"« Modifica G.V. classe {category.car_classes[0].car_class.name}",
                callback_data=str(ASK_FASTEST_LAP_1),
            ),
            InlineKeyboardButton(text=button_text, callback_data=callback_data),
        ]
    )

    reply_markup = InlineKeyboardMarkup(chunked_buttons)
    text = f"Chi ha segnato il giro più veloce in {car_class.name}?"

    if update.message:
        user_data["race_results"][championship_round.long_race][
            "results"
        ] = text_to_results(update.message.text, user_data["category"])
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    return SAVE_RACE_1_RESULTS


async def save_race_1_results(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Saves the results (fastest lap, driver order of arrival) into user_data and
    if no other races are expected for the chosen category, asks the user whether to
    save the results to the database or not. If more results are expected, prompts the user
    to send them."""
    user_data = cast(dict, context.user_data)
    category: Category = user_data["category"]
    championship_round: Round = user_data["round"]

    # Saves driver who scored the fastest lap if callback data contains a driver.
    if update.callback_query.data != "save_race_1_results":
        if user_data["race_results"][championship_round.long_race].get(
            "fastest_lap_drivers"
        ):
            user_data["race_results"][championship_round.long_race][
                "fastest_lap_drivers"
            ].append(
                category.active_drivers()[
                    int(update.callback_query.data[1])
                ].driver.psn_id
            )
        else:
            user_data["race_results"][championship_round.long_race][
                "fastest_lap_drivers"
            ] = [
                category.active_drivers()[
                    int(update.callback_query.data[1])
                ].driver.psn_id
            ]

    if championship_round.has_sprint_race:
        text = "Invia i risultati di gara 2."
        reply_markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "« Giro veloce gara 1", callback_data=str(ASK_FASTEST_LAP_1)
                    )
                ]
            ]
        )

        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

        return DOWNLOAD_RACE_2_RESULTS

    text = "Dopo aver controllato che i risultati siano corretti, premi conferma per salvarli."
    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "« Giro veloce gara 1", callback_data=str(ASK_FASTEST_LAP_1)
                ),
                InlineKeyboardButton(
                    "Conferma e salva ✅", callback_data="persist_results"
                ),
            ]
        ]
    )

    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    return PERSIST_RESULTS


async def download_race_2_results(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Downloads the screenshot sent by the user and passes it to recognize_results
    function to analyze it's contents. If results weren't recognized correctly,
    forces the user to correct them manually. Otherwise the user is asked to confirm
    that the recognized results are correct."""

    if update.callback_query:
        await update.callback_query.edit_message_text(
            "Inviami i risultati di gara 2 corretti:"
        )
        return SAVE_RACE_2_RESULTS

    user_data = cast(dict, context.user_data)
    category: Category = user_data["category"]
    championship_round: Round = user_data["round"]

    drivers = [driver.driver for driver in category.active_drivers()]
    if update.message:
        if update.message.text:
            results = text_to_results(update.message.text, category=category)
        else:

            await cast(Chat, update.effective_chat).send_action(ChatAction.TYPING)

            try:
                file = await update.message.document.get_file()
            except AttributeError:
                await update.message.reply_text(WRONG_FILE_FORMAT_MESSAGE)
                user_data["sqla_session"].close()
                user_data.clear()
                return ConversationHandler.END

            screenshot = await file.download_to_drive("results_1.jpg")

            _, results = recognize_results(screenshot, drivers)

    user_data["race_results"][championship_round.sprint_race]["results"] = results
    text = ""

    for result in results:
        if result.seconds is None:
            racetime = "ASSENTE"
        elif not result.seconds:
            racetime = "/"
        else:
            racetime = seconds_to_str(result.seconds)
        text += f"\n{result.driver} {racetime}"
    await update.message.reply_text(text)

    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "« Usa un'altra immagine", callback_data=str(SAVE_RACE_1_RESULTS)
                ),
                InlineKeyboardButton(
                    "Giro veloce »", callback_data="race_2_results_ok"
                ),
            ]
        ]
    )

    text = (
        "Controlla che i risultati siano corretti. "
        "Per correggere copia il messaggio sopra."
    )
    await update.message.reply_text(text, reply_markup=reply_markup)

    return ASK_FASTEST_LAP_2


async def ask_fastest_lap_2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Asks the user which driver scored the fastest lap in the second race."""
    user_data = cast(dict, context.user_data)
    category: Category = user_data["category"]
    championship_round: Round = user_data["round"]

    buttons = []
    for i, driver in enumerate(category.active_drivers()):
        buttons.append(
            InlineKeyboardButton(driver.driver.psn_id, callback_data=f"d{i}")
        )
    chunked_buttons: list[list[InlineKeyboardButton]] = list(chunked(buttons, 2))

    chunked_buttons.append(
        [
            InlineKeyboardButton(
                "« Modifica risultati gara 2",
                callback_data=str(DOWNLOAD_RACE_2_RESULTS),
            ),
            InlineKeyboardButton(
                text="Salva risultati »", callback_data="save_race_2_results"
            ),
        ]
    )

    reply_markup = InlineKeyboardMarkup(chunked_buttons)
    text = "Chi ha segnato il giro più veloce?"

    # Saves corrected results if a message was sent.
    if update.message:
        user_data["race_results"][championship_round.sprint_race][0] = text_to_results(
            update.message.text, user_data["category"]
        )
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    return SAVE_RACE_2_RESULTS


async def save_race_2_results(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Saves the results (fastest lap, driver order of arrival) into user_data and
    asks the user whether to save the results to the database or not."""

    user_data = cast(dict, context.user_data)
    category: Category = user_data["category"]
    championship_round: Round = user_data["round"]
    # Saves driver who scored the fastest lap.
    if update.callback_query.data != "save_race_2_results":
        user_data["race_results"][championship_round.sprint_race][
            "fastest_lap_driver"
        ] = [
            category.active_drivers()[int(update.callback_query.data[1])].driver.psn_id
        ]

    # Ask if to persist results or edit fastest driver
    text = "Dopo aver controllato che i risultati siano corretti, premi conferma per salvarli."
    reply_markup = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "« Giro veloce gara 2", callback_data=str(ASK_FASTEST_LAP_2)
                ),
                InlineKeyboardButton(
                    "Conferma e salva ✅", callback_data="persist_results"
                ),
            ]
        ]
    )

    await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    return PERSIST_RESULTS


def create_quali_result_objs(
    sqla_session: SQLASession,
    quali_results: list[QualifyingResult],
    category: Category,
    championship_round: Round,
):
    result_objs = []
    individual_class_results = separate_car_classes(category, quali_results)

    for class_results in individual_class_results.values():
        class_pole_time = class_results[0].seconds
        for pos, quali_res in enumerate(class_results, start=1):
            if quali_res.seconds:
                gap_to_first = quali_res.seconds - class_pole_time

            participated = bool(quali_res.position)
            result_objs.append(
                QualifyingResult(
                    position=quali_res.position,
                    gap_to_first=gap_to_first,
                    laptime=quali_res.seconds,
                    driver=get_driver(sqla_session, psn_id=quali_res.driver),
                    round=championship_round,
                    participated=bool(quali_res.position),
                    relative_position=pos if participated else None,
                    session=championship_round.qualifying_session,
                    category=category,
                )
            )
    return result_objs


def create_race_result_objs(
    sqla_session: SQLASession, category, championship_round: Round, race_results: dict
):
    result_objs = []
    for session, stuff in race_results.items():
        results, fastest_laps = stuff.values()
        separated_results = separate_car_classes(category, results)

        for class_results in separated_results.values():
            winners_racetime = class_results[0].seconds
            for pos, result in enumerate(class_results, start=1):

                bonus_points = 0
                if result.driver in fastest_laps:
                    bonus_points += 1
                if result.seconds:
                    gap_to_first = result.seconds - winners_racetime
                else:
                    gap_to_first = None

                result = RaceResult(
                    finishing_position=result.position,
                    fastest_lap_points=bonus_points,
                    driver=get_driver(sqla_session, psn_id=result.driver),
                    session=session,
                    round=championship_round,
                    gap_to_first=gap_to_first,
                    total_racetime=result.seconds,
                    relative_position=pos if pos else None,
                    participated=bool(pos),
                    category=category,
                )
                result_objs.append(result)
    return result_objs


async def persist_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves the results to the database. If successful, send the user a confirmation
    message."""
    user_data = cast(dict, context.user_data)
    category: Category = user_data["category"]
    championship_round: Round = user_data["round"]
    quali_results: Optional[list[QualifyingResult]] = user_data.get("quali_results")
    race_results: dict[Any, Any] = user_data["race_results"]
    sqla_session: SQLASession = user_data["sqla_session"]
    result_objs = []  # All QualifyingResults and RaceResults will be added to this.

    if quali_results:
        result_objs.extend(
            create_quali_result_objs(
                sqla_session=sqla_session,
                quali_results=quali_results,
                category=category,
                championship_round=championship_round,
            )
        )

    result_objs.extend(
        create_race_result_objs(
            sqla_session=sqla_session,
            category=category,
            championship_round=championship_round,
            race_results=race_results,
        )
    )

    buttons = []
    for i, category in enumerate(user_data["championship"].categories):
        if category.category_id != category.category_id:
            buttons.append(
                InlineKeyboardButton(f"{category.name}", callback_data=f"c{i}")
            )

    sqla_session.add_all(result_objs)
    championship_round.completed = True
    sqla_session.commit()

    reply_markup = InlineKeyboardMarkup([buttons])
    await update.callback_query.edit_message_text(
        "Risultati salvati con successo.", reply_markup=reply_markup
    )

    championship = user_data["championship"]
    user_data.clear()
    user_data["championship"] = championship

    return ASK_QUALI_RESULTS


async def change_conversation_state(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """This callback is called when a number is returned in the inline keyboard
    callback data. It allows for the implementation of go-forwards and go-backwards
    buttons."""
    callbacks = {
        ASK_QUALI_RESULTS: ask_qualifying_results,
        DOWNLOAD_QUALI_RESULTS: download_quali_results,
        SAVE_QUALI_RESULTS: save_quali_results,
        DOWNLOAD_RACE_1_RESULTS: download_race_1_results,
        ASK_FASTEST_LAP_1: ask_fastest_lap_1,
        SAVE_RACE_1_RESULTS: save_race_1_results,
        DOWNLOAD_RACE_2_RESULTS: download_race_2_results,
        ASK_FASTEST_LAP_2: ask_fastest_lap_2,
        SAVE_RACE_2_RESULTS: save_race_2_results,
    }
    state = int(update.callback_query.data)
    await callbacks[state](update, context)
    return state + 1


save_results_conv = ConversationHandler(
    entry_points=[
        CommandHandler(
            "salva_risultati",
            results_input_entry_point,
            filters=filters.ChatType.PRIVATE,
        )
    ],
    states={
        ASK_QUALI_RESULTS: [
            CallbackQueryHandler(ask_qualifying_results, r"^c[0-9]{1,}$")
        ],
        DOWNLOAD_QUALI_RESULTS: [
            MessageHandler(filters.ATTACHMENT, download_quali_results),
            CallbackQueryHandler(download_quali_results, r"^skip_quali$"),
            MessageHandler(filters.Regex(r"[^/]{60,}"), download_quali_results),
        ],
        SAVE_QUALI_RESULTS: [
            CallbackQueryHandler(save_quali_results, r"^confirm_quali_results$"),
            MessageHandler(filters.Regex(r"^[^/][\s\S]{70,}$"), save_quali_results),
        ],
        DOWNLOAD_RACE_1_RESULTS: [
            CallbackQueryHandler(download_race_1_results, r"^download_race_1_results$"),
            MessageHandler(filters.ATTACHMENT, download_race_1_results),
            MessageHandler(filters.Regex(r"[^/]{60,}"), download_race_1_results),
        ],
        ASK_FASTEST_LAP_1: [
            CallbackQueryHandler(ask_fastest_lap_1, r"^race_1_results_ok$"),
            MessageHandler(filters.Regex(r"^[^/][\s\S]{70,}$"), ask_fastest_lap_1),
        ],
        ASK_2ND_FASTEST_LAP_1: [
            CallbackQueryHandler(
                ask_2nd_fastest_lap_1,
                r"^d[0-9]{1,}$|^save_race_1_results$",
            )
        ],
        SAVE_RACE_1_RESULTS: [
            CallbackQueryHandler(
                save_race_1_results,
                r"^d[0-9]{1,}$|^save_race_1_results$",
            )
        ],
        DOWNLOAD_RACE_2_RESULTS: [
            CallbackQueryHandler(download_race_2_results, "^download_race_2_results$"),
            MessageHandler(filters.ATTACHMENT, download_race_2_results),
            MessageHandler(filters.Regex(r"[^/]{60,}"), download_race_2_results),
        ],
        ASK_FASTEST_LAP_2: [
            CallbackQueryHandler(ask_fastest_lap_2, "^race_2_results_ok$"),
            MessageHandler(filters.Regex(r"^[^/][\s\S]{70,}$"), ask_fastest_lap_2),
        ],
        SAVE_RACE_2_RESULTS: [
            CallbackQueryHandler(
                save_race_2_results,
                (r"^d[0-9]{1,}$|^save_race_2_results$"),
            )
        ],
        PERSIST_RESULTS: [CallbackQueryHandler(persist_results, "persist_results")],
    },
    fallbacks=[
        CommandHandler(
            "salva_risultati",
            results_input_entry_point,
        ),
        CallbackQueryHandler(change_conversation_state, r"^2[7-9]$|^3[0-8]$"),
    ],
)
