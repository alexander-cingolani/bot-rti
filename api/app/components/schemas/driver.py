from pydantic import BaseModel


class DriverSchema(BaseModel):
    driver_id: int
    email: str
    hashed_password: str
    psn_id: str
    rre_id: int