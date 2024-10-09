"""
This module contains the driver ranking function.
"""

from decimal import Decimal
import os


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import trueskill as ts  # type: ignore

from models import Driver, RaceResult, SessionCompletionStatus
from queries import fetch_championship, fetch_drivers

TrueSkillEnv = ts.TrueSkill(
    draw_probability=0,
)


def update_ratings(results: list[RaceResult]) -> None:
    """Updates the driver ratings"""
    ranks: list[int] = []
    rating_groups: list[tuple[ts.Rating]] = []
    race_results: list[RaceResult] = []
    for result in results:
        driver: Driver = result.driver
        if result.status == SessionCompletionStatus.finished:
            rating_groups.append((ts.Rating(float(driver.mu), float(driver.sigma)),))
            ranks.append(result.position)
            race_results.append(result)

    rating_groups = TrueSkillEnv.rate(rating_groups, ranks)

    for rating_group, result in zip(rating_groups, race_results):
        result.mu = result.driver.mu = Decimal(str(rating_group[0].mu))
        result.sigma = result.driver.sigma = Decimal(str(rating_group[0].sigma))


TrueSkillEnv = ts.TrueSkill(
    draw_probability=0,
)
DB_URL = "mysql+mysqlconnector://alexander:alexander@172.19.0.2:3306/rti-dev"
if not DB_URL:
    raise RuntimeError("DB_URL not found.")

engine = create_engine(DB_URL)

DBSession = sessionmaker(bind=engine, autoflush=False)


def recalculate_ratings():
    """Only used to recalculate all the ratings in the last championship."""
    sqla_session = DBSession()
    championship = fetch_championship(sqla_session, championship_id=2)

    if not championship:
        return

    for category in championship.categories:
        for rnd in category.rounds:
            for session in rnd.sessions:
                if session.is_quali:
                    continue

                initial_ratings: list[tuple[ts.Rating]] = []
                finishing_positions: list[int] = []
                race_results: list[RaceResult] = []
                for result in session.race_results:
                    if result.status == SessionCompletionStatus.finished:
                        rtg = (
                            ts.Rating(
                                mu=float(result.driver.mu),
                                sigma=float(result.driver.sigma),
                            ),
                        )
                        initial_ratings.append(rtg)
                        finishing_positions.append(result.position)
                        race_results.append(result)
                        result.mu = rtg[0].mu
                        result.sigma = rtg[0].sigma
                print(initial_ratings)
                print(finishing_positions)
                if initial_ratings:
                    new_ratings = ts.rate(initial_ratings, finishing_positions)
                    for i, result in enumerate(race_results):
                        result.driver.mu = Decimal.from_float(
                            new_ratings[i][0].mu
                        ).quantize(Decimal("1.000000"))
                        result.driver.sigma = Decimal.from_float(
                            new_ratings[i][0].sigma
                        ).quantize(Decimal("1.000000"))

    sqla_session.commit()
    sqla_session.expire_all()

    championship = fetch_championship(sqla_session)

    if not championship:
        return

    drivers = championship.driver_list

    drivers.sort(key=lambda x: x.rating if x.rating else 0, reverse=True)

    for driver in drivers:
        print(f"{driver.psn_id_or_full_name}: {driver.mu} - {driver.sigma}")


def recalculate_all_ratings():
    """Only used to recalculate all the ratings in the last championship."""
    sqla_session = DBSession()

    drivers = fetch_drivers(sqla_session)
    for driver in drivers:
        driver.mu = 25
        driver.sigma = 25 / 3
    sqla_session.commit()

    for i in range(5):
        championship = fetch_championship(sqla_session, i)
        for category in championship.categories:
            for rnd in category.rounds:
                for session in rnd.sessions:
                    if session.is_quali:
                        continue
                    initial_ratings: list[tuple[ts.Rating]] = []
                    finishing_positions: list[int] = []
                    race_results: list[RaceResult] = []
                    for result in session.race_results:
                        if result.status == SessionCompletionStatus.finished:
                            rtg = (
                                ts.Rating(
                                    mu=float(result.driver.mu),
                                    sigma=float(result.driver.sigma),
                                ),
                            )
                            initial_ratings.append(rtg)
                            finishing_positions.append(result.position)
                            race_results.append(result)
                            result.mu = rtg[0].mu
                            result.sigma = rtg[0].sigma
                    if initial_ratings:
                        new_ratings = ts.rate(initial_ratings, finishing_positions)
                        for i, result in enumerate(race_results):
                            result.driver.mu = Decimal.from_float(
                                new_ratings[i][0].mu
                            ).quantize(Decimal("1.000000"))
                            result.driver.sigma = Decimal.from_float(
                                new_ratings[i][0].sigma
                            ).quantize(Decimal("1.000000"))
    sqla_session.commit()
    sqla_session.expire_all()

    drivers = fetch_drivers(sqla_session)

    drivers.sort(key=lambda x: x.rating if x.rating else 0, reverse=True)

    for driver in drivers:
        if driver.is_current_member and 3 not in [
            c.category.game_id for c in driver.categories
        ]:
            print(f"{driver.psn_id_or_abbreviated_name}: {round(driver.rating, 3)}")


if __name__ == "__main__":
    recalculate_all_ratings()
