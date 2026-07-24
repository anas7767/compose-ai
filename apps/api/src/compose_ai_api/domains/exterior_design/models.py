from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from compose_ai_api.models.base import Base
from compose_ai_api.models.mixins import (
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class ExteriorDesignRunStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    PARTIALLY_SUCCEEDED = "partially_succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RATE_LIMITED = "rate_limited"
    TIMED_OUT = "timed_out"


class ExteriorDesignOptionStatus(StrEnum):
    GENERATED = "generated"
    VALID = "valid"
    INVALID = "invalid"
    APPROVED = "approved"
    REJECTED = "rejected"
    HIDDEN = "hidden"


class ExteriorDesignApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ExteriorDesignViewType(StrEnum):
    FRONT = "front"
    LEFT = "left"
    RIGHT = "right"
    REAR = "rear"


class ExteriorDesignStyle(StrEnum):
    MODERN = "modern"
    CONTEMPORARY = "contemporary"
    MINIMAL = "minimal"
    TRADITIONAL = "traditional"
    TROPICAL = "tropical"
    COLONIAL = "colonial"
    INDUSTRIAL = "industrial"


class ExteriorDesignContextSnapshot(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "exterior_design_context_snapshots"
    __table_args__ = (
        UniqueConstraint("organization_id", "context_hash", name="uq_exterior_context_hash"),
        Index("ix_exterior_context_project_created", "project_id", "created_at", "id"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_design_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_design_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_scene_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("building_scene_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_editor_checkpoint_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_editor_checkpoints.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_brief_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ai_architect_brief_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_versions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class ExteriorDesignRun(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "exterior_design_runs"
    __table_args__ = (
        CheckConstraint(
            "requested_option_count between 1 and 4", name="exterior_run_option_count_range"
        ),
        CheckConstraint("completed_option_count >= 0", name="exterior_run_completed_non_negative"),
        CheckConstraint("input_tokens >= 0", name="exterior_run_input_tokens_non_negative"),
        CheckConstraint("output_tokens >= 0", name="exterior_run_output_tokens_non_negative"),
        CheckConstraint("cost_microusd >= 0", name="exterior_run_cost_non_negative"),
        UniqueConstraint(
            "organization_id",
            "created_by",
            "idempotency_key",
            name="uq_exterior_runs_org_actor_idempotency",
        ),
        Index("ix_exterior_runs_project_created", "project_id", "created_at", "id"),
        Index("ix_exterior_runs_org_status_created", "organization_id", "status", "created_at"),
        Index("ix_exterior_runs_cache", "organization_id", "cache_key"),
        Index("ix_exterior_runs_context", "organization_id", "context_hash"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    context_snapshot_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("exterior_design_context_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_design_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_design_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_scene_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("building_scene_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_editor_checkpoint_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_editor_checkpoints.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=ExteriorDesignRunStatus.QUEUED, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    requested_option_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    completed_option_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    style: Mapped[str] = mapped_column(String(40), nullable=False)
    view_type: Mapped[str] = mapped_column(String(24), nullable=False)
    material_preferences: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    user_instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    negative_constraints: Mapped[str | None] = mapped_column(Text, nullable=True)
    seed: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    cache_key: Mapped[str] = mapped_column(String(64), nullable=False)
    cache_hit: Mapped[bool] = mapped_column(nullable=False, default=False)
    cache_source_run_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("exterior_design_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    sanitized_prompt: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    safe_failure_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_microusd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    created_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExteriorDesignOption(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "exterior_design_options"
    __table_args__ = (
        UniqueConstraint("run_id", "option_number", name="uq_exterior_options_run_number"),
        CheckConstraint("option_number between 1 and 4", name="exterior_option_number_range"),
        Index("ix_exterior_options_project_created", "project_id", "created_at", "id"),
        Index("ix_exterior_options_run_status", "run_id", "status", "option_number"),
        Index(
            "ix_exterior_options_active_approved",
            "project_id",
            "approval_status",
            postgresql_where=text("deleted_at is null"),
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("exterior_design_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    context_snapshot_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("exterior_design_context_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_design_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_design_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_scene_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("building_scene_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_editor_checkpoint_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_editor_checkpoints.id", ondelete="RESTRICT"),
        nullable=False,
    )
    option_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    style: Mapped[str] = mapped_column(String(40), nullable=False)
    view_type: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=ExteriorDesignOptionStatus.GENERATED
    )
    approval_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=ExteriorDesignApprovalStatus.PENDING
    )
    is_conceptual: Mapped[bool] = mapped_column(nullable=False, default=True)
    disclaimer: Mapped[str] = mapped_column(String(160), nullable=False)
    safety_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_versions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    approved_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)


class ExteriorDesignAsset(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "exterior_design_assets"
    __table_args__ = (
        UniqueConstraint("storage_provider", "storage_key", name="uq_exterior_assets_storage_key"),
        Index("ix_exterior_assets_option_created", "option_id", "created_at", "id"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    option_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("exterior_design_options.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    storage_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    thumbnail_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    mime_type: Mapped[str] = mapped_column(String(80), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    integrity_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_asset_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    delivery_reference: Mapped[str] = mapped_column(String(1200), nullable=False)


class ExteriorDesignValidationResult(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "exterior_design_validation_results"
    __table_args__ = (UniqueConstraint("option_id", name="uq_exterior_validation_option"),)

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    option_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("exterior_design_options.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    validation_engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ExteriorDesignEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "exterior_design_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_exterior_events_run_sequence"),
        CheckConstraint("sequence > 0", name="exterior_event_sequence_positive"),
        Index("ix_exterior_events_run_sequence", "run_id", "sequence"),
    )

    run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("exterior_design_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
