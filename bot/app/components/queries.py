"""
This module contains class-specific queries to the database; as well as
general purpose functions such as save_object and update_object.
"""

import sqlalchemy as sa
from app.components.models import (
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
    session: SQLASession, championship_id: int = None
) -> Championship | None:
    """Returns the current championship if not given a specific championship_id."""

    if championship_id:
        statement = select(Championship).where(
            Championship.championship_id == championship_id
        )
    else:
        statement = select(Championship).order_by(desc(Championship.start))

    result = session.execute(statement).one_or_none()
    if result:
        return result[0]
    return None


def get_current_team_leaders(session: SQLASession) -> list[Driver]:

    statement = (
        select(Driver)
        .join(DriverAssignment, DriverAssignment.driver_id == Driver.driver_id)
        .join(Team, DriverAssignment.team_id == Team.team_id)
        .where(DriverAssignment.is_leader == True)
        .join(TeamChampionship, TeamChampionship.team_id == Team.team_id)
        .join(
            Championship,
            Championship.championship_id == TeamChampionship.championship_id,
        )
    )
    q = session.execute(statement).all()

    return q


def get_reports(
    session: SQLASession,
    round_id: int = None,
    is_reviewed: bool = None,
    is_queued: bool = None,
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
    if is_queued is not None:
        statement = statement.where(Report.is_queued == is_queued)

    result = session.execute(statement.order_by(Report.number)).all()
    return [res[0] for res in result]


@cached(cache=TTLCache(maxsize=50, ttl=30))
def get_driver(
    session: SQLASession, psn_id: str = None, telegram_id: str = None
) -> Driver | None:
    """Returns corresponding Driver object to the given psn_id or telegram_id."""
    statement = select(Driver)
    if psn_id:
        statement = statement.where(Driver.psn_id == psn_id)
    if telegram_id:
        statement = statement.where(Driver._telegram_id == str(telegram_id))

    try:
        result = session.execute(statement).one_or_none()

    except MultipleResultsFound:
        return None
    return result[0] if result else None


def get_report(session: SQLASession, report_id: int) -> Report | None:

    result = session.execute(
        select(Report).where(Report.report_id == report_id)
    ).one_or_none()
    if result:
        return result[0]
    return None


def get_similar_driver(session: SQLASession, psn_id: str) -> Driver | None:
    """Returns the Driver object with the psn_id most similar to the one given."""
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
        int: _description_
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
    0 is returned if no penalties have been given in that round."""
    result = session.execute(
        select(Penalty.number)
        .where(Penalty.round_id == round_id)
        .order_by(desc(Penalty.number))
    ).first()

    if result:
        return result[0]
    return 0


def save_object(session: SQLASession, obj) -> None:
    """Saves the object if it doesn't already exist in the database"""

    session.add(obj)
    session.commit()


def save_multiple_objects(session: SQLASession, objs: list) -> None:
    "Saves a list of objects to the database."
    session.add_all(objs)
    session.commit()


def save_qualifying_penalty(session: SQLASession, penalty: Penalty) -> None:
    """Saves and applies a penalty to a driver in qualifying."""
    quali_result = session.execute(
        select(QualifyingResult)
        .where(QualifyingResult.driver_id == penalty.reported_driver_id)
        .where(QualifyingResult.session_id == penalty.session_id)
    ).one_or_none()

    if not quali_result:
        raise Exception("QualifyingResult not found")

    for driver_category in penalty.reported_driver.categories:
        if driver_category.category_id == penalty.category.category_id:
            driver_category.licence_points -= penalty.licence_points
            driver_category.warnings += penalty.warnings

    quali_result: QualifyingResult = quali_result[0]
    quali_result.warnings = penalty.warnings
    quali_result.licence_points = penalty.licence_points
    quali_result.penalty_points = penalty.penalty_points

    session.commit()
    penalty.reported_driver_id = penalty.reported_driver.driver_id
    save_object(session, penalty)


def save_and_apply_penalty(session: SQLASession, penalty: Penalty) -> None:
    """Saves a report and applies the time penalty, changing the finishing positions
    of the other drivers as well if needed."""

    for driver_category in penalty.reported_driver.categories:
        if driver_category.category_id == penalty.category.category_id:
            driver_category.licence_points -= penalty.licence_points
            driver_category.warnings += penalty.warnings

    if not penalty.time_penalty:
        if not penalty.reporting_driver:
            session.commit()
            save_object(session, penalty)
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

    session.commit()
    penalty.reported_driver_id = penalty.reported_driver.driver_id

    session.add(penalty)
    session.commit()
    return


def update_object(session) -> None:
    """Calls Session.commit()"""
    session.commit()


def delete_report(session: SQLASession, report_id: str) -> None:
    """Deletes the given report from the database."""
    session.execute(delete(Report).where(Report.report_id == report_id))
    session.commit()
    session.expire_all()
