from datetime import datetime, timedelta
import sqlalchemy as sa

from sqlalchemy import desc
from sqlalchemy.future import create_engine, select
from sqlalchemy.orm import joinedload, sessionmaker

from components.models import (
    CarClass,
    Category,
    Championship,
    Driver,
    Game,
    RaceResult,
    Report,
    Team,
)

engine = create_engine("postgresql+pg8000://alexander:alexander@localhost:5432/rti")
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


def get_games() -> list[Game]:
    """Returns the list of games."""
    return _session.execute(select(Game)).all()


def get_game(name: str) -> Game | None:
    """Returns the game matching the given name."""
    return _session.execute(select(Game).where(Game.name == name)).one_or_none()


def get_category(category_id: int) -> Category | None:
    """Returns the category corresponding to the given category_id."""
    return _session.execute(
        select(Category).where(Category.category_id == category_id)
    ).one_or_none()


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
) -> list[Report] | None:
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


def get_driver(psn_id: str = None, telegram_id: str | int = None) -> Driver | None:
    """Returns corresponding Driver object to the given psn_id or telegram_id."""
    statement = select(Driver)
    if psn_id:
        statement = statement.where(Driver.psn_id == psn_id)
    if telegram_id:
        statement = statement.where(Driver.telegram_id == telegram_id)

    result = _session.execute(statement).one_or_none()
    return result[0] if result else None


def get_similar_driver(psn_id: str) -> Driver | None:
    """Returns the Driver object with the psn_id most similar to the one given"""
    result = _session.execute(
        select(Driver).where(sa.func.similarity(Driver.psn_id, psn_id) > 0.2)
    ).first()

    if result:
        return result[0]
    else:
        return None


def get_latest_report_number(category_id: int) -> int:
    result = _session.execute(
        select(Report)
        .where(Report.category_id == category_id)
        .order_by(desc(Report.number))
    ).first()
    if result:
        return result[0].number
    return 0


# def get_leader(telegram_id: str) -> Driver | None:
#     return _session.execute(
#         select(Driver).where(
#             Driver.telegram_id == str(telegram_id) and Driver.is_leader
#         )
#     ).one_or_none()


def get_team(team_name: str) -> Team | None:
    result = _session.execute(select(Team).where(Team.name == team_name)).one_or_none()
    return result[0] if result else None


def get_car_class(class_name: str, game_id: int) -> CarClass | None:
    result = _session.execute(
        select(CarClass)
        .where(CarClass.name == class_name)
        .where(CarClass.game_id == game_id)
    ).one_or_none()
    return result[0] if result else None


def delete_last_report(leader: Driver) -> None:
    report: Report = (
        _session.execute(select(Report))
        .where(Report.reporting_team_id == leader.current_team().name)
        .order_by(desc(Report.report_time))
        .first()
    )
    if report:
        if (datetime.now() - report.report_time) <= timedelta(minutes=30):
            _session.delete(report)
            return True
    return False


def save_object(obj) -> None:
    """Saves the object if it doesn't already exist in the database"""
    print(obj)
    _session.add(obj)
    _session.commit()


def save_multiple_objects(objs: list) -> None:
    _session.add_all(objs)
    _session.commit()


def save_and_apply_report(report: Report) -> None:
    if not report.time_penalty:
        update_object()

    rows = _session.execute(
        select(RaceResult)
        .where(
            (RaceResult.category_id, RaceResult.round_id, report.session_id)
            == (report.category_id, report.round_id, report.session_id)
        )
        .order_by(RaceResult.finishing_position)
    ).all()

    race_results = [row[0] for row in rows]
    for race_result in race_results:
        if race_result.driver_id == report.reported_driver_id:
            race_result.gap_to_first += report.time_penalty
            break

    race_results.sort(key=lambda x: x.gap_to_first)

    for i, race_result in enumerate(race_results):
        if race_result.finishing_position:
            race_result.finishing_position = i + 1

    update_object()


def update_object() -> None:
    """Calls Session.commit()"""
    _session.commit()


def get_max_races() -> Driver | None:
    """Returns driver with the most races"""
    return _session.execute(
        """SELECT driver_id, COUNT(DISTINCT(rr.round_id))  from race_results rr WHERE rr.finishing_position != 0 GROUP BY rr.driver_id ORDER BY COUNT(rr.round_id) DESC LIMIT 1"""
    ).one_or_none()[0]


if __name__ == "__main__":

    print(get_championship())
    print(get_driver("RTI_Sbinotto17").race_results)
    print(get_current_category())
    print(get_games())
    print(get_latest_report_number(11))
    print(get_max_races())
