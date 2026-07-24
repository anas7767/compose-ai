from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class AuthBootstrapRequest(CamelModel):
    email: EmailStr | None = None
    name: str = Field(min_length=1, max_length=160)
    avatar_url: str | None = Field(default=None, max_length=2048)
    active_clerk_organization_id: str | None = Field(default=None, max_length=255)
    active_organization_name: str | None = Field(default=None, max_length=160)
    active_organization_slug: str | None = Field(default=None, max_length=180)
    active_organization_role: str | None = Field(default=None, max_length=80)


class AuthUserResponse(CamelModel):
    id: UUID
    clerk_user_id: str
    email: str | None
    name: str
    avatar_url: str | None
    status: str
    last_login_at: datetime


class AuthOrganizationResponse(CamelModel):
    id: UUID
    clerk_organization_id: str | None
    name: str
    slug: str
    type: str
    plan_status: str


class AuthMembershipResponse(CamelModel):
    id: UUID
    role: str
    status: str


class AuthSubscriptionResponse(CamelModel):
    id: UUID
    plan_code: str
    status: str
    project_limit: int
    ai_credit_limit: int
    render_limit: int
    storage_limit_mb: int


class AuthContextResponse(CamelModel):
    user: AuthUserResponse
    organization: AuthOrganizationResponse
    membership: AuthMembershipResponse
    subscription: AuthSubscriptionResponse
    permissions: list[str]


class AuthSessionResponse(CamelModel):
    clerk_user_id: str
    clerk_session_id: str | None
    clerk_organization_id: str | None
    clerk_organization_role: str | None
    expires_at: int | None
    issued_at: int | None
