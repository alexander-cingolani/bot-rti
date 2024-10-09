from pydantic import BaseModel


class SessionInfoSchema(BaseModel):
    session_id: str
    race_name: str
    order: int


class RoundInfoSchema(BaseModel):
    circuit_logo: str
    circuit: str
    info: list[SessionInfoSchema]
