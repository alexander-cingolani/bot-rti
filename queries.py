"""
This module contains the necessary queries in order to retrieve specific objects
such as Protests, Categories and Drivers.
"""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import logging

import sqlalchemy as sa
import trueskill as ts
from cachetools import TTLCache, cached
from sqlalchemy import delete, desc, select, update
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.orm import Session as DBSession
from sqlalchemy.orm import joinedload

from models import (
    Category,
    Championship,
    Chat,
    Driver,
    DriverContract,
    DriverCategory,
    DriverRole,
    Penalty,
    QualifyingResult,
    RaceResult,
    Protest,
    Reprimand,
    RoundParticipant,
    Session,
    SessionCompletionStatus,
    Team,
    TeamChampionship,
)

TrueSkillEnv = ts.TrueSkill(
    draw_probability=0,
)


def fetch_championship(
    db: DBSession, championship_id: int | None = None
) -> Championship | None:
    """If not given a championship_id, returns the most recent one.

    Args:
        db (DBSession): Session to execute the query with.
        championship_id (int, optional): ID of the championship to retrieve.
            Defaults to None.

    Returns:
        Championship | None: Only None if no championships are registered in
            the database.
    """

    if championship_id:
        statement = select(Championship).where(Championship.id == championship_id)
    else:
        statement = select(Championship).order_by(desc(Championship.start))

    result = db.execute(statement).first()
    if result:
        return result[0]
    return None


def fetch_championships(db: DBSession, active: bool | None) -> list[Championship]:
    statement = select(Championship)
    if active is None:
        pass
    elif active:
        statement.where(Championship.end.is_(None)).where(
            Championship.end > datetime.now().date()
        )
    else:
        statement.where(Championship.end.isnot(None)).where(
            Championship.end < datetime.now().date()
        )

    result = db.execute(statement).all()

    if result:
        return [row[0] for row in result]
    return []


def fetch_championship_by_tag(db: DBSession, tag: str) -> Championship | None:
    statement = select(Championship).where(Championship.tag.lower() == tag.lower())
    result = db.execute(statement).one_or_none()

    if result:
        return result[0]
    return None


def fetch_team_leaders(
    db: DBSession, championship_id: int | None = None
) -> list[Driver]:
    """Returns a list of the team leaders in the championship specified by championship_id.
    If championship_id is not given, the function defaults to the latest championship.

    Args:
        db (DBSession): Session to execute the query with.
        championship_id (int, optional): _description_. Defaults to None.

    Returns:
        list[Driver]: List of drivers who were team leaders in the championship.
    """
    if not championship_id:
        championship = fetch_championship(db)
        if championship:
            championship_id = championship.id
        else:
            return []

    statement = (
        select(Driver)
        .join(DriverContract, DriverContract.driver_id == Driver.id)
        .join(Team, DriverContract.team_id == Team.id)
        .where(DriverContract.role_id == 1)
        .join(TeamChampionship, TeamChampionship.team_id == Team.id)
        .where(TeamChampionship.championship_id == championship_id)
    )

    result = db.execute(statement).all()
    if result:
        return [row[0] for row in result]
    return []


def fetch_admins(db: DBSession) -> list[Driver]:
    statement = (
        select(Driver)
        .join(DriverRole, Driver.id == DriverRole.driver_id)
        .where(DriverRole.role_id == 4)
    )

    result = db.execute(statement).all()

    if result:
        return [row[0] for row in result]
    return []


def fetch_protests(
    db: DBSession,
    round_id: int | None = None,
    category_id: int | None = None,
    is_reviewed: bool | None = None,
) -> list[Protest]:
    """Returns a list of protests matching the given arguments.

    Args:
        round_id (int, optional): round_id of the round the protests were made in. Defaults to None.
        is_reviewed (bool, optional): If the protest is reviewed or not. Defaults to None.
        is_queued (bool, optional): If the protest is queued or not. Defaults to None.
    """
    statement = select(Protest)
    if round_id:
        statement = statement.where(Protest.round_id == round_id)
    elif category_id:
        statement = statement.where(Protest.category_id == category_id)

    if is_reviewed is not None:
        statement = statement.where(Protest.is_reviewed == is_reviewed)

    result = db.execute(statement.order_by(Protest.number)).all()
    protests: list[Protest] = [res[0] for res in result]

    protests.sort(key=lambda r: r.round.date)
    return protests


@cached(cache=TTLCache(maxsize=50, ttl=30))  # type: ignore
def fetch_driver_by_psn_id(db: DBSession, psn_id: str) -> Driver | None:

    statement = select(Driver).where(Driver.psn_id == psn_id)
    try:
        result = db.execute(statement).one_or_none()
    except MultipleResultsFound:
        return None

    return result[0] if result else None


@cached(cache=TTLCache(maxsize=50, ttl=30))  # type: ignore
def fetch_driver_by_telegram_id(db: DBSession, telegram_id: str) -> Driver | None:
    statement = select(Driver).where(Driver._telegram_id == str(telegram_id))  # type: ignore
    result = db.execute(statement).first()
    return result[0] if result else None


@cached(cache=TTLCache(maxsize=50, ttl=30))  # type: ignore
def fetch_driver_by_rre_id(db: DBSession, rre_id: int) -> Driver | None:
    statement = select(Driver).where(Driver.rre_id == rre_id)
    result = db.execute(statement).first()
    return result[0] if result else None


@cached(cache=TTLCache(maxsize=50, ttl=30))  # type: ignore
def fetch_driver_by_discord_id(db: DBSession, discord_id: int) -> Driver | None:
    statement = select(Driver).where(Driver.discord_id == discord_id)
    result = db.execute(statement).first()
    return result[0] if result else None


@cached(cache=TTLCache(maxsize=50, ttl=30))  # type: ignore
def fetch_driver_by_email(db: DBSession, email: str) -> Driver | None:
    statement = select(Driver).where(Driver.email == email)
    result = db.execute(statement).first()
    return result[0] if result else None


def fetch_teams(db: DBSession, championship_id: int) -> list[Team]:
    """Returns the list of teams participating to the given championship, ordered by
    championship position.

    Args:
        db (DBSession): Session to execute the query with.
        championship_id (int): ID of the championship to get the teams of.

    Returns:
        list[Team]: Teams participating to the given championship.
    """

    statement = (
        select(TeamChampionship)
        .where(TeamChampionship.championship_id == championship_id)
        .options(joinedload(TeamChampionship.team))
        .order_by(desc(TeamChampionship.points))
    )

    result = db.execute(statement).all()
    db.commit()

    teams: list[Team] = []
    if result:
        for row in result:
            teams.append(row[0].team)
    return teams


def fetch_protest(db: DBSession, protest_id: str) -> Protest | None:
    """Returns the protest matching the given protest_id.

    Args:
        db (DBSession): Session to execute the query with.
        protest_id (int): ID of the protest to fetch.

    Returns:
        Protest | None: None if no matching protest_id was found in the database.
        Protest | None: None if no matching protest_id was found in the database.
    """
    result = db.execute(select(Protest).where(Protest.id == protest_id)).one_or_none()
    if result:
        return result[0]
    return None


def fetch_similar_driver(db: DBSession, psn_id: str) -> Driver | None:
    """Returns the Driver object with a psn_id similar to the one given.

    Args:
        db (DBSession): Session to execute the query with.
        psn_id (str): ID to search for.

    Returns:
        Driver | None: None if no driver with a psn_id similar enough was found.
    """
    result = db.execute(
        select(Driver).where(sa.func.similarity(Driver.psn_id, psn_id) > 0.4)
    ).first()

    if result:
        return result[0]
    return None


def fetch_last_protest_number(db: DBSession, category_id: int, round_id: int) -> int:
    """Gets the number of the last protest made in a specific category and round.

    Args:
        category_id (int): ID of the category of which to return the last protest.
        round_id (int): ID of the round of which to return the last protest.

    Returns:
        int: Number of the last protest made in the given round.
    """

    result = db.execute(
        select(Protest)
        .where(Protest.round_id == round_id)
        .order_by(desc(Protest.number))
    ).first()

    if result:
        return result[0].number
    return 0


def fetch_last_penalty_number(db: DBSession, round_id: int) -> int:
    """Returns the last penalty number for any given round.
    0 is returned if no penalties have been applied in that round.

    Args:
        db (DBSession): Session to execute the query from.
        round_id (int): ID of the round in which you're looking for the
            last penalty number.
    Returns:
        int: 0 if no penalties have been applied yet in that round.
    """
    result = db.execute(
        select(Penalty.number)
        .where(Penalty.round_id == round_id)
        .order_by(desc(Penalty.number))
    ).first()

    if result:
        return result[0]
    return 0


def save_qualifying_penalty(db: DBSession, penalty: Penalty) -> None:
    """Saves a protest and applies the penalties inside it (if any)
    modifying the results of the session the penalty is referred to.

    Args:
        db (DBSession): Session to execute the query with.
        penalty (Penalty): Penalty object to persist to the database.

    Raises:
        ValueError: Raised when the qualifying result record couldn't be found.
    """
    result = db.execute(
        select(QualifyingResult)
        .where(QualifyingResult.driver_id == penalty.driver_id)
        .where(QualifyingResult.session_id == penalty.session_id)
    ).one_or_none()

    if not result:
        raise ValueError("QualifyingResult not in database.")

    # penalty.protested_driver_id = penalty.driver.driver_id
    db.add(penalty)
    db.commit()


def _update_ratings(results: list[RaceResult]) -> None:
    """Updates the driver ratings"""
    ranks: list[int] = []
    rating_groups: list[tuple[ts.Rating]] = []
    race_results: list[RaceResult] = []
    for result in results:
        driver: Driver = result.driver

        if result.status == SessionCompletionStatus.finished:
            rating_groups.append((ts.Rating(float(driver.mu), float(driver.sigma)),))
            ranks.append(result.position)  # type: ignore
            race_results.append(result)

    rating_groups = TrueSkillEnv.rate(rating_groups, ranks)  # type: ignore

    for rating_group, result in zip(rating_groups, race_results):  # type: ignore
        result.mu = result.driver.mu = Decimal(str(rating_group[0].mu))  # type: ignore
        result.sigma = result.driver.sigma = Decimal(str(rating_group[0].sigma))


def reverse_qualifying_penalty(db: DBSession, penalty: Penalty) -> None:
    """Reverses a qualifying penalty."""
    result = db.execute(
        select(QualifyingResult)
        .where(QualifyingResult.driver_id == penalty.driver_id)
        .where(QualifyingResult.session_id == penalty.session_id)
    ).one_or_none()

    if not result:
        raise ValueError("QualifyingResult not in database.")

    for driver_category in penalty.driver.categories:
        if driver_category.category_id == penalty.category.category_id:
            driver_category.licence_points += penalty.licence_points
            driver_category.warnings -= penalty.warnings

    db.commit()


def save_results(
    db: DBSession,
    qualifying_results: list[QualifyingResult],
    races: dict[Session, list[RaceResult]],
) -> None:
    """"""

    driver_points: defaultdict[Driver, float] = defaultdict(float)
    category = qualifying_results[0].category

    # Calculates points earned in qualifying by each driver.
    db.add_all(qualifying_results)
    for quali_result in qualifying_results:
        points_earned = quali_result.points_earned
        driver_points[quali_result.driver] += points_earned

        # Should never be None, since every driver who takes part in a race/qualifying session
        # must also be part of a team.
        team = quali_result.driver.current_team()

        if team is None:
            logging.error(
                "Driver {d} is not associated with a category".format(
                    quali_result.driver.id
                )
            )
            raise ValueError(
                "Driver {d} is not associated with a category".format(
                    quali_result.driver.id
                )
            )

        for team_championship in team.championships:
            if team_championship.championship_id == category.championship_id:
                team_championship.points += float(points_earned)
                break

    # Calculates points earned across all race sessions by each driver.
    for _, race_results in races.items():
        db.add_all(race_results)
        _update_ratings(race_results)
        for race_result in race_results:
            points_earned = race_result.points_earned
            driver_points[race_result.driver] += points_earned

            team = race_result.driver.current_team()
            if team is None:
                logging.error(
                    "Driver {d} is not associated with a category".format(
                        race_result.driver.id
                    )
                )
                raise ValueError(
                    "Driver {d} is not associated with a category".format(
                        race_result.driver.id
                    )
                )

            for team_championship in team.championships:
                if team_championship.championship_id == category.championship_id:
                    team_championship.points += float(points_earned)
                    break

    drivers = qualifying_results[0].category.drivers

    for driver in drivers:
        driver.points += driver_points[driver.driver]
        driver_points.pop(driver.driver)

    # Remaining drivers are reserves who are covering in this category for the first time
    if driver_points:
        category = qualifying_results[0].category
        for driver, points in driver_points.items():
            dc = DriverCategory(
                driver=driver,
                category=category,
                race_number=0,
                points=points,
            )
            db.add(dc)
            drivers.append(dc)

    drivers.sort(key=lambda d: d.points, reverse=True)

    for p, driver in enumerate(drivers, 1):
        driver.position = p

    db.commit()


def save_and_apply_penalty(db: DBSession, penalty: Penalty) -> None:
    """Saves a protest and applies the penalties inside it (if any)
    modifying the results of the session the penalty is referred to, while also
    deducting lost points from the driver's team points tally.

    Args:
        db (DBSession): Session to execute the query with.
        penalty (Penalty): Penalty object to persist to the database.
    """

    # Applies licence points and warnings to the penalised driver's record.
    for driver_category in penalty.driver.categories:
        if driver_category.category_id == penalty.category.id:
            driver_category.licence_points -= penalty.licence_points
            driver_category.warnings += penalty.warnings
            driver_category.points -= penalty.points

            if penalty.points:
                if team := driver_category.driver.current_team():
                    team_championship = team.get_championship(
                        driver_category.category.championship_id
                    )
                    team_championship.points -= penalty.points  # type:  ignore
                # Sort drivers in case standings changed
                drivers = [d for d in driver_category.category.drivers]
                drivers.sort(key=lambda d: d.points, reverse=True)
                for pos, driver in enumerate(drivers):
                    driver.position = pos

    # If no time penalty was issued there aren't any changes left to make, so it saves and returns.
    if not penalty.time_penalty:
        db.add(penalty)
        db.commit()
        return

    if penalty.session.is_quali:
        save_qualifying_penalty(db, penalty)
        return

    # Gets the race results from the relevant session ordered by finishing position.
    rows = db.execute(
        select(RaceResult)
        .where(RaceResult.session_id == penalty.session.id)
        .where(RaceResult.status == SessionCompletionStatus.finished)
        .order_by(RaceResult.position)
    ).all()

    penalised_race_result: RaceResult | None = None
    race_results: list[RaceResult] = []
    driver_points: dict[Driver, float] = {}
    # Finds the race result belonging to the penalised driver and applies the time penalty
    for row in rows:
        race_result: RaceResult = row[0]
        race_results.append(race_result)
        driver_points[race_result.driver] = race_result.points_earned
        if (
            race_result.driver_id == penalty.driver.id
            and race_result.status == SessionCompletionStatus.finished
        ):
            race_result.total_racetime += penalty.time_penalty  # type: ignore
            penalised_race_result = race_result

    # Defers the time penalty in case the penalised driver did not complete the race
    if not penalised_race_result:
        if penalty.session.name == "Gara 1":
            driver_points.clear()
            # If penalty was applied in first race, check if driver completed the second race and apply it there
            race_results = penalty.round.long_race.race_results
            for race_result in race_results:
                race_results.append(race_result)
                driver_points[race_result.driver] = race_result.points_earned
                if (
                    race_result.driver_id == penalty.driver.id
                    and race_result.status == SessionCompletionStatus.finished
                ):
                    race_result.total_racetime += penalty.time_penalty  # type: ignore
                    penalised_race_result = race_result
                    break

        elif penalty.session.name in ("Gara", "Gara 2"):
            category = penalty.category
            session = penalty.session
            index = category.rounds.index(session.round) + 1

            if len(category.rounds) == index:
                db.commit()
                return

            db.commit()
            return

    # Sorts the race results after the time penalty has been applied
    race_results.sort(key=lambda x: x.total_racetime)  # type: ignore

    # Applies the correct finishing position, recalculates the gap_to_first.
    best_time = race_results[0].total_racetime
    for position, result in enumerate(race_results, start=1):
        result.gap_to_first = result.total_racetime - best_time  # type: ignore
        result.position = position

    # Remove points earned before the penalty and add the points after the penalty.
    drivers: list[DriverCategory] = []
    for race_result in race_results:
        driver = race_result.driver

        driver_category: DriverCategory = driver.current_category()  # type: ignore

        team = driver.current_team()

        if team is None:
            logging.error(
                "Driver {d} is not associated with a category".format(
                    race_result.driver.id
                )
            )
            raise ValueError(
                "Driver {d} is not associated with a category".format(
                    race_result.driver.id
                )
            )
        drivers.append(driver_category)

        for team_championship in team.championships:
            if team_championship.championship_id == driver_category.driver_id:

                driver_category.points -= driver_points[driver]
                team_championship.points -= driver_points[driver]

                points_earned = race_result.points_earned
                driver_category.points += points_earned
                team_championship.points += points_earned
                break

    drivers.sort(key=lambda d: d.points, reverse=True)

    # Apply correct championship positions.
    for pos, driver in enumerate(drivers, start=1):
        driver.position = pos
        if driver.driver_id == penalty.driver_id:
            break

    db.add(penalty)
    db.commit()
    return


def fetch_category(db: DBSession, category_id: int) -> Category | None:
    """Returns a Category given an id.

    Args:
        db (DBSession): Session to execute the query with.
        category_id (int): ID of the category to fetch.

    Returns:
        Category | None: None if no matching category is found.
    """

    result = db.execute(
        select(Category).where(Category.id == category_id)
    ).one_or_none()

    if result:
        return result[0]
    return None


def delete_protest(db: DBSession, protest_id: str) -> None:
    """Deletes the protest matching the protest_id from the database.

    Args:
        db (DBSession): Session to execute the query with.
        protest_id (str): ID of the protest to delete.
    """
    db.execute(delete(Protest).where(Protest.id == protest_id))
    db.commit()
    db.expire_all()


def fetch_drivers(db: DBSession) -> list[Driver]:
    """Returns a list containing all the drivers currently saved in the database.

    Args:
        db (DBSession): Session to execute the query with.
    """

    result = db.execute(select(Driver)).all()

    return [r[0] for r in result]


def fetch_round_participants(db: DBSession, round_id: int) -> list[RoundParticipant]:
    """Returns a list containing the participants to a particular round.

    Args:
        db (DBSession): Session to execute the query with.
    """
    result = db.execute(
        select(RoundParticipant).where(RoundParticipant.round_id == round_id)
    ).all()

    return [r[0] for r in result]


def update_participant_status(db: DBSession, participant: RoundParticipant):
    stmt = (
        update(RoundParticipant)
        .where(
            RoundParticipant.driver_id == participant.driver_id,
            RoundParticipant.round_id == participant.round_id,
        )
        .values(participating=participant.participating)
    )

    db.execute(stmt)
    db.commit()


def delete_chat(db: DBSession, chat_id: int):
    stmt = delete(Chat).where(Chat.id == chat_id)
    db.execute(stmt)
    db.commit()


@cached(cache=TTLCache(maxsize=50, ttl=20000))  # type: ignore
def fetch_reprimand_types(db: DBSession) -> list[Reprimand]:
    result = db.execute(select(Reprimand)).all()

    return [r[0] for r in result]


def reverse_penalty(db: DBSession, penalty: Penalty):
    """Reverses and deletes the given penalty."""

    delete_penalty_stmt = delete(Penalty).where(Penalty.id == penalty.id)
    category = penalty.category
    drivers = category.active_drivers()

    if penalty.protest:
        penalty.protest.is_reviewed = False

    # Gives back licence points, championship points, removes reprimands
    # and warnings on the penalised driver's record.
    for driver_category in penalty.driver.categories:
        if driver_category.category_id == penalty.category_id:
            if penalty.reprimand:
                driver_category.reprimands -= 1

            driver_category.licence_points += penalty.licence_points
            driver_category.warnings -= penalty.warnings
            driver_category.points += penalty.points
            break
    else:
        raise RuntimeError()

    # If no time penalty was issued, give back points to the driver's team (if any), save and return.
    if not penalty.time_penalty:
        driver_team = penalty.driver.current_team()
        if driver_team and penalty.points:
            teams: list[TeamChampionship] = []
            for team in category.championship.teams:
                teams.append(team)
                if driver_team.id == team.team_id:
                    team.points += penalty.points

        db.execute(delete_penalty_stmt)
        db.commit()
        return

    # Gets the race results from the relevant session ordered by finishing position.
    rows = db.execute(
        select(RaceResult)
        .where(RaceResult.session_id == penalty.session_id)
        .where(RaceResult.status == SessionCompletionStatus.finished)
        .order_by(RaceResult.position)
    ).all()

    race_results: list[RaceResult] = []
    # Finds the no longer penalised driver's race result and removes the time penalty from it.
    driver_points_before_penalty_deletion: dict[Driver, float] = {}
    for i, row in enumerate(rows):
        race_result: RaceResult = row[0]
        race_results.append(race_result)
        driver_points_before_penalty_deletion[race_result.driver] = (
            race_result.points_earned
        )

        # Remove the penalty from the driver's result
        if race_result.driver_id == penalty.driver_id:
            race_result.total_racetime -= penalty.time_penalty  # type: ignore
            race_result.gap_to_first -= penalty.time_penalty  # type: ignore

            if (
                len(row) < i + 1
                and rows[i - 1][0].gap_to_first < race_result.gap_to_first
            ):
                db.execute(delete_penalty_stmt)
                db.commit()
                return

    race_results.sort(key=lambda x: x.total_racetime)  # type: ignore

    # Applies the correct finishing position, recalculates the gap_to_first and points.
    best_time = race_results[0].total_racetime
    driver_points_after_penalty_deletion: dict[Driver, float] = {}
    for position, result in enumerate(race_results, start=1):
        result.gap_to_first = result.total_racetime - best_time  # type: ignore
        result.position = position
        driver_points_after_penalty_deletion[result.driver] = result.points_earned

    # Apply championships standings changes
    for driver_category in drivers:
        driver = driver_category.driver
        if driver in driver_points_after_penalty_deletion:
            delta = (
                driver_points_before_penalty_deletion[driver]
                - driver_points_after_penalty_deletion[driver]
            )
            driver_category.points -= delta
            driver.current_team().get_championship(category.championship_id).points -= delta  # type: ignore

    drivers.sort(key=lambda d: d.points, reverse=True)

    for position, driver_category in enumerate(drivers):
        driver_category.position = position

    db.execute(delete_penalty_stmt)
    db.commit()
    return
