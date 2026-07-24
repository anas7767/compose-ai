from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from compose_ai_api.models.base import Base
from compose_ai_api.models.mixins import SoftDeleteMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from compose_ai_api.domains.identity.models import Organization


class SubscriptionProvider(StrEnum):
    INTERNAL = "internal"
    STRIPE = "stripe"
    RAZORPAY = "razorpay"


class SubscriptionStatus(StrEnum):
    FREE = "free"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELLED = "cancelled"


class Plan(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "plans"

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    monthly_price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    yearly_price_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    project_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ai_credit_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=25)
    render_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    storage_limit_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=250)
    features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    subscriptions: Mapped[list[Subscription]] = relationship(back_populates="plan")


class Subscription(UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index(
            "uq_subscriptions_organization_active",
            "organization_id",
            unique=True,
            postgresql_where=text(
                "status in ('free', 'trialing', 'active') and deleted_at is null"
            ),
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
    )
    provider: Mapped[SubscriptionProvider] = mapped_column(
        String(32),
        nullable=False,
        default=SubscriptionProvider.INTERNAL,
    )
    provider_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[SubscriptionStatus] = mapped_column(
        String(32),
        nullable=False,
        default=SubscriptionStatus.FREE,
        index=True,
    )
    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancel_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tax_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    usage_balance: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False, default=0)

    organization: Mapped[Organization] = relationship(back_populates="subscriptions")
    plan: Mapped[Plan] = relationship(back_populates="subscriptions")
