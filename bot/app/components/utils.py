"""
Helper stuff.
"""
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from telegram import Update

from app.components.models import Driver


@dataclass
class Result:
    """Helper class to store data necessary to create a RaceResult
    or a QualifyingResult
    """

    driver: Driver
    seconds: Decimal | None
    car_class: Any
    position: int | None

    def __init__(self, driver, seconds):
        self.seconds = seconds
        self.driver = driver
        self.car_class = 0
        self.position = 0

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
    milliseconds_str = "0"
    if "." in other:
        other, milliseconds_str = matched_string.split(".")

    hours_str, minutes_str = "0", "0"
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
