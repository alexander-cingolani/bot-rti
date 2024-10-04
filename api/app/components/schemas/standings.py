from pydantic import BaseModel


class StandingsSchema(BaseModel):
    category_id: int
