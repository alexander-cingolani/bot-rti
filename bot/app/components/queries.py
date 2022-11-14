"""
This module contains class-specific queries to the database; as well as
general purpose functions such as save_object and update_object.
"""

import os
from datetime import datetime, timedelta

import sqlalchemy as sa
from app.components.utils import separate_car_classes
from app.components.models import (Category, Championship, Driver,
                                   QualifyingResult, RaceResult, Report)
from cachetools import TTLCache, cached
from sqlalchemy import delete, desc
from sqlalchemy.exc import MultipleResultsFound
from sqlalchemy.future import create_engine, select
from sqlalchemy.orm import joinedload, sessionmaker

engine = create_engine(os.environ.get("DB_URL"))
_Session = sessionmaker(bind=engine, autoflush=False)
_session = _Session()


def get_championship(championship_id: int = None) -> Championship | None:
    """Returns the current championship if not given a specific ID."""
    if championship_id:
        result = _session.execute(
            select(Championship).where(Championship.championship_id == championship_id)
        ).one_or_none()
        if result:
            return result[0]
        return None

    result = _session.execute(
        select(Championship)
        .order_by(desc(Championship.start))
        .options(
            joinedload(Championship.categories),
        )
    ).first()
    if result:
        return result[0]
    return None


def get_current_category() -> Category | None:
    """Returns the current championship's category whose race_weekday corresponds to yesterday."""

    return _session.execute(
        select(Category).where(
            Category.round_weekday == (datetime.today() - timedelta(days=1)).weekday()
        )
    ).all()


def get_reports(
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
    statement = select(Report).options(joinedload(Report.category))
    if round_id:
        statement = statement.where(Report.round_id == round_id)
    if is_reviewed is not None:
        statement = statement.where(Report.is_reviewed == is_reviewed)
    if is_queued is not None:
        statement = statement.where(Report.is_queued == is_queued)

    result = _session.execute(statement.order_by(Report.number)).all()
    return [res[0] for res in result]


def get_last_report_by(reporting_team_id: int) -> Report | None:
    """Returns the last report made by the given leader."""

    result = _session.execute(
        select(Report)
        .where(Report.reporting_team_id == reporting_team_id)
        .order_by(desc(Report.report_time))
    ).first()
    if result:
        return result[0]
    return result


@cached(cache=TTLCache(maxsize=50, ttl=30))
def get_driver(psn_id: str = None, telegram_id: str = None) -> Driver | None:
    """Returns corresponding Driver object to the given psn_id or telegram_id."""
    statement = select(Driver)
    if psn_id:
        statement = statement.where(Driver.psn_id == psn_id)
    if telegram_id:
        statement = statement.where(Driver._telegram_id == str(telegram_id))

    try:
        result = _session.execute(statement).one_or_none()

    except MultipleResultsFound:
        return None
    return result[0] if result else None


def get_similar_driver(psn_id: str) -> Driver | None:
    """Returns the Driver object with the psn_id most similar to the one given."""
    result = _session.execute(
        select(Driver).where(sa.func.similarity(Driver.psn_id, psn_id) > 0.4)
    ).first()

    if result:
        return result[0]
    return None


def get_last_report_number(category_id: int, round_id: int) -> int:
    """Gets the number of the last report made in a specific category and round.

    Args:
        category_id (int): ID of the category of which to return the last report.
        round_id (int): ID of the round of which to return the last report.

    Returns:
        int: _description_
    """

    result = _session.execute(
        select(Report)
        .where(Report.category_id == category_id)
        .where(Report.round_id == round_id)
        .order_by(desc(Report.number))
    ).first()
    if result:
        return result[0].number
    return 0


def save_object(obj) -> None:
    """Saves the object if it doesn't already exist in the database"""

    _session.add(obj)
    _session.commit()
                

def save_multiple_objects(objs: list) -> None:
    "Saves a list of objects to the database."
    _session.add_all(objs)
    _session.commit()


def save_qualifying_report(report: Report) -> None:
    """Saves and applies a penalty to a driver in qualifying."""
    quali_result = _session.execute(
        select(QualifyingResult).where(
            QualifyingResult.driver_id == report.reported_driver_id
            and QualifyingResult.session_id == report.session_id
            and QualifyingResult.round_id == report.round_id
        )

    ).one_or_none()
    for driver_category in report.reported_driver.categories:
        if driver_category.category_id == report.category.category_id:
            driver_category.licence_points -= report.licence_points
            driver_category.warnings += report.warnings
    
    
    if quali_result:
        quali_result: QualifyingResult = quali_result[0]
        quali_result.warnings = report.warnings
        quali_result.licence_points = report.licence_points
        quali_result.penalty_points = report.championship_penalty_points
        update_object()
        return
    raise Exception("QualifyingResult not found")


def save_and_apply_report(report: Report) -> None:
    """Saves a report and applies the time penalty, changing the finishing positions
    of the other drivers as well if needed."""

    report.is_reviewed = True

    if not report.time_penalty:
        if not report.reporting_driver:
            save_object(report)
        else:
            update_object()
        return
    if report.session.is_quali:
        save_qualifying_report(report)
        return 

    rows = _session.execute(
        select(RaceResult)
        .where(
            RaceResult.category_id == report.category.category_id
            and RaceResult.round_id == report.round_id
            and RaceResult.session_id == report.session_id
        )
        .order_by(RaceResult.finishing_position)
    ).all()

    race_results: list[RaceResult] = []
    for row in rows:
        race_result = row[0]
        if race_result.total_racetime:
            if race_result.driver_id == report.reported_driver.driver_id:
                race_result.total_racetime += report.time_penalty
            race_results.append(race_result)
            
    race_results.sort(key=lambda x: x.total_racetime)
    
    for position, result in enumerate(race_results, start=1):

        result.finishing_position = position
        
    for _, class_results in separate_car_classes(report.category, race_results).items():
        winners_racetime = race_results[0].total_racetime
        for relative_position, race_result in enumerate(class_results, start=1):
            race_result.relative_position = relative_position
            race_result.gap_to_first = result.total_racetime - winners_racetime
    
    
    if not report.reporting_driver:
        update_object()
        save_object(report)
        
    else:
        update_object()

def update_object() -> None:
    """Calls Session.commit()"""
    _session.commit()


def delete_report(report: Report) -> None:
    """Deletes the given report from the database."""
    _session.execute(delete(Report).where(Report.report_id == report.report_id))
