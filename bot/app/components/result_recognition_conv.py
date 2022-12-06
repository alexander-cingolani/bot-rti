from decimal import Decimal
import os
from difflib import get_close_matches
from typing import cast

from app.components import config
from app.components.models import Category, QualifyingResult, RaceResult, Round
from app.components.ocr import Result, recognize_results, string_to_seconds
from app.components.queries import (
    get_championship,
    get_driver,
)
from app.components.utils import send_or_edit_message, separate_car_classes
from more_itertools import chunked
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SQLASession
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
    ASK_2ND_FASTEST_LAP_2,
    SAVE_RACE_2_RESULTS,
    PERSIST_RESULTS,
) = range(27, 39)


WRONG_FILE_FORMAT_MESSAGE = (
    "Il file dei risultati deve essere inviato in formato 16:9 senza compressione."
    "\nè consigliabile fare lo screenshot dei risultati da PC, in quanto "
    "il formato degli screenshot fatti da smartphone risulta dilatato rispetto al "
    "formato 16:9, rendendo impossibile la corretta identificazione dei giocatori "
    "e dei tempi di gara."
)

engine = create_engine(os.environ.get("DB_URL"))
_Session = sessionmaker(bind=engine, autoflush=False)


def text_to_results(session, text: str, category: Category) -> list[Result]:
    """This is a helper function for ask_fastest_lap callbacks.
    It receives the block of text sent by the user to correct race/qualifying results
    and transforms it into a list of Result objects. Driver psn id's don't have to be
    spelt perfectly, this function automatically selects the closest driver to the one
    given in the message.

    Args:
        text (str): Text to convert into results.

    Returns:
        list[Result]: Results obtained
    """
    results = list(chunked(text.split(), 2))
    driver_classes = {
        driver.driver.psn_id: driver.car_class for driver in category.active_drivers()
    }
    drivers = [driver.driver.psn_id for driver in category.active_drivers()]
    for i, (driver, gap) in enumerate(results):
        if driver not in drivers:
            driver = get_close_matches(driver, drivers, cutoff=0.2)[0]
            driver_obj = get_driver(session, psn_id=driver)
            if driver:
                drivers.remove(driver)
        else:
            driver_obj = get_driver(session, driver)
            drivers.remove(driver)
        seconds = string_to_seconds(gap)

        if driver:
            result = Result(driver_obj.psn_id, seconds)
            result.car_class = driver_classes[driver_obj.psn_id]
            results[i] = result
    for driver in drivers:
        driver_obj = get_driver(session, psn_id=driver)
        result = Result(driver_obj.psn_id, 0)

        result.car_class = driver_classes[driver_obj.psn_id]
        results.append(result)

    return results


async def results_input_entry_point(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Asks the admin for the category he wants to add results to."""
    user_data = context.user_data
    user_data.clear()
    if update.effective_user.id not in config.ADMINS:
        await update.message.reply_text(
            "Non sei autorizzato ad usare in questa funzione,"
            f" se credi di doverlo essere, contatta {config.OWNER}"
        )

    sqla_session = _Session()
    championship = get_championship(sqla_session)
    user_data["sqla_session"] = sqla_session
    user_data["championship"] = championship

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

    user_data = context.user_data

    if not getattr(update.callback_query, "data", "").isnumeric():

        user_data["category"] = user_data["championship"].categories[
            int(update.callback_query.data[1])
        ]

    category = cast(Category, user_data["category"])

    current_round = category.first_non_completed_round()
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
    seconds = str(seconds)
    if "." in seconds:
        seconds, milliseconds = seconds.split(".")
        minutes, seconds = divmod(int(seconds), 60)
        return (
            f"{str(minutes) + ':' if minutes else ''}{seconds:02d}.{milliseconds:0<3}"
        )
    return seconds


async def download_quali_results(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Performs OCR on the received image and asks if the results are correct."""
    user_data = context.user_data
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
    await update.effective_chat.send_action(ChatAction.TYPING)

    # Save the photo containing the results.
    if update.message:
        if update.message.text:
            results = text_to_results(
                sqla_session, update.message.text, category=category
            )
            user_data["quali_results"] = results
            success = True
        else:

            try:
                file = await update.message.document.get_file()
            except AttributeError:
                await update.message.reply_text(WRONG_FILE_FORMAT_MESSAGE)
                return
            await file.download("results.jpg")

            driver_names = [
                driver.driver.psn_id for driver in category.active_drivers()
            ]
            success, user_data["quali_results"] = recognize_results(
                sqla_session, "results.jpg", driver_names
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

    user_data = context.user_data
    category: Category = user_data["category"]
    sqla_session: SQLASession = user_data["sqla_session"]
    if not update.callback_query:
        text = update.message.text
        results = text_to_results(sqla_session, text, category)
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

    user_data = context.user_data
    category: Category = user_data["category"]
    sqla_session: SQLASession = user_data
    if update.callback_query:
        if user_data["round"].has_sprint_race:
            gara = " 1"
        else:
            gara = ""
        await update.callback_query.edit_message_text(
            f"Inviami i risultati di gara{gara} corretti:"
        )
        return SAVE_RACE_1_RESULTS

    drivers = [driver.driver.psn_id for driver in category.active_drivers()]

    if update.message:

        if update.message.text:
            results = text_to_results(
                sqla_session, update.message.text, category=category
            )
        else:

            await update.effective_chat.send_action(ChatAction.TYPING)

            try:
                file = await update.message.document.get_file()
            except AttributeError:
                await update.message.reply_text(WRONG_FILE_FORMAT_MESSAGE)
                return

            screenshot = await file.download("results_1.jpg")
            results = recognize_results(sqla_session, screenshot, drivers)[1]

    user_data["race_1_results"] = results
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

    user_data = context.user_data
    category: Category = user_data["category"]
    sqla_session: SQLASession = user_data["sqla_session"]

    buttons = []
    car_class = category.car_classes[0].car_class
    for i, driver in enumerate(category.active_drivers()):
        if driver.car_class_id == car_class.car_class_id:
            buttons.append(
                InlineKeyboardButton(driver.driver.psn_id, callback_data=f"d{i}")
            )
    buttons = list(chunked(buttons, 2))

    if not category.multi_class:
        text = "Chi ha segnato il giro più veloce?"
        if user_data["round"].has_sprint_race:
            button_text = "Salva risultati »"
            callback_data = "save_race_1_results"
        else:
            button_text = "Risultati gara 2 »"
            callback_data = "save_race_1_results"
    else:
        text = f"Chi ha segnato il giro più veloce in {car_class.name}?"
        if user_data["round"].has_sprint_race:
            button_text = f"G.V. classe {category.car_classes[1].car_class.name} »"
            callback_data = "ask_2nd_fastest_lap_1"
        else:
            button_text = "Risultati gara 2 »"
            callback_data = "save_race_1_results"

    buttons.append(
        [
            InlineKeyboardButton(
                "« Modifica risultati gara 1",
                callback_data=str(DOWNLOAD_RACE_1_RESULTS),
            ),
            InlineKeyboardButton(text=button_text, callback_data=callback_data),
        ]
    )

    reply_markup = InlineKeyboardMarkup(buttons)

    # Saves corrected results if a message was sent.
    if update.message:
        user_data["race_1_results"] = text_to_results(
            sqla_session, update.message.text, user_data["category"]
        )
        await update.message.reply_text(text, reply_markup=reply_markup)

    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    if category.multi_class:
        return ASK_2ND_FASTEST_LAP_1

    return SAVE_RACE_1_RESULTS


async def ask_2nd_fastest_lap_1(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:

    user_data = context.user_data
    category = cast(Category, user_data["category"])
    sqla_session: SQLASession = user_data["sqla_session"]

    # Saves driver who scored the fastest lap if callback data contains a driver.
    if update.callback_query.data != "save_race_1_results":
        user_data["fastest_lap_1"] = category.active_drivers()[
            int(update.callback_query.data[1])
        ].driver

    buttons = []
    car_class = category.car_classes[1].car_class
    for i, driver in enumerate(category.active_drivers()):
        if driver.car_class_id == car_class.car_class_id:
            buttons.append(
                InlineKeyboardButton(driver.driver.psn_id, callback_data=f"d{i}")
            )
    buttons = list(chunked(buttons, 2))

    if user_data["round"].has_sprint_race:
        button_text = "Salva risultati »"
        callback_data = "save_race_1_results"
    else:
        button_text = "Risultati gara 2 »"
        callback_data = "save_race_1_results"

    buttons.append(
        [
            InlineKeyboardButton(
                f"« Modifica G.V. classe {category.car_classes[0].car_class.name}",
                callback_data=str(ASK_FASTEST_LAP_1),
            ),
            InlineKeyboardButton(text=button_text, callback_data=callback_data),
        ]
    )

    reply_markup = InlineKeyboardMarkup(buttons)
    text = f"Chi ha segnato il giro più veloce in {car_class.name}?"

    if update.message:
        user_data["race_1_results"] = text_to_results(
            sqla_session, update.message.text, user_data["category"]
        )
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    return SAVE_RACE_1_RESULTS


async def save_race_1_results(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:

    user_data = context.user_data
    category: Category = user_data["category"]

    # Saves driver who scored the fastest lap if callback data contains a driver.
    if update.callback_query.data != "save_race_1_results":
        if not category.multi_class:
            user_data["fastest_lap_1"] = category.active_drivers()[
                int(update.callback_query.data[1])
            ].driver
        else:
            user_data["2nd_fastest_lap_1"] = category.active_drivers()[
                int(update.callback_query.data[1])
            ].driver

    if user_data["round"].has_sprint_race:
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

    if update.callback_query:
        await update.callback_query.edit_message_text(
            "Inviami i risultati di gara 2 corretti:"
        )
        return SAVE_RACE_2_RESULTS

    user_data = context.user_data
    category: Category = user_data["category"]
    sqla_session: SQLASession = user_data["sqla_session"]
    drivers = [driver.driver.psn_id for driver in category.active_drivers()]

    # gt7 needs 2 screenshots, therefore after the first screenshot is received
    # DOWNLOAD_RACE_RESULTS is returned again, to receive the second screenshot.
    if update.message:
        if update.message.text:
            results = text_to_results(
                sqla_session, update.message.text, category=category
            )
        else:

            await update.effective_chat.send_action(ChatAction.TYPING)

            try:
                file = await update.message.document.get_file()
            except AttributeError:
                await update.message.reply_text(WRONG_FILE_FORMAT_MESSAGE)
                return

            screenshot = await file.download("results_1.jpg")
            results = recognize_results(sqla_session, screenshot, drivers)[1]

    user_data["race_2_results"] = results
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

    user_data = context.user_data
    category: Category = user_data["category"]
    sqla_session: SQLASession = user_data["sqla_session"]
    buttons = []
    for i, driver in enumerate(category.active_drivers()):
        buttons.append(
            InlineKeyboardButton(driver.driver.psn_id, callback_data=f"d{i}")
        )
    buttons = list(chunked(buttons, 2))

    buttons.append(
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

    reply_markup = InlineKeyboardMarkup(buttons)
    text = "Chi ha segnato il giro più veloce?"

    # Saves corrected results if a message was sent.
    if update.message:
        user_data["race_2_results"] = text_to_results(
            sqla_session, update.message.text, user_data["category"]
        )
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    return SAVE_RACE_2_RESULTS


async def save_race_2_results(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:

    user_data = context.user_data
    category: Category = user_data["category"]

    # Saves driver who scored the fastest lap.
    if update.callback_query.data != "save_race_2_results":
        user_data["fastest_lap_2"] = category.active_drivers()[
            int(update.callback_query.data[1])
        ].driver

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


async def persist_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    user_data = context.user_data
    category = cast(Category, user_data["category"])
    championship_round: Round = user_data["round"]
    quali_results: list[Result] = user_data.get("quali_results")
    sqla_session: SQLASession = user_data["sqla_session"]
    result_objs = []  # All QualifyingResults and RaceResults will be added to this.

    if quali_results:

        individual_class_results = separate_car_classes(category, quali_results)

        for class_results in individual_class_results.values():
            class_pole_time = class_results[0].seconds
            for pos, quali_res in enumerate(class_results, start=1):
                if quali_res.seconds:
                    gap_to_first = quali_res.seconds - class_pole_time
                participated = bool(quali_res.position)
                if not participated:
                    pos = None
                result_objs.append(
                    QualifyingResult(
                        position=quali_res.position,
                        gap_to_first=gap_to_first,
                        laptime=quali_res.seconds,
                        driver=get_driver(sqla_session, psn_id=quali_res.driver),
                        round=championship_round,
                        participated=bool(quali_res.position),
                        relative_position=pos,
                    )
                )

    if user_data["round"].has_sprint_race:
        race_1_results: list[Result] = user_data["race_1_results"]
        race_2_results: list[Result] = user_data["race_2_results"]
        sessions = [
            (championship_round.sprint_race, race_1_results),
            (championship_round.long_race, race_2_results),
        ]
    else:
        # If the category has no sprint race then it can only have a long race.
        race_results: list[Result] = user_data["race_1_results"]
        sessions = [(championship_round.long_race, race_results)]

    # Saves race results for every race session.
    for i, (session, results) in enumerate(sessions):
        fastest_lap_drivers = [user_data[f"fastest_lap_{i + 1}"].psn_id]

        if user_data.get(f"2nd_fastest_lap_{i + 1}"):
            fastest_lap_drivers.append(user_data[f"2nd_fastest_lap_{i + 1}"].psn_id)

        separated_results = separate_car_classes(category, results)

        for class_results in separated_results.values():
            winners_racetime = class_results[0].seconds
            for pos, result in enumerate(class_results, start=1):

                bonus_points = 0
                if result.driver in fastest_lap_drivers:
                    bonus_points += 1
                if result.seconds:
                    gap_to_first = result.seconds - winners_racetime
                else:
                    gap_to_first = None
                    pos = None
                result = RaceResult(
                    finishing_position=result.position,
                    fastest_lap_points=bonus_points,
                    driver=get_driver(sqla_session, driver=result.driver),
                    session=session,
                    round=championship_round,
                    gap_to_first=gap_to_first,
                    total_racetime=result.seconds,
                    relative_position=pos,
                )
                result.participated = bool(pos)
                result_objs.append(result)

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
