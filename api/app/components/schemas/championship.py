from pydantic import BaseModel


class ChampionshipSchema(BaseModel):
    championship_id: int
