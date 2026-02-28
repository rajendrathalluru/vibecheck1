from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.assessment import Assessment
from api.models.agent_log import AgentLog
from api.schemas.agent_log import AgentLogResponse, AgentLogListResponse
from api.utils.errors import VibeCheckError
from api.utils.pagination import paginate

router = APIRouter(tags=["Agent Logs"])


@router.get(
    "/v1/assessments/{assessment_id}/logs",
    response_model=AgentLogListResponse,
)
async def list_logs(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    per_page: int = 20,
    agent: str | None = None,
):
    assessment = await db.get(Assessment, assessment_id)
    if not assessment:
        raise VibeCheckError.not_found("Assessment", assessment_id)
    if assessment.mode == "lightweight":
        raise VibeCheckError.logs_not_available()

    query = (
        select(AgentLog)
        .where(AgentLog.assessment_id == assessment_id)
        .order_by(AgentLog.timestamp.asc())
    )
    if agent is not None:
        query = query.where(AgentLog.agent == agent)

    items, meta = await paginate(db, query, page, per_page)
    return AgentLogListResponse(
        data=[AgentLogResponse.model_validate(l) for l in items],
        pagination=meta,
    )
