from pydantic import BaseModel


class ErrorResponse(BaseModel):
    detail: str
    filename: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
