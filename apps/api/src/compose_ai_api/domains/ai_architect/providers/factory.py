from compose_ai_api.core.config import Settings
from compose_ai_api.domains.ai_architect.providers.base import AIProvider, AIProviderError
from compose_ai_api.domains.ai_architect.providers.gemini import GeminiProvider
from compose_ai_api.domains.ai_architect.providers.mock import MockAIProvider
from compose_ai_api.domains.ai_architect.providers.openai import OpenAIProvider


def create_provider(settings: Settings, provider_name: str) -> AIProvider:
    if provider_name == "mock":
        return MockAIProvider(settings.ai_mock_seed)
    if provider_name == "gemini":
        if not settings.gemini_api_key:
            raise AIProviderError(
                "AI_PROVIDER_NOT_CONFIGURED",
                "Gemini API key missing",
                retryable=False,
            )
        return GeminiProvider(
            api_key=settings.gemini_api_key,
            timeout_seconds=settings.ai_request_timeout_seconds,
        )
    if provider_name == "openai":
        if not settings.openai_api_key:
            raise AIProviderError(
                "AI_PROVIDER_NOT_CONFIGURED",
                "OpenAI is selected but OPENAI_API_KEY is not configured.",
                retryable=False,
            )
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            organization=settings.openai_organization,
            project=settings.openai_project,
            timeout_seconds=settings.ai_request_timeout_seconds,
        )
    raise AIProviderError(
        "AI_PROVIDER_NOT_CONFIGURED",
        f"Unsupported AI provider: {provider_name}.",
        retryable=False,
    )


def model_for_alias(settings: Settings, provider_name: str, alias: str) -> str:
    if provider_name == "mock":
        return f"compose-mock-{alias}-v1"
    if provider_name == "gemini":
        if not settings.gemini_text_model:
            raise AIProviderError(
                "AI_PROVIDER_NOT_CONFIGURED",
                "Gemini text model missing",
                retryable=False,
            )
        return settings.gemini_text_model
    values = {
        "architect_brief": settings.openai_model_brief,
        "architect_chat": settings.openai_model_chat,
        "requirement_normalizer": settings.openai_model_normalizer,
        "fallback_text": settings.openai_model_fallback,
    }
    model = values.get(alias)
    if not model:
        raise AIProviderError(
            "AI_PROVIDER_NOT_CONFIGURED",
            f"No OpenAI model is configured for {alias}.",
            retryable=False,
        )
    return model
