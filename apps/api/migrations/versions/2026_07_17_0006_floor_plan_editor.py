"""floor plan editor

Revision ID: 2026_07_17_0006
Revises: 202607130005
Create Date: 2026-07-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2026_07_17_0006"
down_revision: str | None = "202607130005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "floor_plan_editor_documents",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_design_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_geometry_snapshot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("current_revision", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=40), nullable=False),
        sa.Column("renderer_contract_version", sa.String(length=40), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("validation_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("view_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("layer_state", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("current_revision >= 0", name="current_revision_non_negative"),
        sa.CheckConstraint("renderer_contract_version <> ''", name="renderer_contract_required"),
        sa.CheckConstraint("schema_version <> ''", name="schema_version_required"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_design_version_id"], ["floor_plan_design_versions.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["source_geometry_snapshot_id"],
            ["floor_plan_geometry_snapshots.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", name="uq_editor_documents_project"),
    )
    op.create_index(
        "ix_editor_documents_org_active",
        "floor_plan_editor_documents",
        ["organization_id", "status"],
        unique=False,
        postgresql_where=sa.text("deleted_at is null"),
    )
    op.create_index(
        op.f("ix_floor_plan_editor_documents_organization_id"),
        "floor_plan_editor_documents",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "floor_plan_editor_operation_batches",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("client_batch_id", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("base_revision", sa.Integer(), nullable=False),
        sa.Column("result_revision", sa.Integer(), nullable=False),
        sa.Column("operations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("inverse_operations", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("validation_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("base_revision >= 0", name="base_revision_non_negative"),
        sa.CheckConstraint("result_revision > base_revision", name="result_revision_advances"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["floor_plan_editor_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "client_batch_id", name="uq_editor_batches_client_batch"),
        sa.UniqueConstraint(
            "organization_id",
            "created_by",
            "idempotency_key",
            name="uq_editor_batches_org_actor_idempotency",
        ),
    )
    op.create_index(
        "ix_editor_batches_document_revision",
        "floor_plan_editor_operation_batches",
        ["document_id", "result_revision"],
        unique=False,
    )
    op.create_index(
        op.f("ix_floor_plan_editor_operation_batches_document_id"),
        "floor_plan_editor_operation_batches",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_floor_plan_editor_operation_batches_organization_id"),
        "floor_plan_editor_operation_batches",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "floor_plan_editor_validation_results",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("validation_engine_version", sa.String(length=80), nullable=False),
        sa.Column("geometry_engine_version", sa.String(length=160), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("issues", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["floor_plan_editor_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_editor_validation_document_revision",
        "floor_plan_editor_validation_results",
        ["document_id", "revision", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_floor_plan_editor_validation_results_document_id"),
        "floor_plan_editor_validation_results",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_floor_plan_editor_validation_results_organization_id"),
        "floor_plan_editor_validation_results",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "floor_plan_editor_checkpoints",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_revision", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("snapshot_hash", sa.String(length=64), nullable=False),
        sa.Column("validation_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("source_revision >= 0", name="checkpoint_revision_non_negative"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["floor_plan_editor_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_editor_checkpoints_document_created",
        "floor_plan_editor_checkpoints",
        ["document_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_editor_checkpoints_project_created",
        "floor_plan_editor_checkpoints",
        ["project_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_floor_plan_editor_checkpoints_document_id"),
        "floor_plan_editor_checkpoints",
        ["document_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_floor_plan_editor_checkpoints_organization_id"),
        "floor_plan_editor_checkpoints",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "floor_plan_editor_audit_events",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["document_id"], ["floor_plan_editor_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_editor_audit_document_created",
        "floor_plan_editor_audit_events",
        ["document_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_editor_audit_project_created",
        "floor_plan_editor_audit_events",
        ["project_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_floor_plan_editor_audit_events_organization_id"),
        "floor_plan_editor_audit_events",
        ["organization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_floor_plan_editor_audit_events_organization_id"), table_name="floor_plan_editor_audit_events")
    op.drop_index("ix_editor_audit_project_created", table_name="floor_plan_editor_audit_events")
    op.drop_index("ix_editor_audit_document_created", table_name="floor_plan_editor_audit_events")
    op.drop_table("floor_plan_editor_audit_events")
    op.drop_index(op.f("ix_floor_plan_editor_checkpoints_organization_id"), table_name="floor_plan_editor_checkpoints")
    op.drop_index(op.f("ix_floor_plan_editor_checkpoints_document_id"), table_name="floor_plan_editor_checkpoints")
    op.drop_index("ix_editor_checkpoints_project_created", table_name="floor_plan_editor_checkpoints")
    op.drop_index("ix_editor_checkpoints_document_created", table_name="floor_plan_editor_checkpoints")
    op.drop_table("floor_plan_editor_checkpoints")
    op.drop_index(op.f("ix_floor_plan_editor_validation_results_organization_id"), table_name="floor_plan_editor_validation_results")
    op.drop_index(op.f("ix_floor_plan_editor_validation_results_document_id"), table_name="floor_plan_editor_validation_results")
    op.drop_index("ix_editor_validation_document_revision", table_name="floor_plan_editor_validation_results")
    op.drop_table("floor_plan_editor_validation_results")
    op.drop_index(op.f("ix_floor_plan_editor_operation_batches_organization_id"), table_name="floor_plan_editor_operation_batches")
    op.drop_index(op.f("ix_floor_plan_editor_operation_batches_document_id"), table_name="floor_plan_editor_operation_batches")
    op.drop_index("ix_editor_batches_document_revision", table_name="floor_plan_editor_operation_batches")
    op.drop_table("floor_plan_editor_operation_batches")
    op.drop_index(op.f("ix_floor_plan_editor_documents_organization_id"), table_name="floor_plan_editor_documents")
    op.drop_index("ix_editor_documents_org_active", table_name="floor_plan_editor_documents", postgresql_where=sa.text("deleted_at is null"))
    op.drop_table("floor_plan_editor_documents")
