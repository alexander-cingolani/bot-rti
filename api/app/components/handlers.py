from datetime import datetime, timedelta
import logging
import json
import os
from collections import defaultdict
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as DBSession

from models import (
    Category,
    Driver,
    Protest,
    QualifyingResult,
    RaceResult,
    Session,
    SessionCompletionStatus,
)
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


def _create_driver_result_list(race_results: list[RaceResult]) -> list[dict[str, Any]]:
    driver_results: list[dict[str, Any]] = []
    for race_result in race_results:
        if "1" in race_result.session.name or not race_result.round.has_sprint_race:
            info_gp = f"SR{race_result.round_id}"

            extra_points: int | float = race_result.fastest_lap_points
            quali_results = race_result.round.qualifying_results
            for quali_result in quali_results:
                if quali_result.driver_id == race_result.driver_id:
                    extra_points += quali_result.points_earned
                    break
        else:
            info_gp = f"LR{race_result.round_id}"
            extra_points = race_result.fastest_lap_points

        position = race_result.position if race_result.position else "/"
        race_result.points_earned
        driver_results.append(
            {
                "info_gp": info_gp,
                "position": position,
                "extra_points": extra_points,
            }
        )

    return driver_results


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
    return players


def detect_category(sqla_session: DBSession, data: dict[str, Any]):

    players_per_category: defaultdict[Category, int] = defaultdict(int)
    for player in data["Sessions"][2]["Players"]:
        driver = get_driver(session=sqla_session, rre_id=player["UserId"])
        if not driver:
            continue
        if not (category := driver.current_category()):
            continue
        players_per_category[category.category] += 1

    return max(players_per_category, key=lambda key: players_per_category[key])


def calculate_gap_to_winner(race_data: dict[str, Any], player: dict[str, Any]):
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


def fastest_lap_scorer(race_data: dict[str, Any]) -> int:
    fastest_lap = float("inf")
    driver_with_fastest_lap = 0
    for player in race_data["Players"]:
        for lap in player["RaceSessionLaps"]:
            if lap["Time"] <= 0:
                continue

            if lap["Time"] > 0 and lap["Time"] < fastest_lap:
                driver_with_fastest_lap = player["UserId"]
                fastest_lap = lap["Time"]

    return driver_with_fastest_lap


async def save_rre_results(json_str: bytes) -> None:
    logger.info("Loading data from json file...")
    data = json.loads(json_str)
    sqla_session = SQLASession()
    championship = get_championship(sqla_session)

    if not championship:
        logging.info("Incorrect championship configuration, results not saved.")
        raise HTTPException(
            500, "Championship was not configured correctly in the database."
        )

    category = detect_category(sqla_session, data)

    date_round = {r.date: r for r in category.rounds}
    start_date = datetime.fromtimestamp(data["StartTime"]).date()
    current_round = date_round.get(start_date)

    if not current_round:
        logging.info("The date in the file did not match any date in the championship calendar. Results not saved.")
        raise HTTPException(
            400, "The date in the file does not match any date in the championship."
        )

    if current_round.is_completed:
        logging.info("File had already been saved.")
        raise HTTPException(422, "This file has already been saved and cannot be saved again.")

    driver_objs = category.active_drivers()

    if not driver_objs:
        logging.error("Failed to save results, no drivers in " + category.name)
        raise HTTPException(500, "No drivers participating in this category, could not save results.")

    drivers: dict[int, Driver] = {}
    for d in driver_objs:
        if d.driver.rre_id is not None:
            drivers[d.driver.rre_id] = d.driver
        else:
            logging.error("Could not match driver due to missing rre_id in the database. Driver ID: " + d.driver.full_name)
            raise HTTPException(500, "Could not match driver due to a missing rre_id in the database.")

    reserves: list[int] = []
    for team in championship.teams:
        for reserve in team.team.reserves():
            if reserve.driver.rre_id is not None:
                reserves.append(reserve.driver.rre_id)

    expected_player_ids = reserves + list(drivers.keys())

    for session in data["Sessions"]:
        session["Players"] = remove_wild_cards(expected_player_ids, session["Players"])

    qualifying_results: list[QualifyingResult] = []
    races: defaultdict[Session, list[RaceResult]] = defaultdict(list)

    qualifying_data = data["Sessions"][1]

    pole_lap = qualifying_data["Players"][0]["BestLapTime"]

    if session := current_round.qualifying_session:
        remaining_drivers = set(drivers.values())
        for player in qualifying_data["Players"]:
            
            rre_id = cast(int, player["UserId"])
            driver = drivers[rre_id]
            laptime = None
            gap_to_pole = None
            position = None
            remaining_drivers.discard(driver)

            match player.get("FinishStatus"):
                case "DidNotFinish":
                    status = SessionCompletionStatus.dnf
                case "Disqualified":
                    status = SessionCompletionStatus.dsq
                case _:
                    position = cast(int, player["PositionInClass"])
                    status = SessionCompletionStatus.finished
                    laptime = cast(int, player["BestLapTime"])
                    if laptime > 0:
                        gap_to_pole = laptime - pole_lap
                    else:
                        laptime = None
                        gap_to_pole = None

            qualifying_results.append(
                QualifyingResult(
                    session=session,
                    round_id=current_round.id,
                    category_id=category.id,
                    gap_to_first=gap_to_pole,
                    laptime=laptime,
                    position=position,
                    driver_id=driver.id,
                    driver=driver,
                    status=status
                )
            )

        for driver in remaining_drivers:
            qualifying_results.append(
                QualifyingResult(
                    driver_id=driver.id,
                    driver=driver,
                    status=SessionCompletionStatus.dns,
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

        driver_with_fastest_lap = fastest_lap_scorer(race_data)
        remaining_drivers = set(drivers.values())

        for player in race_data["Players"]:

            rre_id = cast(int, player["UserId"])
            driver = drivers[rre_id]
            remaining_drivers.discard(driver)
            driver_racetime = None
            gap_to_winner = None
            position = None

            match player.get("FinishStatus"):
                case "DidNotFinish":
                    status = SessionCompletionStatus.dnf
                case "Disqualified":
                    status = SessionCompletionStatus.dsq
                case _:
                    status = SessionCompletionStatus.finished
                    driver_racetime = player["TotalTime"]

                    if driver_racetime > 0:
                        gap_to_winner = calculate_gap_to_winner(race_data, player)
                    else:
                        driver_racetime = None
                        gap_to_winner = None

                    position = cast(int, player["PositionInClass"])

            race_result = RaceResult(
                position=position,
                driver_id=driver.id,
                driver=driver,
                total_racetime=driver_racetime,
                gap_to_first=gap_to_winner,
                status=status,
                round_id=current_round.id,
                session=session,
                category_id=category.id,
                fastest_lap=rre_id == driver_with_fastest_lap,
            )

            races[session].append(race_result)

        for driver in remaining_drivers:
            races[session].append(
                RaceResult(
                    driver_id=driver.id,
                    driver=driver,
                    status=SessionCompletionStatus.dns,
                    round_id=current_round.id,
                    session=session,
                    category_id=category.id,
                )
            )

        sqla_session.add_all(races[session])

    current_round.is_completed = True
    save_results(sqla_session, qualifying_results, races)

    logging.info("Results saved.")


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

    if not protesting_driver:
        logging.warning("discord_id does not match any driver in the database.")
        raise HTTPException(404, "Protesting driver's discord_id not found in database.")
    
    protested_driver = get_driver(sqla_session, discord_id=protested_driver_discord_id)

    if not protested_driver:
        logging.warning("discord_id does not match any driver in the database.")
        raise HTTPException(404, "Protested driver's discord_id not found in database.")

    category = protesting_driver.current_category()
    if not category:
        raise ValueError("Driver is not currently part of any category.")

    category = category.category
    championship = category.championship

    rounds = championship.protesting_rounds()

    rnd = {rnd.category: rnd for rnd in rounds}.get(category)

    if not rnd:
        logging.info("Protest sent outside of the report window.")
        raise HTTPException(410, "Protest was sent outside of the report window.")

    if session_name == "Gara 1":
        if not rnd.sprint_race:
            logging.error("Protest contained incorrect session_name for round type.")
            raise HTTPException(400, "Received incorrect session_name for round type.")
        session = rnd.sprint_race
    elif session_name == "Gara 2" or session_name == "Gara":
        session = rnd.long_race
    elif session_name == "Qualifica":
        session = rnd.qualifying_session
    else:
        logging.error("Protest contained invalid session_name.")
        raise HTTPException(400, "Received invalid session_name.")

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
