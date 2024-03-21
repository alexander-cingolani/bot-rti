"""
Contains functions used to operate on results or parts of results.
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from difflib import get_close_matches
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageFilter
from pytesseract import image_to_string  # type: ignore

from models import DriverCategory

LEFT_1, RIGHT_1 = 410 * 3, 580 * 3
LEFT_2, RIGHT_2 = 1320 * 3, 1405 * 3
TOP_START = 200 * 3
BOTTOM_START = 250 * 3
INCREMENT = 50 * 3


@dataclass
class Result:
    """Helper class to store data necessary to create RaceResult
    or QualifyingResult objects.
    """

    def __str__(self) -> str:
        if self.driver:
            return (
                f"(driver_name={self.driver.driver.psn_id}, position={self.position})"
            )
        return f"(driver_name=None, position={self.position})"

    def __init__(self, driver: DriverCategory, seconds: int | None):
        self.driver = driver
        self.seconds = seconds
        self.position = 0
        self.fastest_lap = False

    def __hash__(self) -> int:
        return hash(str(self))

    def prepare_result(self, best_time: int, position: int):
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


def text_to_results(text: str, expected_drivers: list[DriverCategory]) -> list[Result]:
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
        list[Result]: Results obtained.
    """

    # Creates a dictionary containing driver psn_ids mapped to a DriverCategory object.
    driver_map: dict[str, DriverCategory] = {
        driver.driver.psn_id: driver for driver in expected_drivers
    }

    results: list[Result] = []
    for line in text.splitlines():
        given_driver_name, gap = line.split()
        if given_driver_name not in driver_map:
            matches = get_close_matches(
                given_driver_name, driver_map.keys(), cutoff=0.2
            )
            if matches:
                driver_name = matches[0]  # Gets best match
            else:
                driver_name = ""
        else:
            driver_name = given_driver_name

        if driver_name:
            driver_category = driver_map.pop(driver_name)
            seconds = string_to_seconds(gap)
            result = Result(driver_category, seconds)
            results.append(result)

    # Add unrecognized drivers to the results list.
    for given_driver_name in driver_map:
        driver_category = driver_map[given_driver_name]
        result = Result(driver_category, 0)
        results.append(result)

    return results


def image_to_results(
    image: str | BytesIO | Path, expected_drivers: list[DriverCategory]
) -> list[Result]:
    """Transforms the results of a race or qualifying session from a screenshot
    of the results taken from the game or the live stream.

    Args:
        session (SQLASession): SQLAlchemy orm session to use.
        image (str): Screenshot containing the qualifying or race results.
        expected_drivers (list[str]): Drivers which are expected to be found in
            the screenshot. Drivers given in this list will be marked as absent if
            not found/recognized.

    Returns:
        list[Result]: List of recognized results. Non recognized drivers
        will have None in the driver attribute, similarly, non recognized laptimes
        will have None in the seconds attribute.
    """

    image_file = Image.open(fp=image)

    image_file = image_file.convert("L").resize(
        [3 * _ for _ in image_file.size], Image.BICUBIC  # type: ignore
    )
    image_file = image_file.point(lambda p: p > 100 and p + 100)  # type: ignore
    image_file = image_file.filter(ImageFilter.MinFilter(3))
    # image_file = image_file.convert("L")
    # image_file = Brightness(image_file).enhance(0.3)
    # image_file.save("../debug/brightness.png", format="png")
    # image_file = Contrast(image_file).enhance(2)
    # image_file = ImageOps.grayscale(image_file)
    # image_file = ImageOps.invert(image_file)
    # image_file = Contrast(image_file).enhance(2)
    # image_file = image_file.convert('1')
    top = TOP_START
    bottom = BOTTOM_START
    results: list[Result] = []
    remaining_drivers = {driver.driver.psn_id: driver for driver in expected_drivers}

    for _ in range(len(expected_drivers)):
        name_box = image_file.crop((LEFT_1, top, RIGHT_1, bottom))
        laptime_box = image_file.crop((LEFT_2, top, RIGHT_2, bottom))

        driver_psn_id: str = image_to_string(name_box).strip()

        seconds_str: str = image_to_string(laptime_box)
        seconds = string_to_seconds(seconds_str)
        matches = get_close_matches(driver_psn_id, remaining_drivers.keys(), cutoff=0)

        if matches and len(driver_psn_id) >= 3:
            driver_category = remaining_drivers.pop(matches[0])
            race_res = Result(driver_category, seconds)
            results.append(race_res)

        top += INCREMENT
        bottom += INCREMENT

    for driver_category in remaining_drivers.values():
        race_res = Result(driver_category, None)
        results.append(race_res)

    return results


def results_to_text(results: list[Result]) -> str:
    """Takes a list of results and converts it to a user-friendly message."""
    text = ""
    for result in results:
        if result.seconds:
            gap = seconds_to_text(result.seconds)
        else:
            gap = "ASSENTE"
        driver = result.driver.driver.psn_id if result.driver else "NON_RICONOSCIUTO"
        text += f"\n{driver} {gap}"
    return text


def seconds_to_text(seconds: int) -> str:
    """Converts seconds to a user-friendly string format.

    Args:
        seconds (int): seconds to covert into string.
            Must contain at least one decimal number.

    Returns:
        str: User-friendly string.
    """
    seconds, milliseconds = divmod(seconds, 1000)
    minutes, seconds = divmod(seconds, 60)
    return (
        f"{str(minutes) + ':' if minutes else ''}{int(seconds):02d}.{milliseconds:0>3}"
    )


def string_to_seconds(string: str) -> int | None:
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
            return 0
        # if string is equals to "ASSENTE" None is retured.
        return None

    matched_string = match.group(0)
    matched_string = matched_string.replace(",", ".")

    if matched_string.count(":") == 2 and "." in matched_string:
        t = datetime.strptime(matched_string, "%H:%M:%S.%f").time()
    elif matched_string.count(":") == 2:
        t = datetime.strptime(matched_string, "%H:%M:%S").time()
    elif ":" in matched_string and "." in matched_string:
        t = datetime.strptime(matched_string, "%M:%S.%f").time()
    elif ":" in matched_string:
        t = datetime.strptime(matched_string, "%H:%M:%S").time()
    elif "." in matched_string:
        t = datetime.strptime(matched_string, "%S.%f").time()
    else:
        return int(matched_string * 1000)

    seconds = (t.hour * 60 + t.minute) * 60 + t.second
    decimal_part = t.microsecond / 1_000_000

    return int((seconds + decimal_part) * 1000)
