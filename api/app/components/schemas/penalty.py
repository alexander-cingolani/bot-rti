from pydantic import BaseModel


class PenaltySchema(BaseModel):
    penalty_id: int
