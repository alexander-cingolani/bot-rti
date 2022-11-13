"""
This module contains functions which calculate various driver statistics
"""

from statistics import stdev

from app.components.models import Driver, RaceResult
from cachetools import TTLCache, cached


@cached(cache=TTLCache(maxsize=50, ttl=30))
def consistency(driver: Driver) -> int:
    """This  a number from 0 to 99 calculated on the standard deviation of
    the set of relative finishing positions.

    Args:
        results (list[RaceResult]): The results to calculate the consistency of.

    Returns:
        int: Consistency rating. (0-99)
    """

    race_results: list[RaceResult] = list(
        filter(lambda x: x.participated, driver.race_results)
    )
    if len(race_results) < 2:
        return 0
    positions = [race_result.relative_position for race_result in race_results]

    return round(99 - (stdev(positions) * 7))


@cached(cache=TTLCache(maxsize=50, ttl=30))
def speed(driver: Driver) -> int:
    """This statistic is calculated based on the average gap between
    the driver's qualifying times and the poleman's.

    Args:
        driver (Driver): The Driver to calculate the speed rating of.

    Returns:
        int: Speed rating. (0-99)
    """
    current_category = driver.current_category()
    pole_laptimes = current_category.pole_lap_times()

    if not pole_laptimes:
        return 0

    driver_laptimes = []
    poles = []
    for quali_result, pole in zip(driver.qualifying_results, pole_laptimes):
        if quali_result.category_id == current_category.category_id:
            if quali_result.laptime:
                driver_laptimes.append(quali_result.laptime)
                poles.append(pole)

    percentages = []
    for pole, driver_time in zip(poles, driver_laptimes):
        percentages.append((driver_time - pole) / pole * 99)

    if percentages:
        return round(99 - sum(percentages) / len(percentages) * 3)
    return 0


@cached(cache=TTLCache(maxsize=50, ttl=30))
def experience(driver: Driver, max_races: int) -> int:
    """This statistic is calculated based on the maximum number of races
    completed by any driver in the database. The closer the amount of races
    completed by the given driver the closer the resulting score is to 99.

    Args:
        driver (Driver): The driver to calculate the experience of.
        max_races (int): Maximum number of races completed by any driver.

    Returns:
        int: Experience rating. (0-99)
    """

    if not max_races:
        return 0

    disputed_rounds = []
    for race_result in driver.race_results:
        if (
            race_result.gap_to_first != 0
            and race_result.round.round_id not in disputed_rounds
        ):
            disputed_rounds.append(race_result.round.round_id)

    if not disputed_rounds:
        return 0

    return round(99 - ((max_races - len(disputed_rounds)) / max_races * 99) * 0.6)


@cached(cache=TTLCache(maxsize=50, ttl=30))
def sportsmanship(driver: Driver) -> int:
    """This statistic is calculated based on the amount and gravity of reports received.

    Args:
        driver (Driver): The Driver to calculate the sportsmanship of.

    Returns:
        int: Sportsmanship rating. (0-99)
    """

    if not driver.race_results:
        return 0

    if not driver.received_reports:
        return 99

    penalty_score = (rr.penalty_points for rr in driver.race_results)

    if penalty_score:
        return round(99 - sum(penalty_score) * 10 / len(driver.race_results))
    return 0


# @cached(cache=cache)
def race_pace(driver: Driver) -> int:
    """This statistic is calculated based on the average gap from the race winner
    in all of the races completed by the driver.

    Args:
        driver (Driver): The Driver to calculate the race pace of.

    Return:
        int: Race pace score. (0-99)
    """
    race_results = list(filter(lambda x: x.participated, driver.race_results))
    if not race_results:
        return 0

    return round(
        99
        - (
            sum(race_result.gap_to_first for race_result in race_results)
            / (len(race_results) * 2.5)
        )
    )


@cached(cache=TTLCache(maxsize=50, ttl=30))
def stats(driver: Driver) -> tuple[int, int, int]:
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

    for race_result in driver.race_results:
        if race_result.participated:
            if race_result.relative_position == 1:
                wins += 1
            if race_result.relative_position <= 3:
                podiums += 1

            quali_res = race_result.round.get_qualifying_result(
                driver_id=driver.driver_id
            )
            if quali_res:
                poles += 1 if quali_res.relative_position == 1 else 0
            fastest_laps += race_result.fastest_lap_points

    return wins, podiums, poles, fastest_laps
