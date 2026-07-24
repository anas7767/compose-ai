from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    service: str


class HealthCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "failed", "disabled"]
    code: str | None = None
    message: str | None = Field(default=None, max_length=240)


class ReadinessResponse(HealthResponse):
    checks: dict[str, HealthCheckResponse]
