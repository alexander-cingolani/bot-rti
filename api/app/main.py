from datetime import timedelta
import logging
from typing import Annotated

from fastapi.security import OAuth2PasswordRequestForm
from app.components.auth import (
    Token,
    User,
    authenticate_user,
    create_access_token,
    get_current_user,
)

from app.components.handlers import (
    get_calendar,
    get_categories,
    get_drivers_points,
    get_standings_with_results,
    get_teams_list,
    save_rre_results_file,
)
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

app = FastAPI()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

app = FastAPI()

origin = r".*"

app.mount("/images", StaticFiles(directory="/api/app/public/images"), name="images")
app.mount("/fonts", StaticFiles(directory="/api/app/public/fonts"), name="fonts")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=origin,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ACCESS_TOKEN_EXPIRE_MINUTES = 20400


@app.post("/api")
async def rti(
    action: str = Form(),
    championship_id: str | int | None = Form(default="latest"),
    category_id: int | None = Form(default=None),
):
    logging.info(f"{action}, {championship_id}, {category_id}")
    match action:
        case "get_teams":
            if championship_id is None:
                raise HTTPException(
                    422,
                    "Argument 'championship_id' must be provided for 'get_teams' action",
                )
            result = get_teams_list(int(championship_id))

        case "get_category_list":
            if championship_id is None:
                raise HTTPException(
                    422,
                    "Argument 'championship_id' must be provided for 'get_category_list' action",
                )
            result = get_categories(championship_id)

        case "get_calendar":
            if category_id is None:
                raise HTTPException(
                    422,
                    "Argument 'category_id' must be provided for 'get_calendar' action",
                )
            result = get_calendar(int(category_id))

        case "get_standings":
            if category_id is None:
                raise HTTPException(
                    422,
                    "Argument 'category_id' must be provided for 'get_standings' action",
                )
            result = get_standings_with_results(int(category_id))

        case "get_driver_points":
            if championship_id is None:
                raise HTTPException(
                    422,
                    "Argument 'category_id' must be provided for 'get_driver_points' action",
                )
            result = get_drivers_points(int(championship_id))

        case other:
            raise HTTPException(400, f"'{other}' action is invalid.")

    return result


@app.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/upload-rre-results/", response_model=User)
async def upload_rre_results(
    current_user: Annotated[User, Depends(get_current_user)], file: UploadFile = File()
):
    await save_rre_results_file(file)
    access_token = create_access_token({"sub": current_user.username})
    return {"access_token": access_token, "token_type_bearer": "bearer"}
