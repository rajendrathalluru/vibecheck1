from pydantic import BaseModel


class ErrorDetail(BaseModel):
    type: str
    message: str
    code: str
    param: str | None = None
    doc_url: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
