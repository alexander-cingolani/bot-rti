import logging

from app.components.handlers import (
    get_calendar,
    get_categories,
    get_drivers_points,
    get_standings_with_results,
    get_teams_list,
)
from fastapi import FastAPI, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

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


@app.post("/api")
async def rti(
    action: str = Form(),
    championship_id: str | int | None = Form(default="latest"),
    category_id: int | None = Form(default=None),
):

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
            if category_id is None:
                raise HTTPException(
                    422,
                    "Argument 'category_id' must be provided for 'get_driver_points' action",
                )
            result = get_drivers_points(int(championship_id))

        case other:
            raise HTTPException(400, f"'{other}' action is invalid.")

    return result
