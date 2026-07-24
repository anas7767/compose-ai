from compose_ai_api.core.config import Settings
from compose_ai_api.domains.ai_architect.providers.base import AIProviderError
from compose_ai_api.domains.ai_architect.providers.gemini import GeminiProvider
from compose_ai_api.domains.ai_architect.providers.openai import OpenAIProvider
from compose_ai_api.domains.floor_plans.providers.base import FloorPlanProgramProvider
from compose_ai_api.domains.floor_plans.providers.gemini import GeminiFloorPlanProgramProvider
from compose_ai_api.domains.floor_plans.providers.mock import MockFloorPlanProgramProvider
from compose_ai_api.domains.floor_plans.providers.openai import OpenAIFloorPlanProgramProvider


def create_floor_plan_provider(
    settings: Settings, provider_name: str
) -> tuple[FloorPlanProgramProvider, str]:
    if provider_name == "mock":
        return MockFloorPlanProgramProvider(), "compose-mock-floor-plan-v1"
    if provider_name == "gemini":
        if not settings.gemini_api_key or not settings.gemini_text_model:
            raise AIProviderError(
                "AI_PROVIDER_NOT_CONFIGURED",
                "Gemini floor-plan generation is not configured.",
                retryable=False,
            )
        provider = GeminiProvider(
            api_key=settings.gemini_api_key,
            timeout_seconds=settings.ai_request_timeout_seconds,
        )
        return GeminiFloorPlanProgramProvider(provider), settings.gemini_text_model
    if provider_name == "openai":
        if not settings.openai_api_key or not settings.openai_model_floor_plan:
            raise AIProviderError(
                "AI_PROVIDER_NOT_CONFIGURED",
                "OpenAI floor-plan generation is not configured.",
                retryable=False,
            )
        provider = OpenAIProvider(
            api_key=settings.openai_api_key,
            organization=settings.openai_organization,
            project=settings.openai_project,
            timeout_seconds=settings.ai_request_timeout_seconds,
        )
        return OpenAIFloorPlanProgramProvider(provider), settings.openai_model_floor_plan
    raise AIProviderError(
        "AI_PROVIDER_NOT_CONFIGURED",
        f"Unsupported floor-plan provider: {provider_name}.",
        retryable=False,
    )
