"""project system

Revision ID: 202607120002
Revises: 202607110001
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202607120002"
down_revision: str | None = "202607110001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="draft", nullable=False),
        sa.Column("project_type", sa.String(length=40), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit_system", sa.String(length=16), server_default="metric", nullable=False),
        sa.Column("currency", sa.String(length=3), server_default="USD", nullable=False),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("wizard_step", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deleted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("duplicate_source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "thumbnail_source", sa.String(length=32), server_default="placeholder", nullable=False
        ),
        sa.Column("thumbnail_storage_key", sa.String(length=1024), nullable=True),
        sa.Column("thumbnail_mime_type", sa.String(length=100), nullable=True),
        sa.Column("thumbnail_width", sa.Integer(), nullable=True),
        sa.Column("thumbnail_height", sa.Integer(), nullable=True),
        sa.Column("thumbnail_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("thumbnail_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "thumbnail_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("updated_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version > 0", name=op.f("ck_projects_version_positive")),
        sa.CheckConstraint(
            "wizard_step between 1 and 5", name=op.f("ck_projects_wizard_step_range")
        ),
        sa.ForeignKeyConstraint(
            ["archived_by"],
            ["users.id"],
            name=op.f("fk_projects_archived_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_projects_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["deleted_by"],
            ["users.id"],
            name=op.f("fk_projects_deleted_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["duplicate_source_id"],
            ["projects.id"],
            name=op.f("fk_projects_duplicate_source_id_projects"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_projects_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"],
            ["users.id"],
            name=op.f("fk_projects_updated_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
    )
    op.create_index(op.f("ix_projects_country"), "projects", ["country"], unique=False)
    op.create_index(
        op.f("ix_projects_duplicate_source_id"), "projects", ["duplicate_source_id"], unique=False
    )
    op.create_index(
        op.f("ix_projects_organization_id"), "projects", ["organization_id"], unique=False
    )
    op.create_index(op.f("ix_projects_project_type"), "projects", ["project_type"], unique=False)
    op.create_index(op.f("ix_projects_status"), "projects", ["status"], unique=False)
    op.create_index(
        "ix_projects_org_status_updated",
        "projects",
        ["organization_id", "status", "updated_at", "id"],
        unique=False,
        postgresql_where=sa.text("deleted_at is null"),
    )
    op.create_index(
        "ix_projects_org_visible_updated",
        "projects",
        ["organization_id", "updated_at", "id"],
        unique=False,
        postgresql_where=sa.text("deleted_at is null"),
    )
    op.create_index(
        "ix_projects_org_deleted_updated",
        "projects",
        ["organization_id", "updated_at", "id"],
        unique=False,
        postgresql_where=sa.text("deleted_at is not null"),
    )

    op.create_table(
        "project_clients",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=True),
        sa.Column("company", sa.String(length=160), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_clients_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("project_id", name=op.f("pk_project_clients")),
    )

    op.create_table(
        "project_sites",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plot_length", sa.Numeric(precision=14, scale=3), nullable=True),
        sa.Column("plot_width", sa.Numeric(precision=14, scale=3), nullable=True),
        sa.Column("plot_area", sa.Numeric(precision=16, scale=3), nullable=True),
        sa.Column("plot_shape", sa.String(length=24), nullable=True),
        sa.Column("road_direction_primary", sa.String(length=16), nullable=True),
        sa.Column("road_direction_secondary", sa.String(length=16), nullable=True),
        sa.Column("open_sides", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("corner_plot", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("address_line_1", sa.String(length=255), nullable=True),
        sa.Column("address_line_2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("region", sa.String(length=120), nullable=True),
        sa.Column("postal_code", sa.String(length=32), nullable=True),
        sa.Column("latitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("longitude", sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column("boundary_geojson", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("boundary_schema_version", sa.SmallInteger(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "latitude is null or latitude between -90 and 90",
            name=op.f("ck_project_sites_latitude_range"),
        ),
        sa.CheckConstraint(
            "longitude is null or longitude between -180 and 180",
            name=op.f("ck_project_sites_longitude_range"),
        ),
        sa.CheckConstraint(
            "open_sides between 0 and 4", name=op.f("ck_project_sites_open_sides_range")
        ),
        sa.CheckConstraint(
            "plot_area is null or plot_area > 0",
            name=op.f("ck_project_sites_plot_area_positive"),
        ),
        sa.CheckConstraint(
            "plot_length is null or plot_length > 0",
            name=op.f("ck_project_sites_plot_length_positive"),
        ),
        sa.CheckConstraint(
            "plot_width is null or plot_width > 0",
            name=op.f("ck_project_sites_plot_width_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_sites_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("project_id", name=op.f("pk_project_sites")),
    )

    op.create_table(
        "project_requirements",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bedrooms", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column(
            "bathrooms", sa.Numeric(precision=4, scale=1), server_default="0", nullable=False
        ),
        sa.Column("floors", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("parking_spaces", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("budget", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("construction_quality", sa.String(length=24), nullable=True),
        sa.Column("preferred_style", sa.String(length=80), nullable=True),
        sa.Column(
            "vastu_preference", sa.String(length=24), server_default="not_required", nullable=False
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "bathrooms between 0 and 50", name=op.f("ck_project_requirements_bathrooms_range")
        ),
        sa.CheckConstraint(
            "bedrooms between 0 and 50", name=op.f("ck_project_requirements_bedrooms_range")
        ),
        sa.CheckConstraint(
            "budget is null or budget >= 0",
            name=op.f("ck_project_requirements_budget_non_negative"),
        ),
        sa.CheckConstraint(
            "floors between 1 and 100", name=op.f("ck_project_requirements_floors_range")
        ),
        sa.CheckConstraint(
            "parking_spaces between 0 and 100",
            name=op.f("ck_project_requirements_parking_range"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_requirements_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("project_id", name=op.f("pk_project_requirements")),
    )

    op.create_table(
        "project_room_requirements",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("room_type", sa.String(length=80), nullable=True),
        sa.Column("quantity", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("preferred_floor", sa.SmallInteger(), nullable=True),
        sa.Column("minimum_area", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("sort_order", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "minimum_area is null or minimum_area > 0",
            name=op.f("ck_project_room_requirements_minimum_area_positive"),
        ),
        sa.CheckConstraint(
            "quantity between 1 and 20",
            name=op.f("ck_project_room_requirements_quantity_range"),
        ),
        sa.CheckConstraint(
            "sort_order >= 0",
            name=op.f("ck_project_room_requirements_sort_order_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_room_requirements_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_room_requirements")),
    )
    op.create_index(
        op.f("ix_project_room_requirements_project_id"),
        "project_room_requirements",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_room_requirements_project_sort",
        "project_room_requirements",
        ["project_id", "sort_order"],
        unique=False,
    )

    op.create_table(
        "tags",
        sa.Column("normalized_name", sa.String(length=30), nullable=False),
        sa.Column("display_name", sa.String(length=30), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_tags_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tags")),
        sa.UniqueConstraint(
            "organization_id", "normalized_name", name="uq_tags_org_normalized_name"
        ),
    )
    op.create_index(op.f("ix_tags_organization_id"), "tags", ["organization_id"], unique=False)
    op.create_index(
        "ix_tags_org_display_name", "tags", ["organization_id", "display_name"], unique=False
    )

    op.create_table(
        "project_tag_assignments",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_tag_assignments_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
            name=op.f("fk_project_tag_assignments_tag_id_tags"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("project_id", "tag_id", name=op.f("pk_project_tag_assignments")),
    )

    op.create_table(
        "audit_logs",
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("entity_type", sa.String(length=80), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("before_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_audit_logs_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_audit_logs_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_logs")),
    )
    op.create_index(op.f("ix_audit_logs_action"), "audit_logs", ["action"], unique=False)
    op.create_index(
        op.f("ix_audit_logs_actor_user_id"), "audit_logs", ["actor_user_id"], unique=False
    )
    op.create_index(
        op.f("ix_audit_logs_organization_id"), "audit_logs", ["organization_id"], unique=False
    )
    op.create_index(
        "ix_audit_logs_org_created",
        "audit_logs",
        ["organization_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_audit_logs_entity_created",
        "audit_logs",
        ["entity_type", "entity_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "idempotency_records",
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.SmallInteger(), nullable=False),
        sa.Column("response_body", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_idempotency_records_actor_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_idempotency_records_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_idempotency_records")),
        sa.UniqueConstraint(
            "organization_id",
            "actor_user_id",
            "scope",
            "idempotency_key",
            name="uq_idempotency_org_actor_scope_key",
        ),
    )
    op.create_index(
        op.f("ix_idempotency_records_organization_id"),
        "idempotency_records",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_idempotency_records_expires_at",
        "idempotency_records",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_idempotency_records_expires_at", table_name="idempotency_records")
    op.drop_index(op.f("ix_idempotency_records_organization_id"), table_name="idempotency_records")
    op.drop_table("idempotency_records")
    op.drop_index("ix_audit_logs_entity_created", table_name="audit_logs")
    op.drop_index("ix_audit_logs_org_created", table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_organization_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_actor_user_id"), table_name="audit_logs")
    op.drop_index(op.f("ix_audit_logs_action"), table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_table("project_tag_assignments")
    op.drop_index("ix_tags_org_display_name", table_name="tags")
    op.drop_index(op.f("ix_tags_organization_id"), table_name="tags")
    op.drop_table("tags")
    op.drop_index(
        "ix_project_room_requirements_project_sort", table_name="project_room_requirements"
    )
    op.drop_index(
        op.f("ix_project_room_requirements_project_id"),
        table_name="project_room_requirements",
    )
    op.drop_table("project_room_requirements")
    op.drop_table("project_requirements")
    op.drop_table("project_sites")
    op.drop_table("project_clients")
    op.drop_index("ix_projects_org_deleted_updated", table_name="projects")
    op.drop_index("ix_projects_org_visible_updated", table_name="projects")
    op.drop_index("ix_projects_org_status_updated", table_name="projects")
    op.drop_index(op.f("ix_projects_status"), table_name="projects")
    op.drop_index(op.f("ix_projects_project_type"), table_name="projects")
    op.drop_index(op.f("ix_projects_organization_id"), table_name="projects")
    op.drop_index(op.f("ix_projects_duplicate_source_id"), table_name="projects")
    op.drop_index(op.f("ix_projects_country"), table_name="projects")
    op.drop_table("projects")
