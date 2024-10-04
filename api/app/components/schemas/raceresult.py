from pydantic import BaseModel


class RaceResultSchema(BaseModel):
    race_result_id: int
