from pydantic import BaseModel


class SessionSchema(BaseModel):
    session_id: int