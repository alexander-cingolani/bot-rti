from pydantic import BaseModel


class ProtestSchema(BaseModel):
    protest_id: int


class CreateProtestSchema(BaseModel):
    protesting_driver_discord_id: int
    protested_driver_discord_id: int
    protest_reason: str
    incident_time: str
    session_name: str
