from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from api.schemas.pagination import PaginationMeta


class FileUpload(BaseModel):
    path: str
    content: str


class CreateAssessmentRequest(BaseModel):
    mode: Literal["lightweight", "robust"]
    repo_url: str | None = None
    files: list[FileUpload] | None = None
    tunnel_session_id: str | None = None
    agents: list[str] = ["recon", "auth", "injection", "config"]
    depth: Literal["quick", "standard", "deep"] = "standard"
    idempotency_key: str | None = None

    @model_validator(mode="after")
    def validate_mode_fields(self):
        if self.mode == "lightweight" and not self.repo_url and not self.files:
            raise ValueError("Lightweight mode requires either 'repo_url' or 'files'")
        if self.mode == "robust" and not self.tunnel_session_id:
            raise ValueError("Robust mode requires 'tunnel_session_id'")
        if self.mode == "robust":
            valid_agents = {"recon", "auth", "injection", "config"}
            for a in self.agents:
                if a not in valid_agents:
                    raise ValueError(f"Unknown agent: {a}")
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "mode": "lightweight",
                    "repo_url": "https://github.com/user/my-vibe-coded-app",
                },
                {
                    "mode": "robust",
                    "tunnel_session_id": "tun_a1b2c3d4e5f6",
                    "agents": ["recon", "auth", "injection", "config"],
                    "depth": "standard",
                },
            ]
        }
    )


class AssessmentResponse(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "asm_a1b2c3d4e5f6",
                    "mode": "lightweight",
                    "status": "queued",
                    "repo_url": "https://github.com/user/my-vibe-coded-app",
                    "created_at": "2026-02-28T12:00:00Z",
                    "links": {
                        "self": "/v1/assessments/asm_a1b2c3d4e5f6",
                        "findings": "/v1/assessments/asm_a1b2c3d4e5f6/findings",
                        "logs": "/v1/assessments/asm_a1b2c3d4e5f6/logs",
                    },
                }
            ]
        },
    )

    id: str
    mode: str
    status: str
    repo_url: str | None = None
    tunnel_session_id: str | None = None
    agents: list[str] | None = None
    depth: str
    finding_counts: dict
    idempotency_key: str | None = None
    error_type: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    links: dict = {}

    @model_validator(mode="after")
    def build_links(self):
        self.links = {
            "self": f"/v1/assessments/{self.id}",
            "findings": f"/v1/assessments/{self.id}/findings",
            "logs": f"/v1/assessments/{self.id}/logs",
        }
        return self


class AssessmentListResponse(BaseModel):
    data: list[AssessmentResponse]
    pagination: PaginationMeta


class RerunAssessmentRequest(BaseModel):
    agents: list[str] | None = None
    idempotency_key: str | None = None
