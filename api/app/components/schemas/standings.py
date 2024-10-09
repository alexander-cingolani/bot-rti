from typing import Literal
from pydantic import BaseModel


class DriverStandingsResultInfo(BaseModel):
    info_gp: str
    position: int | Literal["/"]
    extra_points: float | int


class DriverSummary(BaseModel):
    driver_id: int
    driver_name: str
    points: float | int
    team: str
    info: list[DriverStandingsResultInfo]
