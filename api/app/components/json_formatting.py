import os
from app.components.models import Category, RaceResult
from app.components.queries import get_championship
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

URL = os.environ["DB_URL"]

engine = create_engine(url=URL)
Session = sessionmaker(engine)


def get_categories(championship_id: int):

    session = Session()
    championship = get_championship(session, championship_id)
    if not championship:
        return []

    categories = []
    for i, category in enumerate(championship.categories):
        categories.append(
            {
                "id": category.category_id,
                "categoria": category.name,
                "campionato": category.championship_id,
                "ordinamento": i,
            }
        )
    session.close()
    return categories


def get_calendar(championship_id: int, category_id: int):
    session = Session()
    championship = get_championship(session, championship_id)

    if not championship:
        return []

    if not championship.categories:
        return []

    order = 0
    for i, category in enumerate(championship.categories):
        if category.category_id == category_id:
            order = i
            break

    calendar = []

    for championship_round in category.rounds:
        sprint_race = championship_round.has_sprint_race
        if sprint_race:
            info = [
                {
                    "id": f"SR{championship_round.round_id}",
                    "nome_gp": championship_round.sprint_race.name,
                    "ordinamento": 1,
                    "campionato": category.championship_id,
                },
                {
                    "id": f"LR{championship_round.round_id}",
                    "nome_gp": championship_round.long_race.name,
                    "ordinamento": 2,
                    "campionato": category.championship_id,
                },
            ]
        else:
            info = [
                {
                    "id": f"LR{championship_round.round_id}",
                    "ordinamento": 0,
                }
            ]

        calendar.append(
            {
                "id": championship_round.round_id,
                "ordinamento": order,
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
            quali_session = race_result.round.get_qualifying_result(driver.driver_id)
            extra_points = race_result.fastest_lap_points
            penalties = race_result.session.get_penalty_seconds_of(driver.driver_id)
            if quali_session:
                extra_points += quali_session.points_earned
        else:

            info_gp = f"LR{race_result.round_id}"
            extra_points = race_result.fastest_lap_points
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


def get_standings_with_results(championship_id: int | str, category_id: int):
    session = Session()

    if championship_id == "latest":
        championship = get_championship(session)
    else:
        championship = get_championship(session, championship_id)

    for category in championship.categories:
        if category.category_id == category_id:
            break
    if not category:
        return []

    standings = []

    for driver_results, points_tally in category.standings_with_results():
        driver = driver_results[0].driver
        team = driver.current_team()
        if not team:
            team = driver.teams[-1].team

        driver_summary = {
            "id": driver.driver_id,
            "pilota": driver.psn_id,
            "classe_auto": driver.current_class(),
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

    result: dict[list[list]] = {}
    championship = get_championship(session, championship_id=championship_id)
    for category in championship.categories:
        result[category.category_id] = category.points_per_round()
        result[category.category_id].insert()
    return result
