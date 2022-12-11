"""
This module contains the necessary queries in order to retrieve specific objects
such as Reports, Categories and Drivers.
"""

import sqlalchemy as sa
from app.components.models import (
    Category,
    Championship,
    Driver,
    DriverAssignment,
    Penalty,
    QualifyingResult,
    RaceResult,
    Report,
    Team,
    TeamChampionship,
)
from app.components.utils import separate_car_classes
from cachetools import TTLCache, cached
from sqlalchemy import delete, desc
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.future import select
from sqlalchemy.orm import Session as SQLASession


def get_championship(
    session: SQLASession, championship_id: int | None = None
) -> Championship | None:
    """If not given a specific championship_id, returns the last one in
    chronological order.

    Args:
        session (SQLASession): Session to execute the query with.
        championship_id (int, optional): ID of the championship to retrieve.
            Defaults to None.

    Returns:
        Championship | None: Only None if no championships are registered in
            the database.
    """

    if championship_id:
        statement = select(Championship).where(
            Championship.championship_id == championship_id
        )
    else:
        statement = select(Championship).order_by(desc(Championship.start))

    result = session.execute(statement).first()
    if result:
        return result[0]
    return None


def get_team_leaders(
    session: SQLASession, championship_id: int | None = None
) -> list[Driver] | None:
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
            championship_id = championship.championship_id
        else:
            return None

    statement = (
        select(Driver)
        .join(DriverAssignment, DriverAssignment.driver_id == Driver.driver_id)
        .join(Team, DriverAssignment.team_id == Team.team_id)
        .where(DriverAssignment.is_leader == True)
        .join(TeamChampionship, TeamChampionship.team_id == Team.team_id)
        .where(TeamChampionship.championship_id == championship_id)
    )

    result = session.execute(statement).all()
    if result:
        return [row[0] for row in result]
    return None


def get_reports(
    session: SQLASession,
    round_id: int | None = None,
    is_reviewed: bool | None = None,
    is_queued: bool | None = None,
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
    return [res[0] for res in result]


@cached(cache=TTLCache(maxsize=50, ttl=30))
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
        statement = statement.where(Driver._telegram_id == str(telegram_id))
    else:
        raise ValueError("Neither psn_id or telegram_id were given.")

    try:
        result = session.execute(statement).one_or_none()
    except MultipleResultsFound:
        return None

    return result[0] if result else None


def get_report(session: SQLASession, report_id: int) -> Report | None:
    """Returns the report matching the given report_id.

    Args:
        session (SQLASession): Session to execute the query with.
        report_id (int): ID of the report to fetch.

    Returns:
        Report | None: None if no matching report_id was found in the database.
    """
    result = session.execute(
        select(Report).where(Report.report_id == report_id)
    ).one_or_none()
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
        .where(QualifyingResult.driver_id == penalty.reported_driver_id)
        .where(QualifyingResult.session_id == penalty.session_id)
    ).one_or_none()

    if not result:
        raise ValueError("QualifyingResult not in database.")

    for driver_category in penalty.reported_driver.categories:
        if driver_category.category_id == penalty.category.category_id:
            driver_category.licence_points -= penalty.licence_points
            driver_category.warnings += penalty.warnings

    # penalty.reported_driver_id = penalty.reported_driver.driver_id
    session.add(penalty)
    session.commit()


def save_and_apply_penalty(session: SQLASession, penalty: Penalty) -> None:
    """Saves a report and applies the penalties inside it (if any)
    modifying the results of the session the penalty is referred to.

    Args:
        session (SQLASession): Session to execute the query with.
        penalty (Penalty): Penalty object to persist to the database.
    """

    for driver_category in penalty.reported_driver.categories:
        if driver_category.category_id == penalty.category.category_id:
            driver_category.licence_points -= penalty.licence_points
            driver_category.warnings += penalty.warnings

    if not penalty.time_penalty:
        if not penalty.reporting_driver:
            session.add(penalty)
            session.commit()
            return
        return
    if penalty.session.is_quali:
        save_qualifying_penalty(session, penalty)
        return

    rows = session.execute(
        select(RaceResult)
        .where(RaceResult.session_id == penalty.session.session_id)
        .order_by(RaceResult.finishing_position)
    ).all()

    race_results: list[RaceResult] = []
    for row in rows:
        race_result: RaceResult = row[0]
        if race_result.total_racetime:
            if race_result.driver_id == penalty.reported_driver.driver_id:
                race_result.total_racetime += penalty.time_penalty

            race_results.append(race_result)

    race_results.sort(key=lambda x: x.total_racetime)

    for position, result in enumerate(race_results, start=1):
        result.finishing_position = position

    for _, class_results in separate_car_classes(
        penalty.category, race_results
    ).items():
        winners_racetime = class_results[0].total_racetime
        for relative_position, race_result in enumerate(class_results, start=1):
            race_result.relative_position = relative_position
            race_result.gap_to_first = race_result.total_racetime - winners_racetime

    # penalty.reported_driver_id = penalty.reported_driver.driver_id
    session.add(penalty)
    session.commit()
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
        select(Category).where(Category.category_id == category_id)
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
    session.execute(delete(Report).where(Report.report_id == report_id))
    session.commit()
    session.expire_all()
