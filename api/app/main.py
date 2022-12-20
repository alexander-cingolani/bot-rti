import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.components.json_formatting import (
    get_calendar,
    get_categories,
    get_drivers_points,
    get_standings_with_results,
)

app = FastAPI()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

app = FastAPI()

# app.mount(
#     "/static",
#     StaticFiles(directory="api/app/static/standings-page/"),
#     name="standings-page",
# )
# app.mount(
#     "/tg-webapp", StaticFiles(directory="./app/static/telegram-webapp/"), name="tg-app"
# )


@app.get("/")
async def root():
    return HTMLResponse(open("api/app/static/standings-page/index.html", "r").read())


class Item(BaseModel):
    action: str | None = None
    championship_id: str | int = "latest"
    category_id: str | int | None = None


@app.post("/api")
async def rti(item: Item):
    match item.action:
        case "get_category_list":
            result = get_categories(item.championship_id)
        case "get_calendar":
            if item.category_id is None:
                raise HTTPException(
                    422,
                    "Argument 'category_id' must be provided for 'get_calendar' action",
                )
            result = get_calendar(int(item.category_id))
        case "get_standings":

            if item.category_id is None:
                raise HTTPException(
                    422,
                    "Argument 'category_id' must be provided for 'get_standings' action",
                )

            result = get_standings_with_results(int(item.category_id))
        case "get_driver_points":
            if item.category_id is None:
                raise HTTPException(
                    422,
                    "Argument 'category_id' must be provided for 'get_driver_points' action",
                )
            result = get_standings_with_results(int(item.category_id))

            result = get_drivers_points(int(item.championship_id))
        case other:
            raise HTTPException(400, f"'{other}' action is invalid.")
    return result


# @app.get("/classifiche", response_class=HTMLResponse)
# async def classifiche():
#     content = open("./app/static/standings-page/html/index.html", "r")
#     text = content.read()
#     return HTMLResponse(content=text)

# @app.get("/tg-app", response_class=HTMLResponse)
# async def tg_app():
#     content = open("./app/static/telegram-webapp/html/index.html", "r")
#     text = content.read()
#     return HTMLResponse(content=text)
