"""
Contains the function which recognizes results from a screenshot.
"""
from difflib import get_close_matches

from app.components.utils import Result, string_to_seconds
from PIL import Image, ImageOps
from PIL.ImageEnhance import Contrast
from pytesseract import image_to_string

from app.components.models import Driver
from pathlib import Path

LEFT_1, RIGHT_1 = 400, 580
LEFT_2, RIGHT_2 = 1280, 1500
TOP_START = 200
BOTTOM_START = 250
INCREMENT = 50


def recognize_results(
    image: str | bytes | Path, expected_drivers: list[Driver]
) -> tuple[bool, list[Result]]:
    """Transforms the results of a race or qualifying session from a screenshot
    of the results taken from the game or the live stream.

    Args:
        session (SQLASession): SQLAlchemy orm session to use.
        image (str): Screenshot containing the qualifying or race results.
        expected_drivers (list[str]): Drivers which are expected to be found in
            the screenshot. Drivers given in this list will be marked as absent if
            not found/recognized.

    Returns:
        tuple[bool, list[Result]]: The boolean value indicates whether all the drivers
            were recognized or not.
    """
    image_file = Image.open(image)

    image_file = image_file.convert("L")
    image_file = Contrast(image_file).enhance(2)
    image_file = ImageOps.grayscale(image_file)
    image_file = ImageOps.invert(image_file)

    top = TOP_START
    bottom = BOTTOM_START
    success = True
    results = []
    remaining_drivers = {driver.psn_id: driver for driver in expected_drivers}

    for _ in range(len(expected_drivers)):
        name_box = image_file.crop((LEFT_1, top, RIGHT_1, bottom))
        laptime_box = image_file.crop((LEFT_2, top, RIGHT_2, bottom))

        driver = image_to_string(name_box).strip()
        seconds = string_to_seconds(image_to_string(laptime_box))
        matches = get_close_matches(driver, remaining_drivers.keys(), cutoff=0.1)

        if matches and len(driver) >= 3:
            driver = remaining_drivers.pop(matches[0])
            race_res = Result(driver, seconds)
            race_res.car_class = driver.current_class()
            results.append(race_res)

        elif seconds:
            success = False
            results.append(Result(None, seconds))
        top += INCREMENT
        bottom += INCREMENT

    for driver_obj in remaining_drivers.values():
        race_res = Result(driver_obj, None)
        race_res.car_class = driver_obj.current_class()
        results.append(race_res)

    return success, results
