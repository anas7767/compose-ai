from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from compose_ai_api.domains.ai_architect.providers.base import ProviderUsage
from compose_ai_api.domains.floor_plans.schemas import FloorPlanProgramOutput


@dataclass(frozen=True)
class FloorPlanProgramRequest:
    model: str
    context: dict[str, Any]
    deterministic_seed: int
    max_output_tokens: int


@dataclass(frozen=True)
class FloorPlanProgramResponse:
    program: FloorPlanProgramOutput
    usage: ProviderUsage
    provider_request_id: str | None = None


class FloorPlanProgramProvider(Protocol):
    name: str

    async def generate_program(
        self, request: FloorPlanProgramRequest
    ) -> FloorPlanProgramResponse: ...
