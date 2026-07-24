from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from compose_ai_api.models.base import Base
from compose_ai_api.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from compose_ai_api.domains.billing.models import Subscription


class UserStatus(StrEnum):
    ACTIVE = "active"
    DISABLED = "disabled"


class OrganizationType(StrEnum):
    PERSONAL = "personal"
    HOMEOWNER = "homeowner"
    STUDIO = "studio"
    BUILDER = "builder"
    ENTERPRISE = "enterprise"


class OrganizationPlanStatus(StrEnum):
    FREE = "free"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"


class OrganizationRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"
    CLIENT = "client"
    CONTRACTOR = "contractor"


class OrganizationMemberStatus(StrEnum):
    INVITED = "invited"
    ACTIVE = "active"
    DISABLED = "disabled"


class User(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "users"

    clerk_user_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    locale: Mapped[str | None] = mapped_column(String(24), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[UserStatus] = mapped_column(
        String(32),
        nullable=False,
        default=UserStatus.ACTIVE,
        index=True,
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    memberships: Mapped[list[OrganizationMember]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    personal_organizations: Mapped[list[Organization]] = relationship(
        back_populates="personal_owner",
        foreign_keys="Organization.personal_owner_user_id",
    )


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "organizations"

    clerk_organization_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )
    personal_owner_user_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    slug: Mapped[str] = mapped_column(String(180), nullable=False, unique=True, index=True)
    type: Mapped[OrganizationType] = mapped_column(
        String(32),
        nullable=False,
        default=OrganizationType.PERSONAL,
    )
    billing_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    default_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    plan_status: Mapped[OrganizationPlanStatus] = mapped_column(
        String(32),
        nullable=False,
        default=OrganizationPlanStatus.FREE,
        index=True,
    )

    personal_owner: Mapped[User | None] = relationship(
        back_populates="personal_organizations",
        foreign_keys=[personal_owner_user_id],
    )
    memberships: Mapped[list[OrganizationMember]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    subscriptions: Mapped[list[Subscription]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )


class OrganizationMember(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "organization_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_organization_members_org_user"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[OrganizationRole] = mapped_column(
        String(32),
        nullable=False,
        default=OrganizationRole.OWNER,
        index=True,
    )
    status: Mapped[OrganizationMemberStatus] = mapped_column(
        String(32),
        nullable=False,
        default=OrganizationMemberStatus.ACTIVE,
        index=True,
    )
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped[Organization] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")
