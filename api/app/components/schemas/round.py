from pydantic import BaseModel

from app.components.schemas.info import SessionInfoSchema


class RoundSchema(BaseModel):
    round_id: int


class RoundResponseSchema(BaseModel):
    circuit_logo: str
    circuit: str
    info: list[SessionInfoSchema]
