from datetime import datetime, timedelta
import logging
import json
import os
from collections import defaultdict
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Category, Driver, Protest, QualifyingResult, RaceResult, Session
from queries import (
    get_category,
    get_championship,
    get_driver,
    get_last_protest_number,
    get_teams,
    save_results,
)
from documents import ProtestDocument

URL = os.environ["DB_URL"]
RRE_GAME_ID = 3

engine = create_engine(url=URL)
SQLASession = sessionmaker(engine)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def get_categories(championship_id: int | str | None) -> list[dict[str, Any]]:
    session = SQLASession()

    if championship_id == "latest":
        championship_id = None
    elif isinstance(championship_id, str):
        championship_id = int(championship_id)

    championship = get_championship(session, championship_id)

    if not championship:
        return []

    categories: list[dict[str, Any]] = []
    for i, category in enumerate(championship.categories):
        provisional_results = False
        last_round = category.last_completed_round()

        categories.append(
            {
                "category_id": category.id,
                "category_name": category.name,
                "championship": category.championship_id,
                "order": i,
                "provisional": provisional_results,
            }
        )

        if not last_round:
            continue

        if (datetime.now().date() - last_round.date) < timedelta(days=1):
            provisional_results = True
        else:
            for protest in last_round.protests:
                if not protest.is_reviewed:
                    provisional_results = True
                    break
    session.close()

    return categories


def get_calendar(category_id: int) -> list[dict[str, Any]] | None:
    session = SQLASession()

    category = get_category(session=session, category_id=category_id)

    if not category:
        return

    calendar: list[dict[str, Any]] = []
    for championship_round in category.rounds:
        if championship_round.sprint_race:
            info = [
                {
                    "session_id": f"SR{championship_round.id}",
                    "race_name": championship_round.sprint_race.name,
                    "order": 1,
                },
                {
                    "session_id": f"LR{championship_round.id}",
                    "race_name": championship_round.long_race.name,
                    "order": 2,
                },
            ]
        else:
            info = [
                {
                    "session_id": f"LR{championship_round.id}",
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

        else:
            info_gp = f"LR{race_result.round_id}"
            extra_points = race_result.fastest_lap

        position = race_result.position if race_result.position is not None else "/"

        driv_res.append(
            {
                "info_gp": info_gp,
                "position": position,
                "extra_points": int(extra_points),
            }
        )

    return driv_res


def get_standings_with_results(category_id: int) -> list[dict[str, Any]] | None:
    session = SQLASession()

    category = get_category(session=session, category_id=category_id)
    if not category:
        return

    results = category.standings_with_results()

    response: list[dict[str, Any]] = []
    if not results:
        for driver in category.active_drivers():
            team = driver.driver.current_team()

            if not team:
                team = driver.driver.contracts[-1].team

            response.append(
                {
                    "driver_id": driver.driver_id,
                    "driver_name": driver.driver.abbreviated_name,
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
            team = driver.contracts[-1].team

        driver_summary = {
            "driver_id": driver.id,
            "driver_name": driver.abbreviated_name,
            "points": points_tally,
            "team": team.name,
            "info": _create_driver_result_list(
                driver_results,
            ),
        }
        response.append(driver_summary)

    session.close()

    return response


def get_drivers_points(championship_id: int):
    session = SQLASession()

    result: dict[int, list[list[float]]] = {}
    championship = get_championship(session, championship_id=championship_id)

    if not championship:
        return

    for category in championship.categories:
        result[category.id] = category.points_per_round()

    return result


def get_teams_list(championship_id: int) -> list[dict[str, Any]]:
    """Returns the teams participating to the championship ordered by position."""
    session = SQLASession()
    team_objs = get_teams(session, championship_id)

    teams: list[dict[str, Any]] = []
    for team in team_objs:
        teams.append(
            {"points": team.current_championship().points, "logo": team.logo_url}
        )

    return teams


def remove_wild_cards(
    expected_player_ids: list[int], results: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    players: list[dict[str, Any]] = []
    wild_card_counter = 0
    for player in results:
        if player["UserId"] in expected_player_ids:
            player["PositionInClass"] -= wild_card_counter
            players.append(player)
        else:
            wild_card_counter += 1
            logging.info(f"id: {player["UserId"]} name: {player["FullName"]}")
    logging.info(f"wild cards: {wild_card_counter}")
    return players


def detect_category(sqla_session, data: dict[str, Any]):

    players_per_category: defaultdict[Category, int] = defaultdict(int)
    for player in data["Sessions"][2]["Players"]:
        driver = get_driver(session=sqla_session, rre_id=player["UserId"])
        if not driver:
            continue
        if not (category := driver.current_category()):
            continue
        players_per_category[category.category] += 1

    return max(players_per_category, key=lambda key: players_per_category[key])


def gap_to_first_in_race(race_data: dict[str, Any], player: dict[str, Any]):
    gap_to_first = 0
    for winners_lap, players_lap in zip(
        race_data["Players"][0]["RaceSessionLaps"], player["RaceSessionLaps"]
    ):
        if players_lap["Time"] > 0:
            gap_to_first += players_lap["Time"] - winners_lap["Time"]
            continue

        for winner_sector, player_sector in zip(
            reversed(winners_lap["SectorTimes"]),
            reversed(players_lap["SectorTimes"]),
        ):
            if player_sector > 0:
                gap_to_first += player_sector - winner_sector
    return gap_to_first


async def save_rre_results(json_str: bytes) -> None:
    logger.info("save_rre_results called, loading data from json...")
    data = json.loads(json_str)
    sqla_session = SQLASession()
    championship = get_championship(sqla_session)

    if not championship:
        raise HTTPException(
            500, "Championship was not configured correctly in the database."
        )

    category = detect_category(sqla_session, data)

    date_round = {r.date: r for r in category.rounds}
    if not (
        current_round := date_round[datetime.fromtimestamp(data["StartTime"]).date()]
    ):
        raise HTTPException(
            400, "The date in the file does not match any date in the championship."
        )
    if current_round.is_completed:
        raise HTTPException(422, "This file has already been saved.")

    driver_objs = category.active_drivers()

    logging.info(driver_objs)

    drivers = {d.driver.rre_id: d.driver for d in driver_objs}
    reserves: list[int] = []

    for team in championship.teams:
        for reserve in team.team.reserves():
            if reserve.driver.rre_id:
                reserves.append(reserve.driver.rre_id)
    expected_player_ids = reserves + list(drivers.keys())
    logging.info(expected_player_ids)
    for session in data["Sessions"]:
        players = remove_wild_cards(expected_player_ids, session["Players"])
        session["Players"] = players

    qualifying_results: list[QualifyingResult] = []
    races: defaultdict[Session, list[RaceResult]] = defaultdict(list)

    qualifying_data = data["Sessions"][1]

    pole_lap = qualifying_data["Players"][0]["BestLapTime"]

    if session := current_round.qualifying_session:
        for player in qualifying_data["Players"]:
            rre_id = cast(int, player["UserId"])
            position = cast(int, player["PositionInClass"])
            laptime = cast(int, player["BestLapTime"])
            gap_to_first = laptime - pole_lap

            driver = drivers[rre_id]

            if laptime < 0:
                laptime = None
                gap_to_first = None

            qualifying_results.append(
                QualifyingResult(
                    session=session,
                    round_id=current_round.id,
                    category_id=category.id,
                    gap_to_first=gap_to_first,
                    laptime=laptime,
                    position=position,
                    driver_id=driver.id,
                    driver=driver,
                    participated=True,
                )
            )

        # Add qualifying results for drivers who didn't participate in quali
        for driver in driver_objs:
            for result in qualifying_results:
                if result.driver_id == driver.driver_id:
                    break
            else:
                qualifying_results.append(
                    QualifyingResult(
                        driver_id=driver.driver_id,
                        driver=driver.driver,
                        participated=False,
                        round_id=current_round.id,
                        session=session,
                        category_id=category.id,
                    )
                )
        sqla_session.add_all(qualifying_results)

    for i, race_data in enumerate(data["Sessions"][2:]):

        if current_round.has_sprint_race and i == 0:
            session = cast(Session, current_round.sprint_race)
        else:
            session = current_round.long_race

        for player in race_data["Players"]:
            if status := player.get("FinishStatus"):
                if status != "Finished":
                    break

            gap_to_first = gap_to_first_in_race(race_data, player)

            rre_id = cast(int, player["UserId"])
            position = cast(int, player["PositionInClass"])
            total_racetime = player["TotalTime"]
            driver = drivers[rre_id]

            if total_racetime < 0:
                total_racetime = None
                gap_to_first = None

            race_res = RaceResult(
                position=position,
                driver_id=driver.id,
                driver=driver,
                total_racetime=total_racetime,
                gap_to_first=gap_to_first,
                participated=True,
                round_id=current_round.id,
                session=session,
                category_id=category.id,
                fastest_lap=player["FastLap"],
            )

            races[session].append(race_res)

        # Add raceresults for drivers who didn't participate to this session
        for driver in driver_objs:
            for result in races[session]:
                if result.driver_id == driver.driver_id:
                    break
            else:
                races[session].append(
                    RaceResult(
                        driver_id=driver.driver_id,
                        driver=driver.driver,
                        participated=False,
                        round_id=current_round.id,
                        session=session,
                        category_id=category.id,
                    )
                )

        sqla_session.add_all(races[session])

    current_round.is_completed = True
    save_results(sqla_session, qualifying_results, races)

    logging.info("Results saved successfully.")


async def generate_protest_document(
    protesting_driver_discord_id: int,
    protested_driver_discord_id: int,
    protest_reason: str,
    incident_time: str,
    session_name: str,
) -> tuple[bytes, str]:

    sqla_session = SQLASession()

    protesting_driver = get_driver(
        sqla_session, discord_id=protesting_driver_discord_id
    )
    protested_driver = get_driver(sqla_session, discord_id=protested_driver_discord_id)

    category = protesting_driver.current_category()
    if not category:
        raise ValueError("Driver is not currently part of any category.")
    category = category.category
    championship = category.championship

    rounds = championship.protesting_rounds()

    rnd = {rnd.category: rnd for rnd in rounds}[category]

    if session_name == "Gara 1":
        if not rnd.sprint_race:
            raise ValueError("Received incorrect session_name for round type.")
        session = rnd.sprint_race
    elif session_name == "Gara 2" or session_name == "Gara":
        session = rnd.long_race
    elif session_name == "Qualifica":
        session = rnd.qualifying_session
    else:
        raise ValueError("Received invalid session name.")

    number = (
        get_last_protest_number(sqla_session, category_id=category.id, round_id=rnd.id)
        + 1
    )

    protest = Protest(
        protested_driver=protested_driver,
        protesting_driver=protesting_driver,
        reason=protest_reason,
        incident_time=incident_time,
        session=session,
        round=rnd,
        category=category,
        protesting_team=protesting_driver.current_team(),
        protested_team=protested_driver.current_team(),
        number=number,
    )
    sqla_session.add(protest)
    sqla_session.commit()
    protest_document = ProtestDocument(protest)
    return protest_document.generate_document()
