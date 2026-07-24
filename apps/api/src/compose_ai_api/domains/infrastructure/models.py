from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, Index, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from compose_ai_api.models.base import Base
from compose_ai_api.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class WorkerKind(StrEnum):
    AI_ARCHITECT = "ai_architect"
    FLOOR_PLAN = "floor_plan"


class WorkerStatus(StrEnum):
    RUNNING = "running"
    DRAINING = "draining"


class WorkerHeartbeat(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "worker_heartbeats"
    __table_args__ = (
        CheckConstraint("heartbeat_interval_seconds > 0", name="heartbeat_interval_positive"),
        UniqueConstraint("worker_kind", "worker_id", name="uq_worker_heartbeats_kind_id"),
        Index("ix_worker_heartbeats_kind_seen", "worker_kind", "last_seen_at"),
    )

    worker_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    worker_id: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    heartbeat_interval_seconds: Mapped[int] = mapped_column(nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
