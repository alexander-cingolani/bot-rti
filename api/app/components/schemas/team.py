from pydantic import BaseModel


class EditTeamSchema(BaseModel):
    team_id: int


class TeamSchema(BaseModel):
    team_id: int


class TeamStandingsSchema(BaseModel):
    points: int | float
    logo: str
    name: str
