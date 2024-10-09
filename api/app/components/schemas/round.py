from pydantic import BaseModel


class RoundSchema(BaseModel):
    round_id: int
