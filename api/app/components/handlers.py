import os
from typing import Any, cast

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Driver, RaceResult
from queries import get_category, get_championship, get_teams

URL = os.environ["DB_URL"]

engine = create_engine(url=URL)
Session = sessionmaker(engine)


def get_categories(championship_id: int | str | None):
    session = Session()

    if championship_id == "latest":
        championship_id = None
    elif isinstance(championship_id, str):
        championship_id = int(championship_id)

    championship = get_championship(session, championship_id)

    if not championship:
        return []

    categories: list[dict[str, Any]] = []
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

    calendar: list[dict[str, Any]] = []
    for championship_round in category.rounds:
        if championship_round.sprint_race:
            info = [
                {
                    "session_id": f"SR{championship_round.round_id}",
                    "race_name": championship_round.sprint_race.name,
                    "order": 1,
                },
                {
                    "session_id": f"LR{championship_round.round_id}",
                    "race_name": championship_round.long_race.name,
                    "order": 2,
                },
            ]
        else:
            info = [
                {
                    "session_id": f"LR{championship_round.round_id}",
                    "race_name": championship_round.long_race.name,
                    "order": 0,
                }
            ]

        calendar.append(
            {
                "circuit_logo": championship_round.circuit.logo_url,
                "circuit": championship_round.circuit.abbreviated_name,
                "info": info,
            }
        )
    session.close()
    return calendar


# TODO: Optimize this function by removing quali results search
def _create_driver_result_list(race_results: list[RaceResult]) -> list[dict[str, Any]]:
    """Creates a list containing"""

    driver = race_results[0].driver
    quali_results = driver.qualifying_results

    driv_res: list[dict[str, Any]] = []
    for race_result in race_results:
        if "1" in race_result.session.name:
            info_gp = f"SR{race_result.round_id}"

            quali_result = None
            for quali_res in quali_results:
                if quali_res.session_id == race_result.session_id:
                    quali_result = quali_res

            extra_points: int | float = race_result.fastest_lap

            if quali_result:
                extra_points += quali_result.points_earned

            penalties = race_result.session.get_penalty_seconds_of(driver.driver_id)

        else:
            info_gp = f"LR{race_result.round_id}"
            extra_points = race_result.fastest_lap
            penalties = race_result.session.get_penalty_seconds_of(driver.driver_id)

        position = race_result.position if race_result.position is not None else "/"

        driv_res.append(
            {
                "info_gp": info_gp,
                "position": position,
                "extra_points": int(extra_points),
                "penalties": penalties,
            }
        )

    return driv_res


def get_standings_with_results(category_id: int):
    session = Session()

    category = get_category(session=session, category_id=category_id)
    if not category:
        return

    results = category.standings_with_results()

    response = []

    if not results:
        for driver in category.active_drivers():
            team = driver.driver.current_team()

            if not team:
                team = driver.teams[-1].team

            response.append(
                {
                    "driver_id": driver.driver_id,
                    "driver_name": driver.driver.psn_id,
                    "points": 0,
                    "team": team.name,
                    "info": [],
                }
            )
        return response

    for driver_results, points_tally in results:
        driver = cast(Driver, driver_results[0].driver)
        team = driver.current_team()

        if not team:
            team = driver.teams[-1].team

        driver_summary = {
            "driver_id": driver.driver_id,
            "driver_name": driver.psn_id,
            "points": int(points_tally),
            "team": team.name,
            "info": _create_driver_result_list(
                driver_results,
            ),
        }
        response.append(driver_summary)

    session.close()

    return response


def get_drivers_points(championship_id: int):
    session = Session()

    result: dict[int, list[list]] = {}
    championship = get_championship(session, championship_id=championship_id)

    if not championship:
        return

    for category in championship.categories:
        result[category.category_id] = category.points_per_round()

    return result


def get_teams_list(championship_id: int):
    """Returns the teams participating to the championship ordered by position."""
    session = Session()
    team_objs = get_teams(session, championship_id)

    teams = []
    for team in team_objs:
        teams.append(
            {"points": team.current_championship().points, "logo": team.logo_url}
        )

    return teams
