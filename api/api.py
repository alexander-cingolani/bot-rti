import logging

from fastapi import FastAPI, Form, HTTPException
from pydantic import BaseModel

from components.json_formatting import get_calendar, get_categories, get_standings


class Item(BaseModel):
    action: str
    championship: int
    category: int | None


app = FastAPI()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG
)
logger = logging.getLogger(__name__)

app = FastAPI()


@app.post("/")
async def root(
    action: str = Form(),
    id: int = Form(default=None),
    idCampionato: int = Form(default=None),
    idCategoria: int = Form(),
):
    if action == "get_categorie_fe":
        result = get_categories(id)
    elif action == "get_calendario":
        result = get_calendar(idCampionato, idCategoria)
    elif action == "get_classifica":
        result = get_standings(idCampionato, idCategoria)
    else:
        raise HTTPException(400, f"'{action}' action is invalid.")

    logging.log(logging.INFO, result)
    return result
