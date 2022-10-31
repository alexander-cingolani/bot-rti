from statistics import stdev
from app.components.models import Driver


def consistency(driver: Driver) -> int:
    """Returns a number from 0 to 100 calculated on the standard deviation of 
    the set of finishing positions and taking absences into account. """
    if not driver.race_results:
        return 0

    race_results = []
    absences = 0
    for race_result in driver.race_results:
        if race_result.finishing_position != 0:
            race_results.append(race_result.finishing_position)
        else:
            absences += 1

    return round((10 - (stdev(race_results) * 0.7) - absences / 10) * 10)


def speed(driver: Driver) -> int:
    """Returns an int between 0 and 100 indicating """
    current_category = driver.current_category()
    pole_laptimes = current_category.pole_lap_times()

    if not len(pole_laptimes):
        return 0

    driver_laptimes = []
    for quali_result in driver.qualifying_results:
        if quali_result.category_id == current_category.category_id:
            driver_laptimes.append()

    percentages = []
    for pole, driver_time in zip(pole_laptimes, driver_laptimes):
        percentages.append((driver_time - pole) / pole * 100)

    return round(100 - sum(percentages) / len(percentages) * 4)


def experience(driver: Driver, max_races) -> int:

    if not max_races:
        return 0

    disputed_rounds = []
    for race_result in driver.race_results:
        if (
            race_result.gap_to_first != 0
            and race_result.round.round_id not in disputed_rounds
        ):
            disputed_rounds.append(race_result.round.round_id)

    if not len(disputed_rounds):
        return 0
    return round(100 - (((max_races - len(disputed_rounds)) / max_races * 100) * 0.6))


def sportsmanship(driver: Driver) -> int:

    if not driver.race_results:
        return 0

    return round(
        100
        - sum((rr.penalty_points for rr in driver.race_results))
        * 10
        / len(driver.race_results)
    )


def race_pace(driver: Driver) -> int:

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


def stats(driver: Driver) -> int:
    """Returns number of wins, podiums and poles and fastest laps achieved by the driver."""
    wins = 0
    podiums = 0
    poles = 0

    for rr in driver.race_results:
        if rr.finishing_position == 1:
            wins += 1
        if rr.finishing_position <= 3:
            podiums += 1

        poles += rr.fastest_lap_points

    return wins, podiums, poles
