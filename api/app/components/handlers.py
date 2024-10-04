from datetime import datetime, timedelta
import logging
from collections import defaultdict
from typing import Any, cast

from fastapi import HTTPException
from sqlalchemy.orm import Session as DBSession

from schemas.standings import StandingsSchema
from schemas.resultsfile import (
    RaceRoomResultsSchema,
)
from schemas.protest import CreateProtestSchema
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
    fetch_category,
    fetch_championship,
    fetch_driver_by_discord_id,
    fetch_driver_by_rre_id,
    fetch_last_protest_number,
    fetch_teams,
    save_results,
)
from documents import ProtestDocument


RRE_GAME_ID = 3

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


def get_categories(
    db: DBSession, championship_id: int | str | None
) -> list[dict[str, Any]]:

    if championship_id == "latest":
        championship_id = None
    elif isinstance(championship_id, str):
        championship_id = int(championship_id)

    championship = fetch_championship(db, championship_id)

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

    return categories


def get_calendar(db: DBSession, category_id: int) -> list[dict[str, Any]] | None:

    category = fetch_category(db, category_id=category_id)

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


def get_standings_with_results(
    db: DBSession, category_id: int
) -> list[dict[str, Any]] | None:

    category = fetch_category(db, category_id=category_id)
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

    return response


def get_drivers_points(db: DBSession, championship_id: int):

    result: dict[int, list[list[float]]] = {}
    championship = fetch_championship(db, championship_id=championship_id)

    if not championship:
        return

    for category in championship.categories:
        result[category.id] = category.points_per_round()

    return result


def get_teams_list(db: DBSession, championship_id: int) -> list[dict[str, Any]]:
    """Returns the teams participating to the championship ordered by position."""
    team_objs = fetch_teams(db, championship_id)

    teams: list[dict[str, Any]] = []
    for team in team_objs:
        teams.append(
            {"points": team.current_championship().points, "logo": team.logo_url}
        )

    return teams


def detect_category(db: DBSession, results: RaceRoomResultsSchema):

    players_per_category: defaultdict[Category, int] = defaultdict(int)
    for player in results.sessions[2].players:
        driver = fetch_driver_by_rre_id(db, player.rre_id)
        if not driver:
            continue
        if not (category := driver.current_category()):
            continue
        players_per_category[category.category] += 1

    return max(players_per_category, key=lambda key: players_per_category[key])


async def save_rre_results(db: DBSession, results: RaceRoomResultsSchema) -> None:
    logger.info("Loading data from json file...")

    championship = fetch_championship(db, results.championship_id)

    if not championship:
        logging.info("Championship ID does not exist.")
        raise HTTPException(500, "Championship ID does not exist.")

    category = detect_category(db, results)

    date_round = {r.date: r for r in category.rounds}
    date = datetime.fromtimestamp(results.time).date()
    current_round = date_round.get(date)

    if not current_round:
        logging.info(
            "The date in the file does not match any date in the championship calendar. Results not saved."
        )
        raise HTTPException(
            400, "The date in the file does not match any date in the championship."
        )

    if current_round.is_completed:
        logging.info("File had already been saved.")
        raise HTTPException(
            422, "This file has already been saved and cannot be saved again."
        )

    driver_objs = category.active_drivers()

    if not driver_objs:
        logging.error("Failed to save results, no drivers in " + category.name)
        raise HTTPException(
            500, "No drivers participating in this category, could not save results."
        )

    drivers: dict[int, Driver] = {}
    for d in driver_objs:
        if d.driver.rre_id is not None:
            drivers[d.driver.rre_id] = d.driver
        else:
            logging.error(
                "Could not match driver due to missing rre_id in the database. Driver ID: "
                + d.driver.full_name
            )
            raise HTTPException(
                500, "Could not match driver due to a missing rre_id in the database."
            )

    reserves: list[int] = []
    for team in championship.teams:
        for reserve in team.team.reserves():
            if reserve.driver.rre_id is not None:
                reserves.append(reserve.driver.rre_id)

    expected_player_ids = reserves + list(drivers.keys())

    for session in results.sessions:
        session.remove_wild_cards(expected_player_ids)

    qualifying_results: list[QualifyingResult] = []
    races: defaultdict[Session, list[RaceResult]] = defaultdict(list)

    qualifying_data = results.sessions[1]

    pole_lap = qualifying_data.players[0].best_lap_time

    if session := current_round.qualifying_session:
        remaining_drivers = set(drivers.values())
        for player in qualifying_data.players:

            driver = drivers[player.rre_id]
            laptime = None
            gap_to_pole = None
            position = None
            remaining_drivers.discard(driver)

            match player.finish_status:
                case "DidNotFinish":
                    status = SessionCompletionStatus.dnf
                case "Disqualified":
                    status = SessionCompletionStatus.dsq
                case _:
                    position = player.position_in_class
                    status = SessionCompletionStatus.finished
                    laptime = player.best_lap_time
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
                    status=status,
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

        db.add_all(qualifying_results)

    for i, race_data in enumerate(results.sessions[2:]):
        if current_round.has_sprint_race and i == 0:
            session = Session, current_round.sprint_race
        else:
            session = current_round.long_race

        driver_with_fastest_lap = race_data.fastest_lap_scorer()
        remaining_drivers = set(drivers.values())

        for player in race_data.players:

            driver = drivers[player.rre_id]
            remaining_drivers.discard(driver)
            driver_racetime = None
            gap_to_winner = None
            position = None

            match player.finish_status:
                case "DidNotFinish":
                    status = SessionCompletionStatus.dnf
                case "Disqualified":
                    status = SessionCompletionStatus.dsq
                case _:
                    status = SessionCompletionStatus.finished
                    driver_racetime = player.total_time

                    if driver_racetime > 0:
                        gap_to_winner = race_data.gap_to_winner(player)
                    else:
                        driver_racetime = None
                        gap_to_winner = None

                    position = player.position_in_class

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
                fastest_lap=player.rre_id == driver_with_fastest_lap,
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

        db.add_all(races[session])

    current_round.is_completed = True
    save_results(db, qualifying_results, races)

    logging.info("Results saved.")


async def generate_protest_document(
    db: DBSession, protest: CreateProtestSchema
) -> tuple[bytes, str]:

    protesting_driver = fetch_driver_by_discord_id(
        db, protest.protesting_driver_discord_id
    )

    if not protesting_driver:
        logging.warning("discord_id does not match any driver in the database.")
        raise HTTPException(
            404, "Protesting driver's discord_id not found in database."
        )

    protested_driver = fetch_driver_by_discord_id(
        db, protest.protested_driver_discord_id
    )

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

    if protest.session_name == "Gara 1":
        if not rnd.sprint_race:
            logging.error("Protest contained incorrect session_name for round type.")
            raise HTTPException(400, "Received incorrect session_name for round type.")
        session = rnd.sprint_race
    elif protest.session_name == "Gara 2" or protest.session_name == "Gara":
        session = rnd.long_race
    elif protest.session_name == "Qualifica":
        session = rnd.qualifying_session
    else:
        logging.error("Protest contained invalid session_name.")
        raise HTTPException(400, "Received invalid session_name.")

    number = fetch_last_protest_number(db, category_id=category.id, round_id=rnd.id) + 1

    protest_obj = Protest(
        protested_driver=protested_driver,
        protesting_driver=protesting_driver,
        reason=protest.protest_reason,
        incident_time=protest.incident_time,
        session=session,
        round=rnd,
        category=category,
        protesting_team=protesting_driver.current_team(),
        protested_team=protested_driver.current_team(),
        number=number,
    )
    db.add(protest_obj)
    db.commit()
    protest_document = ProtestDocument(protest_obj)
    return protest_document.generate_document()


async def fetch_standings(
    db: DBSession, championship_tag: str | None
) -> list[StandingsSchema]: ...
