"""
This module is for recalculating ratings in the database from scratch.
"""
from collections import defaultdict

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Driver, Team
from queries import get_championship


DB_URL = ""
if not DB_URL:
    raise RuntimeError("DB_URL not found.")

engine = create_engine(DB_URL)

DBSession = sessionmaker(bind=engine, autoflush=False)


def recalculate_points():
    """Only used to recalculate all the ratings in the last championship."""
    sqla_session = DBSession()
    championship = get_championship(sqla_session, championship_id=3)

    if not championship:
        return

    team_championships = {t.team: t for t in championship.teams}
    team_points: defaultdict[Team, float] = defaultdict(float)
    for category in championship.categories:
        print("\n\n\n")
        driver_points: defaultdict[Driver, float] = defaultdict(float)
        for round in category.rounds:
            for session in round.sessions:
                if session.is_quali:
                    for result in session.qualifying_results:
                        driver_points[result.driver] += result.points_earned

                for result in session.race_results:
                    if result.participated:
                        driver_points[result.driver] += result.points_earned

        for driver in category.drivers:
            driver.points = driver_points[driver.driver]
            team_points[driver.driver.contracts[-1].team] += driver.points

        for driver, points in driver_points.items():
            print(driver.full_name, points)

    for team, points in team_points.items():
        team_championships[team].points = points
        print(team.name, points)

    sqla_session.commit()
    sqla_session.expire_all()


if __name__ == "__main__":
    recalculate_points()
