"""
This module contains the driver ranking function.
"""
from decimal import Decimal

import trueskill as ts  # type: ignore
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Driver, RaceResult
from queries import get_championship

TrueSkillEnv = ts.TrueSkill(
    draw_probability=0,
)

engine = create_engine("postgresql://alexander:alexander@172.19.0.2/alexander")

DBSession = sessionmaker(bind=engine, autoflush=False)


def update_ratings(results: list[RaceResult]) -> None:
    """Updates the ratings in the driver objects contained in the RaceResults
    based on their finishing position.
    """
    ranks: list[int] = []
    rating_groups: list[tuple[ts.Rating]] = []
    drivers: list[Driver] = []
    for result in results:
        driver: Driver = result.driver
        if result.participated:
            drivers.append(driver)
            rating_groups.append((ts.Rating(float(driver.mu), float(driver.sigma)),))
            ranks.append(result.finishing_position)

    rating_groups = TrueSkillEnv.rate(rating_groups, ranks)

    for driver, rating_group in zip(drivers, rating_groups):
        driver.mu = Decimal(str(rating_group[0].mu))
        driver.sigma = Decimal(str(rating_group[0].sigma))


def recalculate_ratings():
    """Only used to recalculate all the ratings in the last championship."""
    sqla_session = DBSession()
    championship = get_championship(sqla_session)

    if not championship:
        return

    for category in championship.categories:
        for round in category.rounds:
            for session in round.sessions:
                if session.is_quali:
                    continue

                initial_ratings: list[tuple[ts.Rating]] = []
                finishing_positions: list[int] = []
                race_results: list[RaceResult] = []
                for result in session.race_results:
                    if result.participated:
                        initial_ratings.append(
                            (
                                ts.Rating(
                                    mu=float(result.driver.mu),
                                    sigma=float(result.driver.sigma),
                                ),
                            ),
                        )
                        finishing_positions.append(result.relative_position)
                        race_results.append(result)
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

    championship = get_championship(sqla_session)

    if not championship:
        return

    drivers = championship.driver_list

    drivers.sort(key=lambda x: x.rating if x.rating else 0, reverse=True)

    for driver in drivers:
        print(f"{driver.psn_id}: {driver.mu} - {driver.sigma}")


if __name__ == "__main__":
    recalculate_ratings()
