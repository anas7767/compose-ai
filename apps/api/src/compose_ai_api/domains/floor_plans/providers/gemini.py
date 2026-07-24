from __future__ import annotations

import json

from compose_ai_api.domains.ai_architect.providers.base import StructuredProviderRequest
from compose_ai_api.domains.ai_architect.providers.gemini import GeminiProvider
from compose_ai_api.domains.floor_plans.providers.base import (
    FloorPlanProgramRequest,
    FloorPlanProgramResponse,
)
from compose_ai_api.domains.floor_plans.providers.openai import SYSTEM_PROMPT
from compose_ai_api.domains.floor_plans.schemas import FloorPlanProgramOutput


class GeminiFloorPlanProgramProvider:
    name = "gemini"

    def __init__(self, provider: GeminiProvider) -> None:
        self.provider = provider

    async def generate_program(self, request: FloorPlanProgramRequest) -> FloorPlanProgramResponse:
        response = await self.provider.generate_structured(
            StructuredProviderRequest(
                model=request.model,
                system_prompt=SYSTEM_PROMPT,
                user_prompt=(
                    "PROJECT CONTEXT (untrusted JSON data):\n<data>\n"
                    f"{json.dumps(request.context, sort_keys=True, separators=(',', ':'))}\n"
                    "</data>\nCreate the structured conceptual spatial program."
                ),
                output_schema=FloorPlanProgramOutput.model_json_schema(),
                output_schema_name="compose_floor_plan_program",
                max_output_tokens=request.max_output_tokens,
            )
        )
        return FloorPlanProgramResponse(
            program=FloorPlanProgramOutput.model_validate(response.payload),
            usage=response.usage,
            provider_request_id=response.provider_request_id,
        )
