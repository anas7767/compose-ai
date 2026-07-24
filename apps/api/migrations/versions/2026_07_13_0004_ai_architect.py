"""ai architect brief and requirement normalization

Revision ID: 202607130004
Revises: 202607120003
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202607130004"
down_revision: str | None = "202607120003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _updated_at() -> sa.Column:
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
    )


def _organization_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["organization_id"],
        ["organizations.id"],
        name=op.f(f"fk_{table}_organization_id_organizations"),
        ondelete="RESTRICT",
    )


def _user_fk(table: str, column: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column],
        ["users.id"],
        name=op.f(f"fk_{table}_{column}_users"),
        ondelete="SET NULL",
    )


def _project_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["project_id"],
        ["projects.id"],
        name=op.f(f"fk_{table}_project_id_projects"),
        ondelete="CASCADE",
    )


def upgrade() -> None:
    _create_threads()
    _create_prompt_templates()
    _create_memory_versions()
    _create_runs()
    _create_messages()
    _create_run_events()
    _create_brief_versions()
    _create_proposals()
    _create_response_cache()
    _create_provider_health()
    _create_jobs()
    _create_usage_daily()


def _create_threads() -> None:
    table = "ai_chat_threads"
    op.create_table(
        table,
        _uuid("project_id"),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        _uuid("created_by", nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        _uuid("organization_id"),
        _uuid("id"),
        _created_at(),
        _updated_at(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version > 0", name=op.f("ck_ai_chat_threads_version_positive")),
        _organization_fk(table),
        _project_fk(table),
        _user_fk(table, "created_by"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_chat_threads")),
    )
    _index("ix_ai_chat_threads_organization_id", table, "organization_id")
    _index("ix_ai_chat_threads_project_id", table, "project_id")
    _index("ix_ai_chat_threads_status", table, "status")
    op.create_index(
        "ix_ai_chat_threads_project_status_activity",
        table,
        ["project_id", "status", "last_message_at", "id"],
        unique=False,
        postgresql_where=sa.text("deleted_at is null"),
    )


def _create_prompt_templates() -> None:
    table = "ai_prompt_templates"
    op.create_table(
        table,
        sa.Column("prompt_key", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("task_type", sa.String(length=48), nullable=False),
        sa.Column("system_template", sa.Text(), nullable=False),
        sa.Column("input_template", sa.Text(), nullable=False),
        sa.Column("output_schema_version", sa.String(length=32), nullable=False),
        sa.Column("safety_policy_version", sa.String(length=32), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        _uuid("created_by", nullable=True),
        _uuid("id"),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint("version > 0", name=op.f("ck_ai_prompt_templates_version_positive")),
        _user_fk(table, "created_by"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_prompt_templates")),
        sa.UniqueConstraint("prompt_key", "version", name="uq_ai_prompt_templates_key_version"),
    )
    _index("ix_ai_prompt_templates_status", table, "status")
    op.create_index(
        "ix_ai_prompt_templates_key_status", table, ["prompt_key", "status"], unique=False
    )


def _create_memory_versions() -> None:
    table = "ai_project_memory_versions"
    op.create_table(
        table,
        _uuid("project_id"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("project_version", sa.Integer(), nullable=False),
        sa.Column("plot_profile_revision", sa.Integer(), nullable=True),
        _uuid("boundary_version_id", nullable=True),
        _uuid("analysis_snapshot_id", nullable=True),
        sa.Column("requirements_hash", sa.String(length=64), nullable=False),
        sa.Column("context_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("context_summary", sa.Text(), nullable=False),
        sa.Column("included_sources", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("redaction_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("token_estimate", sa.Integer(), nullable=False),
        sa.Column("context_hash", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        _uuid("supersedes_id", nullable=True),
        _uuid("created_by", nullable=True),
        _created_at(),
        _uuid("organization_id"),
        _uuid("id"),
        sa.CheckConstraint(
            "project_version > 0",
            name=op.f("ck_ai_project_memory_versions_project_version_positive"),
        ),
        sa.CheckConstraint(
            "token_estimate >= 0",
            name=op.f("ck_ai_project_memory_versions_token_estimate_non_negative"),
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_ai_project_memory_versions_version_positive")
        ),
        _organization_fk(table),
        _project_fk(table),
        _user_fk(table, "created_by"),
        sa.ForeignKeyConstraint(
            ["boundary_version_id"],
            ["plot_boundary_versions.id"],
            name=op.f("fk_ai_project_memory_versions_boundary_version_id_plot_boundary_versions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_snapshot_id"],
            ["plot_analysis_snapshots.id"],
            name=op.f("fk_ai_project_memory_versions_analysis_snapshot_id_plot_analysis_snapshots"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["ai_project_memory_versions.id"],
            name=op.f("fk_ai_project_memory_versions_supersedes_id_ai_project_memory_versions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_project_memory_versions")),
        sa.UniqueConstraint("project_id", "version", name="uq_ai_memory_project_version"),
    )
    _index("ix_ai_project_memory_versions_organization_id", table, "organization_id")
    _index("ix_ai_project_memory_versions_project_id", table, "project_id")
    op.create_index(
        "ix_ai_memory_project_created", table, ["project_id", "created_at", "id"], unique=False
    )
    op.create_index(
        "ix_ai_memory_project_hash", table, ["project_id", "context_hash"], unique=False
    )


def _create_runs() -> None:
    table = "ai_runs"
    op.create_table(
        table,
        _uuid("project_id"),
        _uuid("thread_id", nullable=True),
        sa.Column("run_type", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("model_alias", sa.String(length=48), nullable=False),
        _uuid("prompt_template_id"),
        _uuid("memory_version_id"),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("context_hash", sa.String(length=64), nullable=False),
        sa.Column("cache_key", sa.String(length=64), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_output_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_microusd", sa.BigInteger(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cached_tokens", sa.Integer(), nullable=False),
        sa.Column("actual_cost_microusd", sa.BigInteger(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        _uuid("cache_source_run_id", nullable=True),
        sa.Column("attempt_count", sa.SmallInteger(), nullable=False),
        sa.Column("safety_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column(
            "failure_details_redacted", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
        _uuid("created_by", nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        _uuid("organization_id"),
        _uuid("id"),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "actual_cost_microusd >= 0", name=op.f("ck_ai_runs_actual_cost_non_negative")
        ),
        sa.CheckConstraint(
            "attempt_count >= 0", name=op.f("ck_ai_runs_attempt_count_non_negative")
        ),
        sa.CheckConstraint(
            "estimated_cost_microusd >= 0",
            name=op.f("ck_ai_runs_estimated_cost_non_negative"),
        ),
        sa.CheckConstraint(
            "estimated_input_tokens >= 0",
            name=op.f("ck_ai_runs_estimated_input_tokens_non_negative"),
        ),
        sa.CheckConstraint(
            "estimated_output_tokens >= 0",
            name=op.f("ck_ai_runs_estimated_output_tokens_non_negative"),
        ),
        sa.CheckConstraint("input_tokens >= 0", name=op.f("ck_ai_runs_input_tokens_non_negative")),
        sa.CheckConstraint(
            "output_tokens >= 0", name=op.f("ck_ai_runs_output_tokens_non_negative")
        ),
        _organization_fk(table),
        _project_fk(table),
        _user_fk(table, "created_by"),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["ai_chat_threads.id"],
            name=op.f("fk_ai_runs_thread_id_ai_chat_threads"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["prompt_template_id"],
            ["ai_prompt_templates.id"],
            name=op.f("fk_ai_runs_prompt_template_id_ai_prompt_templates"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_version_id"],
            ["ai_project_memory_versions.id"],
            name=op.f("fk_ai_runs_memory_version_id_ai_project_memory_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cache_source_run_id"],
            ["ai_runs.id"],
            name=op.f("fk_ai_runs_cache_source_run_id_ai_runs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_runs")),
    )
    for column in ("organization_id", "project_id", "thread_id", "run_type", "status"):
        _index(f"ix_ai_runs_{column}", table, column)
    op.create_index(
        "ix_ai_runs_project_created", table, ["project_id", "created_at", "id"], unique=False
    )
    op.create_index(
        "ix_ai_runs_org_status_created",
        table,
        ["organization_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_ai_runs_org_actor_created",
        table,
        ["organization_id", "created_by", "created_at"],
        unique=False,
    )
    op.create_index("ix_ai_runs_cache_key", table, ["organization_id", "cache_key"], unique=False)


def _create_messages() -> None:
    table = "ai_chat_messages"
    op.create_table(
        table,
        _uuid("project_id"),
        _uuid("thread_id"),
        _uuid("ai_run_id", nullable=True),
        sa.Column("role", sa.String(length=24), nullable=False),
        sa.Column("mode", sa.String(length=24), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("original_content", sa.Text(), nullable=False),
        sa.Column("display_content", sa.Text(), nullable=False),
        sa.Column("content_format", sa.String(length=24), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("client_message_id", sa.String(length=80), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False),
        _uuid("created_by", nullable=True),
        _uuid("organization_id"),
        _uuid("id"),
        _created_at(),
        _updated_at(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "sequence_number > 0", name=op.f("ck_ai_chat_messages_sequence_positive")
        ),
        sa.CheckConstraint(
            "token_count >= 0", name=op.f("ck_ai_chat_messages_token_count_non_negative")
        ),
        _organization_fk(table),
        _project_fk(table),
        _user_fk(table, "created_by"),
        sa.ForeignKeyConstraint(
            ["thread_id"],
            ["ai_chat_threads.id"],
            name=op.f("fk_ai_chat_messages_thread_id_ai_chat_threads"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["ai_run_id"],
            ["ai_runs.id"],
            name=op.f("fk_ai_chat_messages_ai_run_id_ai_runs"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_chat_messages")),
        sa.UniqueConstraint(
            "thread_id", "client_message_id", name="uq_ai_messages_thread_client_id"
        ),
        sa.UniqueConstraint("thread_id", "sequence_number", name="uq_ai_messages_thread_sequence"),
    )
    for column in ("organization_id", "project_id", "thread_id", "ai_run_id"):
        _index(f"ix_ai_chat_messages_{column}", table, column)
    op.create_index(
        "ix_ai_messages_thread_sequence", table, ["thread_id", "sequence_number"], unique=False
    )
    op.create_index(
        "ix_ai_messages_project_created", table, ["project_id", "created_at", "id"], unique=False
    )


def _create_run_events() -> None:
    table = "ai_run_events"
    op.create_table(
        table,
        _uuid("ai_run_id"),
        sa.Column("event_sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        _created_at(),
        _uuid("id"),
        sa.CheckConstraint(
            "event_sequence > 0", name=op.f("ck_ai_run_events_event_sequence_positive")
        ),
        sa.ForeignKeyConstraint(
            ["ai_run_id"],
            ["ai_runs.id"],
            name=op.f("fk_ai_run_events_ai_run_id_ai_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_run_events")),
        sa.UniqueConstraint("ai_run_id", "event_sequence", name="uq_ai_run_events_run_sequence"),
    )
    _index("ix_ai_run_events_ai_run_id", table, "ai_run_id")
    op.create_index(
        "ix_ai_run_events_run_sequence", table, ["ai_run_id", "event_sequence"], unique=False
    )


def _create_brief_versions() -> None:
    table = "ai_architect_brief_versions"
    op.create_table(
        table,
        _uuid("project_id"),
        sa.Column("version", sa.Integer(), nullable=False),
        _uuid("source_run_id"),
        _uuid("memory_version_id"),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("original_input", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("goals", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("priorities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("constraints", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "normalized_requirements", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("missing_information", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("conflicts", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "clarification_questions", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "recommended_next_steps", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("assumptions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("aggregate_confidence", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("based_on_project_version", sa.Integer(), nullable=False),
        _uuid("supersedes_id", nullable=True),
        _uuid("approved_by", nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        _uuid("created_by", nullable=True),
        _created_at(),
        _uuid("organization_id"),
        _uuid("id"),
        sa.CheckConstraint(
            "aggregate_confidence >= 0 and aggregate_confidence <= 1",
            name=op.f("ck_ai_architect_brief_versions_aggregate_confidence_range"),
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_ai_architect_brief_versions_version_positive")
        ),
        _organization_fk(table),
        _project_fk(table),
        _user_fk(table, "approved_by"),
        _user_fk(table, "created_by"),
        sa.ForeignKeyConstraint(
            ["source_run_id"],
            ["ai_runs.id"],
            name=op.f("fk_ai_architect_brief_versions_source_run_id_ai_runs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_version_id"],
            ["ai_project_memory_versions.id"],
            name=op.f(
                "fk_ai_architect_brief_versions_memory_version_id_ai_project_memory_versions"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["supersedes_id"],
            ["ai_architect_brief_versions.id"],
            name=op.f("fk_ai_architect_brief_versions_supersedes_id_ai_architect_brief_versions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_architect_brief_versions")),
        sa.UniqueConstraint("project_id", "version", name="uq_ai_briefs_project_version"),
    )
    _index("ix_ai_architect_brief_versions_organization_id", table, "organization_id")
    _index("ix_ai_architect_brief_versions_project_id", table, "project_id")
    _index("ix_ai_architect_brief_versions_status", table, "status")
    op.create_index(
        "ix_ai_briefs_project_created", table, ["project_id", "created_at", "id"], unique=False
    )
    op.create_index("ix_ai_briefs_project_status", table, ["project_id", "status"], unique=False)


def _create_proposals() -> None:
    table = "ai_requirement_proposals"
    op.create_table(
        table,
        _uuid("brief_version_id"),
        _uuid("project_id"),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_path", sa.String(length=255), nullable=False),
        sa.Column("existing_value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("proposed_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_references", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("explanation", sa.String(length=1000), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("expected_project_version", sa.Integer(), nullable=False),
        _uuid("reviewed_by", nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        _uuid("organization_id"),
        _uuid("id"),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "confidence >= 0 and confidence <= 1",
            name=op.f("ck_ai_requirement_proposals_confidence_range"),
        ),
        sa.CheckConstraint(
            "length(explanation) > 0",
            name=op.f("ck_ai_requirement_proposals_explanation_required"),
        ),
        _organization_fk(table),
        _project_fk(table),
        _user_fk(table, "reviewed_by"),
        sa.ForeignKeyConstraint(
            ["brief_version_id"],
            ["ai_architect_brief_versions.id"],
            name=op.f("fk_ai_requirement_proposals_brief_version_id_ai_architect_brief_versions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_requirement_proposals")),
    )
    for column in ("organization_id", "brief_version_id", "project_id", "status"):
        _index(f"ix_ai_requirement_proposals_{column}", table, column)
    op.create_index(
        "ix_ai_proposals_brief_status", table, ["brief_version_id", "status", "id"], unique=False
    )
    op.create_index("ix_ai_proposals_project_status", table, ["project_id", "status"], unique=False)


def _create_response_cache() -> None:
    table = "ai_response_cache"
    op.create_table(
        table,
        sa.Column("cache_key", sa.String(length=64), nullable=False),
        sa.Column("run_type", sa.String(length=48), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("prompt_checksum", sa.String(length=64), nullable=False),
        sa.Column("context_hash", sa.String(length=64), nullable=False),
        sa.Column("output_schema_version", sa.String(length=32), nullable=False),
        sa.Column("safety_policy_version", sa.String(length=32), nullable=False),
        sa.Column("response_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        _uuid("source_run_id"),
        sa.Column("hit_count", sa.Integer(), nullable=False),
        _created_at(),
        sa.Column("last_hit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        _uuid("organization_id"),
        _uuid("id"),
        sa.CheckConstraint(
            "hit_count >= 0", name=op.f("ck_ai_response_cache_hit_count_non_negative")
        ),
        _organization_fk(table),
        sa.ForeignKeyConstraint(
            ["source_run_id"],
            ["ai_runs.id"],
            name=op.f("fk_ai_response_cache_source_run_id_ai_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_response_cache")),
        sa.UniqueConstraint("organization_id", "cache_key", name="uq_ai_cache_org_key"),
    )
    _index("ix_ai_response_cache_organization_id", table, "organization_id")
    _index("ix_ai_response_cache_expires", table, "expires_at")


def _create_provider_health() -> None:
    table = "ai_provider_health"
    op.create_table(
        table,
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("environment", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("degraded_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error_code", sa.String(length=80), nullable=True),
        _uuid("id"),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "consecutive_failures >= 0",
            name=op.f("ck_ai_provider_health_consecutive_failures_non_negative"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_provider_health")),
        sa.UniqueConstraint(
            "provider", "model", "environment", name="uq_ai_provider_health_provider_model_env"
        ),
    )
    op.create_index(
        "ix_ai_provider_health_status", table, ["status", "degraded_until"], unique=False
    )


def _create_jobs() -> None:
    table = "ai_jobs"
    op.create_table(
        table,
        _uuid("project_id"),
        _uuid("ai_run_id"),
        sa.Column("job_type", sa.String(length=48), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("priority", sa.SmallInteger(), nullable=False),
        sa.Column("attempt_count", sa.SmallInteger(), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=120), nullable=True),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        _uuid("organization_id"),
        _uuid("id"),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "attempt_count >= 0", name=op.f("ck_ai_jobs_attempt_count_non_negative")
        ),
        _organization_fk(table),
        _project_fk(table),
        sa.ForeignKeyConstraint(
            ["ai_run_id"],
            ["ai_runs.id"],
            name=op.f("fk_ai_jobs_ai_run_id_ai_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_jobs")),
        sa.UniqueConstraint("ai_run_id", name="uq_ai_jobs_run"),
    )
    _index("ix_ai_jobs_organization_id", table, "organization_id")
    _index("ix_ai_jobs_status", table, "status")
    op.create_index(
        "ix_ai_jobs_claim",
        table,
        ["status", "available_at", "priority", "created_at"],
        unique=False,
    )


def _create_usage_daily() -> None:
    table = "ai_usage_daily"
    op.create_table(
        table,
        _uuid("user_id"),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("input_tokens", sa.BigInteger(), nullable=False),
        sa.Column("output_tokens", sa.BigInteger(), nullable=False),
        sa.Column("cost_microusd", sa.BigInteger(), nullable=False),
        sa.Column("run_count", sa.Integer(), nullable=False),
        sa.Column("cache_hit_count", sa.Integer(), nullable=False),
        _uuid("organization_id"),
        _uuid("id"),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint("cost_microusd >= 0", name=op.f("ck_ai_usage_daily_cost_non_negative")),
        sa.CheckConstraint(
            "input_tokens >= 0", name=op.f("ck_ai_usage_daily_input_tokens_non_negative")
        ),
        sa.CheckConstraint(
            "output_tokens >= 0", name=op.f("ck_ai_usage_daily_output_tokens_non_negative")
        ),
        _organization_fk(table),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_ai_usage_daily_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_usage_daily")),
        sa.UniqueConstraint(
            "organization_id",
            "user_id",
            "usage_date",
            "provider",
            "model",
            name="uq_ai_usage_daily_dimensions",
        ),
    )
    _index("ix_ai_usage_daily_organization_id", table, "organization_id")
    op.create_index(
        "ix_ai_usage_daily_org_date", table, ["organization_id", "usage_date"], unique=False
    )


def _index(name: str, table: str, column: str) -> None:
    op.create_index(op.f(name), table, [column], unique=False)


def downgrade() -> None:
    for table in (
        "ai_usage_daily",
        "ai_jobs",
        "ai_provider_health",
        "ai_response_cache",
        "ai_requirement_proposals",
        "ai_architect_brief_versions",
        "ai_run_events",
        "ai_chat_messages",
        "ai_runs",
        "ai_project_memory_versions",
        "ai_prompt_templates",
        "ai_chat_threads",
    ):
        op.drop_table(table)
