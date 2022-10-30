import os
from typing import cast

from more_itertools import chunked
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

from components import config
from components.models import CarClass, Category, QualifyingResult, RaceResult
from components.ocr import (
    Result,
    recognize_quali_results,
    recognize_race_results,
    string_to_seconds,
)
from components.queries import (
    get_championship,
    get_driver,
    save_object,
    update_object,
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
) = range(15, 27)


def text_to_results(text: str) -> list[list[str, float]]:
    """Helper function for ask_fastest_lap callbacks.
    It receives the block of text sent by the user to correct race/qualifying results
    and transforms it into a list of lists, each containing a driver's name (str) and
    his gap (float) to the previous driver.

    Args:
        text (str): Text to convert into results.

    Returns:
        list[list[str, float]]: Results obtained
    """
    results = list(chunked(text.split(), 2))
    for i, (driver, gap) in enumerate(results):
        results[i] = Result(driver, string_to_seconds(gap))
    return results


async def results_input_entry_point(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Asks the admin for the category he wants to add results in."""
    context.user_data.clear()
    if update.effective_user.id not in config.ADMINS:
        await update.message.reply_text(
            "Non sei autorizzato ad usare in questa funzione,"
            f" se credi di doverlo essere, contatta {config.OWNER}"
        )

    championship = get_championship()
    context.user_data["championship"] = championship

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

    round = category.first_non_completed_round()
    text = (
        f"<b>{category.name}</b> - {round.number}ᵃ tappa {round.circuit}.\n"
        "Inviami l'immagine dei risultati della qualifica:"
    )
    reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Salta", callback_data="skip_quali")]]
    )
    await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup)
    return DOWNLOAD_QUALI_RESULTS


def seconds_to_str(seconds: float) -> str:
    if seconds:
        seconds, milliseconds = divmod(seconds, 1)
        minutes, seconds = divmod(seconds, 60)

        minutes = str(round(minutes))
        seconds = round(seconds)
        milliseconds = str(milliseconds)[2:5]
        return f"{minutes + ':' if minutes else ''}{seconds:02d}.{milliseconds:0<3}"
    return seconds


async def download_quali_results(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Performs OCR on the received image and asks if the results are correct."""
    user_data = context.user_data
    category = cast(Category, user_data["category"])

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
    file = await update.message.document.get_file()
    await file.download("results.jpg")

    driver_names = [driver.driver.psn_id for driver in category.drivers]
    success, user_data["quali_results"] = recognize_quali_results(
        "results.jpg", driver_names, category.game.name
    )

    os.remove("results.jpg")

    # Send the results
    results = user_data["quali_results"]
    results_message_text = ""
    for result in results:
        if result.seconds:
            gap = seconds_to_str(result.seconds)

            # if i == 0:
            #     gap = seconds_to_str(gap)
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
    category = cast(Category, user_data["category"])

    if not update.callback_query:
        text = update.message.text
        results = text_to_results(text)
        user_data["quali_results"] = results
    buttons = [
        InlineKeyboardButton(
            "« Modifica risultati qualifica", callback_data=str(DOWNLOAD_QUALI_RESULTS)
        )
    ]

    if category.has_sprint_race():
        text = "Inviami lo screenshot dei risultati di gara 1."
    else:
        text = "Inviami lo screenshot dei risultati di gara."

    reply_markup = InlineKeyboardMarkup([buttons])
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    return DOWNLOAD_RACE_1_RESULTS


async def download_race_1_results(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:

    user_data = context.user_data
    category = cast(Category, user_data["category"])

    if update.callback_query:
        if category.has_sprint_race():
            gara = " 1"
        else:
            gara = ""
        await update.callback_query.edit_message_text(
            f"Inviami i risultati di gara{gara} corretti:"
        )
        return SAVE_RACE_1_RESULTS

    drivers = [driver.driver.psn_id for driver in category.drivers]
    game = category.game.name

    # gt7 needs 2 screenshots, therefore after the first screenshot is received
    # DOWNLOAD_RACE_RESULTS is returned again, to receive the second screenshot.
    if game == "gt7":
        if os.path.exists("results_1.jpg") and not os.path.exists("results_2.jpg"):

            await update.effective_chat.send_action(ChatAction.TYPING)

            file = await update.message.effective_attachment.get_file()
            screenshot = await file.download("results_2.jpg")

            if not user_data.get("partial_race_1_results"):
                user_data["partial_race_1_results"] = {}
            results = user_data["partial_race_1_results"]

            results.update(
                dict.fromkeys(recognize_race_results(screenshot, drivers, game)[1])
            )
            results = list(results.keys())
            user_data["partial_race_1_results"].clear()
            os.remove("results_1.jpg")
            os.remove("results_2.jpg")
        elif not os.path.exists("results_1.jpg"):
            file = await update.message.effective_attachment.get_file()
            screenshot = await file.download("results_1.jpg")
            results = dict.fromkeys(
                recognize_race_results(screenshot, drivers, game)[1]
            )
            return DOWNLOAD_RACE_1_RESULTS
    else:
        await update.effective_chat.send_action(ChatAction.TYPING)
        file = await update.message.effective_attachment.get_file()
        screenshot = await file.download("results_1.jpg")
        results = recognize_race_results(screenshot, drivers, game)[1]

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

    buttons = [
        InlineKeyboardButton(
            "« Usa un'altra immagine", callback_data=str(SAVE_QUALI_RESULTS)
        ),
        InlineKeyboardButton("Giro veloce »", callback_data="race_1_results_ok"),
    ]
    reply_markup = InlineKeyboardMarkup([buttons])
    text = (
        "Controlla che i risultati siano corretti."
        " Per correggere copia il messaggio sopra."
    )
    await update.message.reply_text(text, reply_markup=reply_markup)
    return ASK_FASTEST_LAP_1


async def ask_fastest_lap_1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    user_data = context.user_data
    category = cast(Category, user_data["category"])

    buttons = []
    car_class = category.car_classes[0].car_class
    for i, driver in enumerate(category.drivers):
        if driver.car_class_id == car_class.car_class_id:
            buttons.append(
                InlineKeyboardButton(driver.driver.psn_id, callback_data=f"d{i}")
            )
    buttons = list(chunked(buttons, 2))

    if not category.multi_class:
        text = "Chi ha segnato il giro più veloce?"
        if category.has_sprint_race():
            button_text = "Salva risultati »"
            callback_data = "save_race_1_results"
        else:
            button_text = "Risultati gara 2 »"
            callback_data = "save_race_1_results"
    else:
        text = f"Chi ha segnato il giro più veloce in {car_class.name}"
        if category.has_sprint_race():
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

    # Saves corrected results if sent a message.
    if update.message:
        user_data["race_1_results"] = text_to_results(update.message.text)
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

    # Saves driver who scored the fastest lap if callback data contains a driver.
    if update.callback_query.data != "save_race_1_results":
        user_data["fastest_lap_1"] = category.drivers[
            int(update.callback_query.data[1])
        ].driver

    buttons = []
    car_class = category.car_classes[1].car_class
    for i, driver in enumerate(category.drivers):
        if driver.car_class_id == car_class.car_class_id:
            buttons.append(
                InlineKeyboardButton(driver.driver.psn_id, callback_data=f"d{i}")
            )
    buttons = list(chunked(buttons, 2))

    if category.has_sprint_race():
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
        user_data["race_1_results"] = text_to_results(update.message.text)
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)

    return SAVE_RACE_1_RESULTS


async def save_race_1_results(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    user_data = context.user_data
    category = cast(Category, user_data["category"])

    # Saves driver who scored the fastest lap if callback data contains a driver.
    if update.callback_query.data != "save_race_1_results":
        if not category.multi_class:
            user_data["fastest_lap_1"] = category.drivers[
                int(update.callback_query.data[1])
            ].driver
        else:
            user_data["2nd_fastest_lap_1"] = category.drivers[
                int(update.callback_query.data[1])
            ].driver

    if category.has_sprint_race():
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
    category = cast(Category, user_data["category"])

    drivers = [driver.driver.psn_id for driver in category.drivers]
    game = category.game.name

    # gt7 needs 2 screenshots, therefore after the first screenshot is received
    # DOWNLOAD_RACE_RESULTS is returned again, to receive the second screenshot.
    if game == "gt7":
        if os.path.exists("results_1.jpg") and not os.path.exists("results_2.jpg"):

            await update.effective_chat.send_action(ChatAction.TYPING)

            file = await update.message.effective_attachment.get_file()
            screenshot = await file.download("results_2.jpg")

            if not user_data.get("partial_race_2_results"):
                user_data["partial_race_2_results"] = {}
            results = user_data["partial_race_2_results"]

            results.update(
                dict.fromkeys(recognize_race_results(screenshot, drivers, game)[1])
            )
            results = list(results.keys())
            user_data["partial_race_2_results"].clear()
            os.remove("results_1.jpg")
            os.remove("results_2.jpg")
        elif not os.path.exists("results_1.jpg"):
            file = await update.message.effective_attachment.get_file()
            screenshot = await file.download("results_1.jpg")
            results = dict.fromkeys(
                recognize_race_results(screenshot, drivers, game)[1]
            )
            return DOWNLOAD_RACE_2_RESULTS
    else:
        await update.effective_chat.send_action(ChatAction.TYPING)
        file = await update.message.effective_attachment.get_file()
        screenshot = await file.download("results_1.jpg")
        results = recognize_race_results(screenshot, drivers, game)[1]

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

    buttons = [
        InlineKeyboardButton(
            "« Usa un'altra immagine", callback_data=str(SAVE_RACE_1_RESULTS)
        ),
        InlineKeyboardButton("Giro veloce »", callback_data="race_2_results_ok"),
    ]
    reply_markup = InlineKeyboardMarkup([buttons])
    text = (
        "Controlla che i risultati siano corretti."
        " Per correggere copia il messaggio sopra."
    )
    await update.message.reply_text(text, reply_markup=reply_markup)
    return ASK_FASTEST_LAP_2


async def ask_fastest_lap_2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    user_data = context.user_data
    category = cast(Category, user_data["category"])

    buttons = []
    for i, driver in enumerate(category.drivers):
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
    # Saves corrected results if sent a message.
    if update.message:
        user_data["race_2_results"] = text_to_results(update.message.text)
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    return SAVE_RACE_2_RESULTS


async def save_race_2_results(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    user_data = context.user_data
    category = cast(Category, user_data["category"])

    # Saves driver who scored the fastest lap.
    if update.callback_query.data != "save_race_2_results":
        user_data["fastest_lap_2"] = category.drivers[
            int(update.callback_query.data[1])
        ].driver.psn_id

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


def _prepare_result(raceres: Result, best_time: float, position: int) -> Result:
    if raceres.seconds is None:
        raceres.position = None
    elif raceres.seconds == 0:
        raceres.seconds = None
        raceres.position = position
    elif position == 1:
        raceres.position = position
        raceres.seconds = best_time
        pass
    else:
        raceres.seconds = raceres.seconds + best_time
        raceres.position = position
    return raceres


def _separate_car_classes(
    category: Category, race_results: list[Result]
) -> dict[CarClass, list[Result]]:

    separated_classes = {
        car_class.car_class_id: [] for car_class in category.car_classes
    }
    best_laptime = race_results[0].seconds

    for pos, result in enumerate(race_results):
        if result.car_class.car_class_id in separated_classes:
            separated_classes[result.car_class.car_class_id].append(
                _prepare_result(result, best_laptime, pos + 1)
            )
    return separated_classes


async def persist_results(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_data = context.user_data
    category = cast(Category, user_data["category"])
    rnd = category.first_non_completed_round()
    quali_results = cast(list[Result], user_data.get("quali_results"))

    if quali_results:
        individual_class_results = _separate_car_classes(category, quali_results)
        for class_results in individual_class_results.values():
            for quali_res in class_results:
                driver_obj = get_driver(psn_id=quali_res.driver)
                result = QualifyingResult(
                    position=quali_res.position + 1,
                    laptime=quali_res.seconds,
                    driver=driver_obj,
                    round=rnd,
                )
                save_object(result)

    if category.has_sprint_race():
        race_1_results = cast(list[Result], user_data["race_1_results"])
        race_2_results = cast(list[Result], user_data["race_2_results"])
        sessions = [
            (category.sprint_race, race_1_results),
            (category.long_race, race_2_results),
        ]
    else:
        # If the category has no sprint race then it can only have a long race.
        race_results = cast(list[Result], user_data["race_1_results"])
        sessions = [(category.long_race, race_results)]

    # Saves race results for every race session.
    for i, (session, results) in enumerate(sessions):
        fastest_lap_drivers = [user_data[f"fastest_lap_{i + 1}"].psn_id]

        if user_data.get(f"2nd_fastest_lap_{i + 1}"):
            fastest_lap_drivers.append(user_data[f"2nd_fastest_lap_{i + 1}"].psn_id)

        separated_results = _separate_car_classes(category, results)
        for class_results in separated_results.values():

            for result in class_results:
                bonus_points = 0
                if result.driver in fastest_lap_drivers:
                    bonus_points += 1
                driver_obj = get_driver(result.driver)
                result = RaceResult(
                    finishing_position=result.position,
                    bonus_points=bonus_points,
                    driver=driver_obj,
                    session=session,
                    round=rnd,
                    gap_to_first=result.seconds,
                )
                save_object(result)

    buttons = []
    for i, category in enumerate(user_data["championship"].categories):
        if category.category_id != category.category_id:
            buttons.append(
                InlineKeyboardButton(f"{category.name}", callback_data=f"c{i}")
            )

    rnd.completed = True
    update_object()

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
            CallbackQueryHandler(ask_qualifying_results, r"c0|c1|c2|c3")
        ],
        DOWNLOAD_QUALI_RESULTS: [
            MessageHandler(filters.ATTACHMENT, download_quali_results),
            CallbackQueryHandler(download_quali_results, "skip_quali"),
        ],
        SAVE_QUALI_RESULTS: [
            CallbackQueryHandler(save_quali_results, "confirm_quali_results"),
            MessageHandler(filters.Regex(r"^[^/][\s\S]{70,}$"), save_quali_results),
        ],
        DOWNLOAD_RACE_1_RESULTS: [
            CallbackQueryHandler(download_race_1_results, "download_race_1_results"),
            MessageHandler(filters.ATTACHMENT, download_race_1_results),
        ],
        ASK_FASTEST_LAP_1: [
            CallbackQueryHandler(ask_fastest_lap_1, "race_1_results_ok"),
            MessageHandler(filters.Regex(r"^[^/][\s\S]{70,}$"), ask_fastest_lap_1),
        ],
        ASK_2ND_FASTEST_LAP_1: [
            CallbackQueryHandler(
                ask_2nd_fastest_lap_1,
                r"|".join(f"d{num}" for num in range(14)) + r"|save_race_1_results",
            )
        ],
        SAVE_RACE_1_RESULTS: [
            CallbackQueryHandler(
                save_race_1_results,
                r"|".join(f"d{num}" for num in range(14)) + r"|save_race_1_results",
            )
        ],
        DOWNLOAD_RACE_2_RESULTS: [
            CallbackQueryHandler(download_race_2_results, "download_race_2_results"),
            MessageHandler(filters.ATTACHMENT, download_race_2_results),
        ],
        ASK_FASTEST_LAP_2: [
            CallbackQueryHandler(ask_fastest_lap_2, "race_2_results_ok"),
            MessageHandler(filters.Regex(r"^[^/][\s\S]{70,}$"), ask_fastest_lap_2),
        ],
        SAVE_RACE_2_RESULTS: [
            CallbackQueryHandler(
                save_race_2_results,
                (r"|".join(f"d{num}" for num in range(14)) + r"|save_race_2_results"),
            )
        ],
        PERSIST_RESULTS: [CallbackQueryHandler(persist_results, "persist_results")],
    },
    fallbacks=[
        CommandHandler(
            "salva_risultati",
            results_input_entry_point,
        ),
        CallbackQueryHandler(
            change_conversation_state, r"|".join(str(i) for i in range(15, 25))
        ),
    ],
)
