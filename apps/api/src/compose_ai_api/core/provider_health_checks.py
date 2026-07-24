from __future__ import annotations

from compose_ai_api.core.config import get_settings
from compose_ai_api.domains.ai_architect.providers.base import AIProviderError
from compose_ai_api.domains.ai_architect.providers.gemini import check_gemini_text_health


async def check_ai_provider_connectivity() -> tuple[bool, str | None]:
    settings = get_settings()
    if not settings.readiness_ai_provider_check_enabled:
        return True, None
    if settings.ai_provider == "mock":
        return settings.environment == "local", None if settings.environment == "local" else "mock"
    if settings.ai_provider == "gemini":
        if not settings.gemini_api_key or not settings.gemini_text_model:
            return False, "AI_PROVIDER_NOT_CONFIGURED"
        try:
            ok, _ = await check_gemini_text_health(
                api_key=settings.gemini_api_key,
                model=settings.gemini_text_model,
                timeout_seconds=min(
                    settings.ai_request_timeout_seconds,
                    settings.readiness_ai_provider_timeout_seconds,
                ),
            )
            return ok, None if ok else "AI_PROVIDER_HEALTH_FAILED"
        except AIProviderError as error:
            return False, error.code
    if settings.ai_provider == "openai":
        if settings.openai_api_key:
            return True, None
        return False, "AI_PROVIDER_NOT_CONFIGURED"
    return False, "AI_PROVIDER_NOT_SUPPORTED"
