import re
from dataclasses import dataclass
from datetime import timedelta

from app.components.models import CarClass, Category


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


def _prepare_result(raceres: Result, best_time: float, position: int) -> Result:
    if raceres.seconds is None:
        raceres.position = None
    elif raceres.seconds == 0:
        raceres.seconds = None
        raceres.position = position
    elif position == 1:
        raceres.position = position
        raceres.seconds = best_time
    else:
        raceres.seconds = raceres.seconds + best_time
        raceres.position = position
    return raceres


def separate_car_classes(
    category: Category, results: list[Result]
) -> dict[CarClass, list[Result]]:

    separated_classes = {
        car_class.car_class_id: [] for car_class in category.car_classes
    }
    if isinstance(results[0], Result):
        best_laptime = results[0].seconds

        for pos, result in enumerate(results, start=1):
            if result.car_class.car_class_id in separated_classes:
                separated_classes[result.car_class.car_class_id].append(
                    _prepare_result(result, best_laptime, pos)
                )
        return separated_classes

    best_laptime = results[0].total_racetime

    for pos, result in enumerate(results, start=1):
        car_class = result.driver.current_class().car_class_id
        if car_class in separated_classes:
            separated_classes[car_class].append(result)
        return separated_classes
