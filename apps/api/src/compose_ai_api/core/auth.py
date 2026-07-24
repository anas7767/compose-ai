from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from compose_ai_api.core.database import get_db_session
from compose_ai_api.core.security import AuthenticatedPrincipal, clerk_jwt_verifier
from compose_ai_api.domains.identity.models import (
    OrganizationMember,
    OrganizationMemberStatus,
    User,
)

bearer_scheme = HTTPBearer(auto_error=False)


class AuthRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    CLIENT = "client"
    CONTRACTOR = "contractor"


@dataclass(frozen=True)
class AuthContext:
    principal: AuthenticatedPrincipal
    user: User
    membership: OrganizationMember
    role: AuthRole
    permissions: tuple[str, ...]


async def get_current_principal(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
) -> AuthenticatedPrincipal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer session token.",
        )

    return await clerk_jwt_verifier.verify(credentials.credentials)


async def get_auth_context(
    principal: Annotated[AuthenticatedPrincipal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthContext:
    statement = (
        select(User)
        .where(User.clerk_user_id == principal.clerk_user_id)
        .options(
            selectinload(User.memberships).selectinload(OrganizationMember.organization),
        )
    )
    user = (await session.execute(statement)).scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED,
            detail="Compose account is not initialized. Call /auth/bootstrap first.",
        )

    membership = next(
        (
            user_membership
            for user_membership in user.memberships
            if user_membership.organization.clerk_organization_id == principal.clerk_organization_id
        ),
        None,
    )

    if membership is None:
        membership = next(
            (
                user_membership
                for user_membership in user.memberships
                if user_membership.organization.clerk_organization_id is None
            ),
            None,
        )

    if membership is None and principal.clerk_organization_id is None:
        active_memberships = [
            user_membership
            for user_membership in user.memberships
            if user_membership.status == OrganizationMemberStatus.ACTIVE
        ]
        if len(active_memberships) == 1:
            membership = active_memberships[0]

    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No Compose organization membership is available for this session.",
        )

    role = AuthRole(str(membership.role))

    return AuthContext(
        principal=principal,
        user=user,
        membership=membership,
        role=role,
        permissions=resolve_permissions(role),
    )


def require_roles(*allowed_roles: AuthRole) -> Callable[[AuthContext], AuthContext]:
    def dependency(
        auth_context: Annotated[AuthContext, Depends(get_auth_context)],
    ) -> AuthContext:
        if auth_context.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )

        return auth_context

    return dependency


def resolve_permissions(role: AuthRole) -> tuple[str, ...]:
    permission_map: dict[AuthRole, tuple[str, ...]] = {
        AuthRole.OWNER: (
            "organization:manage",
            "members:manage",
            "billing:manage",
            "projects:manage",
            "projects:read",
        ),
        AuthRole.ADMIN: (
            "members:manage",
            "billing:read",
            "projects:manage",
            "projects:read",
        ),
        AuthRole.EDITOR: ("projects:manage", "projects:read"),
        AuthRole.VIEWER: ("projects:read",),
        AuthRole.CLIENT: ("projects:read", "comments:create"),
        AuthRole.CONTRACTOR: ("projects:read", "boq:read"),
    }

    return permission_map[role]


def organization_id_from_context(auth_context: AuthContext) -> UUID:
    return auth_context.membership.organization_id
