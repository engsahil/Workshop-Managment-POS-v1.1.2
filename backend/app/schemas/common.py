from pydantic import BaseModel


class OkOut(BaseModel):
    ok: bool = True
    message: str = ""


class IdOut(BaseModel):
    id: int


def pagination(page: int = 1, page_size: int = 25) -> tuple[int, int]:
    page = max(1, page)
    page_size = max(1, min(200, page_size))
    return (page - 1) * page_size, page_size
