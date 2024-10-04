from pydantic import BaseModel


class DriverSchema(BaseModel):
    driver_id: int
