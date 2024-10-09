from datetime import datetime, timedelta
import datetime as dt
import os
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from jwt import InvalidTokenError
from sqlalchemy.orm import Session as DBSession

from queries import fetch_driver_by_email

SECRET_KEY = os.environ.get("SECRET_API_KEY", "")
USERNAME = os.environ.get("RRE_SERVER_USERNAME", "")
RRE_SERVER_PASSWORD = os.environ.get("RRE_SERVER_PASSWORD", "")
ALGORITHM = "HS256"

if not any((SECRET_KEY, USERNAME, RRE_SERVER_PASSWORD)):
    raise RuntimeError("Environment variables not set correctly")


class Token(BaseModel):
    access_token: str
    token_type: str


def get_db(request: Request) -> DBSession:
    return request.state.db


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

HASHED_USER_PASSWORD = pwd_context.hash(RRE_SERVER_PASSWORD)

app = FastAPI()


def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str):
    return pwd_context.hash(password)


def authenticate_user(db: DBSession, username: str, password: str):
    user = fetch_driver_by_email(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(dt.UTC) + expires_delta
    else:
        expire = datetime.now(dt.UTC) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: DBSession = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str | None = payload.get("sub")
        if email is None:
            raise credentials_exception

    except InvalidTokenError:
        raise credentials_exception

    user = fetch_driver_by_email(db, email=email)

    if not user:
        raise credentials_exception
    return user
