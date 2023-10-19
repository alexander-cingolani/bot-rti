"""
This module contains the necessary queries in order to retrieve specific objects
such as Reports, Categories and Drivers.
"""

from collections import defaultdict
from decimal import Decimal

import sqlalchemy as sa
import trueskill as ts
from cachetools import TTLCache, cached
from sqlalchemy import delete, desc, select, update
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.orm import Session as SQLASession
from sqlalchemy.orm import joinedload

from models import (
    Category,
    Championship,
    Chat,
    DeferredPenalty,
    Driver,
    DriverCategory,
    DriverContract,
    DriverRole,
    Penalty,
    QualifyingResult,
    RaceResult,
    Report,
    RoundParticipant,
    Session,
    Team,
    TeamChampionship,
)

TrueSkillEnv = ts.TrueSkill(
    draw_probability=0,
)


def get_championship(
    session: SQLASession, championship_id: int | None = None
) -> Championship | None:
    """If not given a specific championship_id, returns the most recent one.

    Args:
        session (SQLASession): Session to execute the query with.
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

    result = session.execute(statement).first()
    if result:
        return result[0]
    return None


def get_team_leaders(
    session: SQLASession, championship_id: int | None = None
) -> list[Driver]:
    """Returns a list of the team leaders in the championship specified by championship_id.
    If championship_id is not given, the function defaults to the latest championship.

    Args:
        session (SQLASession): Session to execute the query with.
        championship_id (int, optional): _description_. Defaults to None.

    Returns:
        list[Driver]: List of drivers who were team leaders in the championship.
    """
    if not championship_id:
        championship = get_championship(session)
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

    result = session.execute(statement).all()
    if result:
        return [row[0] for row in result]
    return []


def get_admins(session: SQLASession) -> list[Driver]:
    statement = (
        select(Driver)
        .join(DriverRole, Driver.id == DriverRole.driver_id)
        .where(DriverRole.role_id == 4)
    )

    result = session.execute(statement).all()

    if result:
        return [row[0] for row in result]
    return []


def get_reports(
    session: SQLASession,
    round_id: int | None = None,
    is_reviewed: bool | None = None,
) -> list[Report]:
    """Returns a list of reports matching the given arguments.

    Args:
        round_id (int, optional): round_id of the round the reports were made in. Defaults to None.
        is_reviewed (bool, optional): If the report is reviewed or not. Defaults to None.
        is_queued (bool, optional): If the report is queued or not. Defaults to None.
    """
    statement = select(Report)
    if round_id:
        statement = statement.where(Report.round_id == round_id)
    if is_reviewed is not None:
        statement = statement.where(Report.is_reviewed == is_reviewed)

    result = session.execute(statement.order_by(Report.number)).all()
    reports: list[Report] = [res[0] for res in result]

    reports.sort(key=lambda r: r.round.date)
    return reports


@cached(cache=TTLCache(maxsize=50, ttl=30))  # type: ignore
def get_driver(
    session: SQLASession,
    psn_id: str | None = None,
    telegram_id: int | str | None = None,
) -> Driver | None:
    """Retrieves a single Driver object from the database given his PSN or Telegram id.
    Either psn_id or telegram are optional, but at least one must be given.
    Args:
        session (SQLASession): Session to execute the query with.
        psn_id (str, optional): Driver's PSN ID. Defaults to None.
        telegram_id (str, optional): Driver's Telegram ID. Defaults to None.

    Returns:
        Driver | None: None if no driver/multiple drivers matching the given ID were found.
    """
    statement = select(Driver)
    if psn_id:
        statement = statement.where(Driver.psn_id == psn_id)
    elif telegram_id:
        statement = statement.where(Driver._telegram_id == str(telegram_id))  # type: ignore
    else:
        raise ValueError("Neither psn_id or telegram_id were given.")

    try:
        result = session.execute(statement).one_or_none()
    except MultipleResultsFound:
        return None

    return result[0] if result else None


def get_teams(session: SQLASession, championship_id: int) -> list[Team]:
    """Returns the list of teams participating to the given championship, ordered by
    championship position.

    Args:
        session (SQLASession): Session to execute the query with.
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

    result = session.execute(statement).all()
    session.commit()

    teams: list[Team] = []
    if result:
        for row in result:
            teams.append(row[0].team)
    return teams


def get_report(session: SQLASession, report_id: str) -> Report | None:
    """Returns the report matching the given report_id.

    Args:
        session (SQLASession): Session to execute the query with.
        report_id (int): ID of the report to fetch.

    Returns:
        Report | None: None if no matching report_id was found in the database.
    """
    result = session.execute(select(Report).where(Report.id == report_id)).one_or_none()
    if result:
        return result[0]
    return None


def get_similar_driver(session: SQLASession, psn_id: str) -> Driver | None:
    """Returns the Driver object with a psn_id similar to the one given.

    Args:
        session (SQLASession): Session to execute the query with.
        psn_id (str): ID to search for.

    Returns:
        Driver | None: None if no driver with a psn_id similar enough was found.
    """
    result = session.execute(
        select(Driver).where(sa.func.similarity(Driver.psn_id, psn_id) > 0.4)
    ).first()

    if result:
        return result[0]
    return None


def get_last_report_number(
    session: SQLASession, category_id: int, round_id: int
) -> int:
    """Gets the number of the last report made in a specific category and round.

    Args:
        category_id (int): ID of the category of which to return the last report.
        round_id (int): ID of the round of which to return the last report.

    Returns:
        int: Number of the last report made in the given round.
    """

    result = session.execute(
        select(Report)
        .where(Report.category_id == category_id)
        .where(Report.round_id == round_id)
        .order_by(desc(Report.number))
    ).first()

    if result:
        return result[0].number
    return 0


def get_last_penalty_number(session: SQLASession, round_id: int) -> int:
    """Returns the last penalty number for any given round.
    0 is returned if no penalties have been applied in that round.

    Args:
        session (SQLASession): Session to execute the query from.
        round_id (int): ID of the round in which you're looking for the
            last penalty number.
    Returns:
        int: 0 if no penalties have been applied yet in that round.
    """
    result = session.execute(
        select(Penalty.number)
        .where(Penalty.round_id == round_id)
        .order_by(desc(Penalty.number))
    ).first()

    if result:
        return result[0]
    return 0


def save_qualifying_penalty(session: SQLASession, penalty: Penalty) -> None:
    """Saves a report and applies the penalties inside it (if any)
    modifying the results of the session the penalty is referred to.

    Args:
        session (SQLASession): Session to execute the query with.
        penalty (Penalty): Penalty object to persist to the database.

    Raises:
        ValueError: Raised when the qualifying result record couldn't be found.
    """
    result = session.execute(
        select(QualifyingResult)
        .where(QualifyingResult.driver_id == penalty.driver_id)
        .where(QualifyingResult.session_id == penalty.session_id)
    ).one_or_none()

    if not result:
        raise ValueError("QualifyingResult not in database.")

    # penalty.reported_driver_id = penalty.driver.driver_id
    session.add(penalty)
    session.commit()


def _update_ratings(results: list[RaceResult]) -> None:
    """Updates the driver ratings"""
    ranks: list[int] = []
    rating_groups: list[tuple[ts.Rating]] = []
    race_results: list[RaceResult] = []
    for result in results:
        driver: Driver = result.driver

        if result.participated:
            rating_groups.append((ts.Rating(float(driver.mu), float(driver.sigma)),))
            ranks.append(result.position)  # type: ignore
            race_results.append(result)

    rating_groups = TrueSkillEnv.rate(rating_groups, ranks)  # type: ignore

    for rating_group, result in zip(rating_groups, race_results):  # type: ignore
        result.mu = result.driver.mu = Decimal(str(rating_group[0].mu))  # type: ignore
        result.sigma = result.driver.sigma = Decimal(str(rating_group[0].sigma))


def save_results(
    sqla_session: SQLASession,
    qualifying_results: list[QualifyingResult],
    races: dict[Session, list[RaceResult]],
) -> None:
    """"""

    driver_points: defaultdict[Driver, float] = defaultdict(float)

    # Calculates points earned in qualifying by each driver.
    sqla_session.add_all(qualifying_results)
    for quali_result in qualifying_results:
        points_earned = quali_result.points_earned
        driver_points[quali_result.driver] += points_earned

        # Should never be None, since every driver who takes part in a race/qualifying session
        # must also be part of a team.
        team_championship: TeamChampionship = quali_result.driver.current_team().current_championship()  # type: ignore
        team_championship.points += points_earned

    # Calculates points earned across all race sessions by each driver.
    for _, race_results in races.items():
        sqla_session.add_all(race_results)
        _update_ratings(race_results)
        for race_result in race_results:
            points_earned = race_result.points_earned
            driver_points[race_result.driver] += points_earned

            current_team = race_result.driver.current_team()

            team_championship: TeamChampionship = (
                current_team.current_championship()  #  type: ignore
            )
            team_championship.points += float(points_earned)

    drivers = qualifying_results[0].category.drivers

    for driver in drivers:
        driver.points += driver_points[driver.driver]
        driver_points.pop(driver.driver)

    # Remaining drivers are reserves who are covering in this category for the first time
    if driver_points:
        current_category = qualifying_results[0].category
        for driver, points in driver_points.items():
            dc = DriverCategory(
                driver=driver,
                category=current_category,
                race_number=0,
                points=points,
            )
            sqla_session.add(dc)
            drivers.append(dc)

    drivers.sort(key=lambda d: d.points, reverse=True)

    for p, driver in enumerate(drivers, 1):
        driver.position = p

    sqla_session.commit()


def save_and_apply_penalty(sqla_session: SQLASession, penalty: Penalty) -> None:
    """Saves a report and applies the penalties inside it (if any)
    modifying the results of the session the penalty is referred to, while also
    deducting lost points from the driver's team points tally.

    Args:
        session (SQLASession): Session to execute the query with.
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
                    team_championship = team.current_championship()
                    team_championship.points -= penalty.points
                # Sort drivers in case standings changed
                drivers = [d for d in driver_category.category.drivers]
                drivers.sort(key=lambda d: d.points, reverse=True)
                for pos, driver in enumerate(drivers):
                    driver.position = pos

    # If no time penalty was issued there aren't any changes left to make, so it saves and returns.
    if not penalty.time_penalty:
        sqla_session.add(penalty)
        sqla_session.commit()
        return

    if penalty.session.is_quali:
        save_qualifying_penalty(sqla_session, penalty)
        return

    # Gets the race results from the relevant session ordered by finishing position.
    rows = sqla_session.execute(
        select(RaceResult)
        .where(RaceResult.session_id == penalty.session.id)
        .where(RaceResult.participated == True)
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
        if race_result.driver_id == penalty.driver.id and race_result.participated:
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
                    and race_result.participated
                ):
                    race_result.total_racetime += penalty.time_penalty  # type: ignore
                    penalised_race_result = race_result

        elif penalty.session.name in ("Gara", "Gara 2"):
            category = penalty.category
            session = penalty.session
            index = category.rounds.index(session.round) + 1

            if len(category.rounds) == index:
                sqla_session.commit()
                return

            sqla_session.add(DeferredPenalty(penalty=penalty, driver=penalty.driver))
            sqla_session.commit()
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
        team: TeamChampionship = driver.current_team().current_championship()  # type: ignore

        drivers.append(driver_category)

        driver_category.points -= driver_points[driver]
        team.points -= driver_points[driver]

        points_earned = race_result.points_earned
        driver_category.points += points_earned
        team.points += points_earned

    drivers.sort(key=lambda d: d.points, reverse=True)

    # Apply correct championship positions.
    for pos, driver in enumerate(drivers, start=1):
        driver.position = pos
        if driver.driver_id == penalty.driver_id:
            break

    sqla_session.add(penalty)
    sqla_session.commit()
    return


def get_category(session: SQLASession, category_id: int) -> Category | None:
    """Returns a Category given an id.

    Args:
        session (SQLASession): Session to execute the query with.
        category_id (int): ID of the category to fetch.

    Returns:
        Category | None: None if no matching category is found.
    """

    result = session.execute(
        select(Category).where(Category.id == category_id)
    ).one_or_none()

    if result:
        return result[0]
    return None


def delete_report(session: SQLASession, report_id: str) -> None:
    """Deletes the report matching the report_id from the database.

    Args:
        session (SQLASession): Session to execute the query with.
        report_id (str): ID of the report to delete.
    """
    session.execute(delete(Report).where(Report.id == report_id))
    session.commit()
    session.expire_all()


def get_all_drivers(session: SQLASession) -> list[Driver]:
    """Returns a list containing all the drivers currently saved in the database.

    Args:
        session (SQLASession): Session to execute the query with.
    """

    result = session.execute(select(Driver)).all()

    drivers = [r[0] for r in result]

    return drivers


def get_participants_from_round(
    session: SQLASession, round_id: int
) -> list[RoundParticipant]:
    """Returns a list containing the participants to a particular round.

    Args:
        session (SQLASession): Session to execute the query with.
    """
    result = session.execute(
        select(RoundParticipant).where(RoundParticipant.round_id == round_id)
    ).all()

    participants = [r[0] for r in result]

    return participants


def update_participant_status(session: SQLASession, participant: RoundParticipant):
    stmt = (
        update(RoundParticipant)
        .where(
            RoundParticipant.driver_id == participant.driver_id,
            RoundParticipant.round_id == participant.round_id,
        )
        .values(participating=participant.participating)
    )

    session.execute(stmt)
    session.commit()


def delete_chat(session: SQLASession, chat_id: int):
    stmt = delete(Chat).where(Chat.id == chat_id)
    session.execute(stmt)
    session.commit()
