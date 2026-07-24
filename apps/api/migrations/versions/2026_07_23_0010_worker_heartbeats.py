"""worker heartbeats

Revision ID: 2026_07_23_0010
Revises: 2026_07_18_0009
Create Date: 2026-07-23 17:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "2026_07_23_0010"
down_revision: str | None = "2026_07_18_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_kind", sa.String(length=40), nullable=False),
        sa.Column("worker_id", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column(
            "last_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("heartbeat_interval_seconds", sa.Integer(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("heartbeat_interval_seconds > 0", name="heartbeat_interval_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("worker_kind", "worker_id", name="uq_worker_heartbeats_kind_id"),
    )
    op.create_index(
        "ix_worker_heartbeats_kind_seen",
        "worker_heartbeats",
        ["worker_kind", "last_seen_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_worker_heartbeats_kind_seen", table_name="worker_heartbeats")
    op.drop_table("worker_heartbeats")
