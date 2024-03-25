"""
This module contains the necessary SQLAlchemy models to keep track of
RacingTeamItalia's championships and drivers.
"""

from __future__ import annotations

import datetime
import enum
import json
import logging
import os
from collections import defaultdict
from datetime import datetime as dt
from datetime import time, timedelta
from decimal import Decimal
from statistics import stdev
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
    UniqueConstraint,
    create_engine,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

DOMAIN = os.environ.get("ZONE")
SUBDOMAIN = os.environ.get("SUBDOMAIN")
IMAGE_DIR_URL = f"https://{SUBDOMAIN + '.' if SUBDOMAIN else ''}{DOMAIN}/images/"
CIRCUIT_LOGO_DIR_URL = (
    f"https://{SUBDOMAIN + '.' if SUBDOMAIN else ''}{DOMAIN}/images/circuit_logos/"
)


class Base(DeclarativeBase):
    pass


class Championship(Base):
    """Represents a championship.
    Each Championship has multiple Drivers, Rounds and Categories categories associated to it.

    Attributes:
        id (int): The championship's unique ID.
        name (str): The championship's name.
        start (datetime.date): Date the championship starts on.
        end (datetime.date): Date the championship ends on.

        categories (list[Category]): Categories belonging to the championship.
            [Ordered by category_id]
        drivers (list[DriverChampionship]): Drivers participating in the championship.
        rounds (list[Round]): Rounds present in the championship.
    """

    __tablename__ = "championships"

    id: Mapped[int] = mapped_column("championship_id", SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    start: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    end: Mapped[datetime.date | None] = mapped_column(Date)

    categories: Mapped[list[Category]] = relationship(
        back_populates="championship", order_by="Category.id"
    )
    teams: Mapped[list[TeamChampionship]] = relationship(back_populates="championship")
    rounds: Mapped[list[Round]] = relationship(
        back_populates="championship", order_by="Round.date"
    )

    def reporting_round(self) -> Round | None:
        """Returns the round in which reports can currently be created."""
        now = datetime.datetime.now().date()
        for championship_roud in self.rounds:
            if (championship_roud.date + timedelta(hours=24)) == now:
                return championship_roud
        return None

    def current_racing_category(self) -> Category | None:
        """Returns the category which races today."""
        for championship_round in self.rounds:
            if championship_round.date == datetime.datetime.now().date():
                return championship_round.category
        return None

    def is_active(self) -> bool:
        """Returns True if the championship is ongoing."""
        return bool(self.non_disputed_rounds())

    def non_disputed_rounds(self) -> list[Round]:
        """Returns all the rounds which have not been disputed yet."""
        rounds: list[Round] = []
        for rnd in self.rounds:
            if not rnd.is_completed:
                rounds.append(rnd)
        return rounds

    @property
    def abbreviated_name(self) -> str:
        """Short version of the championship's name created by taking the first letter
        of each word in it.
        E.G. "eSports Championship 1" -> "EC1"
        """
        return "".join(i[0] for i in self.name.split()).upper()

    @property
    def driver_list(self) -> list[Driver]:
        """List of drivers participating to this championship."""
        drivers: list[Driver] = []
        for category in self.categories:
            for driver in category.drivers:
                drivers.append(driver.driver)
        return drivers


class Game(Base):
    """Represents a game Categories can race in.

    Attributes:
        id (int): The game's unique ID.
        name (str): The name of the game.
    """

    __tablename__ = "games"

    id: Mapped[int] = mapped_column("game_id", Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)

    def __repr__(self) -> str:
        return f"Game(game_id={self.id}, name={self.name})"


class PointSystem(Base):
    """
    Represents a point system that can be used for race or qualifying sessions.

    Attributes:
        id (int): A unique ID.
        point_system (str): String containing the number of points for each position,
            separated by a space. E.g. "25 18 15 .."
    """

    __tablename__ = "point_systems"

    id: Mapped[int] = mapped_column("point_system_id", SmallInteger, primary_key=True)
    _point_system: Mapped[str] = mapped_column(
        "point_system", String(100), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"PointSystem(point_system_id={self.id}, "
            f"point_system={self.point_system})"
        )

    @property
    def point_system(self) -> list[float]:
        return json.loads(self._point_system)


class Permission(Base):
    """Represents a permission that can be granted to one or more roles in the team.

    id (int): Unique ID for the permission.
    name (str): Name of the permission. E.g. "report-filing"
    """

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column("permission_id", Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)


class Role(Base):
    """Represents a role in the organizational chart of the team.

    id (int): Unique ID for the role.
    name (str): Name of the role. E.g. "team-leader"
    """

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column("role_id", Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)

    permissions: Mapped[list[RolePermission]] = relationship(back_populates="role")


class RolePermission(Base):
    """Association object between a role and a permission.

    role_id (int): ID of the role.
    permission_id (int): ID of the permission.

    role (Role): Role object.
    permission (Permission): Permission object.
    """

    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(ForeignKey(Role.id), primary_key=True)
    permission_id: Mapped[int] = mapped_column(
        ForeignKey(Permission.id), primary_key=True
    )

    role: Mapped[Role] = relationship()
    permission: Mapped[Permission] = relationship()


class CarClass(Base):
    """Represents an in-game car class.
    CarClass records are meant to be reused multiple times for different categories
    and championships, their function is mainly to identify which type of car is
    assigned to drivers within the same category, this allows to calculate
    statistics separately from one class and another.

    Attributes:
        name (str): Name of the car class.
        in_game_id (int): ID of the class in the game.

        game_id (int): Unique ID of the game the car class is in.

        game (Game): Game object the car class is associated to.
        cars (list[Cars]): Cars belonging to this class.
    """

    __tablename__ = "car_classes"

    id: Mapped[int] = mapped_column("car_class_id", Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    in_game_id: Mapped[int | None] = mapped_column(Integer)

    game_id: Mapped[int] = mapped_column(ForeignKey(Game.id), nullable=False)

    game: Mapped[Game] = relationship()
    cars: Mapped[list[Car]] = relationship(back_populates="car_class")

    def __repr__(self) -> str:
        return f"CarClass(car_class_id={self.id}, name={self.name})"

    def __key(self) -> int:
        return self.id

    def __hash__(self) -> int:
        return hash(self.__key())

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CarClass):
            return NotImplemented
        return self.id == other.id


class Car(Base):
    """Represents a specific car make and model within a car class.

    id (int): The car's unique id.
    name (str): The car's name.
    in_game_id (int): ID of the car in the game.

    car_class_id (int): The car's class id.

    car_class (CarClass): CarClass the car belongs to.
    """

    __tablename__ = "cars"

    id: Mapped[int] = mapped_column("car_id", Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    in_game_id: Mapped[int | None] = mapped_column(Integer)

    car_class_id: Mapped[int] = mapped_column(ForeignKey(CarClass.id), nullable=False)

    car_class: Mapped[CarClass] = relationship(back_populates="cars")


class Circuit(Base):
    """Represents a circuit within a game.

    circuit_id (int): The circuit's unique ID.
    name (str): The circuit's name.
    abbreviated_name (str): Shorter version of the circuit name.
    game_id (int): The ID of the game this track is in.

    configurations (list[CircuitConfiguration]): All the configurations available in the game.
    rounds (list[Round]): The rounds that took place at this circuit.
    game (Game): The game this track is in.
    """

    __tablename__ = "circuits"

    id: Mapped[int] = mapped_column("circuit_id", SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    abbreviated_name: Mapped[str] = mapped_column(String(20), nullable=False)
    game_id: Mapped[int] = mapped_column(ForeignKey(Game.id), nullable=False)

    configurations: Mapped[list[CircuitConfiguration]] = relationship(
        back_populates="circuit"
    )
    rounds: Mapped[list[Round]] = relationship(back_populates="circuit")
    game: Mapped[Game] = relationship()

    @property
    def logo_url(self) -> str:
        filename = f"{self.name.lower().replace(' ', '-')}.png"
        return CIRCUIT_LOGO_DIR_URL + filename

    def __repr__(self) -> str:
        return (
            f"Circuit(id={self.id}, name={self.name}, abbreviated_name={self.abbreviated_name}"
            f", game_id={self.game_id})"
        )


class CircuitConfiguration(Base):
    """Represents a specific configuration of a circuit.

    circuit_id (int): Unique ID of the circuit this configuration is a variation of.
    configuration_id (int): Unique ID for this configuration.
    name (name): Name of this configuration.

    circuit (Circuit): Circuit object this configuration is a variation of.
    """

    __tablename__ = "circuit_configurations"

    id: Mapped[int] = mapped_column("configuration_id", primary_key=True)
    circuit_id: Mapped[int] = mapped_column(ForeignKey(Circuit.id), primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    circuit: Mapped[Circuit] = relationship(back_populates="configurations")


class Category(Base):
    """Represents a category.

    Attributes:
        id (int): A Unique ID.
        name (str): Name of the category.

        championship_id (int): ID of the championship the category belongs to.
        game_id (int): ID of the game the category is based on.
        split_point (int): If specified, is used to determine how many points are to be assigned
            for the fastest lap based on the driver's finishing position.
        fastest_lap_points (str): One or two numbers in a string split by a " ". The first number
            tells how many points should be assigned for the first x drivers up to the split point,
            while the second number tells how many points should be assigned for the drivers after
            the split point.
        game (Game): Game the category is based on.
        rounds (list[Round]): Rounds in the category.
        race_results (list[RaceResult]): Registered race results.
        qualifying_results (list[QualifyingResult]): Registered qualifying results.
        drivers (list[Driver]): Drivers participating in the category. [Ordered by driver_id]
        championship (Championship): The championship the category belongs to.
    """

    __tablename__ = "categories"

    id: Mapped[int] = mapped_column("category_id", SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    tag: Mapped[str] = mapped_column(String(8), nullable=False)
    display_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    split_point: Mapped[int | None] = mapped_column(SmallInteger)
    fastest_lap_points: Mapped[str | None] = mapped_column(String(15))
    game_id: Mapped[int] = mapped_column(ForeignKey(Game.id), nullable=False)
    championship_id: Mapped[int] = mapped_column(
        ForeignKey(Championship.id), nullable=False
    )

    rounds: Mapped[list[Round]] = relationship(
        back_populates="category", order_by="Round.date"
    )
    race_results: Mapped[list[RaceResult]] = relationship(back_populates="category")
    qualifying_results: Mapped[list[QualifyingResult]] = relationship(
        back_populates="category"
    )
    drivers: Mapped[list[DriverCategory]] = relationship(
        back_populates="category", order_by="DriverCategory.position"
    )
    game: Mapped[Game] = relationship()
    championship: Mapped[Championship] = relationship(back_populates="categories")

    def __repr__(self) -> str:
        return f"Category(id={self.id},name={self.name})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Category):
            return NotImplemented
        return self.id == other.id

    def first_non_completed_round(self) -> Round | None:
        """Returns the first non completed Round."""
        for rnd in self.rounds:
            if not rnd.is_completed:
                return rnd
        return None

    def last_completed_round(self) -> Round | None:
        """Returns the last completed Round."""
        for rnd in reversed(self.rounds):
            if rnd.is_completed:
                return rnd
        return None

    def penultimate_completed_round(self) -> Round | None:
        c = 0
        for rnd in reversed(self.rounds):
            if rnd.is_completed and c == 1:
                return rnd
            elif rnd.is_completed:
                c += 1
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

    def _sort_drivers(
        self, standings: dict[Driver, tuple[Decimal, int, int]]
    ) -> dict[Driver, Decimal]:
        sorted_standings = sorted(
            standings.items(),
            key=lambda x: (x[1][0], -x[1][1] / x[1][2], -x[1][2]),
        )

        return {driver: values[0] for driver, values in sorted_standings}

    def standings(self, n: int = 0) -> dict[Driver, tuple[float, int]]:
        """Calculates the current standings in this category.

        Args:
            n (Optional[int]): Number of races to go back. (Must be 0 or negative)

        Returns:
            DefaultDict[Driver, [float]]: DefaultDict containing Drivers as keys
                and a list containing the total points and the number of positions
                gained by the driver in the championship standings in the last
                completed_rounds.
        """

        driver_points_in_last_round: DefaultDict[Driver, float] = defaultdict(lambda: 0)

        last_completed_round = self.last_completed_round()
        if not last_completed_round:
            return {driver.driver: (0, 0) for driver in self.drivers}

        # Sum points earned in races
        for race_result in self.race_results:
            if race_result.round_id == last_completed_round.id:
                break
            driver_points_in_last_round[race_result.driver] += race_result.points_earned
        # Sum points earned in qualifying sessions
        for quali_result in self.qualifying_results:
            if quali_result.round_id == last_completed_round.id:
                break
            driver_points_in_last_round[
                quali_result.driver
            ] += quali_result.points_earned

        driver_positions_up_to_last_round = sorted(
            driver_points_in_last_round.keys(),
            key=lambda d: driver_points_in_last_round[d],
            reverse=True,
        )
        results: dict[Driver, tuple[float, int]] = {}

        for driver in self.drivers:
            delta = 0
            if driver.driver in driver_positions_up_to_last_round:
                delta = driver.position - (
                    driver_positions_up_to_last_round.index(driver.driver) + 1
                )
            results[driver.driver] = (driver.points, delta)

        return results

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
        result: list[list[float]] = []
        drivers = [driver.driver.full_name for driver in self.drivers]
        driver_map = defaultdict.fromkeys(drivers, float(0))
        result.append(["Tappa"] + drivers)  # type: ignore
        for number, championship_round in enumerate(self.rounds, start=1):
            if not championship_round.is_completed:
                continue

            result.append([number])

            for race_result in championship_round.race_results:
                driver_map[race_result.driver.full_name] += race_result.points_earned
            for qualifying_result in championship_round.qualifying_results:
                driver_map[
                    qualifying_result.driver.full_name
                ] += qualifying_result.points_earned

            result[number].extend(driver_map.values())

        return result


class Round(Base):
    """Represents a round in the calendar of a specific category.
    All RaceResults and QualifyingResults are linked to their Round.

    Attributes:
        id (int): Automatically generated unique ID assigned upon object creation.
        number (int): The number of the round in the calendar order.
        date (date): The date the round takes place on.
        circuit (Circuit): The circuit the round takes place on.
        configuration (CircuitConfiguration): The specific configuration of the circuit.
        is_completed (bool): True if the round has been completed.

        category_id (int): Unique ID of the category the round belongs to.
        championship_id (int): Unique ID of the championship the round belongs to.

        championship (Championship): Championship the round belongs to.
        category (Category): Category the round belongs to.
        race_results (list[RaceResult]): All the race results registered to the round.
        qualifying_results (list[QualifyingResult]): All the qualifying results registered to
            the round.
    """

    __tablename__ = "rounds"

    id: Mapped[int] = mapped_column("round_id", SmallInteger, primary_key=True)
    number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    category_id: Mapped[int] = mapped_column(ForeignKey(Category.id), nullable=False)
    championship_id: Mapped[int] = mapped_column(
        ForeignKey(Championship.id), nullable=False
    )
    circuit_id: Mapped[int] = mapped_column(ForeignKey(Circuit.id), nullable=False)
    configuration_id: Mapped[CircuitConfiguration] = mapped_column(
        ForeignKey(CircuitConfiguration.id), nullable=False
    )

    championship: Mapped[Championship] = relationship(back_populates="rounds")
    category: Mapped[Category] = relationship(back_populates="rounds")
    circuit: Mapped[Circuit] = relationship(back_populates="rounds")
    configuration: Mapped[CircuitConfiguration] = relationship()
    sessions: Mapped[list[Session]] = relationship(
        back_populates="round", order_by="Session.name"
    )

    race_results: Mapped[list[RaceResult]] = relationship(back_populates="round")
    reports: Mapped[list[Report]] = relationship()
    penalties: Mapped[list[Penalty]] = relationship()
    qualifying_results: Mapped[list[QualifyingResult]] = relationship(
        back_populates="round"
    )
    participants: Mapped[list[RoundParticipant]] = relationship(back_populates="round")

    def __repr__(self) -> str:
        return f"Round(circuit={self.circuit.abbreviated_name}, date={self.date}, is_completed={self.is_completed})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Round):
            return NotImplemented
        return self.id == other.id

    def generate_info_message(self) -> str:
        """Generates a message containing info on the category's races."""

        message = (
            f"<i><b>INFO {self.number}ᵃ TAPPA {self.category.name.upper()}</b></i>\n\n"
            f"<b>Tracciato:</b> <i>{self.circuit.name}</i>\n\n"
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
                f"<b>Orario:</b> <i>{session.time_of_day}</i>\n"
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
    def long_race(self) -> Session:
        """The Session object corresponding to this round's long race."""
        for session in self.sessions:
            name = session.name.lower()
            if "gara" == name or "2" in name or "lunga" in name:
                return session
        raise RuntimeError("Round does not have a race session.")


class Session(Base):
    """Represents a session in a round. E.g. a qualifying session or a race session.

    Attributes:
        id (int): Automatically generated unique ID assigned upon object creation.
        name (str): The name of the session.
        fuel_consumption (int): In-game fuel consumption setting.
        tyre_degradation (int): In-game tyre degradation setting.
        time_of_day (str): In-game session time setting.
        weather (str): In-game weather setting.
        laps (int): Number of laps to be completed. (None if session is time based)
        duration (timedelta): Session time limit. (None if session is based on number of laps)
        race_results (Optional(list[RaceResult])): If session is a race session, contains the
            race results. [Ordered by position]
        qualifying_results (Optional(list[QualifyingResult])): If session is a qualifying session,
            contains the qualifying results. [Ordered by position]
        round_id (int): Unique ID of the round the session belongs to.
        point_system_id (int): Unique ID of the point system used in the session.

        point_system (PointSystem): The point system used to interpret the results of a race.
        round (Round): Round which the session belongs to.
    """

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column("session_id", SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(
        Enum("Gara 1", "Gara 2", "Gara", "Qualifica"), nullable=False
    )
    fuel_consumption: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    tyre_degradation: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    time_of_day: Mapped[str] = mapped_column(String(30), nullable=False)
    weather: Mapped[str | None] = mapped_column(String(20))
    laps: Mapped[int | None] = mapped_column(SmallInteger)
    duration: Mapped[datetime.timedelta | None] = mapped_column(Interval)
    round_id: Mapped[int] = mapped_column(ForeignKey(Round.id), nullable=False)
    point_system_id: Mapped[int] = mapped_column(
        ForeignKey(PointSystem.id), nullable=False
    )

    race_results: Mapped[list[RaceResult]] = relationship(
        "RaceResult", back_populates="session", order_by="RaceResult.position"
    )
    qualifying_results: Mapped[list[QualifyingResult]] = relationship(
        "QualifyingResult",
        back_populates="session",
        order_by="QualifyingResult.position",
    )
    point_system: Mapped[PointSystem] = relationship()
    reports: Mapped[list[Report]] = relationship(back_populates="session")
    penalties: Mapped[list[Penalty]] = relationship(back_populates="session")
    round: Mapped[Round] = relationship(back_populates="sessions")

    def __repr__(self) -> str:
        return (
            f"Session(session_id={self.id}, name={self.name}, "
            f"round_id={self.round_id}, tyres={self.tyre_degradation})"
        )

    def participating_drivers(self) -> list[Driver]:
        """Returns a list of drivers who have participated to this session."""
        drivers: list[Driver] = []
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
            if penalty.driver_id == driver_id:
                seconds += penalty.time_penalty
        return seconds

    def results_message(self) -> str:
        """Generates a message containing the results of this session."""
        message = f"<i>{self.name}</i>\n"

        # Sorts results, drivers who didn't participate are put to the back of the list.
        results: list[RaceResult | QualifyingResult] = []  # type: ignore
        if self.is_quali:
            results.extend(
                sorted(
                    self.qualifying_results,
                    key=lambda x: x.laptime if x.laptime is not None else float("inf"),  # type: ignore
                )
            )
        else:
            results.extend(
                sorted(
                    self.race_results,
                    key=lambda x: (
                        x.total_racetime  # type: ignore
                        if x.total_racetime is not None  # type: ignore
                        else float("inf")
                    ),
                )
            )

        for result in results:
            if result.gap_to_first:
                position = str(result.position)
                seconds, milliseconds = divmod(result.gap_to_first, 1000)
                minutes, seconds = divmod(seconds, 60)

                if not minutes:
                    gap = f"+<i>{seconds:01}.{milliseconds:03}</i>"
                else:
                    gap = f"+<i>{minutes:01}:{seconds:02}.{milliseconds:03}</i>"
            elif result.gap_to_first == 0:
                total = getattr(result, "total_racetime", 0)
                if not total:
                    total = getattr(result, "laptime", 0)

                seconds, milliseconds = divmod(total, 1000)
                minutes, seconds = divmod(seconds, 60)

                gap = f"<i>{minutes:01}:{seconds:02}.{milliseconds:03}</i>"
                position = "1"
            else:
                gap = "<i>assente</i>"
                position = "/"

            penalty_seconds = self.get_penalty_seconds_of(result.driver_id)
            message += f"{position} - {result.driver.abbreviated_full_name} {gap}"

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


class Penalty(Base):
    """Represents a penalty applied to a driver in a given session.

    Attributes:
        time_penalty (int): Seconds to add to the driver's total race time.
        points (float): Points to be subtracted from the driver's
            points tally.
        licence_points (int): Points to be subtracted from the driver's licence.
        warnings (int): Number of warnings received.


        category_id (int): Unique ID of the category where incident happened.
        round_id (int): Unique ID of the round where the incident happened.
        session_id (int): Unique ID of the session where the incident happened.

        driver_id (int): Unique ID of the driver receiving the report.
        team_id (int): Unique ID of the team receiving the report.

        incident_time (str): In-game time when the incident happened.
        fact (str): The fact given by the user creating the penalty.
        decision (str): The decision taken. (Made up from time_penalty, penalty_points,
            licence_points and warnings all combined into a nice text format generated
            by the bot).
        reason (str): Detailed explanation why the penalty was issued.
    """

    __tablename__ = "penalties"
    __allow_unmapped__ = True

    incident_time: str
    fact: str
    decision: str
    reason: str
    reporting_driver: Driver

    id: Mapped[int] = mapped_column("penalty_id", Integer, primary_key=True)
    time_penalty: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    licence_points: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    warnings: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    reprimands_legacy: Mapped[int] = mapped_column("reprimands", SmallInteger, default=0)
    points: Mapped[float] = mapped_column(Float(precision=1), default=0, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False, default=datetime.datetime.now().date())

    category: Mapped[Category] = relationship()
    round: Mapped[Round] = relationship(back_populates="penalties")
    session: Mapped[Session] = relationship()

    category_id: Mapped[int] = mapped_column(ForeignKey(Category.id), nullable=False)
    round_id: Mapped[int] = mapped_column(ForeignKey(Round.id), nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey(Session.id), nullable=False)
    driver_id: Mapped[int] = mapped_column(
        ForeignKey("drivers.driver_id"), nullable=False
    )
    reprimand_id: Mapped[int | None] = mapped_column(ForeignKey("reprimands.reprimand_id"))
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.team_id"), nullable=False)

    driver: Mapped[Driver] = relationship(
        back_populates="received_penalties", foreign_keys=[driver_id]
    )
    reprimand: Mapped[Reprimand | None] = relationship()
    team: Mapped[Team] = relationship(
        back_populates="received_penalties", foreign_keys=[team_id]
    )

    @classmethod
    def from_report(
        cls,
        report: Report,
        time_penalty: int = 0,
        licence_points: int = 0,
        warnings: int = 0,
        points: int = 0,
    ) -> Penalty:
        """Initializes a Penalty object from a Report object.

        Args:
            report (Report): Report to initialize the Penalty object from.
            time_penalty (int): Time penalty applied to the driver. (Default: 0)
            licence_points (int): Licence points deducted from the driver's licence. (Default: 0)
            warnings (int): Warnings given to the driver. (Default: 0)
            points (int): Points to be deducted from the driver's points tally.
                (Default: 0)

        Raises:
            TypeError: Raised if report is not of type `Report`.

        Returns:
            Penalty: The new object initialized with the given arguments.
        """

        if not report:
            raise TypeError(f"Cannot initialize Penalty object from {type(report)}.")

        c = cls(
            driver=report.reported_driver,
            time_penalty=time_penalty,
            licence_points=licence_points,
            warnings=warnings,
            points=points,
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
                self.driver,
                self.team,
                self.category,
                self.round,
                self.session,
                self.reason,
                self.fact,
                self.decision,
            )
        )


class Report(Base):
    """Represents a report.
    Each report is associated with two Drivers and their Teams,
    as well as the Category, Round and Session the reported incident happened in.
    N.B. fact, penalty, reason and is_queued may only be provided after
    the report has been reviewed.

    Attributes:
        id (int): Automatically generated unique ID assigned upon report creation.
        number (int): The number of the report in the order it was received in in a Round.
        incident_time (str): String indicating the in-game time when the accident happened.
        reason (str): The reason provided by the reporter for making the report.
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

    __tablename__ = "reports"
    __table_args__ = (CheckConstraint("reporting_team_id != reported_team_id"),)

    __allow_unmapped__ = True
    video_link: str | None = None

    id: Mapped[int] = mapped_column("report_id", Integer, primary_key=True)
    number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    incident_time: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(Text(2000), nullable=False)
    is_reviewed: Mapped[str] = mapped_column(Boolean, nullable=False, default=False)
    report_time: Mapped[datetime.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    channel_message_id: Mapped[int | None] = mapped_column(BigInteger)

    category_id: Mapped[int] = mapped_column(ForeignKey(Category.id), nullable=False)
    round_id: Mapped[int] = mapped_column(ForeignKey(Round.id), nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey(Session.id), nullable=False)
    reported_driver_id: Mapped[int] = mapped_column(
        ForeignKey("drivers.driver_id"), nullable=False
    )

    reporting_driver_id: Mapped[int] = mapped_column(
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

    reported_driver: Mapped[Driver] = relationship(foreign_keys=[reported_driver_id])
    reporting_driver: Mapped[Driver] = relationship(
        back_populates="reports_made", foreign_keys=[reporting_driver_id]
    )
    reported_team: Mapped[Team] = relationship(foreign_keys=[reported_team_id])

    reporting_team: Mapped[Team] = relationship(
        back_populates="reports_made", foreign_keys=[reporting_team_id]
    )

    def __str__(self) -> str:
        return (
            f"Report(number={self.number}, incident_time={self.incident_time},"
            f" reason={self.reason}, reported_driver={self.reported_driver},"
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


class Driver(Base):
    """Represents a driver.

    Attributes:
        driver_id (int): Automatically generated unique ID assigned upon object creation.
        name (str): The driver's real name.
        surname (str): The driver's surname.
        rre_id (int | None): The driver's RaceRoom ID.
        psn_id (str | None): The driver's Playstation ID (max 16 characters).
        telegram_id (str): The driver's telegram ID.

        championships (list[DriverChampionship]): Championships the driver has participated in.
        contracts (list[DriverContract]): All the contracts the driver has signed.
        categories (list[DriverCategory]): Categories the driver has participated in.
        race_results (list[RaceResult]): Results made by the driver in his career.
        received_reports (list[Report]): Reports made against the driver during his career.
        reports_made (list[Report]): Reports made by the driver during his career.
        qualifying_results (list[Report]): Results obtained by the driver in qualifying sessions
            during his career.
        roles (list[DriverRole]): Roles covered by this driver.
    """

    __tablename__ = "drivers"
    __table_args__ = (UniqueConstraint("driver_id", "telegram_id"),)

    id: Mapped[int] = mapped_column("driver_id", SmallInteger, primary_key=True)
    name: Mapped[str | None] = mapped_column(String(30))
    surname: Mapped[str | None] = mapped_column(String(30))
    rre_id: Mapped[int | None] = mapped_column(BigInteger, unique=True)
    psn_id: Mapped[str | None] = mapped_column(String(16), unique=True)
    mu: Mapped[Decimal] = mapped_column(
        Numeric(precision=7, scale=5), nullable=False, default=25
    )
    sigma: Mapped[Decimal] = mapped_column(
        Numeric(precision=7, scale=5), nullable=False, default=25 / 3
    )
    _telegram_id: Mapped[str | None] = mapped_column(
        "telegram_id", String(21), unique=True
    )

    contracts: Mapped[list[DriverContract]] = relationship(
        back_populates="driver",
        order_by="DriverContract.start",
    )
    categories: Mapped[list[DriverCategory]] = relationship(
        back_populates="driver", order_by=("DriverCategory.joined_on")
    )
    race_results: Mapped[list[RaceResult]] = relationship(back_populates="driver")
    received_penalties: Mapped[list[Penalty]] = relationship(back_populates="driver")
    reports_made: Mapped[list[Report]] = relationship(
        back_populates="reporting_driver",
        foreign_keys=[Report.reporting_driver_id],
    )
    qualifying_results: Mapped[list[QualifyingResult]] = relationship(
        back_populates="driver"
    )
    deferred_penalties: Mapped[list[DeferredPenalty]] = relationship(
        back_populates="driver"
    )
    roles: Mapped[list[DriverRole]] = relationship(back_populates="driver")

    def __repr__(self) -> str:
        return f"Driver(full_name={self.full_name}, driver_id={self.id})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Driver):
            return NotImplemented
        return self.id == other.id

    def __key(self) -> tuple[int, str]:
        return self.id, self.full_name

    def __hash__(self) -> int:
        return hash(self.__key())

    def current_team(self) -> Team | None:
        """Returns the team the driver is currently competing with."""
        for contract in self.contracts:
            if not contract.end:
                return contract.team
        return None

    def current_contract(self) -> DriverContract | None:
        """Returns the driver's current contract."""
        for contract in self.contracts:
            if not contract.end:
                return contract
        return None

    def current_category(self) -> DriverCategory | None:
        """Returns the category the driver is currently competing in."""
        if not self.categories:
            return None
        return self.categories[-1]

    @property
    def current_race_number(self) -> int | None:
        """The number currently being used by the Driver in races."""
        current_category = self.current_category()
        if not current_category:
            return None

        for driver_category in current_category.category.drivers:
            if self.id == driver_category.driver_id:
                return driver_category.race_number

        return None

    @property
    def rating(self) -> Decimal:
        """Current TrueSkill rating."""
        k = Decimal(25) / (Decimal(25) / Decimal(3))
        return self.mu - k * self.sigma

    @property
    def telegram_id(self) -> int | None:
        """The telegram_id associated with the Driver."""
        if self._telegram_id:
            return int(self._telegram_id)
        return None

    @telegram_id.setter
    def telegram_id(self, telegram_id: int | None):
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
    def full_name(self) -> str:
        if self.name and self.surname:
            return f"{self.name} {self.surname}"
        return self.psn_id

    @property
    def abbreviated_full_name(self) -> str:
        if self.name and self.surname:
            return f"{self.name[0]}. {self.surname}"
        return self.psn_id

    @property
    def warnings(self) -> int:
        """Returns the warnings received by the driver in the category he is
        currently competing in.
        """
        for driver_category in self.categories:
            if not driver_category.left_on:
                return driver_category.warnings
        return 0

    @property
    def is_active(self) -> bool:
        """A driver is considered active if he is currently competing in a championship."""
        return not self.categories[-1].left_on

    @cached(cache=TTLCache(maxsize=50, ttl=240))  # type: ignore
    def consistency(self) -> int:
        """Number 40-100 calculated based on the
        standard deviation of the set of relative finishing positions and the number
        of absences.
        """

        completed_races: list[RaceResult] = list(
            filter(lambda x: x.participated, self.race_results)
        )
        if len(completed_races) < 2:
            return 0

        positions = [race_result.position for race_result in completed_races]
        participation_ratio = len(completed_races) / len(self.race_results)
        participation_ratio = min(participation_ratio, 1)
        result = round(100 * participation_ratio - 3 * stdev(positions))
        return max(result, 40)

    @cached(cache=TTLCache(maxsize=50, ttl=240))  # type: ignore
    def speed(self) -> int:
        """Statistic calculated on the average gap between
        the driver's qualifying times and the poleman's.

        Args:
            driver (Driver): The Driver to calculate the speed rating of.

        Returns:
            int: Speed rating. (40-100)
        """

        qualifying_results = list(
            filter(lambda x: x.participated, self.qualifying_results)
        )

        if not qualifying_results:
            return 0

        total_gap_percentages = 0.0
        for quali_result in qualifying_results:
            if (
                quali_result.gap_to_first is not None
                and quali_result.laptime is not None
            ):
                total_gap_percentages += (
                    float(
                        quali_result.gap_to_first
                        / (quali_result.laptime - quali_result.gap_to_first)
                    )
                    * 100
                )
                logging.error(str(total_gap_percentages) + self.name)

        average_gap_percentage = pow(
            total_gap_percentages / len(qualifying_results), 1.18
        )

        speed_score = round(100 - average_gap_percentage)
        return max(speed_score, 40)  # Lower bound is 40

    @cached(cache=TTLCache(maxsize=50, ttl=240))  # type: ignore
    def sportsmanship(self) -> int:
        """Based on the seriousness and number of reports received.

        Returns:
            int: Sportsmanship rating. (0-100)
        """

        if len(self.race_results) < 2:
            return 0

        if not self.received_penalties:
            return 100

        penalties = (
            (penalty.time_penalty / 1.5)
            + penalty.warnings
            + (penalty.licence_points * 4)
            + float(penalty.points)
            for penalty in self.received_penalties
        )

        return round(100 - sum(penalties) * 3 / len(self.race_results))

    @cached(cache=TTLCache(maxsize=50, ttl=240))  # type: ignore
    def race_pace(self) -> int:
        """Based on the average gap from the race winner in all of the races
        completed by the driver.

        Return:
            int: Race pace score. (40-100)
                0 if there isn't enough data.

        """
        completed_races = list(filter(lambda x: x.participated, self.race_results))
        if not completed_races:
            return 0

        total_gap_percentages = 0.0
        for race_res in completed_races:
            if (
                race_res.gap_to_first is not None
                and race_res.total_racetime is not None
            ):
                total_gap_percentages += (
                    race_res.gap_to_first
                    / (race_res.total_racetime - race_res.gap_to_first)
                    * 100
                )

        average_gap_percentage = pow(total_gap_percentages / len(completed_races), 1.1)
        average_gap_percentage = min(average_gap_percentage, 60)
        return round(100 - average_gap_percentage)

    @cached(cache=TTLCache(maxsize=50, ttl=240))  # type: ignore
    def stats(self) -> dict[str, int | float]:
        """Calculates the number of wins, podiums and poles achieved by the driver."""

        keys = (
            "wins",
            "podiums",
            "fastest_laps",
            "poles",
            "races_completed",
            "avg_race_position",
            "avg_quali_position",
        )

        statistics: dict[str, int | float] = dict.fromkeys(keys, 0)

        if not self.race_results:
            return statistics

        positions = 0
        missed_races = 0
        for race_result in self.race_results:
            if not race_result.participated:
                missed_races += 1
                continue

            statistics["fastest_laps"] += race_result.fastest_lap_points
            if race_result.position:
                positions += race_result.position
            if race_result.position <= 3:
                statistics["podiums"] += 1
                if race_result.position == 1:
                    statistics["wins"] += 1

        quali_positions = 0
        missed_qualis = 0
        for quali_result in self.qualifying_results:
            if quali_result:
                if quali_result.position == 1:
                    statistics["poles"] += 1
                if quali_result.participated:
                    quali_positions += quali_result.position

        statistics["races_completed"] = len(self.race_results) - missed_races

        if statistics["races_completed"]:
            statistics["avg_race_position"] = round(
                positions / statistics["races_completed"], 2
            )

        quali_sessions_completed = len(self.qualifying_results) - missed_qualis
        if quali_positions:
            statistics["avg_quali_position"] = round(
                quali_positions / quali_sessions_completed, 2
            )

        return statistics

    def has_permission(self, permission_id: int) -> bool:
        """Given a permission ID, returns True if the driver has a role that
        grants him that permission."""
        for role in self.roles:
            for permission in role.role.permissions:
                if permission.permission_id == permission_id:
                    return True
        return False


class Team(Base):
    """Represents a team.

    Attributes:
        reports_made (list[Report]): Reports made by the team.
        received_reports (list[Report]): Reports received by the team.

        drivers (list[DriverContract]): Drivers contracted to the team.
        leader (Driver): Driver who is allowed to make reports for the team.

        team_id (int): The team's unique ID.
        name (str): The team's unique name.
        credits (int): Number of credits available to the team. Used to buy cars and drivers.

        logo (str): URL to the team's logo.
    """

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column("team_id", SmallInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    credits: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)

    championships: Mapped[list[TeamChampionship]] = relationship(
        back_populates="team", order_by="TeamChampionship.joined_on"
    )
    contracted_drivers: Mapped[list[DriverContract]] = relationship(
        back_populates="team"
    )
    reports_made: Mapped[list[Report]] = relationship(
        back_populates="reporting_team",
        foreign_keys=[Report.reporting_team_id],
    )
    received_penalties: Mapped[list[Penalty]] = relationship(
        back_populates="team",
        foreign_keys=[Penalty.team_id],
    )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Team):
            return self.id == other.id
        return NotImplemented

    def __key(self) -> int:
        return self.id

    def __hash__(self) -> int:
        return hash(self.__key())

    @property
    def leader(self) -> Driver | None:
        """The leader of this team."""
        for contract in self.active_drivers:
            if contract.role.name == "team-leader":
                return contract.driver
        return None

    @property
    def active_drivers(self) -> list[DriverContract]:
        """List of drivers who currently have a contract with the team."""
        return [driver for driver in self.contracted_drivers if not driver.end]

    @property
    def logo_url(self) -> str:
        """The path to the team's logo."""
        filename = self.name.lower().replace(" ", "_").replace("#", "") + ".png"
        return IMAGE_DIR_URL + filename

    def current_championship(self) -> TeamChampionship:
        """Returns the most recent championship."""
        return self.championships[-1]

    def reserves(self) -> list[DriverContract]:
        """Returns all drivers who are currently contracted as reserves."""
        return [
            d for d in self.contracted_drivers if d.role.name == "reserve" and not d.end
        ]


class TeamPermission(Base):
    """Represents a permission within a team.

    id (int): Unique ID of the permission.
    name (str): Unique name of the permission.
    """

    __tablename__ = "team_permissions"

    id: Mapped[int] = mapped_column("team_permission_id", Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)


class TeamRole(Base):
    """Represents a role within a team.

    id (int): Unique ID of the role.
    name (int): Unique name of the role.
    """

    __tablename__ = "team_roles"

    id: Mapped[int] = mapped_column("team_role_id", Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)

    permissions: Mapped[list[TeamRolePermission]] = relationship(
        back_populates="team_role"
    )


class TeamRolePermission(Base):
    """Association object between a role and a permission.

    team_role_id (int): ID of the role.
    team_permission_id (int): ID of the permission granted to the role.

    team_role (TeamRole): TeamRole object of the role.
    team_permission (TeamPermission): TeamPermission object of the permission being given
        to the role.
    """

    __tablename__ = "team_role_permissions"

    team_role_id: Mapped[int] = mapped_column(ForeignKey(TeamRole.id), primary_key=True)
    team_permission_id: Mapped[int] = mapped_column(
        ForeignKey(TeamPermission.id), primary_key=True
    )

    team_role: Mapped[TeamRole] = relationship(back_populates="permissions")
    team_permission: Mapped[TeamPermission] = relationship()


class DriverContract(Base):
    """Association object between a Driver and a Team.

    Attributes:
        start_date (date): The starting date of the contract.
        end (date | None): The date the contract ends.
        acquisition_fee (int): Price the team paid to acquire the driver.

        id (int): Auto-generated ID assigned upon object creation.
        driver_id (int): Unique ID of the driver joining the team.
        team_id (int): Unique ID of the team acquiring the driver.
        length (int): Number of seasons the driver is contracted for.

        driver (Driver): Driver joining the team.
        team (Team): Team acquiring the driver.
    """

    __tablename__ = "driver_contracts"
    __table_args__ = (UniqueConstraint("start", "driver_id", "team_id"),)

    start: Mapped[datetime.date] = mapped_column(
        Date, default=datetime.datetime.now().date(), nullable=False
    )
    end: Mapped[datetime.date | None] = mapped_column(Date)
    acquisition_fee: Mapped[Optional[int]] = mapped_column(SmallInteger)
    length: Mapped[int | None] = mapped_column(Integer)
    role_id: Mapped[int] = mapped_column(
        "team_role_id", ForeignKey(TeamRole.id), nullable=False
    )

    id: Mapped[str] = mapped_column(
        "contract_id", Integer, primary_key=True, nullable=False
    )
    driver_id: Mapped[int] = mapped_column(
        ForeignKey(Driver.id), primary_key=True, nullable=False
    )
    team_id: Mapped[int] = mapped_column(
        ForeignKey(Team.id), primary_key=True, nullable=False
    )

    driver: Mapped[Driver] = relationship(back_populates="contracts")
    team: Mapped[Team] = relationship(back_populates="contracted_drivers")
    role: Mapped[TeamRole] = relationship()

    def has_permission(self, team_permission_id: int) -> bool:
        """Returns true if the driver has the required permission."""
        for permission in self.role.permissions:
            if permission.team_permission_id == team_permission_id:
                return True
        return False


class DriverRole(Base):
    """Association object between a driver and a role.
    Drivers can cover multiple roles, and each role grants access to specific permissions.

    driver_id (int): Unique ID of the associated driver.
    role_id (int): Unique ID of the associated role.

    driver (Driver): Associated Driver object.
    role (Role): Associated Role object.
    """

    __tablename__ = "driver_roles"
    driver_id: Mapped[int] = mapped_column(ForeignKey(Driver.id), primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey(Role.id), primary_key=True)

    driver: Mapped[Driver] = relationship(back_populates="roles")
    role: Mapped[Role] = relationship()


class DriverCategory(Base):
    """Association object between a Driver and a Category.

    Attributes:
        joined_on (date): The date on which the driver joined the category.
        left_on (date): The date on which the driver left the category.
        race_number (int): The number used by the driver in the category.
        warnings (int): Number of warnings received in the category.
        licence_points: Number of points remaining on the driver's licence.

        driver_id (int): Unique ID of the driver joining the category.
        category_id (int): Unique ID of the category being joined by the driver.

        driver (Driver): Driver joining the category.
        category (Category): Category being joined by the driver.
    """

    __tablename__ = "drivers_categories"

    __table_args__ = (UniqueConstraint("driver_id", "category_id"),)

    joined_on: Mapped[datetime.date] = mapped_column(Date, default=dt.now().date())
    left_on: Mapped[datetime.date | None] = mapped_column(Date)
    race_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    warnings: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    reprimands: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    licence_points: Mapped[int] = mapped_column(
        SmallInteger, default=10, nullable=False
    )
    position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    points: Mapped[float] = mapped_column(Float, default=0, nullable=False)
    driver_id: Mapped[int] = mapped_column(ForeignKey(Driver.id), primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey(Category.id), primary_key=True)

    driver: Mapped[Driver] = relationship(back_populates="categories")
    category: Mapped[Category] = relationship(back_populates="drivers")

    def __repr__(self) -> str:
        return f"DriverCategory(driver_id={self.driver_id}, category_id={self.category_id})"


class QualifyingResult(Base):
    """Represents a single result made by a driver in a qualifying Session.

    Attributes:
        id (int): Automatically generated unique ID assigned upon
            object creation.
        position (int): Position the driver qualified in.
        laptime (int): Best lap registered by the driver in the.
        gap_to_first (int): Seconds by which the laptime is off from the fastest lap
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

    __tablename__ = "qualifying_results"

    __table_args__ = (
        UniqueConstraint("driver_id", "session_id", "round_id"),
        UniqueConstraint(
            "position", "session_id", "category_id", name="position_session_category_uq"
        ),
    )

    id: Mapped[int] = mapped_column(
        "qualifying_result_id", SmallInteger, primary_key=True
    )
    position: Mapped[int | None] = mapped_column(SmallInteger)
    laptime: Mapped[int | None] = mapped_column(Integer)
    gap_to_first: Mapped[int | None] = mapped_column(Integer)
    participated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    driver_id: Mapped[int] = mapped_column(ForeignKey(Driver.id), nullable=False)
    round_id: Mapped[int] = mapped_column(ForeignKey(Round.id), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey(Category.id), nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey(Session.id), nullable=False)

    driver: Mapped[Driver] = relationship(back_populates="qualifying_results")
    round: Mapped[Round] = relationship(back_populates="qualifying_results")
    category: Mapped[Category] = relationship(back_populates="qualifying_results")
    session: Mapped[Session] = relationship()

    def __str__(self) -> str:
        return f"QualifyingResult({self.driver_id}, {self.position}, {self.laptime})"

    @property
    def points_earned(self) -> float:
        """Points earned by the driver in this qualifying session."""
        if not self.participated:
            return 0

        return self.session.point_system.point_system[self.position - 1]


class TeamChampionship(Base):
    """Association object between a Team and a Championship.
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

    team_id: Mapped[int] = mapped_column(ForeignKey(Team.id), primary_key=True)
    championship_id: Mapped[int] = mapped_column(
        ForeignKey(Championship.id), primary_key=True
    )
    joined_on: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    penalty_points: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    points: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    team: Mapped[Team] = relationship(back_populates="championships")
    championship: Mapped[Championship] = relationship(back_populates="teams")


class RaceResult(Base):
    """Represents a Driver's result in a race session.
    Each Round will have multiple RaceResults, one (two if the round has a sprint race)
    for each driver in the Category the Round is registered in.

    Attributes:
        id (int): Automatically generated unique ID assigned upon object creation.
        position (int): The position the driver finished in the race.
        fastest_lap (bool): True if the driver scored the fastest lap, False by default.
        participated (bool): True if the driver participated to the race.
        gap_to_first (int): Difference between the driver's race time
            and the class winner's race time.
        total_racetime (int): Total time the driver took to complete the race.

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

    id: Mapped[int] = mapped_column("result_id", Integer, primary_key=True)
    position: Mapped[int | None] = mapped_column(SmallInteger)
    fastest_lap: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    participated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    gap_to_first: Mapped[int | None] = mapped_column(Integer)
    total_racetime: Mapped[Integer | None] = mapped_column(Integer)
    mu: Mapped[Decimal | None] = mapped_column(Numeric(precision=6, scale=3))
    sigma: Mapped[Decimal | None] = mapped_column(Numeric(precision=6, scale=3))

    driver_id: Mapped[int] = mapped_column(ForeignKey(Driver.id), nullable=False)
    round_id: Mapped[int] = mapped_column(ForeignKey(Round.id), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey(Category.id), nullable=False)
    session_id: Mapped[int] = mapped_column(ForeignKey(Session.id), nullable=False)

    driver: Mapped[Driver] = relationship(back_populates="race_results")
    round: Mapped[Round] = relationship(back_populates="race_results")
    category: Mapped[Category] = relationship(back_populates="race_results")
    session: Mapped[Session] = relationship(back_populates="race_results")

    def __repr__(self) -> str:
        return (
            f"RaceResult(driver_id={self.driver_id}, "
            f"position={self.position}, "
            f"fastest_lap={self.fastest_lap}, "
            f"total_racetime={self.total_racetime}) "
        )

    @property
    def fastest_lap_points(self) -> float:
        """The amount of points the driver earned for the fastest lap.
        (0 if he didn't score it)"""

        if not self.fastest_lap:
            return 0

        if not self.category.split_point:
            return float(self.category.fastest_lap_points)

        if self.position <= self.category.split_point:
            return float(self.category.fastest_lap_points.split()[0])
        return float(self.category.fastest_lap_points.split()[1])

    @property
    def points_earned(self) -> float:
        """Total amount of points earned by the driver in this race.
        (Finishing position + fastest lap points) *Does not take into account penalty points.
        """

        if not self.participated:
            return 0

        return (
            self.session.point_system.point_system[self.position - 1]
            + self.fastest_lap_points
        )


class Participation(enum.Enum):
    YES = "YES"
    NO = "NO"
    UNCERTAIN = "UNCERTAIN"
    NO_REPLY = "NO_REPLY"


class RoundParticipant(Base):
    """Used to keep track of which drivers have given confirmation for
    participating (or not) to a Round."""

    __tablename__ = "round_participants"

    round_id: Mapped[int] = mapped_column(ForeignKey(Round.id), primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey(Driver.id), primary_key=True)

    participating: Mapped[Participation] = mapped_column(
        Enum(Participation, name="participation"),
        nullable=False,
        default=Participation.NO_REPLY.value,
    )

    round: Mapped[Round] = relationship(back_populates="participants")
    driver: Mapped[Driver] = relationship()


class Chat(Base):
    """Represents a chat the bot is in.

    id (int): The actual chat id used by telegram.
    is_group (bool): True if the chat is a group.
    name (str): The chat name at the time the bot was added.
    user_id (int | None): ID of the user who created the chat. None if not
        a group chat.
    """

    __tablename__ = "chats"

    id: Mapped[int] = mapped_column("chat_id", BigInteger, primary_key=True)
    is_group: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    name: Mapped[str] = mapped_column(String(255))
    user_id: Mapped[int | None] = mapped_column(BigInteger)


class DeferredPenalty(Base):
    """Represents a penalty to be applied to the result of next race the penalised
    driver participates in. The need for this object comes from the fact that
    sometimes drivers can be penalised without having completed the race they were
    penalised in. DeferredPenalty objects are also linked to a separate Penalty
    object which contains all the details about the penalty.

    id (int): Unique ID for this object.
    penalty_id (int): Unique ID of the Penalty this object is related to.
    driver_id (int): Unique ID of the Driver who received the penalty.
    is_applied (bool): True if the penalty was applied.

    penalty (Penalty): Penalty object this DeferredPenalty is related to.
    driver (Driver): Driver object who received the penalty.

    """

    __tablename__ = "deferred_penalties"

    id: Mapped[int] = mapped_column("deferred_penalty_id", Integer, primary_key=True)
    penalty_id: Mapped[int] = mapped_column(ForeignKey(Penalty.id), unique=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey(Driver.id))
    is_applied: Mapped[bool] = mapped_column(Boolean, default=False)

    penalty: Mapped[Penalty] = relationship()
    driver: Mapped[Driver] = relationship(back_populates="deferred_penalties")


class Reprimand(Base):
    """Represents a type reprimand that can be given to a driver in response to a report.

    id (int): Unique ID for this object.
    description (str): A brief description for the type of reprimand.
    """

    __tablename__ = "reprimands"

    id: Mapped[int] = mapped_column("reprimand_id", SmallInteger, primary_key=True)
    description: Mapped[str] = mapped_column(String(100))
