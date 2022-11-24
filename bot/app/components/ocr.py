from difflib import get_close_matches

from app.components.utils import Result, string_to_seconds
from app.components.queries import get_driver
from PIL import Image, ImageOps
from PIL.ImageEnhance import Contrast
from pytesseract import image_to_string

LEFT_1, RIGHT_1 = 380, 580
LEFT_2, RIGHT_2 = 1330, 1445
TOP_START = 201
BOTTOM_START = 237
INCREMENT = 51


def recognize_results(image: str, expected_drivers: list[str]) -> list[list[Result]]:

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

        driver = image_to_string(name_box, config="--psm 8").strip()
        seconds = string_to_seconds(image_to_string(laptime_box, config="--psm 8"))

        matches = get_close_matches(driver, remaining_drivers, cutoff=0.3)

        if matches and len(driver) >= 3:
            race_res = Result(matches[0], seconds)
            race_res.car_class = get_driver(race_res.driver).current_class()
            results.append(race_res)
            remaining_drivers.remove(matches[0])
        elif seconds:
            success = False
            results.append(Result("[NON_RICONOSCIUTO]", seconds))
        top += INCREMENT
        bottom += INCREMENT

    for driver in remaining_drivers:
        race_res = Result(driver, None)
        race_res.car_class = get_driver(driver).current_class()
        results.append(race_res)

    return success, results
