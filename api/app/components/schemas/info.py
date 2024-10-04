from pydantic import BaseModel


class InfoSchema(BaseModel):
    info_gp: str
    position: int | str
    extra_points: int


class SessionInfoSchema(BaseModel):
    session_info_id: int
