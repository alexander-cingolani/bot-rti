import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from difflib import get_close_matches

from app.components.models import CarClass
from app.components.queries import get_driver
from PIL import Image, ImageFilter, ImageOps
from PIL.ImageEnhance import Contrast
from pytesseract import image_to_string


@dataclass
class Result:

    driver: str
    seconds: float
    car_class: CarClass
    position: int

    def __init__(self, driver, seconds):
        self.seconds = seconds
        self.driver = driver
        self.car_class = None
        self.position: int = None

    def __hash__(self) -> int:
        return hash(str(self))


def string_to_seconds(string) -> float | None | str:
    """Converts a string formatted as "mm:ss:SSS" to seconds.
    0 is returned when the gap to the winner wasn't available.
    None is returned when the driver did not finish the race

    Returns:
        float: Number of seconds.
    """
    match = re.search(r"((([0-9]){1,2}:)){0,2}[0-9]{1,2}((\.|,)[0-9]{1,3})?", string)
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
    milliseconds = 0
    other = matched_string
    if "." in other:
        other, milliseconds = matched_string.split(".")

    hours = 0
    minutes = 0
    if other.count(":") == 2:
        hours, minutes, seconds = other.split(":")
    elif other.count(":") == 1:
        minutes, seconds = other.split(":")
    else:
        seconds = other

    return timedelta(
        hours=int(hours),
        minutes=int(minutes),
        seconds=int(seconds),
        milliseconds=int(milliseconds),
    ).total_seconds()


def recognize_quali_results(
    image: str, expected_drivers: list[str], game: str
) -> list[list[Result]]:
    """Uses OCR to recognize the results in the given screenshot.

    Args:
        image (str): Path to the image. Must be FHD or 4K.
        expected_drivers (list[str]): Names of the expected drivers.

    Returns:
        list: List of lists each containing a driver's psn_id and laptime in descending order.
    """
    image = Image.open(image)
    image = image.convert("L")
    image = Contrast(image).enhance(2)
    image = ImageOps.grayscale(image)
    image = ImageOps.invert(image)
    if game == "gts":
        LEFT_1, RIGHT_1 = 380, 580
        LEFT_2, RIGHT_2 = 1330, 1440
        top = 201
        bottom = 237
        increment = 51
    elif game == "gt7":
        image = image.filter(ImageFilter.MinFilter(3))
        LEFT_1, RIGHT_1 = 385, 580
        LEFT_2, RIGHT_2 = 1330, 1435
        top = 203
        bottom = 237
        increment = 51
    else:
        raise ValueError(f'"{game}" is not supported.')

    results = []
    success = True
    remaining_drivers = expected_drivers.copy()
    for _ in range(len(expected_drivers)):
        name_box = image.crop((LEFT_1, top, RIGHT_1, bottom))
        laptime_box = image.crop((LEFT_2, top, RIGHT_2, bottom))

        driver = image_to_string(name_box, config="--psm 8").strip()
        
        seconds = string_to_seconds(a:=image_to_string(laptime_box, config="--psm 8"))
        logging.log(logging.DEBUG, f"{a} - {seconds}")
        matches = get_close_matches(driver, remaining_drivers, cutoff=0.3)
        logging.log(logging.DEBUG, "here2")
        if matches and len(driver) >= 3:
            quali_res = Result(matches[0], seconds)
            quali_res.car_class = get_driver(quali_res.driver).current_class()
            results.append(quali_res)
            remaining_drivers.remove(quali_res.driver)
        elif seconds:
            success = False
            results.append(Result("[NON_RICONOSCIUTO]", seconds))
        top += increment
        bottom += increment

    for driver in remaining_drivers:
        quali_res = Result(driver, None)
        quali_res.car_class = get_driver(driver).current_class()
        results.append(quali_res)

    return success, results


def recognize_race_results(
    image: str, expected_drivers: list[str], game: str
) -> list[list[Result]]:

    image = Image.open(image)

    image = image.convert("L")
    image = Contrast(image).enhance(2)
    image = ImageOps.grayscale(image)
    image = ImageOps.invert(image)

    if game == "gts":
        LEFT_1, RIGHT_1 = 380, 580
        LEFT_2, RIGHT_2 = 1330, 1445
        top = 201
        bottom = 237
        increment = 51
    elif game == "gt7":
        image = image.filter(ImageFilter.MinFilter(3))
        LEFT_1, RIGHT_1 = 307, 500
        LEFT_2, RIGHT_2 = 1360, 1490
        top = 217
        bottom = 256
        increment = 60
    else:
        raise ValueError(f'"{game}" is not supported.')

    success = True
    results = []
    remaining_drivers = expected_drivers.copy()
    for _ in range(len(expected_drivers)):
        logging.log(logging.DEBUG, "here")
        name_box = image.crop((LEFT_1, top, RIGHT_1, bottom))

        laptime_box = image.crop((LEFT_2, top, RIGHT_2, bottom))
        laptime_box.show()
        driver = image_to_string(name_box, config="--psm 8").strip()
        seconds = string_to_seconds(a:=image_to_string(laptime_box, config="--psm 8"))
        
        logging.log(logging.DEBUG, f"{a} - {seconds}")
        matches = get_close_matches(driver, remaining_drivers, cutoff=0.3)
        
        print(matches, seconds)
        if matches and len(driver) >= 3:
            race_res = Result(matches[0], seconds)
            race_res.car_class = get_driver(race_res.driver).current_class()
            results.append(race_res)
            remaining_drivers.remove(matches[0])
        elif seconds:
            success = False
            results.append(Result("[NON_RICONOSCIUTO]", seconds))
        top += increment
        bottom += increment

    for driver in remaining_drivers:
        race_res = Result(driver, None)
        race_res.car_class = get_driver(driver).current_class()
        results.append(race_res)

    return success, results


if __name__ == "__main__":

    drivers = """RTI_Shardana 2:09.164
RTI_Jacobomber06 0:00.041
maurynho993 0:00.426
XAceOfPeaksX 0:00.443
RTI_Morrisss0087 0:00.581
Turbolibix46 0:00.652
RTI_Samtor 0:01.072
RTI_andrea43race 0:01.258
Lightning_blu 0:01.625
RTI_Ninja98 0:40.000
RTI_HawkOne 0:03.802
chiasiellis ASSENTE
BlackSail ASSENTE
RTI_Strummer ASSENTE
"""
    drivers = [i.split()[0] for i in drivers.splitlines()]
    recognize_race_results(
        "./bot/app/images/test_gr4.png", drivers, "gts"
    )
