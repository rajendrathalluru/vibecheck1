from fastapi import Query
from pydantic import BaseModel


class PaginationParams:
    page: int = Query(1, ge=1)
    per_page: int = Query(20, ge=1, le=100)


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int
