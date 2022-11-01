from __future__ import annotations

import datetime
from collections import defaultdict
from datetime import timedelta
from typing import DefaultDict
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class Report(Base):
    """This object represents a report.
    Each report is associated with two Drivers and their Teams,
    as well as the Category, Round and Session the reported incident happened in.
    N.B. fact, penalty, penalty_reason and is_queued may only be provided after the report has been
    reviewed

    Attributes:
        report_id (int): Automatically generated unique ID assigned upon report creation.
        number (int): The number of the report in the order of the batch it was received in.
        incident_time (str): String formatted in mm:ss indicating the time when the accident
            happened.
        report_reason (str): The reason provided by the reporter for making the report.
        video_link: (str): The link towards a YouTube video showing the accident
            happening in a qualifying session.


        fact (str): Brief description of the accident made by the Safety Commission.
        penalty (str): The penalty inflicted to the driver. This attribute must be left empty
            in case the reported_driver is not found culpable.
        time_penalty (int): Seconds to add to the driver's total race time.
        championship_penalty_points (int) Points to be subtracted from the driver's point tally.
        licence_penalty_points (int) Points to be subtracted from the driver's licence.
        penalty_reason (str): Detailed explanation of the reason the penalty was inflicted for.
        is_queued (bool): True if the reviewed report is in queue to be sent out
            to the reports channel.
        report_time (datetime): Timestamp indicating when the report was made.
        channel_message_id: ID of the message the report was sent by the user with.

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

    __tablename__ = "reports"
    __table_args__ = (CheckConstraint("reporting_team_id != reported_team_id"),)

    report_id: int = Column(Integer, primary_key=True)
    number: int = Column("number", SmallInteger, nullable=False)
    incident_time: str = Column(String(12), nullable=False)
    report_reason: str = Column(String(2000), nullable=False)
    video_link: str = Column(String(80))

    fact: str = Column(String(400))
    penalty: str = Column(String(100))
    time_penalty: int = Column(SmallInteger)
    championship_penalty_points = Column(SmallInteger)
    licence_penalty_points: int = Column(SmallInteger)
    penalty_reason: str = Column(String(2000))
    is_reviewed: bool = Column(Boolean, default=False)
    is_queued: bool = Column(Boolean, default=False)
    report_time: datetime = Column(DateTime, server_default=func.now())

    channel_message_id: int = Column(BigInteger)

    category_id: int = Column(ForeignKey("categories.category_id"), nullable=False)
    round_id: int = Column(ForeignKey("rounds.round_id"), nullable=False)
    session_id: str = Column(ForeignKey("sessions.session_id"), nullable=False)
    reported_driver_id: str = Column(ForeignKey("drivers.psn_id"), nullable=False)
    # reporting_driver_id and reporting_team_id are nullable because admins can decide
    # to assign penalties for reasons other than contact between two drivers
    reporting_driver_id: str = Column(ForeignKey("drivers.psn_id"))
    reported_team_id: int = Column(ForeignKey("teams.team_id"), nullable=False)
    reporting_team_id: int = Column(ForeignKey("teams.team_id"))

    category: Category = relationship("Category")
    round: Round = relationship("Round")
    session: Session = relationship("Session")
    reported_driver: Driver = relationship(
        "Driver", back_populates="received_reports", foreign_keys=[reported_driver_id]
    )
    reporting_driver: Driver = relationship(
        "Driver", back_populates="reports_made", foreign_keys=[reporting_driver_id]
    )
    reported_team: Team = relationship(
        "Team", back_populates="received_reports", foreign_keys=[reported_team_id]
    )
    reporting_team: Team = relationship(
        "Team", back_populates="reports_made", foreign_keys=[reporting_team_id]
    )

    def __init__(self):
        """Returns a new Report object."""


class DriverAssignment(Base):
    """This object creates an association between a Driver and a Team

    Attributes:
        joined_on (date): Date the driver joined the team.
        left_on (date): Date the driver left the team.
        bought_for (int): Price the team paid to acquire the driver.
        is_leader (bool): Indicates whether the driver is also the leader of that team.

        assignment_id (str): Auto-generated UUID assigned upon object creation.
        driver_id (int): Unique ID of the driver joining the team.
        team_id (int): Unique ID of the team acquiring the driver.

        driver (Driver): Driver joining the team.
        team (Team): Team acquiring the driver.
    """

    __tablename__ = "driver_assignments"
    __table_args__ = (UniqueConstraint("joined_on", "driver_id", "team_id"),)

    joined_on: datetime.date = Column(Date, server_default=func.now())
    left_on: datetime.date = Column(Date)
    bought_for: int = Column(SmallInteger)
    is_leader: bool = Column(Boolean)

    assignment_id: str = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    driver_id: int = Column(ForeignKey("drivers.driver_id"), primary_key=True)
    team_id: int = Column(ForeignKey("teams.team_id"), primary_key=True)

    driver: Driver = relationship("Driver", back_populates="teams")
    team: Team = relationship("Team", back_populates="drivers")

    def __init__(self, driver: Driver, team: Team, **kwargs) -> None:
        """Returns a new DriverAssignment object.
        Args:
            driver (Driver): Driver joining the team.
            team (Team): Team acquiring the driver.

        Keyword Args:
            bought_for (int): Price the team paid to acquire the driver.
        """
        self.driver = driver
        self.team = team

        self.bought_for = kwargs.get("bought_for")


class DriverCategory(Base):
    """This object creates a new association between a Driver and a Category.

    Attributes:
        joined_on (date): The date the driver joined the category on.
        race_number (int): The number used by the driver in the category.

        driver_category_id (int): Automatically generated unique ID assigned upon object creation.
        driver_id (int): Unique ID of the driver joining the category.
        category_id (int): Unique ID of the category being joined by the driver.

        car_class_id (int): Unique ID of the car class the driver is in.

        driver (Driver): Driver joining the category.
        category (Category): Category being joined by the driver.
    """

    __tablename__ = "drivers_categories"

    __table_args__ = (UniqueConstraint("joined_on", "driver_id", "category_id"),)

    joined_on: datetime.date = Column(Date, server_default=func.now())
    left_on: datetime.date = Column(Date)
    licence_points: int = Column(Integer, default=10)
    race_number: int = Column(SmallInteger)

    driver_id: int = Column(ForeignKey("drivers.driver_id"), primary_key=True)
    category_id: int = Column(ForeignKey("categories.category_id"), primary_key=True)
    car_class_id: int = Column(ForeignKey("car_classes.car_class_id"))

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

        championship (list[DriverChampionship]): Championships the driver has participated in.
        teams (list[DriverAssignment]): Teams the driver has been acquired by.
        categories (list[DriverCategory]): Categories the driver has participated in.
        race_results (list[RaceResult]): Results made by the driver in his career.
        received_reports (list[Report]): Reports made against the driver during his career.
        reports_made (list[Report]): Reports made by the driver during his career.
        qualifying_results (list[Report]): Results obtained by the driver in qualifying sessions
            during his career.
    """

    __tablename__ = "drivers"

    driver_id: int = Column(SmallInteger, primary_key=True)
    psn_id: str = Column(String(16), unique=True, nullable=False)
    _telegram_id: str = Column("telegram_id", Text)

    championships: list[DriverChampionship] = relationship(
        "DriverChampionship", back_populates="driver"
    )
    teams: list[DriverAssignment] = relationship(
        "DriverAssignment", back_populates="driver"
    )
    categories: list[DriverCategory] = relationship(
        "DriverCategory", back_populates="driver"
    )
    race_results: list[RaceResult] = relationship("RaceResult", back_populates="driver")
    received_reports: list[Report] = relationship(
        "Report",
        back_populates="reported_driver",
        foreign_keys=[Report.reported_driver_id],
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

    def __eq__(self, __o: Driver) -> bool:
        return self.driver_id == __o.driver_id

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
    def race_number(self) -> int:
        for driver_category in self.current_category().drivers:
            if self.driver_id == driver_category.driver_id:
                return driver_category.race_number

    @property
    def telegram_id(self) -> int | None:
        if self._telegram_id:
            return int(self._telegram_id)
        return None

    @telegram_id.setter
    def telegram_id(self, telegram_id: int):
        if not isinstance(telegram_id, int):
            raise TypeError
        if telegram_id:
            self._telegram_id = str(telegram_id)


class QualifyingResult(Base):
    """This object represents a single result made by a driver in a qualifying Session.

    Attributes:
        qualifying_result_id (int): Automatically generated unique ID assigned upon
            object creation.
        position (int): Position the driver qualified in.
        laptime (float): Best lap registered by the driver.
        penalty_points (int): Points to be subracted from the driver's total.

        driver_id (int): Unique ID of the driver the result belongs to.
        round_id (int): Unique ID of the round the result was made in.
        category_id (int): Unique ID of the category the result was made in.
        session_id (int): Unique ID of the session the result was made in.

        driver (Driver): Driver the result belongs to.
        round (Round): Round the result was made in.
        category (Category): Category the result was made in.
        session (Session): Session the result was made in.
    """

    __tablename__ = "qualifying_results"

    __table_args__ = (UniqueConstraint("driver_id", "round_id"),)

    qualifying_result_id: int = Column(SmallInteger, primary_key=True)
    position: int = Column(SmallInteger, nullable=False)
    laptime: float = Column(Float, nullable=True)
    penalty_points: int = Column(SmallInteger, default=0, nullable=False)

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
        laptime: float,
        driver: Driver,
        round: Round,
    ) -> None:
        """Returns a new QualifyingResult object.

        Args:
            position (int): Position the driver qualified in.
            laptime (float): Best lap registered by the driver.
            driver (Driver): Driver the result belongs to.
            session (Session): Session the result was made in.
        """
        self.position = position
        self.laptime = laptime
        self.driver = driver
        self.round = round

        self.category = round.category
        self.session = self.category.qualifying_session

    def __str__(self) -> str:
        return f"QualifyingResult({self.driver_id}, {self.position}, {self.laptime})"

    @property
    def points_earned(self) -> float:
        if not self.position:
            return 0

        scoring = self.session.point_system.scoring
        return scoring[self.position - 1]


class CarClass(Base):
    __tablename__ = "car_classes"

    car_class_id: int = Column(Integer, primary_key=True)
    name: str = Column(String(20))

    game_id: int = Column(ForeignKey("games.game_id"))

    game: Game = relationship("Game")

    def __init__(self, name: str, game: Game):
        self.name = name
        self.game = game

    def __repr__(self) -> str:
        return f"CarClass(car_class_id={self.car_class_id}, name={self.name})"

    def __key(self) -> tuple[int, str]:
        return (self.car_class_id, self.name)

    def __hash__(self) -> int:
        return hash(self.__key())

    def __eq__(self, other: CarClass) -> bool:
        if isinstance(other, CarClass):
            return self.car_class_id == other.car_class_id


class Team(Base):
    """This object represents a team.

    Attributes:
        reports_made (list[Report]): All the reports made by the team.
        received_reports (list[Report]): All the reports received by the team.
        drivers (list[DriverAssignment]): All the driver acquisitions made by the team.
        leader (Driver): Leader of the team.

        team_id (int): The team's unique ID.
        name (str): The team's unique name.
        credits (int): Number of credits available to the team. Used to buy cars and drivers.
    """

    __tablename__ = "teams"

    team_id: int = Column(SmallInteger, primary_key=True)
    name: str = Column(String(20), unique=True)
    credits: int = Column("credits", SmallInteger, default=0, nullable=False)

    drivers: list[DriverAssignment] = relationship(
        "DriverAssignment", back_populates="team"
    )
    reports_made: list[Report] = relationship(
        "Report",
        back_populates="reporting_team",
        foreign_keys=[Report.reporting_team_id],
    )
    received_reports: list[Report] = relationship(
        "Report",
        back_populates="reported_team",
        foreign_keys=[Report.reported_team_id],
    )

    def __init__(self, name: str) -> None:
        """Returns a new Team object.

        Args:
            name (str): The team's unique name.
        """
        self.name = name

    def __eq__(self, __o: Team) -> bool:
        if not isinstance(__o, Team):
            return NotImplemented
        return self.team_id == __o.team_id

    def __key(self) -> tuple[int, str]:
        return (self.leader_id, self.team_id)

    def __hash__(self) -> int:
        return hash(self.__key())

    @property
    def leader(self) -> Driver:
        for driver in self.drivers:
            if driver.is_leader:
                return driver.driver


class CategoryClass(Base):

    __tablename__ = "category_classes"

    category_id: int = Column(ForeignKey("categories.category_id"), primary_key=True)
    car_class_id: int = Column(ForeignKey("car_classes.car_class_id"), primary_key=True)

    category: Category = relationship("Category", back_populates="car_classes")
    car_class: CarClass = relationship("CarClass")


class CategorySession(Base):
    """Represents a session present in a specific category, such as a race, sprint race
    or qualifying session.

    Attributes:
        category_id (int): Unique ID of the category the session is being associated with.
        session_id (int): Unique ID of the session the category is being associated with.

        category (Category): Category the session is being associated with.
        session (Session): Session the category is being associated with.
    """

    __tablename__ = "category_sessions"

    category_id: int = Column(ForeignKey("categories.category_id"), primary_key=True)
    session_id: int = Column(ForeignKey("sessions.session_id"), primary_key=True)

    category: Category = relationship("Category", back_populates="sessions")
    session: Session = relationship("Session", back_populates="categories")


class Game(Base):
    """Represents a game Categories can race in.

    Attributes:
        game_id (int): The game's unique ID.
        name (str): The name of the game.
    """

    __tablename__ = "games"

    game_id: int = Column(Integer, primary_key=True)
    name: str = Column(String(30), unique=True)

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
        sessions (list[Session]): Sessions which belong to the category. [Ordered by session_id]
        rounds (list[Round]): Rounds in the category.
        race_results (list[RaceResult]): Registered race results.
        qualifying_results (list[QualifyingResult]): Registered qualifying results.
        drivers (list[Driver]): Drivers participating in the category. [Ordered by driver_id]
        championship (Championship): The championship the category belongs to.
    """

    __tablename__ = "categories"

    category_id: int = Column(SmallInteger, primary_key=True)
    name: str = Column(String(20), nullable=False)
    round_weekday: int = Column(SmallInteger)
    game_id: int = Column(ForeignKey("games.game_id"))
    championship_id: int = Column(ForeignKey("championships.championship_id"))

    sessions: list[CategorySession] = relationship(
        "CategorySession",
        back_populates="category",
        order_by="CategorySession.session_id",
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

    def has_sprint_race(self) -> bool:
        """Returns True if the category has a sprint race"""
        return len(self.sessions) == 3

    def first_non_completed_round(self) -> Round:
        """Returns the first non completed round"""
        for rnd in self.rounds:
            if not rnd.completed:
                return rnd

    def pole_lap_times(self) -> list[float]:
        """Returns the pole position laptimes registered so far in the category."""
        laptimes = []

        for q_res in self.qualifying_results:
            if q_res.position == 1:
                laptimes.append(q_res)
        return laptimes

    @property
    def qualifying_session(self) -> Session:
        """Returns the Session where qualifying takes place in the category."""
        for category_session in self.sessions:
            if "quali" in category_session.session.name.lower():
                return category_session.session

    @property
    def sprint_race(self) -> Session:
        """Returns the first"""
        key_words = ("1", "sprint", "breve", "corta")
        for category_session in self.sessions:
            name = category_session.session.name.lower()
            for key_word in key_words:
                if key_word in name:
                    return category_session.session

    @property
    def long_race(self) -> Session:
        for category_session in self.sessions:
            name = category_session.session.name.lower()
            if "gara" == name or "2" in name or "lunga" in name:
                return category_session.session

    @property
    def multi_class(self) -> bool:
        return len(self.car_classes) > 1

    def current_standings(self) -> list[list[list[RaceResult], int]]:
        """Calculates the current championship standings. and returns a list
        ordered by championship points.

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
            results[race_result.driver][1] += race_result.points_earned
        return sorted(list(results.values()), key=lambda x: x[1], reverse=True)


class PointSystem(Base):
    """
    This object represents a point system which can be attributed to multiple Sessions.

    Attributes:
        point_system_id (int): A unique ID.
        point_system (str): String containing the number of points for each position,
            separated by a space. E.g. "25 18 15"
    """

    __tablename__ = "point_systems"

    point_system_id: int = Column(SmallInteger, primary_key=True)
    point_system: str = Column(String(60), nullable=False)

    def __init__(self, point_system_id: int, point_system: str) -> None:
        self.point_system_id = point_system_id
        self.point_system = point_system

    def __repr__(self) -> str:
        return f"PointSystem(point_system_id={self.point_system_id}, point_system={self.point_system})"

    @property
    def scoring(self) -> dict[int, float]:
        return {i: float(score) for i, score in enumerate(self.point_system.split())}


class Round(Base):
    """
    This object represents a round of a specific category.
    It is used to group RaceResults and QualifyingResults registered on a specific date.

    Attributes:
        round_id (int): Automatically generated unique ID assigned upon object creation.
        number (int): The number of the round in the calendar order.
        date (date): The date the round takes place on.
        circuit (str): The circuit the round takes place on.
        completed (bool): Whether the round has been completed or not.

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
    completed: bool = Column(Boolean, default=False)

    category_id: int = Column(ForeignKey("categories.category_id"))
    championship_id: int = Column(ForeignKey("championships.championship_id"))

    championship: Championship = relationship("Championship", back_populates="rounds")
    category: Category = relationship("Category", back_populates="rounds")
    race_results: list[RaceResult] = relationship("RaceResult", back_populates="round")
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

    def pole_time(self) -> float:
        for quali_result in self.qualifying_results:
            if quali_result.position == 1:
                return quali_result.laptime

    def get_qualifying_result(self, driver_id) -> QualifyingResult:
        for qualifying_result in self.qualifying_results:
            if qualifying_result.driver_id == driver_id:
                return qualifying_result


class Session(Base):
    """This object represents a session in one or multiple Category.

    Attributes:
        session_id (int): Automatically generated unique ID assigned upon object creation.
        name (str): The name of the session.

        point_system_id (int): Unique ID of the point system used in the session.

        point_system (PointSystem): The point system used to interpret the results of a race.
        categories (list[Category]): Categories the session is linked to. [Ordered by category_id]

    """

    __tablename__ = "sessions"

    session_id: int = Column(SmallInteger, primary_key=True)
    name: str = Column(String(30), nullable=False)

    point_system_id: int = Column(
        ForeignKey("point_systems.point_system_id"), nullable=False
    )

    point_system: PointSystem = relationship("PointSystem")
    categories: list[Category] = relationship(
        "CategorySession", back_populates="session"
    )

    def __init__(self, name: str, point_system: PointSystem) -> None:
        """Returns a new Session object.

        Args:
            name (str): The name of the session.
            point_system (PointSystem): The point system used to interpret the results of a race.
        """
        self.name = name
        self.point_system = point_system

    def __repr__(self) -> str:
        return f"Session(name={self.name})"


class RaceResult(Base):
    """This object represents a Driver's result in a race.
    Each Round will have multiple RaceResults, one (two if the round has a sprint race)
    for each driver in the Category the Round is registered in.

    Attributes:
        result_id (int): Automatically generated unique ID assigned upon object creation.
        finishing_position (int): The position the driver finished in the race.
        bonus_points (int): Points obtained from fastest lap/pole position.
        penalty_points (int): Points to be subtracted from the driver's total.
        gap_to_first (float): Difference between the driver's race time
            and the race winner's race time.

        driver_id (int): Unique ID of the driver the result is registered to.
        round_id (int): Unique ID of the round the result is registered to.
        category_id (int): Unique ID of the category the result is registered to.
        session_id (int): Unique ID of the session the result was made in.

        driver (Driver): Driver the result is registered to.
        round (Round): Round the result is registered to.
        category (Category): Category the result is registered to.
        session (Session): Session the result was registered in.
    """

    __tablename__ = "race_results"
    __table_args__ = (
        UniqueConstraint(
            "driver_id", "round_id", "session_id", name="_driver_round_session_uc"
        ),
    )

    result_id: int = Column(Integer, primary_key=True)
    finishing_position: int = Column(SmallInteger)
    fastest_lap_points: int = Column(SmallInteger)
    penalty_points: int = Column(SmallInteger)
    gap_to_first: float = Column(Float)

    driver_id: int = Column(ForeignKey("drivers.driver_id"))
    round_id: int = Column(ForeignKey("rounds.round_id"))
    category_id: int = Column(ForeignKey("categories.category_id"))
    session_id: int = Column(ForeignKey("sessions.session_id"))

    driver: Driver = relationship("Driver", back_populates="race_results")
    round: Round = relationship("Round", back_populates="race_results")
    category: Category = relationship("Category", back_populates="race_results")
    session: Session = relationship("Session")

    def __init__(
        self,
        finishing_position: int,
        bonus_points: int,
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
            gap_to_first (float): Difference between the driver's race time
                and the race winner's race time.
            participated (bool): True if the driver participated to the race.
        """
        self.finishing_position = finishing_position
        self.driver = driver
        self.session = session
        self.fastest_lap_points = bonus_points
        self.round = kwargs.get("round")
        self.penalty_points = kwargs.get("penalty_points")
        self.gap_to_first = kwargs.get("gap_to_first")
        self.participated = bool(kwargs.get("participated"))
        if self.round:
            self.category = self.round.category

    @property
    def points_earned(self) -> float:
        if not self.finishing_position:
            return 0
        scoring = self.session.point_system.scoring
        return scoring[self.finishing_position - 1] + self.fastest_lap_points


class DriverChampionship(Base):
    """This object associates a Driver with a Championship.

    Attributes:
        driver_id (int): Unique ID of the driver the championship is associated with.
        championship_id (int): Unique ID of the championship the driver is associated with.

        driver (Driver): Driver the championship is associated with.
        championship (Championship): Championship the driver is associated with.
    """

    __tablename__ = "driver_championships"

    driver_id: int = Column(ForeignKey("drivers.driver_id"), primary_key=True)
    championship_id: int = Column(
        ForeignKey("championships.championship_id"), primary_key=True
    )

    driver: Driver = relationship("Driver", back_populates="championships")
    championship: Championship = relationship("Championship", back_populates="drivers")


class Championship(Base):
    """This object represents a championship.
    Each Championship has multiple Drivers, Rounds and Categories categories associated to it.

    Attributes:
        championship_id (int): The championship's unique ID.
        championship_name (str): The championship's name.
        start (datetime.date): Date the championship starts on.
        end (datetime.date): Date the championship ends on.

        categories (list[Category]): Categories belonging to the championship. [Ordered by round_weekday]
        drivers (list[DriverChampionship]): Drivers participating in the championship.
        rounds (list[Round]): Rounds present in the championship.
    """

    __tablename__ = "championships"

    championship_id: int = Column(SmallInteger, primary_key=True)
    championship_name: str = Column(String(60), unique=True, nullable=False)

    start: datetime.date = Column(Date, nullable=False)
    end: datetime.date = Column(Date, nullable=True)

    categories: list[Category] = relationship(
        "Category", back_populates="championship", order_by="Category.round_weekday"
    )
    drivers: list[DriverChampionship] = relationship(
        "DriverChampionship", back_populates="championship"
    )
    rounds: list[Round] = relationship("Round", back_populates="championship")

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
        return "".join(i[0] for i in self.championship_name.split()).upper()

    @property
    def driver_list(self) -> list[Driver]:
        drivers = []
        for category in self.categories:
            for driver in category.drivers:
                drivers.append(driver.driver)
        return drivers


def create_tables() -> None:
    """Creates all the tables"""
    engine = create_engine("postgresql://alexander:alexander@localhost:5432/rti")
    _Session = sessionmaker(bind=engine)
    with _Session() as _session:
        Base.metadata.create_all(engine)
        _session.commit()


if __name__ == "__main__":
    create_tables()
    _Session = sessionmaker(
        bind=create_engine("postgresql://alexander:alexander@localhost:5432/rti")
    )
    with _Session() as _session:
        _session.add(Game("gts"))
        _session.add(Game("gt7"))
        _session.commit()
