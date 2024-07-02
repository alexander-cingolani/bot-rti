from pydantic import BaseModel


class Team(BaseModel):
    points: int | float
    logo: str


class Category(BaseModel):
    category_id: int
    category_name: str
    championship: int
    order: int
    provisional: bool


class Info(BaseModel):
    info_gp: str
    position: int | str
    extra_points: int


class DriverResults(BaseModel):
    driver_id: int
    driver_name: str
    points: float | int
    team: str
    info: list[Info]


class SessionInfo(BaseModel):
    session_id: str
    race_name: str
    order: int


class Round(BaseModel):
    circuit_logo: str
    circuit: str
    info: list[SessionInfo]
