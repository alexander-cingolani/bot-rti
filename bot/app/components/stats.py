"""
This module contains functions which calculate various driver statistics
"""

from decimal import Decimal
import logging
from statistics import stdev

from app.components.models import Driver, RaceResult
from cachetools import TTLCache, cached
from math import pow


@cached(cache=TTLCache(maxsize=50, ttl=30))
def consistency(driver: Driver) -> int:
    """This  a number from 0 to 99 calculated on the standard deviation of
    the set of relative finishing positions.

    Args:
        results (list[RaceResult]): The results to calculate the consistency of.

    Returns:
        int: Consistency rating. (0-99)
    """

    completed_races: list[RaceResult] = list(
        filter(lambda x: x.participated, driver.race_results)
    )
    if len(completed_races) < 2:
        return 0

    positions = [race_result.relative_position for race_result in completed_races]
    participation_ratio = len(completed_races) / len(driver.race_results)
    participation_ratio = min(participation_ratio, 1)
    result = round((100 * participation_ratio) - (stdev(positions) * 3))
    return max(result, 40)


@cached(cache=TTLCache(maxsize=50, ttl=240))
def speed(driver: Driver) -> int:
    """This statistic is calculated based on the average gap between
    the driver's qualifying times and the pole man's.

    Args:
        driver (Driver): The Driver to calculate the speed rating of.

    Returns:
        int: Speed rating. (0-99)
    """

    completed_quali_sessions = list(
        filter(lambda x: x.participated, driver.qualifying_results)
    )

    if not completed_quali_sessions:
        return 0

    total_gap_percentages = 0.0
    for quali_result in completed_quali_sessions:
        total_gap_percentages += float(
            quali_result.gap_to_first
            / (quali_result.laptime - quali_result.gap_to_first)
        ) * 1000
    
    average_gap_percentage = pow(total_gap_percentages / len(completed_quali_sessions), 1.18)
    average_gap_percentage = min(total_gap_percentages, 60)
    return round(100 - average_gap_percentage)


@cached(cache=TTLCache(maxsize=50, ttl=240))
def sportsmanship(driver: Driver) -> int:
    """This statistic is calculated based on the amount and gravity of reports received.

    Args:
        driver (Driver): The Driver to calculate the sportsmanship of.

    Returns:
        int: Sportsmanship rating. (0-99)
    """

    if len(driver.race_results) < 2:
        return 0

    if not driver.received_penalties:
        return 100

    penalties = (
        (rr.time_penalty / 1.5)
        + rr.warnings
        + (rr.licence_points * 2)
        + rr.penalty_points
        for rr in driver.received_penalties
    )

    return round(100 - sum(penalties) * 3 / len(driver.race_results))


@cached(cache=TTLCache(maxsize=50, ttl=240))
def race_pace(driver: Driver) -> int:
    """This statistic is calculated based on the average gap from the race winner
    in all of the races completed by the driver.

    Args:
        driver (Driver): The Driver to calculate the race pace of.

    Return:
        int: Race pace score. (0-99)
    """
    completed_races = list(filter(lambda x: x.participated, driver.race_results))
    if not completed_races:
        return 0

    total_gap_percentages = 0.0
    for race_res in completed_races:
        total_gap_percentages += float(
            race_res.gap_to_first
            / (race_res.total_racetime - race_res.gap_to_first)
        ) * 1000

    average_gap_percentage = pow(total_gap_percentages / len(completed_races), 1.1)
    average_gap_percentage = min(average_gap_percentage, 60)
    logging.info(f"{driver.psn_id} - {average_gap_percentage}")
    return round(100 - average_gap_percentage)


@cached(cache=TTLCache(maxsize=50, ttl=240))
def stats(driver: Driver) -> tuple[int, int, int, int, int, float, float]:
    """Calculates the number of wins, podiums and poles achieved by the driver.

    Args:
        driver (Driver): The Driver to calculate the statistics of.

    Returns:
        tuple[int, int, int]: Tuple containing wins, podiums and poles in order.
    """
    wins = 0
    podiums = 0
    fastest_laps = 0
    poles = 0
    no_participation = 0

    if not driver.race_results:
        return 0, 0, 0, 0, 0, 0, 0

    positions = 0
    for race_result in driver.race_results:
        if not race_result.participated:
            no_participation += 1
            continue

        if race_result.relative_position:
            positions += race_result.relative_position
        if race_result.relative_position == 1:
            wins += 1
        if race_result.relative_position <= 3:
            podiums += 1

        fastest_laps += race_result.fastest_lap_points

    quali_positions = 0
    no_quali_participation = 0
    for quali_result in driver.qualifying_results:
        if quali_result:
            if quali_result.relative_position == 1:
                poles += 1
            if quali_result.participated:
                quali_positions += quali_result.relative_position

    races_completed = len(driver.race_results) - no_participation
    if races_completed:
        average_position = round(positions / races_completed, 2)
    else:
        average_position = 0

    qualifying_sessions_completed = (
        len(driver.qualifying_results) - no_quali_participation
    )
    if quali_positions:
        average_quali_position = round(
            quali_positions / qualifying_sessions_completed, 2
        )
    else:
        average_quali_position = 0

    return (
        wins,
        podiums,
        poles,
        fastest_laps,
        races_completed,
        average_position,
        average_quali_position,
    )
