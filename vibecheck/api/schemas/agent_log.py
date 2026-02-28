from datetime import datetime

from pydantic import BaseModel, ConfigDict

from api.schemas.pagination import PaginationMeta


class AgentLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    assessment_id: str
    agent: str
    step: int
    action: str
    target: str
    payload: str | None = None
    response_code: int | None = None
    response_preview: str | None = None
    reasoning: str
    finding_id: str | None = None
    timestamp: datetime


class AgentLogListResponse(BaseModel):
    data: list[AgentLogResponse]
    pagination: PaginationMeta
