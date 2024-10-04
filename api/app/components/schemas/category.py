from pydantic import BaseModel


class CategorySchema(BaseModel):
    category_id: int
    category_name: str
    championship: int
    order: int
    provisional: bool
