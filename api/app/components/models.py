"""
This module contains the necessary SQLAlchemy models to keep track of
RacingTeamItalia's championships and drivers.
"""
from __future__ import annotations

import datetime
from decimal import Decimal
import uuid
from collections import defaultdict
from datetime import datetime as dt
from datetime import time, timedelta
from typing import DefaultDict

from cachetools import TTLCache
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Interval,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    Numeric,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship

# pylint: disable=too-many-lines, redefined-builtin
# In this project "round" always refers to an instance of a Round object.

Base = declarative_base()
cache = TTLCache(maxsize=3, ttl=timedelta(seconds=30))


class Penalty(Base):
    """This class represents a penalty applied to a driver in a given session.

    Attributes:
        *PERSISTED*
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

        *NON PERSISTED*
        These attributes are not persisted since they have no use outside of
        allowing the passing of a single object to the create_penalty_document
        function.

        incident_time (str): In-game time when the incident happened.
        fact (str): The fact given by the user creating the penalty.
        decision (str): The decision taken. (Made up from time_penalty, penalty_points,
            licence_points and warnings all combined into a nice text format generated
            by the bot).
        penalty_reason (str): Detailed explanation why the penalty was issued.
    """

    # pylint: disable=too-many-instance-attributes, too-many-arguments

    __tablename__ = "penalties"

    incident_time: str
    fact: str
    decision: str
    penalty_reason: str

    penalty_id = Column(Integer, primary_key=True)
    time_penalty: int = Column(SmallInteger, default=0, nullable=False)
    licence_points: int = Column(SmallInteger, default=0, nullable=False)
    warnings: int = Column(SmallInteger, default=0, nullable=False)
    penalty_points: float = Column(Float, default=0, nullable=False)
    number: int = Column(Integer, nullable=False)

    category: Category = relationship("Category")
    round: Round = relationship("Round", back_populates="penalties")
    session: Session = relationship("Session")

    category_id: int = Column(ForeignKey("categories.category_id"), nullable=False)
    round_id: int = Column(ForeignKey("rounds.round_id"), nullable=False)
    session_id: str = Column(ForeignKey("sessions.session_id"), nullable=False)
    reported_driver_id: str = Column(ForeignKey("drivers.driver_id"), nullable=False)
    reported_team_id: int = Column(ForeignKey("teams.team_id"), nullable=False)

    reported_driver: Driver = relationship(
        "Driver", back_populates="received_penalties", foreign_keys=[reported_driver_id]
    )
    reported_team: Team = relationship(
        "Team", back_populates="received_penalties", foreign_keys=[reported_team_id]
    )

    def __init__(
        self,
        reported_driver: Driver = None,
        time_penalty: int = 0,
        warnings: int = 0,
        licence_points: int = 0,
        penalty_points: int = 0,
        session: Session = None,
        round: Round = None,
        category: Category = None,
    ) -> None:
        """Initializes a Penalty form scratch.

        Args:
            reported_driver (Driver) = None
            time_penalty (int): Seconds to add to the driver's total race time.
            penalty_points (int): Points to be subtracted from the driver's
                points tally.
            licence_points (int): Points to be subtracted from the driver's licence.
            warnings (int): Number of warnings received.
        """
        self.reported_driver = reported_driver
        self.time_penalty = time_penalty
        self.warnings = warnings
        self.licence_points = licence_points
        self.penalty_points = penalty_points
        self.session = session
        self.round = round
        self.category = category
        self.reporting_driver = None

        if self.reported_driver:
            self.reported_team = reported_driver.current_team()

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

    video_link: str

    report_id: UUID = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    number: int = Column(SmallInteger, nullable=False)
    incident_time: str = Column(String(12), nullable=False)
    report_reason: str = Column(String(2000), nullable=False)
    is_reviewed: str = Column(Boolean, nullable=False, default=False)
    report_time: str = Column(
        DateTime, nullable=False, server_default="current_timestamp"
    )
    channel_message_id: int = Column(BigInteger)

    category_id: int = Column(ForeignKey("categories.category_id"), nullable=False)
    round_id: int = Column(ForeignKey("rounds.round_id"), nullable=False)
    session_id: str = Column(ForeignKey("sessions.session_id"), nullable=False)
    reported_driver_id: str = Column(ForeignKey("drivers.driver_id"), nullable=False)

    reporting_driver_id: str = Column(ForeignKey("drivers.driver_id"), nullable=False)
    reported_team_id: int = Column(ForeignKey("teams.team_id"), nullable=False)
    reporting_team_id: int = Column(ForeignKey("teams.team_id"), nullable=False)

    category: Category = relationship("Category")
    round: Round = relationship("Round", back_populates="reports")
    session: Session = relationship("Session")
    reported_driver: Driver = relationship("Driver", foreign_keys=[reported_driver_id])
    reporting_driver: Driver = relationship(
        "Driver", back_populates="reports_made", foreign_keys=[reporting_driver_id]
    )
    reported_team: Team = relationship("Team", foreign_keys=[reported_team_id])
    reporting_team: Team = relationship(
        "Team", back_populates="reports_made", foreign_keys=[reporting_team_id]
    )

    def __init__(self, **kwargs):
        """Returns a new Report object."""
        self.number = kwargs.get("number")
        self.incident_time = kwargs.get("incident_time")
        self.report_reason = kwargs.get("report_reason")
        self.video_link = kwargs.get("video_link")
        self.channel_message_id = kwargs.get("channel_message_id")

        self.category = kwargs.get("category")
        self.round = kwargs.get("round")
        self.session = kwargs.get("session")
        self.reported_driver = kwargs.get("reported_driver")
        self.reporting_driver = kwargs.get("reporting_driver")

        if self.reporting_driver:
            self.reporting_team = self.reporting_driver.current_team()
        if self.reported_driver:
            self.reported_team = self.reported_driver.current_team()

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

    joined_on: datetime.date = Column(
        Date, server_default=func.now(), default=False, nullable=False
    )
    left_on: datetime.date = Column(Date)
    bought_for: int = Column(SmallInteger)
    is_leader: bool = Column(Boolean, default=False)

    assignment_id: str = Column(UUID(as_uuid=True), primary_key=True, nullable=False)
    driver_id: int = Column(
        ForeignKey("drivers.driver_id"), primary_key=True, nullable=False
    )
    team_id: int = Column(ForeignKey("teams.team_id"), primary_key=True, nullable=False)

    driver: Driver = relationship("Driver", back_populates="teams")
    team: Team = relationship("Team", back_populates="drivers")

    def __init__(self, driver: Driver, team: Team, **kwargs) -> None:
        """Returns a new DriverAssignment object.
        Args:
            driver (Driver): Driver joining the team.
            team (Team): Team acquiring the driver.

        Optional Keyword Args:
            bought_for (int): Price the team paid to acquire the driver.
        """
        self.driver = driver
        self.team = team

        self.bought_for = kwargs.get("bought_for")


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

    joined_on: datetime.date = Column(Date, server_default=func.now())
    left_on: datetime.date = Column(Date)
    race_number: int = Column(SmallInteger, nullable=False)
    warnings: int = Column(SmallInteger, default=0, nullable=False)
    licence_points: int = Column(SmallInteger, default=10, nullable=False)

    driver_id: int = Column(ForeignKey("drivers.driver_id"), primary_key=True)
    category_id: int = Column(ForeignKey("categories.category_id"), primary_key=True)
    car_class_id: int = Column(ForeignKey("car_classes.car_class_id"), nullable=True)

    driver: Driver = relationship("Driver", back_populates="categories")
    category: Category = relationship("Category", back_populates="drivers")
    car_class: CarClass = relationship("CarClass")

    def __init__(self, driver: Driver, category: Category, **kwargs) -> None:
        """Returns a new DriverCategory object.
        Args:
            driver (Driver): Driver joining the category.
            category (Category): Category being joined by the driver.

        Optional Keyword Arguments:
            race_number (int): The number used by the driver in the category.
            joined_on (date): The date the driver joined the category on.
            left_on (date): The date the driver left the category on.
            car_class (CarClass): CarClass the driver is in.
        """
        self.driver = driver
        self.category = category

        self.car_class = kwargs.get("car_class")
        self.joined_on = kwargs.get("joined_on")
        self.race_number = kwargs.get("race_number")
        self.left_on = kwargs.get("left_on")


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

    driver_id: int = Column(SmallInteger, primary_key=True)
    psn_id: str = Column(String(16), unique=True, nullable=False)
    _telegram_id: str = Column("telegram_id", Text, unique=True)

    teams: list[DriverAssignment] = relationship(
        "DriverAssignment", back_populates="driver"
    )
    categories: list[DriverCategory] = relationship(
        "DriverCategory", back_populates="driver"
    )
    race_results: list[RaceResult] = relationship("RaceResult", back_populates="driver")
    received_penalties: list[Penalty] = relationship(
        "Penalty", back_populates="reported_driver"
    )
    reports_made: list[Report] = relationship(
        "Report",
        back_populates="reporting_driver",
        foreign_keys=[Report.reporting_driver_id],
    )
    qualifying_results: list[QualifyingResult] = relationship(
        "QualifyingResult", back_populates="driver"
    )

    def __init__(self, psn_id: str, **kwargs) -> None:
        """Returns a new Driver object.

        Args:
            psn_id (str): The driver's Playstation ID (max 16 characters).

        Optional Keyword Args:
            telegram_id (str): The driver's telegram ID.
        """
        self.psn_id = psn_id
        self.telegram_id = kwargs.get("telegram_id")

    def __repr__(self) -> None:
        return f"Driver(psn_id={self.psn_id}, driver_id={self.driver_id})"

    def __eq__(self, other: Driver) -> bool:
        if isinstance(other, Driver):
            return self.driver_id == other.driver_id
        return NotImplemented

    def __key(self) -> tuple:
        return self.driver_id, self.psn_id

    def __hash__(self) -> int:
        return hash(self.__key())

    def current_team(self) -> Team:
        """Returns the team the driver is currently competing with."""
        for team in self.teams:
            if not team.left_on:
                return team.team

    def current_category(self) -> Category | None:
        """Returns the team the driver is currently competing in."""
        for category in self.categories:
            if not category.left_on:
                return category.category

    def current_class(self) -> CarClass:
        """Returns the car class the driver is currently competing in."""
        for category in self.categories:
            if not category.left_on:
                return category.car_class

    @property
    def current_race_number(self) -> int:
        """The number currently being used by the Driver in races."""
        for driver_category in self.current_category().drivers:
            if self.driver_id == driver_category.driver_id:
                return driver_category.race_number

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

    qualifying_result_id: int = Column(SmallInteger, primary_key=True)
    position: int = Column(SmallInteger)
    relative_position: int = Column(SmallInteger)
    laptime: Decimal = Column(Numeric(precision=8, scale=3))
    gap_to_first: Decimal = Column(Numeric(precision=8, scale=3))
    participated: bool = Column(Boolean, default=False, nullable=False)

    driver_id: int = Column(ForeignKey("drivers.driver_id"), nullable=False)
    round_id: int = Column(ForeignKey("rounds.round_id"), nullable=False)
    category_id: int = Column(ForeignKey("categories.category_id"), nullable=False)
    session_id: int = Column(ForeignKey("sessions.session_id"), nullable=False)

    driver: Driver = relationship("Driver", back_populates="qualifying_results")
    round: Round = relationship("Round", back_populates="qualifying_results")
    category: Category = relationship("Category", back_populates="qualifying_results")
    session: Session = relationship("Session")

    def __init__(
        self,
        position: int,
        laptime: Decimal,
        gap_to_first: Decimal,
        driver: Driver,
        round: Round,
        participated: bool,
        relative_position: int,
    ) -> None:
        """Returns a new QualifyingResult object.

        Args:
            position (int): Position the driver qualified in.
            laptime (Decimal): Best lap registered by the driver.
            driver (Driver): Driver the result belongs to.
            session (Session): Session the result was made in.
        """
        self.position = position
        self.laptime = laptime
        self.gap_to_first = gap_to_first
        self.driver = driver
        self.round = round
        self.participated = participated
        self.relative_position = relative_position

        self.category = round.category
        self.session = self.round.qualifying_session

    def __str__(self) -> str:
        return f"QualifyingResult({self.driver_id}, {self.position}, {self.laptime})"

    @property
    def points_earned(self) -> float:
        """Points earned by the driver in this qualifying session."""
        if not self.position:
            return 0

        scoring = self.session.point_system.scoring
        return scoring[self.relative_position - 1]


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

    car_class_id: int = Column(Integer, primary_key=True)
    name: str = Column(String(20), nullable=False)

    game_id: int = Column(ForeignKey("games.game_id"), nullable=False)

    game: Game = relationship("Game")

    def __init__(self, name: str, game: Game):
        self.name = name
        self.game = game

    def __repr__(self) -> str:
        return f"CarClass(car_class_id={self.car_class_id}, name={self.name})"

    def __key(self) -> tuple[int, str]:
        return self.car_class_id

    def __hash__(self) -> int:
        return hash(self.__key())

    def __eq__(self, other: CarClass) -> bool:
        if isinstance(other, CarClass):
            return self.car_class_id == other.car_class_id
        return NotImplemented


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

    team_id: int = Column(SmallInteger, primary_key=True)
    name: str = Column(String(20), unique=True, nullable=False)
    credits: int = Column(SmallInteger, default=0, nullable=False)

    championships: list[TeamChampionship] = relationship(
        "TeamChampionship", back_populates="team"
    )
    drivers: list[DriverAssignment] = relationship(
        "DriverAssignment", back_populates="team"
    )
    reports_made: list[Report] = relationship(
        "Report",
        back_populates="reporting_team",
        foreign_keys=[Report.reporting_team_id],
    )
    received_penalties: list[Penalty] = relationship(
        "Penalty",
        back_populates="reported_team",
        foreign_keys=[Penalty.reported_team_id],
    )

    def __init__(self, name: str) -> None:
        """Returns a new Team object.

        Args:
            name (str): The team's unique name.
        """
        self.name = name

    def __eq__(self, __o: Team) -> bool:
        if isinstance(__o, Team):
            return self.team_id == __o.team_id
        return NotImplemented

    def __key(self) -> tuple[int, str]:
        return self.team_id

    def __hash__(self) -> int:
        return hash(self.__key())

    @property
    def leader(self) -> Driver:
        """The leader of this team."""
        for driver in self.drivers:
            if driver.is_leader:
                return driver.driver

    def current_championship(self) -> TeamChampionship:
        """Returns the championship which is still underway."""
        for championship in self.championships:
            if championship.championship.is_active():
                return championship


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

    team_id: int = Column(ForeignKey("teams.team_id"), primary_key=True)
    championship_id: int = Column(
        ForeignKey("championships.championship_id"), primary_key=True
    )
    penalty_points: int = Column(SmallInteger, nullable=False, default=0)

    team: Team = relationship("Team", back_populates="championships")
    championship: Championship = relationship("Championship", back_populates="teams")


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

    category_id: int = Column(ForeignKey("categories.category_id"), primary_key=True)
    car_class_id: int = Column(ForeignKey("car_classes.car_class_id"), primary_key=True)

    category: Category = relationship("Category", back_populates="car_classes")
    car_class: CarClass = relationship("CarClass")


class Game(Base):
    """Represents a game Categories can race in.

    Attributes:
        game_id (int): The game's unique ID.
        name (str): The name of the game.
    """

    __tablename__ = "games"

    game_id: int = Column(Integer, primary_key=True)
    name: str = Column(String(30), unique=True, nullable=True)

    def __init__(self, name: str) -> None:
        self.name = name

    def __repr__(self) -> str:
        return f"Game(game_id={self.game_id}, name={self.name})"


class Category(Base):
    """Represents a category.

    Attributes:
        category_id (int): A Unique ID.
        name (str): Name of the category.
        round_weekday (int): Day of the week (Mon = 0, Sun = 6) when the races happen.

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

    category_id: int = Column(SmallInteger, primary_key=True)
    name: str = Column(String(20), nullable=False)
    round_weekday: int = Column(SmallInteger, nullable=False)
    game_id: int = Column(ForeignKey("games.game_id"), nullable=False)
    championship_id: int = Column(
        ForeignKey("championships.championship_id"), nullable=False
    )

    rounds: list[Round] = relationship(
        "Round", back_populates="category", order_by="Round.number"
    )
    race_results: list[RaceResult] = relationship(
        "RaceResult", back_populates="category"
    )
    qualifying_results: list[QualifyingResult] = relationship(
        "QualifyingResult", back_populates="category"
    )
    drivers: list[DriverCategory] = relationship(
        "DriverCategory", back_populates="category", order_by="DriverCategory.driver_id"
    )
    game: Game = relationship("Game")
    championship: Championship = relationship(
        "Championship", back_populates="categories"
    )
    car_classes: list[CategoryClass] = relationship(
        "CategoryClass",
        back_populates="category",
        order_by="CategoryClass.car_class_id",
    )

    def __init__(self, category_id: int, name: str, game: Game) -> None:
        """Returns a new Category object.

        Args:
            category_id (int): A unique ID.
            name (str): Name of the category.
            game (Game): Game the category is based on.

        """
        self.category_id = category_id
        self.name = name
        self.game = game

    def __repr__(self) -> str:
        return f"Category(category_id={self.category_id},name={self.name})"

    def first_non_completed_round(self) -> Round:
        """Returns the first non completed Round."""
        for rnd in self.rounds:
            if not rnd.completed:
                return rnd

    def last_completed_round(self) -> Round:
        """Returns the last completed Round."""
        for rnd in reversed(self.rounds):
            if rnd.completed:
                return rnd

    def next_round(self) -> Round | None:
        """Returns the next round on the calendar."""
        # Rounds in self.rounds are ordered by date
        for championship_round in self.rounds:
            if dt.combine(championship_round.date, time(hour=23)) >= dt.now():
                return championship_round

    def active_drivers(self) -> list[Driver]:
        """Returns list of drivers who are currently competing in this category."""
        return [driver for driver in self.drivers if not driver.left_on]

    @property
    def multi_class(self) -> bool:
        """True if this Category has multiple car classes competing together."""
        return len(self.car_classes) > 1

    def standings(self, n=0) -> DefaultDict[Driver, int]:
        """Calculates the current standings in this category.

        Args (Optional):
            n (int): Number of races to go back. (Must be 0 or negative)

        Returns:
            DefaultDict[Driver, [int, int]]: DefaultDict containing Drivers as keys
                and a list containing the total points and the number of positions
                gained by the driver in the championship standings  since the last n
                number of races.
        """

        if n > 0:
            raise ValueError("n must be less or equals to 0")

        completed_rounds: list[Round] = []
        for round in self.rounds:
            if round.completed:
                completed_rounds.append(round)

        if n == 0:
            n = len(completed_rounds)

        results: DefaultDict[Driver, int] = defaultdict(lambda: 0)

        for round in completed_rounds[:n]:
            for race_result in round.race_results:
                results[race_result.driver] += race_result.points_earned

            for qualifying_result in round.qualifying_results:
                results[qualifying_result.driver] += qualifying_result.points_earned

        results = sorted(results.items(), key=lambda x: x[1], reverse=True)

        if n == len(self.race_results):
            return results

        results = dict(results)

        # Calculate the points earned in the last n races
        results_2: DefaultDict[Driver, int] = defaultdict(lambda: 0)

        for round in completed_rounds[n:]:

            for race_result in round.race_results:
                results_2[race_result.driver] += race_result.points_earned
            for qualifying_result in round.qualifying_results:
                results_2[qualifying_result.driver] += qualifying_result.points_earned

        complete_results = defaultdict(lambda: [0, 0])
        for driver, points in results.items():
            complete_results[driver][0] += points + results_2[driver]

        for driver, points in results_2.items():
            if driver not in complete_results:
                complete_results[driver] = [points, 0]

        complete_results = sorted(
            complete_results.items(), key=lambda x: x[1], reverse=True
        )
        complete_results = {
            driver: [points, pos] for driver, (points, pos) in complete_results
        }

        for i, driver in enumerate(complete_results):
            for i2, driver2 in enumerate(results):
                if driver2 == driver:
                    complete_results[driver][1] = i - i2
                    break

        return complete_results

    def standings_with_results(self):
        """Calculates the current standings in this category.

        Returns:
            list[list[list[RaceResult], int]]: The first level of nesting contains
                lists: each of those lists contains a list of RaceResult s and an
                integer representing the points tally the RaceResults amount to.
        """

        results: DefaultDict[Driver, list[list[RaceResult], int]] = defaultdict(
            lambda: [[], 0]
        )

        for race_result in self.race_results:
            results[race_result.driver][0].append(race_result)
            points_earned = race_result.points_earned
            results[race_result.driver][1] += points_earned

        for qualifying_result in self.qualifying_results:
            results[qualifying_result.driver][1] += qualifying_result.points_earned

        return sorted(list(results.values()), key=lambda x: x[1], reverse=True)

    def can_report_today(self) -> bool:
        """Returns True if today is reporting day for this category."""
        return datetime.datetime.now().weekday() == self.round_weekday + 1


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

    point_system_id: int = Column(SmallInteger, primary_key=True)
    point_system: str = Column(String(60), nullable=False)

    def __init__(self, point_system_id: int, point_system: str) -> None:
        self.point_system_id = point_system_id
        self.point_system = point_system

    def __repr__(self) -> str:
        return (
            f"PointSystem(point_system_id={self.point_system_id}, "
            f"point_system={self.point_system})"
        )

    @property
    def scoring(self) -> dict[int, float]:
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

    round_id: int = Column(SmallInteger, primary_key=True)
    number: int = Column(SmallInteger, nullable=False)
    date: datetime.date = Column(Date, nullable=False)
    circuit: str = Column(String(40), nullable=False)
    completed: bool = Column(Boolean, default=False, nullable=False)

    category_id: int = Column(ForeignKey("categories.category_id"), nullable=False)
    championship_id: int = Column(
        ForeignKey("championships.championship_id"), nullable=False
    )

    championship: Championship = relationship("Championship", back_populates="rounds")
    sessions: list[Session] = relationship("Session", back_populates="round")
    category: Category = relationship("Category", back_populates="rounds")
    race_results: list[RaceResult] = relationship("RaceResult", back_populates="round")
    reports: list[Report] = relationship("Report")
    penalties: list[Penalty] = relationship("Penalty")
    qualifying_results: list[QualifyingResult] = relationship(
        "QualifyingResult",
        back_populates="round",
    )

    def __init__(
        self,
        circuit: str,
        date: datetime.date,
        number: int,
    ) -> None:
        """Returns a new Round object.

        Args:
            circuit (str): The circuit the round takes place on.
            date (date): The date the round takes place on.
            number (int): The number of the round in the calendar order.
        """
        self.circuit = circuit
        self.date = date
        self.number = number

    def __repr__(self) -> str:
        return f"Round(circuit={self.circuit}, date={self.date}, completed={self.completed})"

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
    def qualifying_session(self) -> Session:
        """Returns the Session where qualifying takes place in this Round."""
        for session in self.sessions:
            if session.is_quali:
                return session

    @property
    def sprint_race(self) -> Session:
        """Returns the first race session of this round."""
        for session in self.sessions:
            if "gara 1" in session.name.lower():
                return session

    @property
    def long_race(self) -> Session:
        """The Session object corresponding to this round's long race."""
        for session in self.sessions:
            name = session.name.lower()
            if "gara" == name or "2" in name or "lunga" in name:
                return session


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

    session_id: int = Column(SmallInteger, primary_key=True)
    name: str = Column(Enum("Gara 1", "Gara 2", "Gara", "Qualifica"), nullable=False)
    fuel_consumption: int = Column(SmallInteger, nullable=False)
    tyre_degradation: int = Column(SmallInteger, nullable=False)
    time_of_day: datetime.time = Column(Time, nullable=False)
    weather: str = Column(String(60))
    laps: int = Column(SmallInteger)
    duration: datetime.timedelta = Column(Interval)
    circuit: str = Column(String(100), nullable=False)

    round_id: int = Column(ForeignKey("rounds.round_id"))
    point_system_id: int = Column(
        ForeignKey("point_systems.point_system_id"), nullable=False
    )

    race_results: list[RaceResult] = relationship(
        "RaceResult", back_populates="session"
    )
    qualifying_results: list[QualifyingResult] = relationship(
        "QualifyingResult", back_populates="session"
    )
    point_system: PointSystem = relationship("PointSystem")
    reports: list[Report] = relationship("Report", back_populates="session")
    penalties: list[Penalty] = relationship("Penalty", back_populates="session")
    round: Round = relationship("Round", back_populates="sessions")

    def __init__(self, name: str, point_system: PointSystem) -> None:
        """Returns a new Session object.

        Args:
            name (str): The name of the session.
            point_system (PointSystem): The point system used to interpret the results of a race.
        """
        self.name = name
        self.point_system = point_system

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

    def get_penalty_seconds_of(self, driver_id: int) -> list[Penalty]:
        """Returns total time penalties received by a driver."""
        seconds = 0
        for penalty in self.penalties:
            if penalty.reported_driver_id == driver_id:
                seconds += penalty.time_penalty
        return seconds

    def results(self) -> str:
        """Generates a message containing the results of this session."""
        message = f"<i>{self.name}</i>\n"

        # Sorts results, drivers who didn't participate are put to the back of the list.
        if self.is_quali:
            results = sorted(
                self.qualifying_results,
                key=lambda x: x.laptime if x.laptime is not None else float("inf"),
            )
        else:
            results = sorted(
                self.race_results,
                key=lambda x: x.total_racetime
                if x.total_racetime is not None
                else float("inf"),
            )

        for result in results:
            if result.participated:
                position = result.relative_position
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

    result_id: int = Column(Integer, primary_key=True)
    finishing_position: int = Column(SmallInteger)
    relative_position: int = Column(SmallInteger)
    fastest_lap_points: int = Column(SmallInteger, default=0, nullable=False)
    participated: bool = Column(Boolean, default=False, nullable=False)
    gap_to_first: Decimal = Column(Numeric(precision=8, scale=3))
    total_racetime: Decimal = Column(Numeric(precision=8, scale=3))

    driver_id: int = Column(ForeignKey("drivers.driver_id"), nullable=False)
    round_id: int = Column(ForeignKey("rounds.round_id"), nullable=False)
    category_id: int = Column(ForeignKey("categories.category_id"), nullable=False)
    session_id: int = Column(ForeignKey("sessions.session_id"), nullable=False)

    driver: Driver = relationship("Driver", back_populates="race_results")
    round: Round = relationship("Round", back_populates="race_results")
    category: Category = relationship("Category", back_populates="race_results")
    session: Session = relationship("Session", back_populates="race_results")

    def __init__(
        self,
        finishing_position: int,
        fastest_lap_points: int,
        driver: Driver,
        session: Session,
        **kwargs,
    ) -> None:
        """Returns a new RaceResult object.

        Args:
            finishing_position (int): The position the driver finished in the race.
            bonus_points (int): Points to be added from the driver's total.
            driver (Driver): Driver the result is registered to.
            session (Session): Session the result was registered in.

        Keyword Args:
            round (Round): Round the result is registered to.
            penalty_points (int): Points to be subtracted from the driver's total.
            gap_to_first (Decimal): Difference between the driver's race time
                and the class winner's race time.
            total_racetime (Decimal): Total time the driver took to complete the race.
            participated (bool): True if the driver participated to the race.
        """
        self.finishing_position = finishing_position
        self.driver = driver
        self.session = session
        self.fastest_lap_points = fastest_lap_points
        self.round = kwargs.get("round")
        self.gap_to_first = kwargs.get("gap_to_first")
        self.total_racetime = kwargs.get("total_racetime")
        self.participated = bool(kwargs.get("participated"))
        self.relative_position = kwargs.get("relative_position")
        if self.round:
            self.category = self.round.category

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

        scoring = self.session.point_system.scoring

        points = scoring[self.finishing_position - 1] + self.fastest_lap_points

        return points


class Championship(Base):
    """This object represents a championship.
    Each Championship has multiple Drivers, Rounds and Categories categories associated to it.

    Attributes:
        championship_id (int): The championship's unique ID.
        championship_name (str): The championship's name.
        start (datetime.date): Date the championship starts on.
        end (datetime.date): Date the championship ends on.

        categories (list[Category]): Categories belonging to the championship.
            [Ordered by round_weekday]
        drivers (list[DriverChampionship]): Drivers participating in the championship.
        rounds (list[Round]): Rounds present in the championship.
    """

    __tablename__ = "championships"

    championship_id: int = Column(SmallInteger, primary_key=True)
    championship_name: str = Column(String(60), unique=True, nullable=False)
    start: datetime.date = Column(Date, nullable=False)
    end: datetime.date = Column(Date)

    categories: list[Category] = relationship(
        "Category", back_populates="championship", order_by="Category.round_weekday"
    )
    teams: list[TeamChampionship] = relationship(
        "TeamChampionship", back_populates="championship"
    )
    rounds: list[Round] = relationship(
        "Round", back_populates="championship", order_by="Round.date"
    )

    def __init__(self, championship_id: int, start: datetime.date, **kwargs) -> None:
        """Returns a new Championship object.

        Args:
            championship_id (int): The championship's unique ID.
             (datetime.date): Date the championship starts on.

        Keyword Args:
            championship_name (str): The championship's name.
            end (datetime.date): Date the championship ends on.
        """
        self.championship_id = championship_id
        self.start = start
        self.championship_name = (
            kwargs.get("name") if kwargs else f"Campionato {championship_id}"
        )
        self.end = kwargs.get("end")

    def reporting_category(self) -> Category | None:
        """Returns the category which can create reports today."""
        for category in self.categories:
            if (
                category.round_weekday
                == (datetime.datetime.now() - timedelta(days=1)).weekday()
            ):
                return category
        return None

    def current_racing_category(self) -> Category | None:
        """Returns the category which races today."""
        for category in self.categories:
            if category.round_weekday == datetime.datetime.now().weekday():
                return category
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
