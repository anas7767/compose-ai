from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
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


class AIProviderName(StrEnum):
    MOCK = "mock"
    GEMINI = "gemini"
    OPENAI = "openai"


class AIProviderHealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class AIThreadStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class AIMessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM_INTERNAL = "system_internal"
    TOOL_INTERNAL = "tool_internal"


class AIMessageMode(StrEnum):
    ADVICE = "advice"
    PROPOSAL = "proposal"


class AIMessageStatus(StrEnum):
    PENDING = "pending"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"


class AIRunType(StrEnum):
    ARCHITECT_CHAT = "architect_chat"
    ARCHITECT_BRIEF = "architect_brief"
    REQUIREMENT_NORMALIZATION = "requirement_normalization"


class AIRunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AIBriefStatus(StrEnum):
    GENERATING = "generating"
    PROPOSED = "proposed"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    APPLIED = "applied"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    FAILED = "failed"


class AIProposalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    STALE = "stale"


class AIProposalTarget(StrEnum):
    PROJECT_FIELD = "project_field"
    REQUIREMENTS_FIELD = "requirements_field"
    ROOM_REQUIREMENTS = "room_requirements"
    PLOT_RECOMMENDATION = "plot_recommendation"


class AIPromptStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    RETIRED = "retired"


class AIJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AIChatThread(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "ai_chat_threads"
    __table_args__ = (
        CheckConstraint("version > 0", name="version_positive"),
        Index(
            "ix_ai_chat_threads_project_status_activity",
            "project_id",
            "status",
            "last_message_at",
            "id",
            postgresql_where=text("deleted_at is null"),
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=AIThreadStatus.ACTIVE, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AIPromptTemplate(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_prompt_templates"
    __table_args__ = (
        UniqueConstraint("prompt_key", "version", name="uq_ai_prompt_templates_key_version"),
        Index("ix_ai_prompt_templates_key_status", "prompt_key", "status"),
        CheckConstraint("version > 0", name="version_positive"),
    )

    prompt_key: Mapped[str] = mapped_column(String(80), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    task_type: Mapped[str] = mapped_column(String(48), nullable=False)
    system_template: Mapped[str] = mapped_column(Text, nullable=False)
    input_template: Mapped[str] = mapped_column(Text, nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    safety_policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=AIPromptStatus.DRAFT, index=True
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class AIProjectMemoryVersion(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "ai_project_memory_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_ai_memory_project_version"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint("project_version > 0", name="project_version_positive"),
        CheckConstraint("token_estimate >= 0", name="token_estimate_non_negative"),
        Index("ix_ai_memory_project_created", "project_id", "created_at", "id"),
        Index("ix_ai_memory_project_hash", "project_id", "context_hash"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    project_version: Mapped[int] = mapped_column(Integer, nullable=False)
    plot_profile_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
    boundary_version_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("plot_boundary_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    analysis_snapshot_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("plot_analysis_snapshots.id", ondelete="SET NULL"),
        nullable=True,
    )
    requirements_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    context_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    context_summary: Mapped[str] = mapped_column(Text, nullable=False)
    included_sources: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    redaction_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    supersedes_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ai_project_memory_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AIRun(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "ai_runs"
    __table_args__ = (
        CheckConstraint("attempt_count >= 0", name="attempt_count_non_negative"),
        CheckConstraint("estimated_input_tokens >= 0", name="estimated_input_tokens_non_negative"),
        CheckConstraint(
            "estimated_output_tokens >= 0", name="estimated_output_tokens_non_negative"
        ),
        CheckConstraint("input_tokens >= 0", name="input_tokens_non_negative"),
        CheckConstraint("output_tokens >= 0", name="output_tokens_non_negative"),
        CheckConstraint("estimated_cost_microusd >= 0", name="estimated_cost_non_negative"),
        CheckConstraint("actual_cost_microusd >= 0", name="actual_cost_non_negative"),
        Index("ix_ai_runs_project_created", "project_id", "created_at", "id"),
        Index("ix_ai_runs_org_status_created", "organization_id", "status", "created_at"),
        Index("ix_ai_runs_org_actor_created", "organization_id", "created_by", "created_at"),
        Index("ix_ai_runs_cache_key", "organization_id", "cache_key"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ai_chat_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    run_type: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=AIRunStatus.QUEUED, index=True
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    model_alias: Mapped[str] = mapped_column(String(48), nullable=False)
    prompt_template_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ai_prompt_templates.id", ondelete="RESTRICT"),
        nullable=False,
    )
    memory_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ai_project_memory_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    cache_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    estimated_input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_microusd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cached_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    actual_cost_microusd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_hit: Mapped[bool] = mapped_column(nullable=False, default=False)
    cache_source_run_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ai_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    attempt_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    safety_flags: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_details_redacted: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AIChatMessage(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "ai_chat_messages"
    __table_args__ = (
        UniqueConstraint("thread_id", "sequence_number", name="uq_ai_messages_thread_sequence"),
        UniqueConstraint("thread_id", "client_message_id", name="uq_ai_messages_thread_client_id"),
        CheckConstraint("sequence_number > 0", name="sequence_positive"),
        CheckConstraint("token_count >= 0", name="token_count_non_negative"),
        Index("ix_ai_messages_thread_sequence", "thread_id", "sequence_number"),
        Index("ix_ai_messages_project_created", "project_id", "created_at", "id"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    thread_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ai_chat_threads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ai_run_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ai_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(24), nullable=False)
    mode: Mapped[str] = mapped_column(String(24), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    original_content: Mapped[str] = mapped_column(Text, nullable=False)
    display_content: Mapped[str] = mapped_column(Text, nullable=False)
    content_format: Mapped[str] = mapped_column(String(24), nullable=False, default="text")
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    client_message_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )


class AIRunEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "ai_run_events"
    __table_args__ = (
        UniqueConstraint("ai_run_id", "event_sequence", name="uq_ai_run_events_run_sequence"),
        CheckConstraint("event_sequence > 0", name="event_sequence_positive"),
        Index("ix_ai_run_events_run_sequence", "ai_run_id", "event_sequence"),
    )

    ai_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ai_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AIArchitectBriefVersion(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "ai_architect_brief_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_ai_briefs_project_version"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint(
            "aggregate_confidence >= 0 and aggregate_confidence <= 1",
            name="aggregate_confidence_range",
        ),
        Index("ix_ai_briefs_project_created", "project_id", "created_at", "id"),
        Index("ix_ai_briefs_project_status", "project_id", "status"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ai_runs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    memory_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ai_project_memory_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    original_input: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    goals: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    priorities: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    constraints: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    normalized_requirements: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    missing_information: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    conflicts: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    clarification_questions: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    recommended_next_steps: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    assumptions: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    aggregate_confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    based_on_project_version: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ai_architect_brief_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AIRequirementProposal(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "ai_requirement_proposals"
    __table_args__ = (
        CheckConstraint("confidence >= 0 and confidence <= 1", name="confidence_range"),
        CheckConstraint("length(explanation) > 0", name="explanation_required"),
        Index("ix_ai_proposals_brief_status", "brief_version_id", "status", "id"),
        Index("ix_ai_proposals_project_status", "project_id", "status"),
    )

    brief_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("ai_architect_brief_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_path: Mapped[str] = mapped_column(String(255), nullable=False)
    existing_value: Mapped[Any | None] = mapped_column(JSONB, nullable=True)
    proposed_value: Mapped[Any] = mapped_column(JSONB, nullable=False)
    source_references: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    explanation: Mapped[str] = mapped_column(String(1000), nullable=False)
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=AIProposalStatus.PENDING, index=True
    )
    expected_project_version: Mapped[int] = mapped_column(Integer, nullable=False)
    reviewed_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AIResponseCache(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "ai_response_cache"
    __table_args__ = (
        UniqueConstraint("organization_id", "cache_key", name="uq_ai_cache_org_key"),
        CheckConstraint("hit_count >= 0", name="hit_count_non_negative"),
        Index("ix_ai_response_cache_expires", "expires_at"),
    )

    cache_key: Mapped[str] = mapped_column(String(64), nullable=False)
    run_type: Mapped[str] = mapped_column(String(48), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    safety_policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    response_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    source_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("ai_runs.id", ondelete="CASCADE"), nullable=False
    )
    hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AIProviderHealth(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_provider_health"
    __table_args__ = (
        UniqueConstraint(
            "provider", "model", "environment", name="uq_ai_provider_health_provider_model_env"
        ),
        CheckConstraint("consecutive_failures >= 0", name="consecutive_failures_non_negative"),
        Index("ix_ai_provider_health_status", "status", "degraded_until"),
    )

    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    environment: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=AIProviderHealthStatus.HEALTHY
    )
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    degraded_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class AIJob(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "ai_jobs"
    __table_args__ = (
        UniqueConstraint("ai_run_id", name="uq_ai_jobs_run"),
        CheckConstraint("attempt_count >= 0", name="attempt_count_non_negative"),
        Index("ix_ai_jobs_claim", "status", "available_at", "priority", "created_at"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    ai_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("ai_runs.id", ondelete="CASCADE"), nullable=False
    )
    job_type: Mapped[str] = mapped_column(String(48), nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=AIJobStatus.QUEUED, index=True
    )
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=100)
    attempt_count: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class AIUsageDaily(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "ai_usage_daily"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            "usage_date",
            "provider",
            "model",
            name="uq_ai_usage_daily_dimensions",
        ),
        CheckConstraint("input_tokens >= 0", name="input_tokens_non_negative"),
        CheckConstraint("output_tokens >= 0", name="output_tokens_non_negative"),
        CheckConstraint("cost_microusd >= 0", name="cost_non_negative"),
        Index("ix_ai_usage_daily_org_date", "organization_id", "usage_date"),
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    input_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    cost_microusd: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cache_hit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
