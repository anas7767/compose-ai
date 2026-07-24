"""Add floor plan version management metadata.

Revision ID: 2026_07_18_0008
Revises: 2026_07_18_0007
Create Date: 2026-07-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2026_07_18_0008"
down_revision: str | None = "2026_07_18_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint(
        "uq_floor_plan_design_source_option",
        "floor_plan_design_versions",
        type_="unique",
    )
    op.add_column(
        "floor_plan_design_versions",
        sa.Column("restored_from_design_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "floor_plan_design_versions",
        sa.Column(
            "version_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )
    op.add_column(
        "floor_plan_design_versions",
        sa.Column("source_provider", sa.String(length=32), server_default="unknown", nullable=False),
    )
    op.add_column(
        "floor_plan_design_versions",
        sa.Column("source_model", sa.String(length=120), server_default="unknown", nullable=False),
    )
    op.add_column(
        "floor_plan_design_versions",
        sa.Column("generation_cost_microusd", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.add_column(
        "floor_plan_design_versions",
        sa.Column("generation_time_ms", sa.Integer(), nullable=True),
    )
    op.add_column(
        "floor_plan_design_versions",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_floor_plan_design_restored_from",
        "floor_plan_design_versions",
        "floor_plan_design_versions",
        ["restored_from_design_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_floor_plan_design_project_active",
        "floor_plan_design_versions",
        ["project_id", "version"],
        unique=False,
        postgresql_where=sa.text("deleted_at is null"),
    )
    op.alter_column("floor_plan_design_versions", "version_metadata", server_default=None)
    op.alter_column("floor_plan_design_versions", "source_provider", server_default=None)
    op.alter_column("floor_plan_design_versions", "source_model", server_default=None)
    op.alter_column("floor_plan_design_versions", "generation_cost_microusd", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_floor_plan_design_project_active", table_name="floor_plan_design_versions")
    op.drop_constraint(
        "fk_floor_plan_design_restored_from",
        "floor_plan_design_versions",
        type_="foreignkey",
    )
    op.drop_column("floor_plan_design_versions", "deleted_at")
    op.drop_column("floor_plan_design_versions", "generation_time_ms")
    op.drop_column("floor_plan_design_versions", "generation_cost_microusd")
    op.drop_column("floor_plan_design_versions", "source_model")
    op.drop_column("floor_plan_design_versions", "source_provider")
    op.drop_column("floor_plan_design_versions", "version_metadata")
    op.drop_column("floor_plan_design_versions", "restored_from_design_version_id")
    op.create_unique_constraint(
        "uq_floor_plan_design_source_option",
        "floor_plan_design_versions",
        ["source_option_id"],
    )
