"""add conceptual floor plan generator

Revision ID: 202607130005
Revises: 202607130004
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202607130005"
down_revision: str | None = "202607130004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _uuid(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, postgresql.UUID(as_uuid=True), nullable=nullable)


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def _updated_at() -> sa.Column:
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def _organization_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["organization_id"],
        ["organizations.id"],
        name=op.f(f"fk_{table}_organization_id_organizations"),
        ondelete="RESTRICT",
    )


def _project_fk(table: str) -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        ["project_id"],
        ["projects.id"],
        name=op.f(f"fk_{table}_project_id_projects"),
        ondelete="CASCADE",
    )


def _user_fk(table: str, column: str, *, ondelete: str = "RESTRICT") -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(
        [column],
        ["users.id"],
        name=op.f(f"fk_{table}_{column}_users"),
        ondelete=ondelete,
    )


def upgrade() -> None:
    _create_runs()
    _create_jobs()
    _create_events()
    _create_options()
    _create_geometry_snapshots()
    _create_validation_results()
    _create_design_versions()


def _create_runs() -> None:
    table = "floor_plan_generation_runs"
    op.create_table(
        table,
        _uuid("project_id"),
        _uuid("source_brief_id"),
        _uuid("memory_version_id"),
        _uuid("boundary_version_id"),
        _uuid("analysis_snapshot_id"),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("requested_option_count", sa.SmallInteger(), nullable=False),
        sa.Column("completed_option_count", sa.SmallInteger(), nullable=False),
        sa.Column("deterministic_seed", sa.BigInteger(), nullable=False),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("source_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("engine_version", sa.String(length=80), nullable=False),
        sa.Column("solver_version", sa.String(length=120), nullable=False),
        sa.Column("geometry_engine_version", sa.String(length=160), nullable=False),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("cache_key", sa.String(length=64), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        _uuid("cache_source_run_id", nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("diversity_threshold", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("max_solver_attempts", sa.SmallInteger(), nullable=False),
        sa.Column("max_provider_retries", sa.SmallInteger(), nullable=False),
        sa.Column("max_processing_seconds", sa.Integer(), nullable=False),
        sa.Column("max_invalid_candidates", sa.SmallInteger(), nullable=False),
        sa.Column("solver_attempt_count", sa.SmallInteger(), nullable=False),
        sa.Column("provider_retry_count", sa.SmallInteger(), nullable=False),
        sa.Column("invalid_candidate_count", sa.SmallInteger(), nullable=False),
        sa.Column("estimated_input_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_output_tokens", sa.Integer(), nullable=False),
        sa.Column("estimated_cost_microusd", sa.BigInteger(), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("actual_cost_microusd", sa.BigInteger(), nullable=False),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("failure_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        _uuid("created_by"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        _uuid("organization_id"),
        _uuid("id"),
        _created_at(),
        _updated_at(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "requested_option_count between 3 and 5",
            name=op.f("ck_floor_plan_generation_runs_option_count_range"),
        ),
        sa.CheckConstraint(
            "completed_option_count >= 0",
            name=op.f("ck_floor_plan_generation_runs_completed_count_non_negative"),
        ),
        sa.CheckConstraint(
            "deterministic_seed >= 0",
            name=op.f("ck_floor_plan_generation_runs_seed_non_negative"),
        ),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_floor_plan_generation_runs_version_positive")
        ),
        sa.CheckConstraint(
            "max_solver_attempts between 1 and 100",
            name=op.f("ck_floor_plan_generation_runs_solver_budget_range"),
        ),
        sa.CheckConstraint(
            "max_provider_retries between 0 and 10",
            name=op.f("ck_floor_plan_generation_runs_provider_budget_range"),
        ),
        sa.CheckConstraint(
            "max_processing_seconds between 10 and 1800",
            name=op.f("ck_floor_plan_generation_runs_time_budget_range"),
        ),
        sa.CheckConstraint(
            "max_invalid_candidates between 1 and 100",
            name=op.f("ck_floor_plan_generation_runs_invalid_budget_range"),
        ),
        sa.CheckConstraint(
            "solver_attempt_count >= 0",
            name=op.f("ck_floor_plan_generation_runs_solver_attempts_non_negative"),
        ),
        sa.CheckConstraint(
            "provider_retry_count >= 0",
            name=op.f("ck_floor_plan_generation_runs_provider_retries_non_negative"),
        ),
        sa.CheckConstraint(
            "invalid_candidate_count >= 0",
            name=op.f("ck_floor_plan_generation_runs_invalid_count_non_negative"),
        ),
        sa.CheckConstraint(
            "estimated_input_tokens >= 0",
            name=op.f("ck_floor_plan_generation_runs_estimated_input_non_negative"),
        ),
        sa.CheckConstraint(
            "estimated_output_tokens >= 0",
            name=op.f("ck_floor_plan_generation_runs_estimated_output_non_negative"),
        ),
        sa.CheckConstraint(
            "estimated_cost_microusd >= 0",
            name=op.f("ck_floor_plan_generation_runs_estimated_cost_non_negative"),
        ),
        sa.CheckConstraint(
            "input_tokens >= 0",
            name=op.f("ck_floor_plan_generation_runs_input_tokens_non_negative"),
        ),
        sa.CheckConstraint(
            "output_tokens >= 0",
            name=op.f("ck_floor_plan_generation_runs_output_tokens_non_negative"),
        ),
        sa.CheckConstraint(
            "actual_cost_microusd >= 0",
            name=op.f("ck_floor_plan_generation_runs_actual_cost_non_negative"),
        ),
        sa.CheckConstraint(
            "diversity_threshold >= 0 and diversity_threshold <= 1",
            name=op.f("ck_floor_plan_generation_runs_diversity_threshold_range"),
        ),
        _organization_fk(table),
        _project_fk(table),
        _user_fk(table, "created_by"),
        sa.ForeignKeyConstraint(
            ["source_brief_id"],
            ["ai_architect_brief_versions.id"],
            name=op.f("fk_floor_plan_generation_runs_source_brief_id_ai_architect_brief_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["memory_version_id"],
            ["ai_project_memory_versions.id"],
            name=op.f("fk_floor_plan_generation_runs_memory_version_id_ai_project_memory_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["boundary_version_id"],
            ["plot_boundary_versions.id"],
            name=op.f("fk_floor_plan_generation_runs_boundary_version_id_plot_boundary_versions"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_snapshot_id"],
            ["plot_analysis_snapshots.id"],
            name=op.f("fk_floor_plan_generation_runs_analysis_snapshot_id_plot_analysis_snapshots"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cache_source_run_id"],
            ["floor_plan_generation_runs.id"],
            name=op.f(
                "fk_floor_plan_generation_runs_cache_source_run_id_floor_plan_generation_runs"
            ),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_floor_plan_generation_runs")),
        sa.UniqueConstraint(
            "organization_id",
            "created_by",
            "idempotency_key",
            name="uq_floor_plan_runs_org_actor_idempotency",
        ),
    )
    for column in ("organization_id", "project_id", "status"):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)
    op.create_index("ix_floor_plan_runs_project_created", table, ["project_id", "created_at", "id"])
    op.create_index(
        "ix_floor_plan_runs_org_status_created",
        table,
        ["organization_id", "status", "created_at"],
    )
    op.create_index("ix_floor_plan_runs_cache", table, ["organization_id", "cache_key"])
    op.create_index(
        "ix_floor_plan_runs_project_active",
        table,
        ["project_id", "status"],
        postgresql_where=sa.text("deleted_at is null"),
    )


def _create_jobs() -> None:
    table = "floor_plan_generation_jobs"
    op.create_table(
        table,
        _uuid("project_id"),
        _uuid("run_id"),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("priority", sa.SmallInteger(), nullable=False),
        sa.Column("attempt_count", sa.SmallInteger(), nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_by", sa.String(length=120), nullable=True),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        _uuid("organization_id"),
        _uuid("id"),
        _created_at(),
        _updated_at(),
        sa.CheckConstraint(
            "attempt_count >= 0",
            name=op.f("ck_floor_plan_generation_jobs_attempt_count_non_negative"),
        ),
        _organization_fk(table),
        _project_fk(table),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["floor_plan_generation_runs.id"],
            name=op.f("fk_floor_plan_generation_jobs_run_id_floor_plan_generation_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_floor_plan_generation_jobs")),
        sa.UniqueConstraint("run_id", name="uq_floor_plan_jobs_run"),
    )
    for column in ("organization_id", "status"):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column], unique=False)
    op.create_index(
        "ix_floor_plan_jobs_claim",
        table,
        ["status", "available_at", "priority", "created_at"],
    )


def _create_events() -> None:
    table = "floor_plan_generation_events"
    op.create_table(
        table,
        _uuid("run_id"),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        _created_at(),
        _uuid("id"),
        sa.CheckConstraint(
            "sequence > 0", name=op.f("ck_floor_plan_generation_events_sequence_positive")
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["floor_plan_generation_runs.id"],
            name=op.f("fk_floor_plan_generation_events_run_id_floor_plan_generation_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_floor_plan_generation_events")),
        sa.UniqueConstraint("run_id", "sequence", name="uq_floor_plan_events_run_sequence"),
    )
    op.create_index(op.f(f"ix_{table}_run_id"), table, ["run_id"])
    op.create_index("ix_floor_plan_events_run_sequence", table, ["run_id", "sequence"])


def _create_options() -> None:
    table = "floor_plan_options"
    op.create_table(
        table,
        _uuid("project_id"),
        _uuid("run_id"),
        sa.Column("option_number", sa.SmallInteger(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("deterministic_seed", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("provider_program", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("major_decisions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("constraint_trace", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("area_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("topology_signature", sa.String(length=64), nullable=False),
        sa.Column("topology_features", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("diversity_score", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("solver_attempt", sa.SmallInteger(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("rejection_reason", sa.String(length=1000), nullable=True),
        _uuid("rejected_by", nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        _uuid("organization_id"),
        _uuid("id"),
        _created_at(),
        _updated_at(),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "option_number between 1 and 5",
            name=op.f("ck_floor_plan_options_option_number_range"),
        ),
        sa.CheckConstraint(
            "deterministic_seed >= 0", name=op.f("ck_floor_plan_options_seed_non_negative")
        ),
        sa.CheckConstraint(
            "confidence >= 0 and confidence <= 1",
            name=op.f("ck_floor_plan_options_confidence_range"),
        ),
        sa.CheckConstraint(
            "diversity_score >= 0 and diversity_score <= 1",
            name=op.f("ck_floor_plan_options_diversity_range"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_floor_plan_options_version_positive")),
        _organization_fk(table),
        _project_fk(table),
        _user_fk(table, "rejected_by", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["floor_plan_generation_runs.id"],
            name=op.f("fk_floor_plan_options_run_id_floor_plan_generation_runs"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_floor_plan_options")),
        sa.UniqueConstraint("run_id", "option_number", name="uq_floor_plan_options_run_number"),
    )
    for column in ("organization_id", "run_id", "status"):
        op.create_index(op.f(f"ix_{table}_{column}"), table, [column])
    op.create_index(
        "ix_floor_plan_options_run_status", table, ["run_id", "status", "option_number"]
    )
    op.create_index(
        "ix_floor_plan_options_project_created", table, ["project_id", "created_at", "id"]
    )


def _create_geometry_snapshots() -> None:
    table = "floor_plan_geometry_snapshots"
    op.create_table(
        table,
        _uuid("project_id"),
        _uuid("option_id"),
        sa.Column("coordinate_space", sa.String(length=32), nullable=False),
        sa.Column("unit", sa.String(length=16), nullable=False),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("geometry_engine_version", sa.String(length=160), nullable=False),
        sa.Column("geometry_hash", sa.String(length=64), nullable=False),
        sa.Column("geometry", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("bounding_box", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("gross_area_m2", sa.Numeric(precision=16, scale=3), nullable=False),
        sa.Column("source_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        _created_at(),
        _uuid("organization_id"),
        _uuid("id"),
        sa.CheckConstraint(
            "gross_area_m2 > 0",
            name=op.f("ck_floor_plan_geometry_snapshots_gross_area_positive"),
        ),
        _organization_fk(table),
        _project_fk(table),
        sa.ForeignKeyConstraint(
            ["option_id"],
            ["floor_plan_options.id"],
            name=op.f("fk_floor_plan_geometry_snapshots_option_id_floor_plan_options"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_floor_plan_geometry_snapshots")),
        sa.UniqueConstraint("option_id", name="uq_floor_plan_geometry_option"),
    )
    op.create_index(op.f(f"ix_{table}_organization_id"), table, ["organization_id"])
    op.create_index(
        "ix_floor_plan_geometry_project_created", table, ["project_id", "created_at", "id"]
    )
    op.create_index("ix_floor_plan_geometry_hash", table, ["geometry_hash"])


def _create_validation_results() -> None:
    table = "floor_plan_validation_results"
    op.create_table(
        table,
        _uuid("project_id"),
        _uuid("option_id"),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("validation_engine_version", sa.String(length=80), nullable=False),
        sa.Column("geometry_engine_version", sa.String(length=160), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("checks", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        _created_at(),
        _uuid("organization_id"),
        _uuid("id"),
        _organization_fk(table),
        _project_fk(table),
        sa.ForeignKeyConstraint(
            ["option_id"],
            ["floor_plan_options.id"],
            name=op.f("fk_floor_plan_validation_results_option_id_floor_plan_options"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_floor_plan_validation_results")),
        sa.UniqueConstraint("option_id", name="uq_floor_plan_validation_option"),
    )
    op.create_index(op.f(f"ix_{table}_organization_id"), table, ["organization_id"])
    op.create_index(op.f(f"ix_{table}_status"), table, ["status"])
    op.create_index(
        "ix_floor_plan_validation_project_created", table, ["project_id", "created_at", "id"]
    )


def _create_design_versions() -> None:
    table = "floor_plan_design_versions"
    op.create_table(
        table,
        _uuid("project_id"),
        _uuid("source_run_id"),
        _uuid("source_option_id"),
        _uuid("geometry_snapshot_id"),
        _uuid("validation_result_id"),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("geometry_hash", sa.String(length=64), nullable=False),
        sa.Column("source_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("engine_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("disclaimer", sa.String(length=160), nullable=False),
        _uuid("accepted_by"),
        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        _created_at(),
        _uuid("organization_id"),
        _uuid("id"),
        sa.CheckConstraint(
            "version > 0", name=op.f("ck_floor_plan_design_versions_version_positive")
        ),
        _organization_fk(table),
        _project_fk(table),
        _user_fk(table, "accepted_by"),
        sa.ForeignKeyConstraint(
            ["source_run_id"],
            ["floor_plan_generation_runs.id"],
            name=op.f("fk_floor_plan_design_versions_source_run_id_floor_plan_generation_runs"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_option_id"],
            ["floor_plan_options.id"],
            name=op.f("fk_floor_plan_design_versions_source_option_id_floor_plan_options"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["geometry_snapshot_id"],
            ["floor_plan_geometry_snapshots.id"],
            name=op.f(
                "fk_floor_plan_design_versions_geometry_snapshot_id_floor_plan_geometry_snapshots"
            ),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["validation_result_id"],
            ["floor_plan_validation_results.id"],
            name=op.f(
                "fk_floor_plan_design_versions_validation_result_id_floor_plan_validation_results"
            ),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_floor_plan_design_versions")),
        sa.UniqueConstraint("project_id", "version", name="uq_floor_plan_design_project_version"),
        sa.UniqueConstraint("source_option_id", name="uq_floor_plan_design_source_option"),
    )
    op.create_index(op.f(f"ix_{table}_organization_id"), table, ["organization_id"])
    op.create_index(
        "ix_floor_plan_design_project_created", table, ["project_id", "created_at", "id"]
    )


def downgrade() -> None:
    for table in (
        "floor_plan_design_versions",
        "floor_plan_validation_results",
        "floor_plan_geometry_snapshots",
        "floor_plan_options",
        "floor_plan_generation_events",
        "floor_plan_generation_jobs",
        "floor_plan_generation_runs",
    ):
        op.drop_table(table)
