"""building visualization

Revision ID: 2026_07_18_0007
Revises: 2026_07_17_0006
Create Date: 2026-07-18 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2026_07_18_0007"
down_revision: str | None = "2026_07_17_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "building_scene_compilation_jobs",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_editor_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_editor_checkpoint_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_design_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_editor_revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("progress", sa.SmallInteger(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("scene_engine_version", sa.String(length=80), nullable=False),
        sa.Column("geometry_engine_version", sa.String(length=160), nullable=False),
        sa.Column("scene_schema_version", sa.String(length=40), nullable=False),
        sa.Column("renderer_contract_version", sa.String(length=60), nullable=False),
        sa.Column("failure_code", sa.String(length=80), nullable=True),
        sa.Column("failure_details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("progress >= 0 and progress <= 100", name="scene_job_progress_range"),
        sa.CheckConstraint(
            "source_editor_revision >= 0", name="scene_job_revision_non_negative"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_design_version_id"], ["floor_plan_design_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_editor_checkpoint_id"],
            ["floor_plan_editor_checkpoints.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_editor_document_id"],
            ["floor_plan_editor_documents.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "created_by",
            "idempotency_key",
            name="uq_scene_jobs_org_actor_idempotency",
        ),
    )
    op.create_index(
        "ix_scene_jobs_org_status_created",
        "building_scene_compilation_jobs",
        ["organization_id", "status", "created_at"],
    )
    op.create_index(
        "ix_scene_jobs_project_created",
        "building_scene_compilation_jobs",
        ["project_id", "created_at", "id"],
    )
    op.create_index(
        op.f("ix_building_scene_compilation_jobs_status"),
        "building_scene_compilation_jobs",
        ["status"],
    )

    op.create_table(
        "building_scene_versions",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("compilation_job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_editor_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_editor_checkpoint_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_design_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_editor_revision", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("is_stale", sa.Boolean(), nullable=False),
        sa.Column("manifest", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("object_count", sa.Integer(), nullable=False),
        sa.Column("triangle_count", sa.BigInteger(), nullable=False),
        sa.Column("bounding_box", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("scene_schema_version", sa.String(length=40), nullable=False),
        sa.Column("geometry_engine_version", sa.String(length=160), nullable=False),
        sa.Column("scene_engine_version", sa.String(length=80), nullable=False),
        sa.Column("material_schema_version", sa.String(length=40), nullable=False),
        sa.Column("renderer_contract_version", sa.String(length=60), nullable=False),
        sa.Column("source_versions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("disclaimer", sa.String(length=160), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("object_count >= 0", name="scene_object_count_non_negative"),
        sa.CheckConstraint("triangle_count >= 0", name="scene_triangle_count_non_negative"),
        sa.CheckConstraint("version > 0", name="scene_version_positive"),
        sa.ForeignKeyConstraint(
            ["compilation_job_id"], ["building_scene_compilation_jobs.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_design_version_id"], ["floor_plan_design_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_editor_checkpoint_id"],
            ["floor_plan_editor_checkpoints.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_editor_document_id"],
            ["floor_plan_editor_documents.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("compilation_job_id", name="uq_scene_versions_job"),
        sa.UniqueConstraint("project_id", "version", name="uq_scene_versions_project_version"),
    )
    op.create_index(
        "ix_scene_versions_project_active",
        "building_scene_versions",
        ["project_id", "status"],
        postgresql_where=sa.text("deleted_at is null"),
    )
    op.create_index(
        "ix_scene_versions_project_created",
        "building_scene_versions",
        ["project_id", "created_at", "id"],
    )

    _create_child_tables()


def _create_child_tables() -> None:
    op.create_table(
        "building_scene_compilation_events",
        sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint("sequence > 0", name="scene_event_sequence_positive"),
        sa.ForeignKeyConstraint(
            ["job_id"], ["building_scene_compilation_jobs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "sequence", name="uq_scene_events_job_sequence"),
    )
    op.create_index(
        op.f("ix_building_scene_compilation_events_job_id"),
        "building_scene_compilation_events",
        ["job_id"],
    )
    op.create_index(
        "ix_scene_events_job_sequence",
        "building_scene_compilation_events",
        ["job_id", "sequence"],
    )
    _create_scene_object_tables()


def _create_scene_object_tables() -> None:
    op.create_table(
        "building_scene_objects",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scene_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("stable_object_id", sa.String(length=160), nullable=False),
        sa.Column("source_2d_object_id", sa.String(length=160), nullable=True),
        sa.Column("source_2d_object_type", sa.String(length=40), nullable=True),
        sa.Column("object_type", sa.String(length=32), nullable=False),
        sa.Column("floor_id", sa.String(length=120), nullable=True),
        sa.Column("parent_object_id", sa.String(length=160), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("geometry_kind", sa.String(length=32), nullable=False),
        sa.Column("transform", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("geometry", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("bounding_box", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("material_id", sa.String(length=80), nullable=False),
        sa.Column("triangle_count", sa.Integer(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "triangle_count >= 0", name="scene_object_triangle_count_non_negative"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["scene_version_id"], ["building_scene_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scene_version_id", "stable_object_id", name="uq_scene_objects_stable"),
    )
    op.create_index(
        op.f("ix_building_scene_objects_scene_version_id"),
        "building_scene_objects",
        ["scene_version_id"],
    )
    op.create_index("ix_scene_objects_source_2d", "building_scene_objects", ["source_2d_object_id"])
    op.create_index(
        "ix_scene_objects_version_type",
        "building_scene_objects",
        ["scene_version_id", "object_type"],
    )
    _create_scene_support_tables()


def _create_scene_support_tables() -> None:
    op.create_table(
        "building_scene_materials",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scene_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("material_id", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["scene_version_id"], ["building_scene_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scene_version_id", "material_id", name="uq_scene_materials_key"),
    )
    op.create_index(
        op.f("ix_building_scene_materials_scene_version_id"),
        "building_scene_materials",
        ["scene_version_id"],
    )
    op.create_index(
        "ix_scene_materials_version_category",
        "building_scene_materials",
        ["scene_version_id", "category"],
    )
    _create_scene_user_tables()


def _create_scene_user_tables() -> None:
    op.create_table(
        "building_scene_camera_views",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scene_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("camera", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["scene_version_id"], ["building_scene_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_building_scene_camera_views_scene_version_id"),
        "building_scene_camera_views",
        ["scene_version_id"],
    )
    op.create_index(
        "ix_scene_camera_views_version_created",
        "building_scene_camera_views",
        ["scene_version_id", "created_at", "id"],
    )
    _create_scene_validation_and_audit_tables()


def _create_scene_validation_and_audit_tables() -> None:
    op.create_table(
        "building_scene_validation_results",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scene_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("compilation_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("validation_engine_version", sa.String(length=80), nullable=False),
        sa.Column("geometry_engine_version", sa.String(length=160), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("issues", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["compilation_job_id"], ["building_scene_compilation_jobs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["scene_version_id"], ["building_scene_versions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scene_validation_version_created",
        "building_scene_validation_results",
        ["scene_version_id", "created_at", "id"],
    )
    op.create_table(
        "building_scene_audit_events",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scene_audit_entity", "building_scene_audit_events", ["entity_type", "entity_id"]
    )
    op.create_index(
        "ix_scene_audit_project_created",
        "building_scene_audit_events",
        ["project_id", "created_at", "id"],
    )


def downgrade() -> None:
    op.drop_index("ix_scene_audit_project_created", table_name="building_scene_audit_events")
    op.drop_index("ix_scene_audit_entity", table_name="building_scene_audit_events")
    op.drop_table("building_scene_audit_events")
    op.drop_index(
        "ix_scene_validation_version_created", table_name="building_scene_validation_results"
    )
    op.drop_table("building_scene_validation_results")
    op.drop_index(
        "ix_scene_camera_views_version_created", table_name="building_scene_camera_views"
    )
    op.drop_index(
        op.f("ix_building_scene_camera_views_scene_version_id"),
        table_name="building_scene_camera_views",
    )
    op.drop_table("building_scene_camera_views")
    op.drop_index("ix_scene_materials_version_category", table_name="building_scene_materials")
    op.drop_index(
        op.f("ix_building_scene_materials_scene_version_id"),
        table_name="building_scene_materials",
    )
    op.drop_table("building_scene_materials")
    op.drop_index("ix_scene_objects_version_type", table_name="building_scene_objects")
    op.drop_index("ix_scene_objects_source_2d", table_name="building_scene_objects")
    op.drop_index(
        op.f("ix_building_scene_objects_scene_version_id"),
        table_name="building_scene_objects",
    )
    op.drop_table("building_scene_objects")
    op.drop_index("ix_scene_events_job_sequence", table_name="building_scene_compilation_events")
    op.drop_index(
        op.f("ix_building_scene_compilation_events_job_id"),
        table_name="building_scene_compilation_events",
    )
    op.drop_table("building_scene_compilation_events")
    op.drop_index("ix_scene_versions_project_created", table_name="building_scene_versions")
    op.drop_index(
        "ix_scene_versions_project_active",
        table_name="building_scene_versions",
        postgresql_where=sa.text("deleted_at is null"),
    )
    op.drop_table("building_scene_versions")
    op.drop_index(
        op.f("ix_building_scene_compilation_jobs_status"),
        table_name="building_scene_compilation_jobs",
    )
    op.drop_index("ix_scene_jobs_project_created", table_name="building_scene_compilation_jobs")
    op.drop_index("ix_scene_jobs_org_status_created", table_name="building_scene_compilation_jobs")
    op.drop_table("building_scene_compilation_jobs")
