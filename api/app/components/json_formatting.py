import os
from typing import cast

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Driver, RaceResult
from queries import get_category, get_championship

URL = os.environ["DB_URL"]

engine = create_engine(url=URL)
Session = sessionmaker(engine)


def get_categories(championship_id: int | str | None):

    if championship_id == "latest":
        championship_id = None
    elif isinstance(championship_id, str):
        championship_id = int(championship_id)
    session = Session()
    championship = get_championship(session, championship_id)
    if not championship:
        return []

    categories = []
    for i, category in enumerate(championship.categories):
        categories.append(
            {
                "category_id": category.category_id,
                "category_name": category.name,
                "championship": category.championship_id,
                "order": i,
            }
        )
    session.close()
    return categories


def get_calendar(category_id: int):
    session = Session()

    category = get_category(session=session, category_id=category_id)

    if not category:
        return

    calendar = []
    for championship_round in category.rounds:
        if championship_round.sprint_race:
            info = [
                {
                    "session_id": f"SR{championship_round.round_id}",
                    "track": championship_round.sprint_race.name,
                    "order": 1,
                    "championship": category.championship_id,
                },
                {
                    "session_id": f"LR{championship_round.round_id}",
                    "track": championship_round.long_race.name,  # type: ignore
                    "order": 2,
                    "championship": category.championship_id,
                },
            ]
        else:
            info = [
                {
                    "session_id": f"LR{championship_round.round_id}",
                    "order": 0,
                }
            ]

        calendar.append(
            {
                "round_id": championship_round.round_id,
                "order": category.display_order,
                "info": info,
            }
        )
    session.close()
    return calendar


def _create_driver_result_list(race_results: list[RaceResult]) -> list[dict]:
    """Creates a list containing"""

    driver = race_results[0].driver
    driv_res = []

    for race_result in race_results:
        if "1" in race_result.session.name:
            info_gp = f"SR{race_result.round_id}"
            quali_session = race_result.session.get_qualifying_result(driver.driver_id)
            extra_points: int | float = race_result.fastest_lap
            penalties = race_result.session.get_penalty_seconds_of(driver.driver_id)
            if quali_session:
                extra_points += quali_session.points_earned
        else:

            info_gp = f"LR{race_result.round_id}"
            extra_points = race_result.fastest_lap
            penalties = race_result.session.get_penalty_seconds_of(driver.driver_id)

        finishing_position = (
            race_result.finishing_position
            if race_result.finishing_position is not None
            else "DNS"
        )

        driv_res.append(
            {
                "info_gp": info_gp,
                "posizione": finishing_position,
                "punti_extra": int(extra_points),
                "penalita": penalties,
            }
        )

    return driv_res


def get_standings_with_results(category_id: int):
    session = Session()

    category = get_category(session=session, category_id=category_id)
    if not category:
        return

    standings = []
    for driver_results, points_tally in category.standings_with_results():
        driver = cast(Driver, driver_results[0].driver)
        team = driver.current_team()
        if not team:
            team = driver.teams[-1].team

        driver_summary = {
            "driver_id": driver.driver_id,
            "pilota": driver.psn_id,
            "car_class": driver.current_class(),
            "punti_totali": int(points_tally),
            "scuderia": team.name,
            "info": _create_driver_result_list(
                driver_results,
            ),
        }
        standings.append(driver_summary)
    session.close()
    return standings


def get_drivers_points(championship_id: int):
    session = Session()

    result: dict[int, list[list]] = {}
    championship = get_championship(session, championship_id=championship_id)

    if not championship:
        return

    for category in championship.categories:
        result[category.category_id] = category.points_per_round()

    return result
