from __future__ import annotations

from datetime import datetime
from decimal import Decimal
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
    Numeric,
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


class FloorPlanRunStatus(StrEnum):
    QUEUED = "queued"
    PREFLIGHTING = "preflighting"
    BUILDING_CONTEXT = "building_context"
    GENERATING = "generating"
    SOLVING = "solving"
    VALIDATING = "validating"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FloorPlanJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FloorPlanOptionStatus(StrEnum):
    GENERATING = "generating"
    VALIDATING = "validating"
    VALID = "valid"
    INVALID = "invalid"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class FloorPlanValidationStatus(StrEnum):
    VALID = "valid"
    INVALID = "invalid"


class FloorPlanGenerationRun(
    UUIDPrimaryKeyMixin,
    TenantMixin,
    TimestampMixin,
    SoftDeleteMixin,
    Base,
):
    __tablename__ = "floor_plan_generation_runs"
    __table_args__ = (
        CheckConstraint("requested_option_count between 3 and 5", name="option_count_range"),
        CheckConstraint("completed_option_count >= 0", name="completed_count_non_negative"),
        CheckConstraint("deterministic_seed >= 0", name="seed_non_negative"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint("max_solver_attempts between 1 and 100", name="solver_budget_range"),
        CheckConstraint("max_provider_retries between 0 and 10", name="provider_budget_range"),
        CheckConstraint("max_processing_seconds between 10 and 1800", name="time_budget_range"),
        CheckConstraint("max_invalid_candidates between 1 and 100", name="invalid_budget_range"),
        CheckConstraint("solver_attempt_count >= 0", name="solver_attempts_non_negative"),
        CheckConstraint("provider_retry_count >= 0", name="provider_retries_non_negative"),
        CheckConstraint("invalid_candidate_count >= 0", name="invalid_count_non_negative"),
        CheckConstraint("estimated_input_tokens >= 0", name="estimated_input_non_negative"),
        CheckConstraint("estimated_output_tokens >= 0", name="estimated_output_non_negative"),
        CheckConstraint("estimated_cost_microusd >= 0", name="estimated_cost_non_negative"),
        CheckConstraint("input_tokens >= 0", name="input_tokens_non_negative"),
        CheckConstraint("output_tokens >= 0", name="output_tokens_non_negative"),
        CheckConstraint("actual_cost_microusd >= 0", name="actual_cost_non_negative"),
        CheckConstraint(
            "diversity_threshold >= 0 and diversity_threshold <= 1",
            name="diversity_threshold_range",
        ),
        UniqueConstraint(
            "organization_id",
            "created_by",
            "idempotency_key",
            name="uq_floor_plan_runs_org_actor_idempotency",
        ),
        Index("ix_floor_plan_runs_project_created", "project_id", "created_at", "id"),
        Index("ix_floor_plan_runs_org_status_created", "organization_id", "status", "created_at"),
        Index("ix_floor_plan_runs_cache", "organization_id", "cache_key"),
        Index(
            "ix_floor_plan_runs_project_active",
            "project_id",
            "status",
            postgresql_where=text("deleted_at is null"),
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_brief_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ai_architect_brief_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    memory_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ai_project_memory_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    boundary_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("plot_boundary_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    analysis_snapshot_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("plot_analysis_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=FloorPlanRunStatus.QUEUED, index=True
    )
    requested_option_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    completed_option_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    deterministic_seed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_versions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    solver_version: Mapped[str] = mapped_column(String(120), nullable=False)
    geometry_engine_version: Mapped[str] = mapped_column(String(160), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    cache_key: Mapped[str] = mapped_column(String(64), nullable=False)
    cache_hit: Mapped[bool] = mapped_column(nullable=False, default=False)
    cache_source_run_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_generation_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    diversity_threshold: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    max_solver_attempts: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    max_provider_retries: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    max_processing_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    max_invalid_candidates: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    solver_attempt_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    provider_retry_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    invalid_candidate_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    estimated_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_microusd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actual_cost_microusd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FloorPlanGenerationJob(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "floor_plan_generation_jobs"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_floor_plan_jobs_run"),
        CheckConstraint("attempt_count >= 0", name="attempt_count_non_negative"),
        Index("ix_floor_plan_jobs_claim", "status", "available_at", "priority", "created_at"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_generation_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=FloorPlanJobStatus.QUEUED, index=True
    )
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=100)
    attempt_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class FloorPlanGenerationEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "floor_plan_generation_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_floor_plan_events_run_sequence"),
        CheckConstraint("sequence > 0", name="sequence_positive"),
        Index("ix_floor_plan_events_run_sequence", "run_id", "sequence"),
    )

    run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_generation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FloorPlanOption(
    UUIDPrimaryKeyMixin,
    TenantMixin,
    TimestampMixin,
    SoftDeleteMixin,
    Base,
):
    __tablename__ = "floor_plan_options"
    __table_args__ = (
        UniqueConstraint("run_id", "option_number", name="uq_floor_plan_options_run_number"),
        CheckConstraint("option_number between 1 and 5", name="option_number_range"),
        CheckConstraint("deterministic_seed >= 0", name="seed_non_negative"),
        CheckConstraint("confidence >= 0 and confidence <= 1", name="confidence_range"),
        CheckConstraint("diversity_score >= 0 and diversity_score <= 1", name="diversity_range"),
        CheckConstraint("version > 0", name="version_positive"),
        Index("ix_floor_plan_options_run_status", "run_id", "status", "option_number"),
        Index("ix_floor_plan_options_project_created", "project_id", "created_at", "id"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_generation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    option_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    deterministic_seed: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    provider_program: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    major_decisions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    constraint_trace: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    area_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    topology_signature: Mapped[str] = mapped_column(String(64), nullable=False)
    topology_features: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    diversity_score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    solver_attempt: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rejection_reason: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    rejected_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FloorPlanGeometrySnapshot(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "floor_plan_geometry_snapshots"
    __table_args__ = (
        UniqueConstraint("option_id", name="uq_floor_plan_geometry_option"),
        CheckConstraint("gross_area_m2 > 0", name="gross_area_positive"),
        Index("ix_floor_plan_geometry_project_created", "project_id", "created_at", "id"),
        Index("ix_floor_plan_geometry_hash", "geometry_hash"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    option_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_options.id", ondelete="CASCADE"),
        nullable=False,
    )
    coordinate_space: Mapped[str] = mapped_column(String(32), nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    geometry_engine_version: Mapped[str] = mapped_column(String(160), nullable=False)
    geometry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    geometry: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    bounding_box: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    gross_area_m2: Mapped[Decimal] = mapped_column(Numeric(16, 3), nullable=False)
    source_versions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FloorPlanValidationResult(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "floor_plan_validation_results"
    __table_args__ = (
        UniqueConstraint("option_id", name="uq_floor_plan_validation_option"),
        Index("ix_floor_plan_validation_project_created", "project_id", "created_at", "id"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    option_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_options.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    validation_engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    geometry_engine_version: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    errors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class FloorPlanDesignVersion(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "floor_plan_design_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_floor_plan_design_project_version"),
        CheckConstraint("version > 0", name="version_positive"),
        Index("ix_floor_plan_design_project_created", "project_id", "created_at", "id"),
        Index(
            "ix_floor_plan_design_project_active",
            "project_id",
            "version",
            postgresql_where=text("deleted_at is null"),
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_generation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_option_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_options.id", ondelete="RESTRICT"),
        nullable=False,
    )
    geometry_snapshot_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_geometry_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    validation_result_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_validation_results.id", ondelete="RESTRICT"),
        nullable=False,
    )
    restored_from_design_version_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_design_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    geometry_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_versions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    engine_versions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    version_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    source_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    source_model: Mapped[str] = mapped_column(String(120), nullable=False)
    generation_cost_microusd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    generation_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    disclaimer: Mapped[str] = mapped_column(String(160), nullable=False)
    accepted_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
