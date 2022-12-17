"""
This module contains the necessary SQLAlchemy models to keep track of
RacingTeamItalia's championships and drivers.
"""
from __future__ import annotations

import datetime
import logging
from statistics import stdev
import uuid
from collections import defaultdict
from datetime import datetime as dt
from datetime import time, timedelta
from decimal import Decimal
from typing import Any, DefaultDict, Optional
from cachetools import TTLCache, cached

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Interval,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.orm.relationships import _ORMColCollectionArgument

# In this project "round" always refers to an instance of a Round object.


class Base(DeclarativeBase):
    pass


class Penalty(Base):
    """This class represents a penalty applied to a driver in a given session.

    Attributes:
        time_penalty (int): Seconds to add to the driver's total race time.
        penalty_points (int): Points to be subtracted from the driver's
            points tally.
        licence_points (int): Points to be subtracted from the driver's licence.
        warnings (int): Number of warnings received.

        category_id (int): Unique ID of the category where incident happened.
        round_id (int): Unique ID of the round where the incident happened.
        session_id (int): Unique ID of the session where the incident happened.

        reported_driver_id (int): Unique ID of the driver receiving the report.
        reported_team_id (int): Unique ID of the team receiving the report.

        incident_time (str): In-game time when the incident happened.
        fact (str): The fact given by the user creating the penalty.
        decision (str): The decision taken. (Made up from time_penalty, penalty_points,
            licence_points and warnings all combined into a nice text format generated
            by the bot).
        penalty_reason (str): Detailed explanation why the penalty was issued.
    """

    # pylint: disable=too-many-instance-attributes, too-many-arguments

    __tablename__ = "penalties"
    __allow_unmapped__ = True

    incident_time: str
    fact: str
    decision: str
    penalty_reason: str
    reporting_driver: Driver

    penalty_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    time_penalty: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    licence_points: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    warnings: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    penalty_points: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)

    category: Mapped[Category] = relationship("Category")
    round: Mapped[Round] = relationship("Round", back_populates="penalties")
    session: Mapped[Session] = relationship("Session")

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.category_id"), nullable=False
    )
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.round_id"), nullable=False)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id"), nullable=False
    )
    reported_driver_id: Mapped[str] = mapped_column(
        ForeignKey("drivers.driver_id"), nullable=False
    )
    reported_team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.team_id"), nullable=False
    )

    reported_driver: Mapped[Driver] = relationship(
        back_populates="received_penalties", foreign_keys=[reported_driver_id]  # type: ignore
    )
    reported_team: Mapped[Team] = relationship(
        back_populates="received_penalties", foreign_keys=[reported_team_id]  # type: ignore
    )

    @classmethod
    def from_report(
        cls,
        report: Report,
        time_penalty: int = 0,
        licence_points: int = 0,
        warnings: int = 0,
        penalty_points: int = 0,
    ) -> Penalty:
        """Initializes a Penalty object from a Report object.

        Args:
            report (Report): Report to initialize the Penalty object from.
            time_penalty (int): Time penalty applied to the driver. (Default: 0)
            licence_points (int): Licence points deducted from the driver's licence. (Default: 0)
            warnings (int): Warnings given to the driver. (Default: 0)
            penalty_points (int): Points to be deducted from the driver's points tally.
                (Default: 0)

        Raises:
            TypeError: Raised if report is not of type `Report`.

        Returns:
            Penalty: The new object initialized with the given arguments.
        """

        if not isinstance(report, Report):
            raise TypeError(f"Cannot initialize Penalty object from {type(report)}.")

        c = cls(
            reported_driver=report.reported_driver,
            time_penalty=time_penalty,
            licence_points=licence_points,
            warnings=warnings,
            penalty_points=penalty_points,
        )
        c.incident_time = report.incident_time
        c.category = report.category
        c.round = report.round
        c.session = report.session
        c.reporting_driver = report.reporting_driver
        return c

    def is_complete(self) -> bool:
        """Returns True if all the necessary arguments have been provided."""
        logging.info(self.__dict__)
        return all(
            (
                self.reported_driver,
                self.reported_team,
                self.category,
                self.round,
                self.session,
                self.penalty_reason,
                self.fact,
                self.decision,
            )
        )


class Report(Base):
    """This object represents a report.
    Each report is associated with two Drivers and their Teams,
    as well as the Category, Round and Session the reported incident happened in.
    N.B. fact, penalty, penalty_reason and is_queued may only be provided after
    the report has been reviewed.

    Attributes:
        report_id (uuid4): Automatically generated unique ID assigned upon report creation.
        number (int): The number of the report in the order it was received in in a Round.
        incident_time (str): String indicating the in-game time when the accident happened.
        report_reason (str): The reason provided by the reporter for making the report.
        video_link (str): [Not persisted] Link towards a YouTube video showing the accident
            happening. (Only intended for qualifying sessions)
        is_reviewed (bool): False by default, indicates if the report has been reviewed yet.
        report_time (datetime): Timestamp indicating when the report was made.
        channel_message_id (int): ID of the message the report was sent by the user with.

        category_id (int): Unique ID of the category where incident happened.
        round_id (int): Unique ID of the round where the incident happened.
        session_id (int): Unique ID of the session where the incident happened.
        reported_driver_id (int): Unique ID of the driver receiving the report.
        reporting_driver_id (int): Unique ID of the driver making the report.
        reported_team_id (int): Unique ID of the team receiving the report.
        reporting_team_id (int): Unique ID of the team making the report.

        category (Category): Category where the incident happened.
        round (Round): Round where the incident happened.
        session (Session): Session where the incident happened.
        reported_driver (Driver): The driver receiving the report.
        reporting_driver (Driver): The driver making the report.
        reported_team (Team): The team receiving the report.
        reporting_team (Team): The team making the report.
    """

    # pylint: disable=too-many-instance-attributes, too-many-arguments

    __tablename__ = "reports"
    __table_args__ = (CheckConstraint("reporting_team_id != reported_team_id"),)

    __allow_unmapped__ = True
    video_link: str | None = None

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    incident_time: Mapped[str] = mapped_column(String(12), nullable=False)
    report_reason: Mapped[str] = mapped_column(String(2000), nullable=False)
    is_reviewed: Mapped[str] = mapped_column(Boolean, nullable=False, default=False)
    report_time: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default="current_timestamp"
    )
    channel_message_id: Mapped[int] = mapped_column(BigInteger)

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.category_id"), nullable=False
    )
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.round_id"), nullable=False)
    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.session_id"), nullable=False
    )
    reported_driver_id: Mapped[str] = mapped_column(
        ForeignKey("drivers.driver_id"), nullable=False
    )

    reporting_driver_id: Mapped[str] = mapped_column(
        ForeignKey("drivers.driver_id"), nullable=False
    )
    reported_team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.team_id"), nullable=False
    )
    reporting_team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.team_id"), nullable=False
    )

    category: Mapped[Category] = relationship()
    round: Mapped[Round] = relationship(back_populates="reports")
    session: Mapped[Session] = relationship()
    reported_driver: Mapped[Driver] = relationship(foreign_keys=[reported_driver_id])  # type: ignore
    reporting_driver: Mapped[Driver] = relationship(
        back_populates="reports_made", foreign_keys=[reporting_driver_id]  # type: ignore
    )
    reported_team: Mapped[Team] = relationship(foreign_keys=[reported_team_id])  # type: ignore
    reporting_team: Mapped[Team] = relationship(
        back_populates="reports_made", foreign_keys=[reporting_team_id]  # type: ignore
    )

    def __str__(self) -> str:
        return (
            f"Report(number={self.number}, incident_time={self.incident_time},"
            f" report_reason={self.report_reason}, reported_driver={self.reported_driver},"
            f" reporting_driver={self.reporting_driver}, reported_team={self.reported_team})"
        )

    def is_complete(self) -> bool:
        """Returns True if all the necessary arguments have been provided."""
        return all(
            (
                self.incident_time,
                self.reported_driver,
                self.reporting_driver,
                self.category,
                self.round,
                self.session,
                self.reported_team,
                self.reporting_team,
                self.number,
            )
        )


class DriverAssignment(Base):
    """This object creates an association between a Driver and a Team

    Attributes:
        joined_on (date): Date the driver joined the team.
        left_on (date): Date the driver left the team.
        bought_for (int): Price the team paid to acquire the driver.
        is_leader (bool): Indicates whether the driver is also the leader of that team.

        assignment_id (uuid): Auto-generated UUID assigned upon object creation.
        driver_id (int): Unique ID of the driver joining the team.
        team_id (int): Unique ID of the team acquiring the driver.

        driver (Driver): Driver joining the team.
        team (Team): Team acquiring the driver.
    """

    __tablename__ = "driver_assignments"
    __table_args__ = (UniqueConstraint("joined_on", "driver_id", "team_id"),)

    joined_on: Mapped[datetime.date] = mapped_column(
        Date, server_default=func.now(), default=False, nullable=False
    )
    left_on: Mapped[datetime.date] = mapped_column(Date)
    bought_for: Mapped[Optional[int]] = mapped_column(SmallInteger)
    is_leader: Mapped[bool] = mapped_column(Boolean, default=False)

    assignment_id: Mapped[str] = mapped_column(
        UUID(as_uuid=True), primary_key=True, nullable=False
    )
    driver_id: Mapped[int] = mapped_column(
        ForeignKey("drivers.driver_id"), primary_key=True, nullable=False
    )
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.team_id"), primary_key=True, nullable=False
    )

    driver: Mapped[Driver] = relationship("Driver", back_populates="teams")
    team: Mapped[Team] = relationship("Team", back_populates="drivers")


class DriverCategory(Base):
    """This object creates a new association between a Driver and a Category.

    Attributes:
        joined_on (date): The date on which the driver joined the category.
        left_on (date): The date on which the driver left the category.
        race_number (int): The number used by the driver in the category.
        warnings (int): Number of warnings received in the category.
        licence_points: Number of points remaining on the driver's licence.

        driver_id (int): Unique ID of the driver joining the category.
        category_id (int): Unique ID of the category being joined by the driver.
        car_class_id (int): Unique ID of the car class the driver is in.

        driver (Driver): Driver joining the category.
        category (Category): Category being joined by the driver.
        car_class (CarClass): CarClass the driver is in.
    """

    __tablename__ = "drivers_categories"

    __table_args__ = (UniqueConstraint("driver_id", "category_id"),)

    joined_on: Mapped[datetime.date] = mapped_column(Date, server_default=func.now())
    left_on: Mapped[datetime.date] = mapped_column(Date)
    race_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    warnings: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    licence_points: Mapped[int] = mapped_column(
        SmallInteger, default=10, nullable=False
    )

    driver_id: Mapped[int] = mapped_column(
        ForeignKey("drivers.driver_id"), primary_key=True
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.category_id"), primary_key=True
    )
    car_class_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("car_classes.car_class_id")
    )

    driver: Mapped[Driver] = relationship("Driver", back_populates="categories")
    category: Mapped[Category] = relationship("Category", back_populates="drivers")
    car_class: Mapped[CarClass] = relationship("CarClass")


class Driver(Base):
    """This object represents a driver.

    Attributes:
        driver_id (int): Automatically generated unique ID assigned upon object creation.
        psn_id (str): The driver's Playstation ID (max 16 characters).
        telegram_id (str): The driver's telegram ID.

        championships (list[DriverChampionship]): Championships the driver has participated in.
        teams (list[DriverAssignment]): Teams the driver has been acquired by.
        categories (list[DriverCategory]): Categories the driver has participated in.
        race_results (list[RaceResult]): Results made by the driver in his career.
        received_reports (list[Report]): Reports made against the driver during his career.
        reports_made (list[Report]): Reports made by the driver during his career.
        qualifying_results (list[Report]): Results obtained by the driver in qualifying sessions
            during his career.
    """

    __tablename__ = "drivers"
    __table_args__ = (UniqueConstraint("driver_id", "telegram_id"),)

    driver_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    psn_id: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    _telegram_id: Mapped[str] = mapped_column("telegram_id", Text, unique=True)

    teams: Mapped[list[DriverAssignment]] = relationship(
        "DriverAssignment", back_populates="driver"
    )
    categories: Mapped[list[DriverCategory]] = relationship(
        "DriverCategory", back_populates="driver"
    )
    race_results: Mapped[list[RaceResult]] = relationship(
        "RaceResult", back_populates="driver"
    )
    received_penalties: Mapped[list[Penalty]] = relationship(
        "Penalty", back_populates="reported_driver"
    )
    reports_made: Mapped[list[Report]] = relationship(
        "Report",
        back_populates="reporting_driver",
        foreign_keys=[Report.reporting_driver_id],
    )
    qualifying_results: Mapped[list[QualifyingResult]] = relationship(
        "QualifyingResult", back_populates="driver"
    )

    def __repr__(self) -> str:
        return f"Driver(psn_id={self.psn_id}, driver_id={self.driver_id})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Driver):
            return NotImplemented
        return self.driver_id == other.driver_id

    def __key(self) -> tuple:
        return self.driver_id, self.psn_id

    def __hash__(self) -> int:
        return hash(self.__key())

    def current_team(self) -> Team | None:
        """Returns the team the driver is currently competing with."""
        for team in self.teams:
            if not team.left_on:
                return team.team
        return None

    def current_category(self) -> Category | None:
        """Returns the team the driver is currently competing in."""
        for category in self.categories:
            if not category.left_on:
                return category.category
        return None

    def current_class(self) -> CarClass | None:
        """Returns the car class the driver is currently competing in."""
        for category in self.categories:
            if not category.left_on:
                return category.car_class
        return None

    @property
    def current_race_number(self) -> int | None:
        """The number currently being used by the Driver in races."""
        current_category = self.current_category()
        if current_category:
            for driver_category in current_category.drivers:
                if self.driver_id == driver_category.driver_id:
                    return driver_category.race_number
        return None

    @property
    def telegram_id(self) -> int | None:
        """The telegram_id associated with the Driver."""
        if self._telegram_id:
            return int(self._telegram_id)
        return None

    @telegram_id.setter
    def telegram_id(self, telegram_id: int):
        if telegram_id is None:
            self._telegram_id = None
        elif str(telegram_id).isnumeric():
            self._telegram_id = str(telegram_id)
        else:
            raise ValueError("Telegram ids can only contain numbers.")

    @property
    def licence_points(self) -> int:
        """The amount of licence points this driver has currently."""
        for driver_category in self.categories:
            if not driver_category.left_on:
                return driver_category.licence_points
        return 0

    @property
    def warnings(self) -> int:
        for driver_category in self.categories:
            if not driver_category.left_on:
                return driver_category.warnings
        return 0

    @cached(cache=TTLCache(maxsize=50, ttl=240))
    def consistency(self) -> str:
        """Number 40-100 calculated based on the
        standard deviation of the set of relative finishing positions and the number
        of absences.
        """

        completed_races: list[RaceResult] = list(
            filter(lambda x: x.participated, self.race_results)
        )
        if len(completed_races) < 2:
            return "dati insufficienti"

        positions = [race_result.relative_position for race_result in completed_races]
        participation_ratio = len(completed_races) / len(self.race_results)
        participation_ratio = min(participation_ratio, 1)
        result = round((100 * participation_ratio) - (stdev(positions) * 3))
        return str(max(result, 40))

    @cached(cache=TTLCache(maxsize=50, ttl=240))
    def speed(self) -> str:
        """Statistic calculated on the average gap between
        the driver's qualifying times and the pole man's.

        Args:
            driver (Driver): The Driver to calculate the speed rating of.

        Returns:
            str: Speed rating. (40-100)
        """

        completed_quali_sessions = list(
            filter(lambda x: x.participated, self.qualifying_results)
        )

        if not completed_quali_sessions:
            return "dati insufficienti"

        total_gap_percentages = 0.0
        for quali_result in completed_quali_sessions:
            total_gap_percentages += (
                float(
                    quali_result.gap_to_first
                    / (quali_result.laptime - quali_result.gap_to_first)
                )
                * 1000
            )

        average_gap_percentage = pow(
            total_gap_percentages / len(completed_quali_sessions), 1.18
        )
        average_gap_percentage = min(average_gap_percentage, 60)
        return str(round(100 - average_gap_percentage))

    @cached(cache=TTLCache(maxsize=50, ttl=240))
    def sportsmanship(self) -> str:
        """This statistic is calculated based on the amount and gravity of reports received.

        Returns:
            str: Sportsmanship rating. (0-100)
        """

        if len(self.race_results) < 2:
            return "dati insufficienti"

        if not self.received_penalties:
            return "100"

        penalties = (
            (rr.time_penalty / 1.5)
            + rr.warnings
            + (rr.licence_points * 2)
            + rr.penalty_points
            for rr in self.received_penalties
        )

        return str(round(100 - sum(penalties) * 3 / len(self.race_results)))

    @cached(cache=TTLCache(maxsize=50, ttl=240))
    def race_pace(self) -> str:
        """This statistic is calculated based on the average gap from the race winner
        in all of the races completed by the driver.

        Return:
            str: Race pace score. (40-100)
        """
        completed_races = list(filter(lambda x: x.participated, self.race_results))
        if not completed_races:
            return "dati insufficienti"

        total_gap_percentages = 0.0
        for race_res in completed_races:
            total_gap_percentages += (
                float(
                    race_res.gap_to_first
                    / (race_res.total_racetime - race_res.gap_to_first)
                )
                * 1000
            )

        average_gap_percentage = pow(total_gap_percentages / len(completed_races), 1.1)
        average_gap_percentage = min(average_gap_percentage, 60)

        return str(round(100 - average_gap_percentage))

    @cached(cache=TTLCache(maxsize=50, ttl=240))
    def stats(self) -> tuple[str, str, str, str, str, str, str]:
        """Calculates the number of wins, podiums and poles achieved by the driver."""
        wins = 0
        podiums = 0
        fastest_laps = 0
        poles = 0
        no_participation = 0

        if not self.race_results:
            return "0", "0", "0", "0", "0", "0", "0"

        positions = 0
        for race_result in self.race_results:
            if not race_result.participated:
                no_participation += 1
                continue

            if race_result.relative_position:
                positions += race_result.relative_position
            if race_result.relative_position == 1:
                wins += 1
            if race_result.relative_position <= 3:
                podiums += 1

            fastest_laps += race_result.fastest_lap_points

        quali_positions = 0
        no_quali_participation = 0
        for quali_result in self.qualifying_results:
            if quali_result:
                if quali_result.relative_position == 1:
                    poles += 1
                if quali_result.participated:
                    quali_positions += quali_result.relative_position

        races_completed = len(self.race_results) - no_participation
        if races_completed:
            average_position = round(positions / races_completed, 2)
        else:
            average_position = 0

        qualifying_sessions_completed = (
            len(self.qualifying_results) - no_quali_participation
        )
        if quali_positions:
            average_quali_position = round(
                quali_positions / qualifying_sessions_completed, 2
            )
        else:
            average_quali_position = 0

        return (
            wins,
            podiums,
            poles,
            fastest_laps,
            races_completed,
            average_position,
            average_quali_position,
        )


class QualifyingResult(Base):
    """This object represents a single result made by a driver in a qualifying Session.

    Attributes:
        qualifying_result_id (int): Automatically generated unique ID assigned upon
            object creation.
        position (int): Position the driver qualified in.
        relative_position (int): Qualifying position in the driver's car class.
        laptime (Decimal): Best lap registered by the driver in the.
        gap_to_first (Decimal): Seconds by which the laptime is off from the fastest lap
            time in the driver's car class.
        participated (bool): True if the driver participated to the Qualifying session.

        driver_id (int): Unique ID of the driver the result belongs to.
        round_id (int): Unique ID of the round the result was made in.
        category_id (int): Unique ID of the category the result was made in.
        session_id (int): Unique ID of the session the result was made in.

        driver (Driver): Driver the result belongs to.
        round (Round): Round the result was made in.
        category (Category): Category the result was made in.
        session (Session): Session the result was made in.
    """

    # pylint: disable=too-many-instance-attributes, too-many-arguments

    __tablename__ = "qualifying_results"

    __table_args__ = (
        UniqueConstraint("driver_id", "session_id", "round_id"),
        UniqueConstraint("position", "session_id", name="position_session_uq"),
    )

    qualifying_result_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    position: Mapped[int] = mapped_column(SmallInteger)
    relative_position: Mapped[int] = mapped_column(SmallInteger)
    laptime: Mapped[Decimal] = mapped_column(Numeric(precision=8, scale=3))
    gap_to_first: Mapped[Decimal] = mapped_column(Numeric(precision=8, scale=3))
    participated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    driver_id: Mapped[int] = mapped_column(
        ForeignKey("drivers.driver_id"), nullable=False
    )
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.round_id"), nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.category_id"), nullable=False
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.session_id"), nullable=False
    )

    driver: Mapped[Driver] = relationship("Driver", back_populates="qualifying_results")
    round: Mapped[Round] = relationship("Round", back_populates="qualifying_results")
    category: Mapped[Category] = relationship(
        "Category", back_populates="qualifying_results"
    )
    session: Mapped[Session] = relationship("Session")

    def __str__(self) -> str:
        return f"QualifyingResult({self.driver_id}, {self.position}, {self.laptime})"

    @property
    def points_earned(self) -> float:
        """Points earned by the driver in this qualifying session."""
        if not self.position:
            return 0

        return self.session.point_system.scoring[self.relative_position - 1]


class CarClass(Base):
    """This object represents an in-game car class.
    CarClass records are meant to be reused multiple times for different categories
    and championships, their function is mainly to identify which type of car is
    assigned to drivers within the same category, this therefore allows to calculate
    statistics separately from one class and another.

    Attributes:
        car_class_id (int): Unique ID of the car class.
        name (str): Name of the car class.

        game_id (int): Unique ID of the game the car class is in.

        game (Game): Game object the car class is associated to.
    """

    __tablename__ = "car_classes"

    car_class_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(20), nullable=False)

    game_id: Mapped[int] = mapped_column(ForeignKey("games.game_id"), nullable=False)

    game: Mapped[Game] = relationship("Game")

    def __repr__(self) -> str:
        return f"CarClass(car_class_id={self.car_class_id}, name={self.name})"

    def __key(self) -> int:
        return self.car_class_id

    def __hash__(self) -> int:
        return hash(self.__key())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CarClass):
            return NotImplemented
        return self.car_class_id == other.car_class_id


class Team(Base):
    """This object represents a team.

    Attributes:
        reports_made (list[Report]): Reports made by the team.
        received_reports (list[Report]): Reports received by the team.

        drivers (list[DriverAssignment]): Drivers who are members of the team.
        leader (Driver): Driver who is allowed to make reports for the team.

        team_id (int): The team's unique ID.
        name (str): The team's unique name.
        credits (int): Number of credits available to the team. Used to buy cars and drivers.
    """

    __tablename__ = "teams"

    team_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    credits: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)

    championships: Mapped[list[TeamChampionship]] = relationship(
        "TeamChampionship", back_populates="team"
    )
    drivers: Mapped[list[DriverAssignment]] = relationship(
        "DriverAssignment", back_populates="team"
    )
    reports_made: Mapped[list[Report]] = relationship(
        "Report",
        back_populates="reporting_team",
        foreign_keys=[Report.reporting_team_id],
    )
    received_penalties: Mapped[list[Penalty]] = relationship(
        "Penalty",
        back_populates="reported_team",
        foreign_keys=[Penalty.reported_team_id],
    )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Team):
            return self.team_id == other.team_id
        return NotImplemented

    def __key(self) -> int:
        return self.team_id

    def __hash__(self) -> int:
        return hash(self.__key())

    @property
    def leader(self) -> Driver | None:
        """The leader of this team."""
        for driver in self.drivers:
            if driver.is_leader:
                return driver.driver
        return None

    def current_championship(self) -> TeamChampionship | None:
        """Returns the championship which is still underway."""
        for championship in self.championships:
            if championship.championship.is_active():
                return championship
        return None


class TeamChampionship(Base):
    """This class binds a Team and a Championship together.
    It allows to keep track of the Championships to which teams have participated,
    while also allowing to add penalties to a team's points tally.

    Attributes:
        team_id (int): ID of the team participating to the championship.
        championship_id (int): ID of the championship the team is entering.

        penalty_points (int): Points to be added to the team's points tally.
            Can be either a positive or a negative number.

        team (Team): Team object associated with the team_id
        championship (Championship): Championship object associated with the championship_id.
    """

    __tablename__ = "team_championships"

    team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), primary_key=True)
    championship_id: Mapped[int] = mapped_column(
        ForeignKey("championships.championship_id"), primary_key=True
    )
    penalty_points: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    team: Mapped[Team] = relationship("Team", back_populates="championships")
    championship: Mapped[Championship] = relationship(
        "Championship", back_populates="teams"
    )


class CategoryClass(Base):
    """This class binds a Category to a CarClass.
    It allows for a Category to be associated with multiple CarClasses while also
    reusing CarClasses for multiple Categories, since they are determined by the game
    and are unlikely to change.

    Attributes:
        category_id (int): ID of the category the class is being registered to.
        car_class_id (int): ID of the car_class being registered to the category.

        category (Category): Category object associated with the category_id.
        car_class (CarClass): CarClass object associated with the car_class_id
    """

    __tablename__ = "category_classes"

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.category_id"), primary_key=True
    )
    car_class_id: Mapped[int] = mapped_column(
        ForeignKey("car_classes.car_class_id"), primary_key=True
    )

    category: Mapped[Category] = relationship("Category", back_populates="car_classes")
    car_class: Mapped[CarClass] = relationship("CarClass")


class Game(Base):
    """Represents a game Categories can race in.

    Attributes:
        game_id (int): The game's unique ID.
        name (str): The name of the game.
    """

    __tablename__ = "games"

    game_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(30), unique=True, nullable=True)

    def __repr__(self) -> str:
        return f"Game(game_id={self.game_id}, name={self.name})"


class Category(Base):
    """Represents a category.

    Attributes:
        category_id (int): A Unique ID.
        name (str): Name of the category.

        championship_id (int): ID of the championship the category belongs to.
        game_id (int): ID of the game the category is based on.

        game (Game): Game the category is based on.
        rounds (list[Round]): Rounds in the category.
        race_results (list[RaceResult]): Registered race results.
        qualifying_results (list[QualifyingResult]): Registered qualifying results.
        drivers (list[Driver]): Drivers participating in the category. [Ordered by driver_id]
        championship (Championship): The championship the category belongs to.
    """

    __tablename__ = "categories"

    category_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.game_id"), nullable=False)
    championship_id: Mapped[int] = mapped_column(
        ForeignKey("championships.championship_id"), nullable=False
    )

    rounds: Mapped[list[Round]] = relationship(
        "Round", back_populates="category", order_by="Round.date"
    )
    race_results: Mapped[list[RaceResult]] = relationship(
        "RaceResult", back_populates="category"
    )
    qualifying_results: Mapped[list[QualifyingResult]] = relationship(
        "QualifyingResult", back_populates="category"
    )
    drivers: Mapped[list[DriverCategory]] = relationship(
        "DriverCategory", back_populates="category", order_by="DriverCategory.driver_id"
    )
    game: Mapped[Game] = relationship("Game")
    championship: Mapped[Championship] = relationship(
        "Championship", back_populates="categories"
    )
    car_classes: Mapped[list[CategoryClass]] = relationship(
        "CategoryClass",
        back_populates="category",
        order_by="CategoryClass.car_class_id",
    )

    def __repr__(self) -> str:
        return f"Category(category_id={self.category_id},name={self.name})"

    def first_non_completed_round(self) -> Round | None:
        """Returns the first non completed Round."""
        for rnd in self.rounds:
            if not rnd.completed:
                return rnd
        return None

    def last_completed_round(self) -> Round | None:
        """Returns the last completed Round."""
        for rnd in reversed(self.rounds):
            if rnd.completed:
                return rnd
        return None

    def next_round(self) -> Round | None:
        """Returns the next round on the calendar."""
        # Rounds in self.rounds are ordered by date
        for championship_round in self.rounds:
            if dt.combine(championship_round.date, time(hour=23)) >= dt.now():
                return championship_round
        return None

    def active_drivers(self) -> list[DriverCategory]:
        """Returns list of drivers who are currently competing in this category."""
        return [driver for driver in self.drivers if not driver.left_on]

    @property
    def multi_class(self) -> bool:
        """True if this Category has multiple car classes competing together."""
        return len(self.car_classes) > 1

    def standings(self, n=0) -> dict[Driver, list[float]]:
        """Calculates the current standings in this category.

        Args:
            n (Optional[int]): Number of races to go back. (Must be 0 or negative)

        Returns:
            DefaultDict[Driver, [int, int]]: DefaultDict containing Drivers as keys
                and a list containing the total points and the number of positions
                gained by the driver in the championship standings in the last
                completed_rounds - n races.
        """

        if n > 0:
            raise ValueError("n must be less or equals to 0")

        completed_rounds: list[Round] = []
        for round in self.rounds:
            if round.completed:
                completed_rounds.append(round)

        if n == 0:
            n = len(completed_rounds)

        results_up_to_n: DefaultDict[Driver, list[float]] = defaultdict(lambda: [0, 0])

        for round in completed_rounds[:n]:
            for race_result in round.race_results:
                results_up_to_n[race_result.driver][0] += race_result.points_earned

            for qualifying_result in round.qualifying_results:
                results_up_to_n[qualifying_result.driver][
                    0
                ] += qualifying_result.points_earned

        sorted_results_up_to_n = dict(
            sorted(results_up_to_n.items(), key=lambda x: x[1], reverse=True)
        )

        if n == len(self.race_results):
            return sorted_results_up_to_n

        # Calculates the points earned in the last n races
        results_after_n: DefaultDict[Driver, float] = defaultdict(lambda: 0)
        for round in completed_rounds[n:]:
            for race_result in round.race_results:
                results_after_n[race_result.driver] += race_result.points_earned
            for qualifying_result in round.qualifying_results:
                results_after_n[
                    qualifying_result.driver
                ] += qualifying_result.points_earned

        complete_results: DefaultDict[Driver, list[float]] = defaultdict(lambda: [0, 0])
        for driver, (points, _) in sorted_results_up_to_n.items():
            complete_results[driver][0] += points + results_after_n[driver]

        # Adds the drivers who may have joined the championship within those n races
        # in complete_results as well.
        for driver, points in results_after_n.items():
            if driver not in complete_results:
                complete_results[driver] = [points, 0]

        complete_sorted_results = dict(
            sorted(complete_results.items(), key=lambda x: x[1], reverse=True)
        )
        for i, driver in enumerate(complete_sorted_results):
            for i2, driver2 in enumerate(sorted_results_up_to_n):
                if driver2 == driver:
                    complete_sorted_results[driver][1] = i - i2
                    break

        return complete_sorted_results

    def standings_with_results(self):
        """Calculates the current standings in this category.

        Returns:
            list[list[list[RaceResult], int]]: The first level of nesting contains
                lists: each of those lists contains a list of RaceResult s and an
                integer representing the points tally the RaceResults amount to.
        """

        results: DefaultDict[Driver, list[Any]] = defaultdict(lambda: [[], 0])

        for race_result in self.race_results:
            results[race_result.driver][0].append(race_result)
            points_earned = race_result.points_earned
            results[race_result.driver][1] += points_earned

        for qualifying_result in self.qualifying_results:
            results[qualifying_result.driver][1] += qualifying_result.points_earned

        return sorted(list(results.values()), key=lambda x: x[1], reverse=True)

    def points_per_round(self):
        """Creates a list containing a list for each round which contains the total amount
        of points each driver had after that round.
        """
        array: list[list] = []
        drivers = [driver.driver.psn_id for driver in self.drivers]
        driver_map = defaultdict.fromkeys(drivers, 0.0)
        array.append(["Tappa"] + drivers)
        for number, round in enumerate(self.rounds, start=1):

            if not round.completed:
                continue

            array.append([number])

            for race_result in round.race_results:
                driver_map[race_result.driver.psn_id] += race_result.points_earned
            for qualifying_result in round.qualifying_results:
                driver_map[
                    qualifying_result.driver.psn_id
                ] += qualifying_result.points_earned

            array[number].extend(driver_map.values())

        return array


class PointSystem(Base):
    """
    This object represents a point system.
    Each point system can be associated with multiple Sessions.

    Attributes:
        point_system_id (int): A unique ID.
        point_system (str): String containing the number of points for each position,
            separated by a space. E.g. "25 18 15 .."
    """

    __tablename__ = "point_systems"

    point_system_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    point_system: Mapped[str] = mapped_column(String(60), nullable=False)

    def __repr__(self) -> str:
        return (
            f"PointSystem(point_system_id={self.point_system_id}, "
            f"point_system={self.point_system})"
        )

    @property
    def scoring(self) -> list[float]:
        """Dictionary which can be used to easily get the amount of points earned
        by using the finishing position in the race or qualifying session as the key to
        the dictionary."""
        return list(map(float, self.point_system.split()))


class Round(Base):
    """This object represents a round of a specific category.
    It is used to group RaceResults and QualifyingResults registered on a specific date.

    Attributes:
        round_id (int): Automatically generated unique ID assigned upon object creation.
        number (int): The number of the round in the calendar order.
        date (date): The date the round takes place on.
        circuit (str): The circuit the round takes place on.
        completed (bool): True if the round has been completed.

        category_id (int): Unique ID of the category the round belongs to.
        championship_id (int): Unique ID of the championship the round belongs to.

        championship (Championship): Championship the round belongs to.
        category (Category): Category the round belongs to.
        race_results (list[RaceResult]): All the race results registered to the round.
        qualifying_results (list[QualifyingResult]): All the qualifying results registered to
            the round.
    """

    __tablename__ = "rounds"

    round_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    circuit: Mapped[str] = mapped_column(String(40), nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.category_id"), nullable=False
    )
    championship_id: Mapped[int] = mapped_column(
        ForeignKey("championships.championship_id"), nullable=False
    )

    championship: Mapped[Championship] = relationship(
        "Championship", back_populates="rounds"
    )
    sessions: Mapped[list[Session]] = relationship("Session", back_populates="round")
    category: Mapped[Category] = relationship("Category", back_populates="rounds")
    race_results: Mapped[list[RaceResult]] = relationship(
        "RaceResult", back_populates="round"
    )
    reports: Mapped[list[Report]] = relationship("Report")
    penalties: Mapped[list[Penalty]] = relationship("Penalty")
    qualifying_results: Mapped[list[QualifyingResult]] = relationship(
        "QualifyingResult",
        back_populates="round",
    )

    def __repr__(self) -> str:
        return f"Round(circuit={self.circuit}, date={self.date}, completed={self.completed})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Round):
            return NotImplemented
        return self.round_id == other.round_id

    def generate_info_message(self) -> str:
        """Generates a message containing info on the category's races."""

        message = (
            f"<i><b>INFO {self.number}ᵃ TAPPA {self.category.name.upper()}</b></i>\n\n"
            f"<b>Tracciato:</b> <i>{self.circuit}</i>\n\n"
        )

        for session in self.sessions:

            if session.duration:
                race_length = (
                    f"<b>Durata:</b> <i>{session.duration.seconds // 60} min.</i>\n"
                )
            else:
                race_length = f"<b>Giri:</b> <i>{session.laps}</i>\n"

            message += (
                f"<i>{session.name}</i>\n"
                + race_length
                + f"<b>Consumo benzina:</b> <i>{session.fuel_consumption}x</i>\n"
                f"<b>Consumo gomme:</b> <i>{session.tyre_degradation}x</i>\n"
                f"<b>Orario:</b> <i>{session.time_of_day.strftime('%H:%M')}</i>\n"
            )
            if session.weather:
                message += f"<b>Meteo:</b> <i>{session.weather}</i>\n"

            message += "\n"

        return message

    @property
    def has_sprint_race(self) -> bool:
        """Returns True if the category has a sprint race."""
        return len(self.sessions) == 3

    @property
    def qualifying_session(self) -> Session | None:
        """Returns the Session where qualifying takes place in this Round."""
        for session in self.sessions:
            if session.is_quali:
                return session
        return None

    @property
    def race_sessions(self) -> list[Session] | None:
        sessions: list[Session] = []
        for session in self.sessions:
            if not session.is_quali:
                sessions.append(session)
        return None

    @property
    def sprint_race(self) -> Session | None:
        """Returns the first race session of this round."""
        for session in self.sessions:
            if "gara 1" in session.name.lower():
                return session
        return None

    @property
    def long_race(self) -> Session | None:
        """The Session object corresponding to this round's long race."""
        for session in self.sessions:
            name = session.name.lower()
            if "gara" == name or "2" in name or "lunga" in name:
                return session
        return None


class Session(Base):
    """This object represents a session.
    Sessions can be either Race or Qualifying sessions, this is determined by the
    name attribute.

    Attributes:
        session_id (int): Automatically generated unique ID assigned upon object creation.
        name (str): The name of the session.
        fuel_consumption (int): In-game fuel consumption setting.
        tyre_degradation (int): In-game tyre degradation setting.
        time_of_day (int): In-game session time setting.
        weather (str): In-game weather setting.
        laps (int): Number of laps to be completed. (None if session is time based)
        duration (timedelta): Session time limit. (None if session is based on number of laps)
        circuit (str): In-game setting for the circuit.

        round_id (int): Unique ID of the round the session belongs to.
        point_system_id (int): Unique ID of the point system used in the session.

        point_system (PointSystem): The point system used to interpret the results of a race.
        round (Round): Round which the session belongs to.
    """

    __tablename__ = "sessions"

    session_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(
        Enum("Gara 1", "Gara 2", "Gara", "Qualifica"), nullable=False
    )
    fuel_consumption: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    tyre_degradation: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    time_of_day: Mapped[datetime.time] = mapped_column(Time, nullable=False)
    weather: Mapped[str] = mapped_column(String(60))
    laps: Mapped[int] = mapped_column(SmallInteger)
    duration: Mapped[datetime.timedelta] = mapped_column(Interval)
    circuit: Mapped[str] = mapped_column(String(100), nullable=False)

    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.round_id"))
    point_system_id: Mapped[int] = mapped_column(
        ForeignKey("point_systems.point_system_id"), nullable=False
    )

    race_results: Mapped[list[RaceResult]] = relationship(
        "RaceResult", back_populates="session"
    )
    qualifying_results: Mapped[list[QualifyingResult]] = relationship(
        "QualifyingResult", back_populates="session"
    )
    point_system: Mapped[PointSystem] = relationship("PointSystem")
    reports: Mapped[list[Report]] = relationship("Report", back_populates="session")
    penalties: Mapped[list[Penalty]] = relationship("Penalty", back_populates="session")
    round: Mapped[Round] = relationship("Round", back_populates="sessions")

    def __repr__(self) -> str:
        return (
            f"Session(session_id={self.session_id}, name={self.name}, circuit={self.circuit}, "
            f"round_id={self.round_id}, tyres={self.tyre_degradation})"
        )

    def participating_drivers(self) -> list[Driver]:
        """Returns a list of drivers who have participated to this session."""
        drivers = []
        if self.is_quali:
            for quali_result in self.qualifying_results:
                if quali_result.participated:
                    drivers.append(quali_result.driver)
            return drivers

        for race_result in self.race_results:
            if race_result.participated:
                drivers.append(race_result.driver)
        return drivers

    def get_penalty_seconds_of(self, driver_id: int) -> int:
        """Returns total time penalties received by a driver."""
        seconds = 0
        for penalty in self.penalties:
            if penalty.reported_driver_id == driver_id:
                seconds += penalty.time_penalty
        return seconds

    def results_message(self) -> str:
        """Generates a message containing the results of this session."""
        message = f"<i>{self.name}</i>\n"

        # Sorts results, drivers who didn't participate are put to the back of the list.
        if self.is_quali:
            results: list[QualifyingResult] = sorted(
                self.qualifying_results,
                key=lambda x: x.laptime if x.laptime is not None else float("inf"),
            )
        else:
            results: list[RaceResult] = sorted(  # type: ignore
                self.race_results,
                key=lambda x: x.total_racetime
                if x.total_racetime is not None
                else float("inf"),
            )

        for result in results:
            if result.participated:
                position = str(result.relative_position)
                minutes, seconds = divmod(result.gap_to_first, 60)
                milliseconds = (seconds % 1) * 1000

                if not minutes:
                    gap = f"+<i>{int(seconds):01}.{int(milliseconds):03}</i>"
                else:
                    gap = f"+<i>{int(minutes):01}:{int(seconds):02}.{int(milliseconds):03}</i>"

            else:
                gap = "<i>assente</i>"
                position = "/"

            penalty_seconds = self.get_penalty_seconds_of(result.driver_id)
            message += f"{position} - {result.driver.psn_id} {gap}"

            if penalty_seconds:
                message += f" (+{penalty_seconds}s)"

            if getattr(result, "fastest_lap_points", 0):
                message += " GV"
            message += "\n"

        return message + "\n"

    @property
    def is_quali(self) -> bool:
        """Is True if this session is a qualifying session."""
        return "quali" in self.name.lower()


class RaceResult(Base):
    """This object represents a Driver's result in a race.
    Each Round will have multiple RaceResults, one (two if the round has a sprint race)
    for each driver in the Category the Round is registered in.

    Attributes:
        result_id (int): Automatically generated unique ID assigned upon object creation.
        finishing_position (int): The position the driver finished in the race.
        relative_position (int): Position in the driver's class.
        fastest_lap_points (int): Points obtained from fastest lap/pole position.
        participated (bool): True if the driver participated to the race.
        gap_to_first (Decimal): Difference between the driver's race time
            and the class winner's race time.
        total_racetime (Decimal): Total time the driver took to complete the race.

        driver_id (int): Unique ID of the driver the result is registered to.
        round_id (int): Unique ID of the round the result is registered to.
        category_id (int): Unique ID of the category the result is registered to.
        session_id (int): Unique ID of the session the result was made in.

        driver (Driver): Driver the result is registered to.
        round (Round): Round the result is registered to.
        category (Category): Category the result is registered to.
        session (Session): Session the result was registered in.
    """

    # pylint: disable=too-many-instance-attributes, too-many-arguments

    __tablename__ = "race_results"
    __table_args__ = (
        UniqueConstraint(
            "driver_id", "round_id", "session_id", name="_driver_round_session_uc"
        ),
    )

    result_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    finishing_position: Mapped[int] = mapped_column(SmallInteger)
    relative_position: Mapped[int] = mapped_column(SmallInteger)
    fastest_lap_points: Mapped[int] = mapped_column(
        SmallInteger, default=0, nullable=False
    )
    participated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gap_to_first: Mapped[Decimal] = mapped_column(Numeric(precision=8, scale=3))
    total_racetime: Mapped[Decimal] = mapped_column(Numeric(precision=8, scale=3))

    driver_id: Mapped[int] = mapped_column(
        ForeignKey("drivers.driver_id"), nullable=False
    )
    round_id: Mapped[int] = mapped_column(ForeignKey("rounds.round_id"), nullable=False)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.category_id"), nullable=False
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.session_id"), nullable=False
    )

    driver: Mapped[Driver] = relationship("Driver", back_populates="race_results")
    round: Mapped[Round] = relationship("Round", back_populates="race_results")
    category: Mapped[Category] = relationship("Category", back_populates="race_results")
    session: Mapped[Session] = relationship("Session", back_populates="race_results")

    def __repr__(self) -> str:
        return (
            f"RaceResult(driver_id={self.driver_id}, "
            f"finishing_position={self.finishing_position}, "
            f"fastest_lap_points={self.fastest_lap_points}, "
            f"total_racetime={self.total_racetime}) "
        )

    @property
    def points_earned(self) -> float:
        """Total amount of points earned by the driver in this race.
        (Finishing position + fastest lap points) *Does not take into account penalty points."""

        if not self.participated:
            return 0

        return (
            self.session.point_system.scoring[self.finishing_position - 1]
            + self.fastest_lap_points
        )


class Championship(Base):
    """This object represents a championship.
    Each Championship has multiple Drivers, Rounds and Categories categories associated to it.

    Attributes:
        championship_id (int): The championship's unique ID.
        championship_name (str): The championship's name.
        start (datetime.date): Date the championship starts on.
        end (datetime.date): Date the championship ends on.

        categories (list[Category]): Categories belonging to the championship.
            [Ordered by category_id]
        drivers (list[DriverChampionship]): Drivers participating in the championship.
        rounds (list[Round]): Rounds present in the championship.
    """

    __tablename__ = "championships"

    championship_id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    championship_name: Mapped[str] = mapped_column(
        String(60), unique=True, nullable=False
    )
    start: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end: Mapped[datetime.date] = mapped_column(Date)

    categories: Mapped[list[Category]] = relationship(
        "Category", back_populates="championship", order_by="Category.category_id"
    )
    teams: Mapped[list[TeamChampionship]] = relationship(
        "TeamChampionship", back_populates="championship"
    )
    rounds: Mapped[list[Round]] = relationship(
        "Round", back_populates="championship", order_by="Round.date"
    )

    def reporting_round(self) -> Round | None:
        """Returns the round in which reports can currently be created."""
        now = datetime.datetime.now().date()
        for round in self.rounds:
            if (round.date + timedelta(hours=24)) == now:
                return round
        return None

    def current_racing_category(self) -> Category | None:
        """Returns the category which races today."""
        for round in self.rounds:
            if round.date == datetime.datetime.now().date():
                return round.category
        return None

    def is_active(self) -> bool:
        """Returns True if the championship is ongoing."""
        return bool(self.non_disputed_rounds())

    def non_disputed_rounds(self) -> list[Round]:
        """Returns all the rounds which have not been disputed yet."""
        rounds = []
        for rnd in self.rounds:
            if not rnd.completed:
                rounds.append(rnd)
        return rounds

    @property
    def abbreviated_name(self) -> str:
        """Short version of the championship's name created by taking the first letter
        of each word in it.
        E.G. "eSports Championship 1" -> "EC1"
        """
        return "".join(i[0] for i in self.championship_name.split()).upper()

    @property
    def driver_list(self) -> list[Driver]:
        """List of drivers participating to this championship."""
        drivers = []
        for category in self.categories:
            for driver in category.drivers:
                drivers.append(driver.driver)
        return drivers
