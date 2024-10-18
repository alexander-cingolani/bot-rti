"""
Contains functions used to operate on results or parts of results.
"""

import re
from dataclasses import dataclass
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
        milliseconds: int | None,
        status: SessionCompletionStatus = SessionCompletionStatus.dns,
    ):
        self.driver = driver
        self.milliseconds = milliseconds
        self.position = 0
        self.fastest_lap = False
        self.status = status

    def __hash__(self) -> int:
        return hash(str(self))

    def prepare_result(self, best_time: int, position: int):
        """Modifies Result to contain valid data for a RaceResult."""
        if self.milliseconds is None:
            self.position = None
        elif self.milliseconds == 0:
            self.milliseconds = None
            self.position = position
        elif position == 1:
            self.position = position
            self.milliseconds = best_time
        else:
            self.milliseconds = self.milliseconds + best_time
            self.position = position


def text_to_results(
    text: str, expected_drivers: list[DriverCategory]
) -> tuple[list[Result], list[str]]:
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
    not_matched: list[str] = []
    results: list[Result] = []
    for line in text.splitlines():
        given_driver_name, gap = line.split()
        if given_driver_name not in driver_map:
            matches = get_close_matches(
                given_driver_name, driver_map.keys(), cutoff=0.3
            )
            if matches:
                driver_name = matches[0]
            else:
                driver_name = ""
                not_matched.append(given_driver_name)
        else:
            driver_name = given_driver_name

        if driver_name:
            driver_category = driver_map.pop(driver_name)
            milliseconds, status = string_to_milliseconds(gap)

            result = Result(driver_category, milliseconds, status)
            results.append(result)

    # Add unrecognized drivers to the results list.
    for given_driver_name in driver_map:
        driver_category = driver_map[given_driver_name]
        result = Result(driver_category, 0)
        results.append(result)

    return results, not_matched


def results_to_text(results: list[Result]) -> str:
    """Takes a list of results and converts it to a user-friendly message."""
    text = ""
    for result in results:
        if result.milliseconds:
            gap = seconds_to_text(result.milliseconds)
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


def string_to_milliseconds(string: str) -> tuple[int | None, SessionCompletionStatus]:
    """Converts a string formatted as "mm:ss:SSS" to seconds.
    0 is returned when the gap to the winner wasn't available.
    SessionCompletionsStatus.dnf, dns or dsq is returne when one of those values is
    entered by the user.
    None is returned if the user didn't input anything, and the driver probably didn't
    complete the race.
    """

    pattern = re.compile(r"(?:(\d+):)?(?:(\d+):)?(\d+)(?:\.(\d+))?")
    match = pattern.match(string.strip())

    if not match:
        if string == "dns":
            return None, SessionCompletionStatus.dns
        if string == "dnf":
            return None, SessionCompletionStatus.dnf
        if string == "dsq":
            return None, SessionCompletionStatus.dsq
        return None, SessionCompletionStatus.dnf

    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0
    seconds = int(match.group(3)) if match.group(3) else 0
    milliseconds = int(match.group(4).ljust(3, "0")) if match.group(4) else 0

    milliseconds += (hours * 3600 + minutes * 60 + seconds) * 1000

    return milliseconds, SessionCompletionStatus.finished
