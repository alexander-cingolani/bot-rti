import logging

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.components.json_formatting import (
    get_calendar,
    get_categories,
    get_drivers_points,
    get_standings_with_results,
)


class Item(BaseModel):
    action: str
    championship: int
    category: int | None


app = FastAPI()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

app = FastAPI()

# app.mount(
#     "/standings-page",
#     StaticFiles(directory="./app/static/standings-page/"),
#     name="standings-page",
# )
# app.mount(
#     "/tg-webapp", StaticFiles(directory="./app/static/telegram-webapp/"), name="tg-app"
# )


@app.get("/")
async def root():
    return HTMLResponse("<h1>Ciao</h1>")


@app.post("/api")
async def rti(
    action: str = Form(),
    championship_id: int = Form(default=None),
    category_id: int = Form(),
):

    match action:
        case "get_category_list":
            result = get_categories(championship_id)
        case "get_calendar":
            result = get_calendar(championship_id, category_id)
        case "get_standings":
            result = get_standings_with_results(championship_id, category_id)
        case "get_driver_points":
            result = get_drivers_points(championship_id)
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