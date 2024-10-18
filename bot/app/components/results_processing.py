"""
Contains functions used to operate on results or parts of results.
"""

import re
from dataclasses import dataclass
from datetime import datetime
from difflib import get_close_matches

from models import DriverCategory, SessionCompletionStatus

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
            return f"(driver_name={self.driver.driver.psn_id_or_full_name}, position={self.position})"
        return f"(driver_name=None, position={self.position})"

    def __init__(
        self,
        driver: DriverCategory,
        seconds: int | None,
        status: SessionCompletionStatus = SessionCompletionStatus.dns,
    ):
        self.driver = driver
        self.seconds = seconds
        self.position = 0
        self.fastest_lap = False
        self.status = status

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

    driver_map: dict[str, DriverCategory] = {
        driver.driver.psn_id_or_full_name.replace(" ", ""): driver
        for driver in expected_drivers
    }

    results: list[Result] = []
    for line in text.splitlines():
        given_driver_name, gap = line.split()
        if given_driver_name not in driver_map:
            matches = get_close_matches(
                given_driver_name, driver_map.keys(), cutoff=0.2
            )
            if matches:
                driver_name = matches[0]
            else:
                driver_name = ""
        else:
            driver_name = given_driver_name

        if driver_name:
            driver_category = driver_map.pop(driver_name)
            seconds, status = string_to_seconds(gap)

            result = Result(driver_category, seconds, status)
            results.append(result)

    # Add unrecognized drivers to the results list.
    for given_driver_name in driver_map:
        driver_category = driver_map[given_driver_name]
        result = Result(driver_category, 0)
        results.append(result)

    return results


def results_to_text(results: list[Result]) -> str:
    """Takes a list of results and converts it to a user-friendly message."""
    text = ""
    for result in results:
        if result.seconds:
            gap = seconds_to_text(result.seconds)
        else:
            gap = result.status.value

        if result.driver:
            driver_name = result.driver.driver.psn_id_or_full_name.replace(" ", "")
        else:
            driver_name = "NON RICONOSCIUTO"

        text += f"\n{driver_name} {gap}"
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


def string_to_seconds(string: str) -> tuple[int | None, SessionCompletionStatus]:
    """Converts a string formatted as "mm:ss:SSS" to seconds.
    0 is returned when the gap to the winner wasn't available.
    SessionCompletionsStatus.dnf, dns or dsq is returne when one of those values is
    entered by the user.
    None is returned if the user didn't input anything, and the driver probably didn't
    complete the race.
    """
    string = string.lower()
    match = re.search(
        r"([0-9]{1,2}:)?([0-9]{1,2}:){0,2}[0-9]{1,2}(\.|,)[0-9]{1,3}", string
    )
    if not match:
        if string == "dns":
            return None, SessionCompletionStatus.dns
        if string == "dnf":
            return None, SessionCompletionStatus.dnf
        if string == "dsq":
            return None, SessionCompletionStatus.dsq
        return None, SessionCompletionStatus.dnf

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
        return int(matched_string * 1000), SessionCompletionStatus.finished

    seconds = (t.hour * 60 + t.minute) * 60 + t.second
    decimal_part = t.microsecond / 1_000_000

    return int((seconds + decimal_part) * 1000), SessionCompletionStatus.finished
