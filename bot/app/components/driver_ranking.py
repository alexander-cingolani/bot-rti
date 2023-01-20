"""
This module contains the driver ranking function.
"""
import logging
import os
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from queries import get_championship

MAX_INCREMENT = 32
engine = create_engine(os.environ["DB_URL"])

DBSession = sessionmaker(bind=engine, autoflush=False)
from trueskill import Rating, TrueSkill, rate


# Only used to recalculate all of the championship's statistics when changes are made.
def update_ratings():

    sqla_session = DBSession()
    championship = get_championship(sqla_session)
    for category in championship.categories:
        for round in category.rounds:
            for session in round.sessions:
                if session.is_quali:
                    continue
                for carclass in category.car_classes:
                    initial_ratings = []
                    finishing_positions = []
                    race_results = []
                    for result in session.race_results:
                        if (
                            result.driver.current_class() == carclass.car_class
                            and result.relative_position
                        ):
                            initial_ratings.append(
                                (
                                    Rating(
                                        mu=float(result.driver.mu),
                                        sigma=float(result.driver.sigma),
                                    ),
                                )
                            )
                            finishing_positions.append(result.relative_position)
                            race_results.append(result)

                    new_ratings = rate(initial_ratings, finishing_positions)

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
    drivers = championship.driver_list

    drivers.sort(key=lambda x: x.rating if x.rating else 0, reverse=True)
    for driver in drivers:
        logging.info(
            f"{driver.psn_id} mu, sigma: {driver.mu}, {driver.sigma}  exp: {driver.rating}"
        )


TrueSkill.expose
