from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.config import Settings
from compose_ai_api.domains.ai_architect.models import (
    AIProviderHealth,
    AIProviderHealthStatus,
)
from compose_ai_api.domains.ai_architect.providers.base import AIProviderError


async def ensure_provider_available(
    session: AsyncSession,
    settings: Settings,
    provider: str,
    model: str,
) -> None:
    health = await _load_health(session, settings, provider, model, for_update=True)
    now = datetime.now(UTC)
    if health is None:
        return
    if health.status == AIProviderHealthStatus.DEGRADED:
        if health.degraded_until and health.degraded_until <= now:
            health.status = AIProviderHealthStatus.HEALTHY
            health.consecutive_failures = 0
            health.degraded_until = None
            await session.flush()
            return
        raise AIProviderError(
            "AI_PROVIDER_DEGRADED",
            "The selected AI provider is temporarily degraded.",
            retryable=True,
            status_code=503,
        )
    if health.status == AIProviderHealthStatus.UNAVAILABLE:
        raise AIProviderError(
            "AI_PROVIDER_UNAVAILABLE",
            "The selected AI provider is unavailable.",
            retryable=True,
            status_code=503,
        )


async def record_provider_success(
    session: AsyncSession,
    settings: Settings,
    provider: str,
    model: str,
) -> None:
    health = await _get_or_create(session, settings, provider, model)
    health.status = AIProviderHealthStatus.HEALTHY
    health.consecutive_failures = 0
    health.last_success_at = datetime.now(UTC)
    health.degraded_until = None
    health.last_error_code = None
    await session.flush()


async def record_provider_failure(
    session: AsyncSession,
    settings: Settings,
    provider: str,
    model: str,
    error_code: str,
) -> AIProviderHealthStatus:
    health = await _get_or_create(session, settings, provider, model)
    health.consecutive_failures += 1
    health.last_failure_at = datetime.now(UTC)
    health.last_error_code = error_code
    if health.consecutive_failures >= settings.ai_provider_failure_threshold:
        health.status = AIProviderHealthStatus.DEGRADED
        health.degraded_until = datetime.now(UTC) + timedelta(
            seconds=settings.ai_provider_degraded_seconds
        )
    await session.flush()
    return AIProviderHealthStatus(str(health.status))


async def _get_or_create(
    session: AsyncSession,
    settings: Settings,
    provider: str,
    model: str,
) -> AIProviderHealth:
    health = await _load_health(session, settings, provider, model, for_update=True)
    if health is not None:
        return health
    health = AIProviderHealth(
        id=uuid4(),
        provider=provider,
        model=model,
        environment=settings.ai_prompt_environment,
        status=AIProviderHealthStatus.HEALTHY,
        consecutive_failures=0,
    )
    session.add(health)
    await session.flush()
    return health


async def _load_health(
    session: AsyncSession,
    settings: Settings,
    provider: str,
    model: str,
    *,
    for_update: bool,
) -> AIProviderHealth | None:
    statement = select(AIProviderHealth).where(
        AIProviderHealth.provider == provider,
        AIProviderHealth.model == model,
        AIProviderHealth.environment == settings.ai_prompt_environment,
    )
    if for_update:
        statement = statement.with_for_update()
    return (await session.execute(statement)).scalar_one_or_none()
