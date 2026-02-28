from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TunnelSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    target_port: int
    status: str
    created_at: datetime
    last_heartbeat: datetime


class TunnelSessionListResponse(BaseModel):
    data: list[TunnelSessionResponse]
