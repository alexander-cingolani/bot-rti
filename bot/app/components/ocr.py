from difflib import get_close_matches

from app.components.queries import get_driver
from app.components.utils import Result, string_to_seconds
from PIL import Image, ImageOps
from PIL.ImageEnhance import Contrast
from pytesseract import image_to_string

LEFT_1, RIGHT_1 = 400, 580
LEFT_2, RIGHT_2 = 1280, 1500
TOP_START = 200
BOTTOM_START = 250
INCREMENT = 50


def recognize_results(
    session, image: str, expected_drivers: list[str]
) -> list[list[Result]]:

    image = Image.open(image)

    image = image.convert("L")
    image = Contrast(image).enhance(2)
    image = ImageOps.grayscale(image)
    image = ImageOps.invert(image)

    top = TOP_START
    bottom = BOTTOM_START
    success = True
    results = []
    remaining_drivers = expected_drivers.copy()
    for _ in range(len(expected_drivers)):
        name_box = image.crop((LEFT_1, top, RIGHT_1, bottom))
        laptime_box = image.crop((LEFT_2, top, RIGHT_2, bottom))
        name_box.show()
        driver = image_to_string(name_box).strip()
        s = image_to_string(laptime_box)
        seconds = string_to_seconds(s)

        matches = get_close_matches(driver, remaining_drivers, cutoff=0.1)
        if matches and len(driver) >= 3:
            race_res = Result(matches[0], seconds)
            race_res.car_class = get_driver(session, race_res.driver).current_class()
            results.append(race_res)
            remaining_drivers.remove(matches[0])
        elif seconds:
            success = False
            results.append(Result("[NON_RICONOSCIUTO]", seconds))
        top += INCREMENT
        bottom += INCREMENT

    for driver in remaining_drivers:
        race_res = Result(driver, None)
        race_res.car_class = get_driver(session, driver).current_class()
        results.append(race_res)

    return success, results
