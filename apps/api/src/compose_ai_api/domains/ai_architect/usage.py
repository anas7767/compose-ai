from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from fastapi import status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.auth import AuthContext
from compose_ai_api.core.config import Settings
from compose_ai_api.domains.ai_architect.models import (
    AIRun,
    AIRunStatus,
    AIUsageDaily,
)
from compose_ai_api.domains.ai_architect.schemas import AIUsageResponse
from compose_ai_api.domains.ai_architect.token_usage import (
    estimate_cost_microusd,
    estimate_tokens,
    usd_to_microusd,
)
from compose_ai_api.domains.billing.models import Plan, Subscription, SubscriptionStatus
from compose_ai_api.domains.identity.models import Organization
from compose_ai_api.domains.projects.service import project_error

ACTIVE_SUBSCRIPTIONS = (
    SubscriptionStatus.FREE,
    SubscriptionStatus.TRIALING,
    SubscriptionStatus.ACTIVE,
)


@dataclass(frozen=True)
class AIUsageEstimate:
    input_tokens: int
    output_tokens: int
    cost_microusd: int


def estimate_request_usage(
    settings: Settings,
    system_prompt: str,
    user_prompt: str,
    output_tokens: int | None = None,
) -> AIUsageEstimate:
    input_tokens = estimate_tokens(system_prompt) + estimate_tokens(user_prompt) + 24
    expected_output_tokens = output_tokens or settings.ai_max_output_tokens
    return AIUsageEstimate(
        input_tokens=input_tokens,
        output_tokens=expected_output_tokens,
        cost_microusd=estimate_cost_microusd(
            input_tokens,
            expected_output_tokens,
            settings.ai_input_price_per_1m_usd,
            settings.ai_output_price_per_1m_usd,
        ),
    )


async def enforce_usage_preflight(
    session: AsyncSession,
    settings: Settings,
    context: AuthContext,
    estimate: AIUsageEstimate,
) -> None:
    if estimate.input_tokens > settings.ai_max_input_tokens:
        raise project_error(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            "AI_CONTEXT_TOO_LARGE",
            "The project context exceeds the configured AI input limit.",
            {"estimatedTokens": estimate.input_tokens, "limit": settings.ai_max_input_tokens},
        )
    await session.execute(
        select(Organization.id)
        .where(Organization.id == context.membership.organization_id)
        .with_for_update()
    )
    now = datetime.now(UTC)
    active_count = (
        await session.execute(
            select(func.count(AIRun.id)).where(
                AIRun.organization_id == context.membership.organization_id,
                AIRun.status.in_((AIRunStatus.QUEUED, AIRunStatus.RUNNING)),
            )
        )
    ).scalar_one()
    if active_count >= settings.ai_max_concurrent_runs_per_org:
        raise project_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "AI_CONCURRENCY_LIMIT_REACHED",
            "The organization has too many AI runs in progress.",
            {"limit": settings.ai_max_concurrent_runs_per_org},
        )
    minute_count = (
        await session.execute(
            select(func.count(AIRun.id)).where(
                AIRun.organization_id == context.membership.organization_id,
                AIRun.created_by == context.user.id,
                AIRun.created_at >= now - timedelta(minutes=1),
            )
        )
    ).scalar_one()
    if minute_count >= settings.ai_user_rate_limit_per_minute:
        raise project_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "AI_RATE_LIMIT_REACHED",
            "The per-user AI request limit has been reached.",
            {"limit": settings.ai_user_rate_limit_per_minute},
        )

    period = await _plan_period(session, context)
    used_credits = (
        await session.execute(
            select(func.count(AIRun.id)).where(
                AIRun.organization_id == context.membership.organization_id,
                AIRun.created_at >= period.start,
                AIRun.cache_hit.is_(False),
                AIRun.status.in_((AIRunStatus.QUEUED, AIRunStatus.RUNNING, AIRunStatus.COMPLETED)),
            )
        )
    ).scalar_one()
    if used_credits >= period.ai_credit_limit:
        raise project_error(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "AI_USAGE_LIMIT_REACHED",
            "The organization's AI run allowance has been reached.",
            {"limit": period.ai_credit_limit, "used": used_credits},
        )

    today = now.date()
    month_start = today.replace(day=1)
    daily_cost = await _cost_since(session, context.membership.organization_id, today)
    monthly_cost = await _cost_since(session, context.membership.organization_id, month_start)
    daily_limit = usd_to_microusd(settings.ai_org_daily_cost_limit_usd)
    monthly_limit = usd_to_microusd(settings.ai_org_monthly_cost_limit_usd)
    if daily_cost + estimate.cost_microusd > daily_limit:
        raise _cost_limit_error("daily", daily_cost, daily_limit, estimate.cost_microusd)
    if monthly_cost + estimate.cost_microusd > monthly_limit:
        raise _cost_limit_error("monthly", monthly_cost, monthly_limit, estimate.cost_microusd)


async def record_usage(
    session: AsyncSession,
    *,
    organization_id: UUID,
    user_id: UUID,
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_microusd: int,
    cache_hit: bool,
) -> None:
    statement = pg_insert(AIUsageDaily).values(
        id=uuid4(),
        organization_id=organization_id,
        user_id=user_id,
        usage_date=datetime.now(UTC).date(),
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_microusd=cost_microusd,
        run_count=1,
        cache_hit_count=1 if cache_hit else 0,
    )
    statement = statement.on_conflict_do_update(
        constraint="uq_ai_usage_daily_dimensions",
        set_={
            "input_tokens": AIUsageDaily.input_tokens + input_tokens,
            "output_tokens": AIUsageDaily.output_tokens + output_tokens,
            "cost_microusd": AIUsageDaily.cost_microusd + cost_microusd,
            "run_count": AIUsageDaily.run_count + 1,
            "cache_hit_count": AIUsageDaily.cache_hit_count + (1 if cache_hit else 0),
            "updated_at": datetime.now(UTC),
        },
    )
    await session.execute(statement)


async def load_usage_summary(
    session: AsyncSession,
    settings: Settings,
    context: AuthContext,
) -> AIUsageResponse:
    today = datetime.now(UTC).date()
    month_start = today.replace(day=1)
    totals = (
        await session.execute(
            select(
                func.coalesce(func.sum(AIUsageDaily.input_tokens), 0),
                func.coalesce(func.sum(AIUsageDaily.output_tokens), 0),
                func.coalesce(func.sum(AIUsageDaily.cost_microusd), 0),
                func.coalesce(func.sum(AIUsageDaily.run_count), 0),
                func.coalesce(func.sum(AIUsageDaily.cache_hit_count), 0),
            ).where(
                AIUsageDaily.organization_id == context.membership.organization_id,
                AIUsageDaily.usage_date >= month_start,
            )
        )
    ).one()
    return AIUsageResponse(
        period_start=month_start,
        period_end=today,
        input_tokens=int(totals[0]),
        output_tokens=int(totals[1]),
        cost_microusd=int(totals[2]),
        run_count=int(totals[3]),
        cache_hit_count=int(totals[4]),
        daily_cost_limit_microusd=usd_to_microusd(settings.ai_org_daily_cost_limit_usd),
        monthly_cost_limit_microusd=usd_to_microusd(settings.ai_org_monthly_cost_limit_usd),
    )


@dataclass(frozen=True)
class _PlanPeriod:
    start: datetime
    ai_credit_limit: int


async def _plan_period(session: AsyncSession, context: AuthContext) -> _PlanPeriod:
    result = (
        await session.execute(
            select(Subscription.current_period_start, Plan.ai_credit_limit)
            .join(Plan, Plan.id == Subscription.plan_id)
            .where(
                Subscription.organization_id == context.membership.organization_id,
                Subscription.status.in_(ACTIVE_SUBSCRIPTIONS),
                Subscription.deleted_at.is_(None),
            )
        )
    ).one_or_none()
    if result is None:
        raise project_error(
            status.HTTP_428_PRECONDITION_REQUIRED,
            "AI_PLAN_UNAVAILABLE",
            "The organization plan is not initialized.",
        )
    current_period_start, ai_credit_limit = result
    fallback_start = datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return _PlanPeriod(
        start=current_period_start or fallback_start,
        ai_credit_limit=ai_credit_limit,
    )


async def _cost_since(session: AsyncSession, organization_id: UUID, start: date) -> int:
    value = (
        await session.execute(
            select(func.coalesce(func.sum(AIUsageDaily.cost_microusd), 0)).where(
                AIUsageDaily.organization_id == organization_id,
                AIUsageDaily.usage_date >= start,
            )
        )
    ).scalar_one()
    return int(value)


def _cost_limit_error(period: str, used: int, limit: int, estimated: int) -> Exception:
    return project_error(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "AI_COST_LIMIT_REACHED",
        f"The organization's {period} AI cost limit would be exceeded.",
        {
            "period": period,
            "usedMicrousd": used,
            "limitMicrousd": limit,
            "estimatedRequestMicrousd": estimated,
        },
    )
