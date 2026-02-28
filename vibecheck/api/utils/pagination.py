import math

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.pagination import PaginationMeta


async def paginate(db: AsyncSession, query, page: int, per_page: int) -> tuple[list, PaginationMeta]:
    count_query = select(func.count()).select_from(query.subquery())
    result = await db.execute(count_query)
    total = result.scalar() or 0
    total_pages = math.ceil(total / per_page) if total > 0 else 0

    items_query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(items_query)
    items = result.scalars().all()

    return list(items), PaginationMeta(
        page=page, per_page=per_page, total=total, total_pages=total_pages
    )
