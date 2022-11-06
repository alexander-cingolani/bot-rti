"""
This module contains functions which calculate various driver statistics
"""

from statistics import stdev

from app.components.models import Driver


def consistency(driver: Driver) -> int:
    """This  a number from 0 to 100 calculated on the standard deviation of
    the set of relative finishing positions and taking absences into account.

    Args:
        driver (Driver): The driver to calculate the consistency of.

    Returns:
        int: Consistency rating.
    """
    if len(driver.race_results) < 2:
        return 0

    race_results = []
    absences = 0
    for race_result in driver.race_results:
        if race_result.relative_position != 0:
            race_results.append(race_result.relative_position)
        else:
            absences += 1

    return round((10 - (stdev(race_results) * 0.7) - absences / 10) * 10)


def speed(driver: Driver) -> int:
    """This statistic is calculated based on the average gap between
    the driver's qualifying times and the poleman's.

    Args:
        driver (Driver): The Driver to calculate the speed rating of.

    Returns:
        int: Speed rating. (0-100)
    """
    current_category = driver.current_category()
    pole_laptimes = current_category.pole_lap_times()

    if not pole_laptimes:
        return 0

    driver_laptimes = []
    for quali_result in driver.qualifying_results:
        if quali_result.category_id == current_category.category_id:
            driver_laptimes.append()

    percentages = []
    for pole, driver_time in zip(pole_laptimes, driver_laptimes):
        percentages.append((driver_time - pole) / pole * 100)

    return round(100 - sum(percentages) / len(percentages) * 4)


def experience(driver: Driver, max_races: int) -> int:
    """This statistic is calculated based on the maximum number of races
    completed by any driver in the database. The closer the amount of races
    completed by the given driver the closer the resulting score is to 100.

    Args:
        driver (Driver): The driver to calculate the experience of.
        max_races (int): Maximum number of races completed by any driver.

    Returns:
        int: Experience rating. (0-100)
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
    return round(100 - (((max_races - len(disputed_rounds)) / max_races * 100) * 0.6))


def sportsmanship(driver: Driver) -> int:
    """This statistic is calculated based on the amount and gravity of reports received.

    Args:
        driver (Driver): The Driver to calculate the sportsmanship of.

    Returns:
        int: Sportsmanship rating. (0-100)
    """
    if not driver.race_results:
        return 0

    if not driver.received_reports:
        return 100

    penalty_score = (rr.penalty_points for rr in driver.race_results)
    
    return round(
        100
        - sum(penalty_score)
        * 10
        / len(driver.race_results)
    )


def race_pace(driver: Driver) -> int:
    """This statistic is calculated based on the average gap from the race winner
    in all of the races completed by the driver.

    Args:
        driver (Driver): The Driver to calculate the race pace of.

    Return:
        int: Race pace score. (0-100)
    """
    if not driver.race_results:
        return 0

    return round(
        100
        - (
            sum(race_result.gap_to_first for race_result in driver.race_results)
            / len(driver.race_results)
        )
        / 8
    )


def stats(driver: Driver) -> tuple[int, int, int]:
    """Calculates the number of wins, podiums and poles achieved by the driver.

    Args:
        driver (Driver): The Driver to calculate the statistics of.

    Returns:
        tuple[int, int, int]: Tuple containing wins, podiums and poles in order.
    """
    wins = 0
    podiums = 0
    poles = 0

    for race_result in driver.race_results:
        if race_result.participated:
            if race_result.relative_position == 1:
                wins += 1
            if race_result.relative_position <= 3:
                podiums += 1
            race_result.round.get_qualifying_result(driver.driver_id)
            poles += race_result.fastest_lap_points

    return wins, podiums, poles
