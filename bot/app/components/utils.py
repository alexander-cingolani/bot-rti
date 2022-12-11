"""
Helper stuff. Hope to get rid of it soon.
"""
from decimal import Decimal
import re
from dataclasses import dataclass
from typing import Any

from telegram import Update


@dataclass
class Result:
    """Helper class to store data necessary to create a RaceResult
    or a QualifyingResult
    """

    driver: str
    seconds: Decimal | None
    car_class: Any
    position: int | None

    def __init__(self, driver, seconds):
        self.seconds = seconds
        self.driver = driver
        self.car_class = None
        self.position = None

    def __hash__(self) -> int:
        return hash(str(self))

    def prepare_result(self, best_time: Decimal, position: int):
        """Modifies Result to contain valid data for a RaceResult."""
        if self.seconds is None:
            self.position = None
        elif self.seconds == 0:
            self.seconds = None
            self.position = position
        elif position == 1:
            self.position = position
            self.seconds = best_time
        else:
            self.seconds = self.seconds + best_time
            self.position = position
        return self


def string_to_seconds(string) -> Decimal | None | str:
    """Converts a string formatted as "mm:ss:SSS" to seconds.
    0 is returned when the gap to the winner wasn't available.
    None is returned when the driver did not finish the race

    Returns:
        float: Number of seconds.
    """
    match = re.search(
        r"([0-9]{1,2}:)?([0-9]{1,2}:){0,2}[0-9]{1,2}(\.|,)[0-9]{1,3}", string
    )
    if not match:
        if (
            "gir" in string
            or "gar" in string
            or "/" == string
            or "1" in string
            or "2" in string
        ):
            return Decimal(0)
        # if string is equals to "ASSENTE" None is retured.
        return None

    matched_string = match.group(0)
    matched_string = matched_string.replace(",", ".")

    other = matched_string
    milliseconds_str = ""
    if "." in other:
        other, milliseconds_str = matched_string.split(".")

    hours_str, minutes_str = "", ""
    if other.count(":") == 2:
        hours_str, minutes_str, seconds_str = other.split(":")
    elif other.count(":") == 1:
        minutes_str, seconds_str = other.split(":")
    else:
        if len(other) > 2:
            seconds_str = other[-2:]
        else:
            seconds_str = other

    return Decimal(
        f"{int(hours_str) * 3600 + int(minutes_str) * 60 + int(seconds_str)}.{int(milliseconds_str)}"
    )


def separate_car_classes(
    category: Any, results: list[Result] | list[Any]
) -> dict[Any, list[Result]] | dict[Any, list[Any]]:
    separated_classes: dict[int, list[Result]] = {
        car_class.car_class_id: [] for car_class in category.car_classes
    }
    if isinstance(results[0], Result):
        best_laptime = results[0].seconds

        for pos, result in enumerate(results, start=1):
            if result.car_class.car_class_id in separated_classes:
                separated_classes[result.car_class.car_class_id].append(
                    result.prepare_result(best_laptime, pos)
                )
        return separated_classes

    best_laptime = results[0].total_racetime

    for pos, result in enumerate(results, start=1):
        car_class = result.driver.current_class().car_class_id
        if car_class in separated_classes:
            separated_classes[car_class].append(result)
    return separated_classes


async def send_or_edit_message(update: Update, message, reply_markup=None) -> None:
    if update.callback_query:
        if not reply_markup:
            await update.callback_query.edit_message_text(text=message)
            return
        await update.callback_query.edit_message_text(
            text=message, reply_markup=reply_markup
        )
        return

    if not reply_markup:
        await update.message.reply_text(message)
        return

    await update.message.reply_text(text=message, reply_markup=reply_markup)
    return
