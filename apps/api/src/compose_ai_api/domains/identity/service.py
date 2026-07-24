from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from compose_ai_api.core.auth import AuthRole, resolve_permissions
from compose_ai_api.core.security import AuthenticatedPrincipal
from compose_ai_api.domains.billing.models import Plan, Subscription, SubscriptionStatus
from compose_ai_api.domains.identity.models import (
    Organization,
    OrganizationMember,
    OrganizationMemberStatus,
    OrganizationPlanStatus,
    OrganizationRole,
    OrganizationType,
    User,
    UserStatus,
)
from compose_ai_api.domains.identity.schemas import (
    AuthBootstrapRequest,
    AuthContextResponse,
    AuthMembershipResponse,
    AuthOrganizationResponse,
    AuthSessionResponse,
    AuthSubscriptionResponse,
    AuthUserResponse,
)


@dataclass(frozen=True)
class BootstrapResult:
    user: User
    organization: Organization
    membership: OrganizationMember
    subscription: Subscription


async def bootstrap_identity(
    session: AsyncSession,
    principal: AuthenticatedPrincipal,
    request: AuthBootstrapRequest,
) -> AuthContextResponse:
    if request.active_clerk_organization_id != principal.clerk_organization_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Active organization does not match the verified Clerk session.",
        )

    result = await _bootstrap_identity_records(session, principal, request)
    await session.commit()
    return build_auth_context_response(result)


async def load_auth_context_response(
    session: AsyncSession,
    principal: AuthenticatedPrincipal,
) -> AuthContextResponse:
    statement = (
        select(User)
        .where(User.clerk_user_id == principal.clerk_user_id)
        .options(
            selectinload(User.memberships)
            .selectinload(OrganizationMember.organization)
            .selectinload(Organization.subscriptions)
            .selectinload(Subscription.plan)
        )
    )
    user = (await session.execute(statement)).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="Compose account is not initialized. Call /auth/bootstrap first.",
        )

    membership = _select_membership_for_principal(user.memberships, principal)

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No Compose organization membership is available for this session.",
        )

    subscription = _select_active_subscription(membership.organization)

    if subscription is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="Organization subscription is not initialized. Call /auth/bootstrap first.",
        )

    return build_auth_context_response(
        BootstrapResult(
            user=user,
            organization=membership.organization,
            membership=membership,
            subscription=subscription,
        )
    )


def build_auth_session_response(principal: AuthenticatedPrincipal) -> AuthSessionResponse:
    return AuthSessionResponse(
        clerk_user_id=principal.clerk_user_id,
        clerk_session_id=principal.clerk_session_id,
        clerk_organization_id=principal.clerk_organization_id,
        clerk_organization_role=principal.clerk_organization_role,
        expires_at=principal.expires_at,
        issued_at=principal.issued_at,
    )


def build_auth_context_response(result: BootstrapResult) -> AuthContextResponse:
    plan = result.subscription.plan
    role = AuthRole(str(result.membership.role))

    return AuthContextResponse(
        user=AuthUserResponse(
            id=result.user.id,
            clerk_user_id=result.user.clerk_user_id,
            email=result.user.email,
            name=result.user.name,
            avatar_url=result.user.avatar_url,
            status=str(result.user.status),
            last_login_at=result.user.last_login_at or datetime.now(UTC),
        ),
        organization=AuthOrganizationResponse(
            id=result.organization.id,
            clerk_organization_id=result.organization.clerk_organization_id,
            name=result.organization.name,
            slug=result.organization.slug,
            type=str(result.organization.type),
            plan_status=str(result.organization.plan_status),
        ),
        membership=AuthMembershipResponse(
            id=result.membership.id,
            role=str(result.membership.role),
            status=str(result.membership.status),
        ),
        subscription=AuthSubscriptionResponse(
            id=result.subscription.id,
            plan_code=plan.code,
            status=str(result.subscription.status),
            project_limit=plan.project_limit,
            ai_credit_limit=plan.ai_credit_limit,
            render_limit=plan.render_limit,
            storage_limit_mb=plan.storage_limit_mb,
        ),
        permissions=list(resolve_permissions(role)),
    )


async def _bootstrap_identity_records(
    session: AsyncSession,
    principal: AuthenticatedPrincipal,
    request: AuthBootstrapRequest,
) -> BootstrapResult:
    now = datetime.now(UTC)
    free_plan = await _ensure_free_plan(session)
    user = await _ensure_user(session, principal, request, now)
    organization = await _ensure_organization(session, principal, request, user)
    membership = await _ensure_membership(session, principal, organization, user)
    subscription = await _ensure_free_subscription(session, organization, free_plan, now)

    return BootstrapResult(
        user=user,
        organization=organization,
        membership=membership,
        subscription=subscription,
    )


async def _ensure_free_plan(session: AsyncSession) -> Plan:
    plan = (await session.execute(select(Plan).where(Plan.code == "free"))).scalar_one_or_none()

    if plan is not None:
        return plan

    plan = Plan(
        code="free",
        name="Free",
        monthly_price_cents=0,
        yearly_price_cents=0,
        currency="USD",
        project_limit=1,
        ai_credit_limit=25,
        render_limit=3,
        storage_limit_mb=250,
        features={
            "auth": True,
            "organizations": True,
            "project_creation": False,
            "ai_floor_plans": False,
        },
        active=True,
    )
    session.add(plan)
    await session.flush()
    return plan


async def _ensure_user(
    session: AsyncSession,
    principal: AuthenticatedPrincipal,
    request: AuthBootstrapRequest,
    now: datetime,
) -> User:
    statement = select(User).where(User.clerk_user_id == principal.clerk_user_id)
    user = (await session.execute(statement)).scalar_one_or_none()

    if user is None:
        user = User(
            clerk_user_id=principal.clerk_user_id,
            email=str(request.email) if request.email else None,
            name=request.name,
            avatar_url=request.avatar_url,
            status=UserStatus.ACTIVE,
            last_login_at=now,
        )
        session.add(user)
        await session.flush()
        return user

    user.email = str(request.email) if request.email else user.email
    user.name = request.name
    user.avatar_url = request.avatar_url
    user.status = UserStatus.ACTIVE
    user.last_login_at = now
    await session.flush()
    return user


async def _ensure_organization(
    session: AsyncSession,
    principal: AuthenticatedPrincipal,
    request: AuthBootstrapRequest,
    user: User,
) -> Organization:
    if principal.clerk_organization_id:
        return await _ensure_clerk_organization(session, principal, request)

    statement = select(Organization).where(
        Organization.personal_owner_user_id == user.id,
        Organization.clerk_organization_id.is_(None),
    )
    organization = (await session.execute(statement)).scalar_one_or_none()

    if organization is not None:
        return organization

    organization = Organization(
        clerk_organization_id=None,
        personal_owner_user_id=user.id,
        name=f"{user.name}'s workspace",
        slug=await _unique_slug(session, f"{user.name} workspace"),
        type=OrganizationType.PERSONAL,
        billing_email=user.email,
        default_currency="USD",
        plan_status=OrganizationPlanStatus.FREE,
    )
    session.add(organization)
    await session.flush()
    return organization


async def _ensure_clerk_organization(
    session: AsyncSession,
    principal: AuthenticatedPrincipal,
    request: AuthBootstrapRequest,
) -> Organization:
    statement = select(Organization).where(
        Organization.clerk_organization_id == principal.clerk_organization_id,
    )
    organization = (await session.execute(statement)).scalar_one_or_none()
    name = request.active_organization_name or "Compose AI workspace"

    if organization is not None:
        organization.name = name
        return organization

    organization = Organization(
        clerk_organization_id=principal.clerk_organization_id,
        name=name,
        slug=await _unique_slug(session, request.active_organization_slug or name),
        type=OrganizationType.STUDIO,
        default_currency="USD",
        plan_status=OrganizationPlanStatus.FREE,
    )
    session.add(organization)
    await session.flush()
    return organization


async def _ensure_membership(
    session: AsyncSession,
    principal: AuthenticatedPrincipal,
    organization: Organization,
    user: User,
) -> OrganizationMember:
    statement = select(OrganizationMember).where(
        OrganizationMember.organization_id == organization.id,
        OrganizationMember.user_id == user.id,
    )
    membership = (await session.execute(statement)).scalar_one_or_none()
    role = _resolve_local_role(principal, organization, membership is None)

    if membership is None:
        membership = OrganizationMember(
            organization_id=organization.id,
            user_id=user.id,
            role=role,
            status=OrganizationMemberStatus.ACTIVE,
            joined_at=datetime.now(UTC),
        )
        session.add(membership)
    else:
        membership.role = role
        membership.status = OrganizationMemberStatus.ACTIVE

    await session.flush()
    return membership


async def _ensure_free_subscription(
    session: AsyncSession,
    organization: Organization,
    free_plan: Plan,
    now: datetime,
) -> Subscription:
    statement = _active_subscription_statement(organization.id)
    subscription = (await session.execute(statement)).scalar_one_or_none()

    if subscription is not None:
        return subscription

    subscription = Subscription(
        organization_id=organization.id,
        plan_id=free_plan.id,
        plan=free_plan,
        status=SubscriptionStatus.FREE,
        current_period_start=now,
        amount_cents=0,
        tax_cents=0,
        total_cents=0,
    )
    session.add(subscription)
    await session.flush()
    return subscription


def _active_subscription_statement(organization_id: object) -> Select[tuple[Subscription]]:
    return (
        select(Subscription)
        .where(
            Subscription.organization_id == organization_id,
            Subscription.status.in_(
                [
                    SubscriptionStatus.FREE,
                    SubscriptionStatus.TRIALING,
                    SubscriptionStatus.ACTIVE,
                ]
            ),
        )
        .options(selectinload(Subscription.plan))
    )


def _select_membership_for_principal(
    memberships: list[OrganizationMember],
    principal: AuthenticatedPrincipal,
) -> OrganizationMember | None:
    for membership in memberships:
        if membership.organization.clerk_organization_id == principal.clerk_organization_id:
            return membership

    if principal.clerk_organization_id is None:
        personal_membership = next(
            (
                membership
                for membership in memberships
                if membership.organization.clerk_organization_id is None
            ),
            None,
        )
        if personal_membership is not None:
            return personal_membership

        active_memberships = [
            membership
            for membership in memberships
            if membership.status == OrganizationMemberStatus.ACTIVE
        ]
        if len(active_memberships) == 1:
            return active_memberships[0]

    return None


def _select_active_subscription(organization: Organization) -> Subscription | None:
    for subscription in organization.subscriptions:
        if subscription.status in {
            SubscriptionStatus.FREE,
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.ACTIVE,
        }:
            return subscription

    return None


def _resolve_local_role(
    principal: AuthenticatedPrincipal,
    organization: Organization,
    is_new_membership: bool,
) -> OrganizationRole:
    if organization.clerk_organization_id is None:
        return OrganizationRole.OWNER

    if is_new_membership:
        return OrganizationRole.OWNER

    clerk_role = principal.clerk_organization_role or ""

    if clerk_role.endswith("admin") or clerk_role in {"admin", "owner", "org:admin"}:
        return OrganizationRole.ADMIN

    return OrganizationRole.EDITOR


async def _unique_slug(session: AsyncSession, value: str) -> str:
    base_slug = _slugify(value) or "workspace"
    candidate = base_slug
    suffix = 2

    while await _slug_exists(session, candidate):
        candidate = f"{base_slug}-{suffix}"
        suffix += 1

    return candidate


async def _slug_exists(session: AsyncSession, slug: str) -> bool:
    statement = select(Organization.id).where(Organization.slug == slug)
    return (await session.execute(statement)).scalar_one_or_none() is not None


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower())
    return normalized.strip("-")[:160]
