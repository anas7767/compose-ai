"""exterior design foundation

Revision ID: 2026_07_18_0009
Revises: 2026_07_18_0008
Create Date: 2026-07-18 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2026_07_18_0009"
down_revision: str | None = "2026_07_18_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "exterior_design_context_snapshots",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_design_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_scene_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_editor_checkpoint_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_brief_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("context_hash", sa.String(length=64), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("engine_version", sa.String(length=80), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_brief_id"], ["ai_architect_brief_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_design_version_id"], ["floor_plan_design_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_editor_checkpoint_id"], ["floor_plan_editor_checkpoints.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_scene_version_id"], ["building_scene_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "context_hash", name="uq_exterior_context_hash"),
    )
    op.create_index("ix_exterior_context_project_created", "exterior_design_context_snapshots", ["project_id", "created_at", "id"])
    op.create_index(op.f("ix_exterior_design_context_snapshots_organization_id"), "exterior_design_context_snapshots", ["organization_id"])

    op.create_table(
        "exterior_design_runs",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_design_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_scene_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_editor_checkpoint_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("prompt_version", sa.String(length=40), nullable=False),
        sa.Column("engine_version", sa.String(length=80), nullable=False),
        sa.Column("requested_option_count", sa.SmallInteger(), nullable=False),
        sa.Column("completed_option_count", sa.SmallInteger(), nullable=False),
        sa.Column("style", sa.String(length=40), nullable=False),
        sa.Column("view_type", sa.String(length=24), nullable=False),
        sa.Column("material_preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("user_instructions", sa.Text(), nullable=True),
        sa.Column("negative_constraints", sa.Text(), nullable=True),
        sa.Column("seed", sa.BigInteger(), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("context_hash", sa.String(length=64), nullable=False),
        sa.Column("cache_key", sa.String(length=64), nullable=False),
        sa.Column("cache_hit", sa.Boolean(), nullable=False),
        sa.Column("cache_source_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sanitized_prompt", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("safe_failure_message", sa.String(length=500), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False),
        sa.Column("output_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_microusd", sa.BigInteger(), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("completed_option_count >= 0", name="exterior_run_completed_non_negative"),
        sa.CheckConstraint("cost_microusd >= 0", name="exterior_run_cost_non_negative"),
        sa.CheckConstraint("input_tokens >= 0", name="exterior_run_input_tokens_non_negative"),
        sa.CheckConstraint("output_tokens >= 0", name="exterior_run_output_tokens_non_negative"),
        sa.CheckConstraint("requested_option_count between 1 and 4", name="exterior_run_option_count_range"),
        sa.ForeignKeyConstraint(["cache_source_run_id"], ["exterior_design_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["context_snapshot_id"], ["exterior_design_context_snapshots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_design_version_id"], ["floor_plan_design_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_editor_checkpoint_id"], ["floor_plan_editor_checkpoints.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_scene_version_id"], ["building_scene_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "created_by", "idempotency_key", name="uq_exterior_runs_org_actor_idempotency"),
    )
    op.create_index("ix_exterior_runs_cache", "exterior_design_runs", ["organization_id", "cache_key"])
    op.create_index("ix_exterior_runs_context", "exterior_design_runs", ["organization_id", "context_hash"])
    op.create_index("ix_exterior_runs_org_status_created", "exterior_design_runs", ["organization_id", "status", "created_at"])
    op.create_index("ix_exterior_runs_project_created", "exterior_design_runs", ["project_id", "created_at", "id"])
    op.create_index(op.f("ix_exterior_design_runs_project_id"), "exterior_design_runs", ["project_id"])
    op.create_index(op.f("ix_exterior_design_runs_status"), "exterior_design_runs", ["status"])

    op.create_table(
        "exterior_design_options",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("context_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_design_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_scene_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_editor_checkpoint_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("option_number", sa.SmallInteger(), nullable=False),
        sa.Column("style", sa.String(length=40), nullable=False),
        sa.Column("view_type", sa.String(length=24), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("approval_status", sa.String(length=24), nullable=False),
        sa.Column("is_conceptual", sa.Boolean(), nullable=False),
        sa.Column("disclaimer", sa.String(length=160), nullable=False),
        sa.Column("safety_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.String(length=1000), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("option_number between 1 and 4", name="exterior_option_number_range"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["context_snapshot_id"], ["exterior_design_context_snapshots.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rejected_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["run_id"], ["exterior_design_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_design_version_id"], ["floor_plan_design_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_editor_checkpoint_id"], ["floor_plan_editor_checkpoints.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["source_scene_version_id"], ["building_scene_versions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "option_number", name="uq_exterior_options_run_number"),
    )
    op.create_index("ix_exterior_options_active_approved", "exterior_design_options", ["project_id", "approval_status"], postgresql_where=sa.text("deleted_at is null"))
    op.create_index("ix_exterior_options_project_created", "exterior_design_options", ["project_id", "created_at", "id"])
    op.create_index("ix_exterior_options_run_status", "exterior_design_options", ["run_id", "status", "option_number"])
    op.create_index(op.f("ix_exterior_design_options_organization_id"), "exterior_design_options", ["organization_id"])
    op.create_index(op.f("ix_exterior_design_options_run_id"), "exterior_design_options", ["run_id"])

    op.create_table(
        "exterior_design_assets",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("option_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_provider", sa.String(length=32), nullable=False),
        sa.Column("storage_key", sa.String(length=1024), nullable=False),
        sa.Column("thumbnail_storage_key", sa.String(length=1024), nullable=True),
        sa.Column("mime_type", sa.String(length=80), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("integrity_hash", sa.String(length=64), nullable=False),
        sa.Column("provider_asset_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("delivery_reference", sa.String(length=1200), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["option_id"], ["exterior_design_options.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_provider", "storage_key", name="uq_exterior_assets_storage_key"),
    )
    op.create_index("ix_exterior_assets_option_created", "exterior_design_assets", ["option_id", "created_at", "id"])
    op.create_index(op.f("ix_exterior_design_assets_option_id"), "exterior_design_assets", ["option_id"])
    op.create_index(op.f("ix_exterior_design_assets_organization_id"), "exterior_design_assets", ["organization_id"])

    op.create_table(
        "exterior_design_validation_results",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("option_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("validation_engine_version", sa.String(length=80), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("issues", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["option_id"], ["exterior_design_options.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("option_id", name="uq_exterior_validation_option"),
    )
    op.create_index(op.f("ix_exterior_design_validation_results_organization_id"), "exterior_design_validation_results", ["organization_id"])

    op.create_table(
        "exterior_design_events",
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("sequence > 0", name="exterior_event_sequence_positive"),
        sa.ForeignKeyConstraint(["run_id"], ["exterior_design_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_exterior_events_run_sequence"),
    )
    op.create_index("ix_exterior_events_run_sequence", "exterior_design_events", ["run_id", "sequence"])
    op.create_index(op.f("ix_exterior_design_events_run_id"), "exterior_design_events", ["run_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_exterior_design_events_run_id"), table_name="exterior_design_events")
    op.drop_index("ix_exterior_events_run_sequence", table_name="exterior_design_events")
    op.drop_table("exterior_design_events")
    op.drop_index(op.f("ix_exterior_design_validation_results_organization_id"), table_name="exterior_design_validation_results")
    op.drop_table("exterior_design_validation_results")
    op.drop_index(op.f("ix_exterior_design_assets_organization_id"), table_name="exterior_design_assets")
    op.drop_index(op.f("ix_exterior_design_assets_option_id"), table_name="exterior_design_assets")
    op.drop_index("ix_exterior_assets_option_created", table_name="exterior_design_assets")
    op.drop_table("exterior_design_assets")
    op.drop_index(op.f("ix_exterior_design_options_run_id"), table_name="exterior_design_options")
    op.drop_index(op.f("ix_exterior_design_options_organization_id"), table_name="exterior_design_options")
    op.drop_index("ix_exterior_options_run_status", table_name="exterior_design_options")
    op.drop_index("ix_exterior_options_project_created", table_name="exterior_design_options")
    op.drop_index("ix_exterior_options_active_approved", table_name="exterior_design_options", postgresql_where=sa.text("deleted_at is null"))
    op.drop_table("exterior_design_options")
    op.drop_index(op.f("ix_exterior_design_runs_status"), table_name="exterior_design_runs")
    op.drop_index(op.f("ix_exterior_design_runs_project_id"), table_name="exterior_design_runs")
    op.drop_index("ix_exterior_runs_project_created", table_name="exterior_design_runs")
    op.drop_index("ix_exterior_runs_org_status_created", table_name="exterior_design_runs")
    op.drop_index("ix_exterior_runs_context", table_name="exterior_design_runs")
    op.drop_index("ix_exterior_runs_cache", table_name="exterior_design_runs")
    op.drop_table("exterior_design_runs")
    op.drop_index(op.f("ix_exterior_design_context_snapshots_organization_id"), table_name="exterior_design_context_snapshots")
    op.drop_index("ix_exterior_context_project_created", table_name="exterior_design_context_snapshots")
    op.drop_table("exterior_design_context_snapshots")
