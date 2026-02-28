from fastapi import APIRouter, Depends
from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.assessment import Assessment
from api.models.finding import Finding
from api.schemas.finding import FindingResponse, FindingListResponse
from api.utils.errors import VibeCheckError
from api.utils.pagination import paginate

# Severity order for sorting: critical=0, high=1, medium=2, low=3, info=4
SEVERITY_ORDER = case(
    (Finding.severity == "critical", 0),
    (Finding.severity == "high", 1),
    (Finding.severity == "medium", 2),
    (Finding.severity == "low", 3),
    (Finding.severity == "info", 4),
    else_=5,
)


async def _get_assessment_or_404(db: AsyncSession, assessment_id: str) -> Assessment:
    assessment = await db.get(Assessment, assessment_id)
    if not assessment:
        raise VibeCheckError.not_found("Assessment", assessment_id)
    return assessment


router = APIRouter(tags=["Findings"])


@router.get(
    "/v1/assessments/{assessment_id}/findings",
    response_model=FindingListResponse,
)
async def list_findings(
    assessment_id: str,
    db: AsyncSession = Depends(get_db),
    page: int = 1,
    per_page: int = 20,
    severity: str | None = None,
    category: str | None = None,
    agent: str | None = None,
    sort: str = "severity",
):
    await _get_assessment_or_404(db, assessment_id)

    query = select(Finding).where(Finding.assessment_id == assessment_id)
    if severity is not None:
        query = query.where(Finding.severity == severity)
    if category is not None:
        query = query.where(Finding.category == category)
    if agent is not None:
        query = query.where(Finding.agent == agent)

    if sort == "severity":
        query = query.order_by(SEVERITY_ORDER.asc(), Finding.created_at.asc())
    else:
        order_col = getattr(Finding, sort, Finding.created_at)
        query = query.order_by(order_col.asc())

    items, meta = await paginate(db, query, page, per_page)
    return FindingListResponse(
        data=[FindingResponse.model_validate(f) for f in items],
        pagination=meta,
    )


@router.get(
    "/v1/assessments/{assessment_id}/findings/{finding_id}",
    response_model=FindingResponse,
)
async def get_finding(
    assessment_id: str,
    finding_id: str,
    db: AsyncSession = Depends(get_db),
):
    await _get_assessment_or_404(db, assessment_id)
    result = await db.execute(
        select(Finding).where(
            Finding.id == finding_id,
            Finding.assessment_id == assessment_id,
        )
    )
    finding = result.scalar_one_or_none()
    if not finding:
        raise VibeCheckError.not_found("Finding", finding_id)
    return FindingResponse.model_validate(finding)
