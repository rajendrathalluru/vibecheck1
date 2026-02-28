from datetime import datetime

from pydantic import BaseModel, ConfigDict

from api.schemas.pagination import PaginationMeta


class FindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    assessment_id: str
    severity: str
    category: str
    title: str
    description: str
    location: dict | None = None
    evidence: dict | None = None
    remediation: str
    agent: str | None = None
    created_at: datetime


class FindingListResponse(BaseModel):
    data: list[FindingResponse]
    pagination: PaginationMeta
