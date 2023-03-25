"""
Contains functions used to operate on results or parts of results.
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from difflib import get_close_matches
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

    driver: DriverCategory | None
    seconds: Decimal | None
    position: int | None
    fastest_lap: bool

    def __init__(self, driver: DriverCategory | None, seconds: Decimal | None):
        self.seconds = seconds
        self.driver = driver
        self.position = 0
        self.fastest_lap = False

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

    results = []
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
        result = Result(driver_category, Decimal(0))
        results.append(result)

    return results


def image_to_results(
    image: str | bytes | Path, expected_drivers: list[DriverCategory]
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
        [3 * _ for _ in image_file.size], Image.BICUBIC
    )
    image_file = image_file.point(lambda p: p > 100 and p + 100)
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
    results = []
    remaining_drivers = {driver.driver.psn_id: driver for driver in expected_drivers}
    
    for _ in range(len(expected_drivers)):

        name_box = image_file.crop((LEFT_1, top, RIGHT_1, bottom))
        laptime_box = image_file.crop((LEFT_2, top, RIGHT_2, bottom))

        driver_psn_id = image_to_string(name_box).strip()
        
        seconds = image_to_string(laptime_box)
        seconds = string_to_seconds(seconds)
        matches = get_close_matches(driver_psn_id, remaining_drivers.keys(), cutoff=0.1)

        if matches and len(driver_psn_id) >= 3:
            driver_category = remaining_drivers.pop(matches[0])
            race_res = Result(driver_category, seconds)
            results.append(race_res)

        elif seconds:
            results.append(Result(None, seconds))
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


def seconds_to_text(seconds: Decimal) -> str:
    """Converts seconds to a user-friendly string format.

    Args:
        seconds (Decimal): seconds to covert into string.
            Must contain at least one decimal number.

    Returns:
        str: User-friendly string.
    """

    minutes, seconds = divmod(seconds, 60)
    seconds, milliseconds = divmod(seconds, 1)
    milliseconds_int = round(milliseconds * 1000)
    return f"{str(minutes) + ':' if minutes else ''}{int(seconds):02d}.{milliseconds_int:0>3}"


def string_to_seconds(string) -> Decimal | None:
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
