"""plot intelligence

Revision ID: 202607120003
Revises: 202607120002
Create Date: 2026-07-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202607120003"
down_revision: str | None = "202607120002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_plot_road_sides",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("boundary_edge_index", sa.SmallInteger(), nullable=True),
        sa.Column("label", sa.String(length=40), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("road_name", sa.String(length=120), nullable=True),
        sa.Column("road_width_m", sa.Numeric(precision=10, scale=3), nullable=True),
        sa.Column("access_allowed", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "boundary_edge_index is null or boundary_edge_index >= 0",
            name=op.f("ck_project_plot_road_sides_boundary_edge_index_non_negative"),
        ),
        sa.CheckConstraint(
            "road_width_m is null or road_width_m > 0",
            name=op.f("ck_project_plot_road_sides_road_width_positive"),
        ),
        sa.CheckConstraint(
            "sort_order between 0 and 3",
            name=op.f("ck_project_plot_road_sides_sort_order_range"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_project_plot_road_sides_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_project_plot_road_sides_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_project_plot_road_sides")),
    )
    op.create_index(
        op.f("ix_project_plot_road_sides_organization_id"),
        "project_plot_road_sides",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_plot_road_sides_project_id"),
        "project_plot_road_sides",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_project_plot_road_sides_project_active",
        "project_plot_road_sides",
        ["project_id", "sort_order"],
        unique=False,
    )
    op.create_index(
        "uq_project_plot_road_sides_primary_active",
        "project_plot_road_sides",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("is_primary and deleted_at is null"),
    )

    op.create_table(
        "plot_boundary_versions",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("previous_boundary_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("restored_from_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("coordinate_space", sa.String(length=24), nullable=False),
        sa.Column("normalized_geojson", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_tombstone", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("geometry_engine_version", sa.String(length=120), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("vertex_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("area_m2", sa.Numeric(precision=16, scale=3), nullable=True),
        sa.Column("perimeter_m", sa.Numeric(precision=16, scale=3), nullable=True),
        sa.Column("bounding_box", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("centroid", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validation_status", sa.String(length=24), nullable=False),
        sa.Column(
            "validation_details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "area_m2 is null or area_m2 > 0",
            name=op.f("ck_plot_boundary_versions_area_positive"),
        ),
        sa.CheckConstraint(
            "perimeter_m is null or perimeter_m > 0",
            name=op.f("ck_plot_boundary_versions_perimeter_positive"),
        ),
        sa.CheckConstraint(
            "schema_version > 0",
            name=op.f("ck_plot_boundary_versions_schema_version_positive"),
        ),
        sa.CheckConstraint("version > 0", name=op.f("ck_plot_boundary_versions_version_positive")),
        sa.CheckConstraint(
            "vertex_count >= 0",
            name=op.f("ck_plot_boundary_versions_vertex_count_non_negative"),
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_plot_boundary_versions_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_plot_boundary_versions_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["previous_boundary_version_id"],
            ["plot_boundary_versions.id"],
            name=op.f(
                "fk_plot_boundary_versions_previous_boundary_version_id_plot_boundary_versions"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_plot_boundary_versions_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["restored_from_version_id"],
            ["plot_boundary_versions.id"],
            name=op.f("fk_plot_boundary_versions_restored_from_version_id_plot_boundary_versions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plot_boundary_versions")),
        sa.UniqueConstraint(
            "project_id", "version", name="uq_plot_boundary_versions_project_version"
        ),
    )
    op.create_index(
        op.f("ix_plot_boundary_versions_organization_id"),
        "plot_boundary_versions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_plot_boundary_versions_project_id"),
        "plot_boundary_versions",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_plot_boundary_versions_project_created",
        "plot_boundary_versions",
        ["project_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_plot_boundary_versions_project_checksum",
        "plot_boundary_versions",
        ["project_id", "checksum"],
        unique=False,
    )

    op.create_table(
        "plot_analysis_snapshots",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("boundary_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("profile_revision", sa.Integer(), nullable=False),
        sa.Column("analysis_engine_version", sa.String(length=80), nullable=False),
        sa.Column("geometry_engine_version", sa.String(length=120), nullable=False),
        sa.Column("input_checksum", sa.String(length=64), nullable=False),
        sa.Column("plot_completeness", sa.SmallInteger(), nullable=False),
        sa.Column("plot_health_score", sa.SmallInteger(), nullable=False),
        sa.Column("plot_health_status", sa.String(length=24), nullable=False),
        sa.Column("feasibility_status", sa.String(length=32), nullable=False),
        sa.Column(
            "pre_regulation_buildable_area_m2",
            sa.Numeric(precision=16, scale=3),
            nullable=True,
        ),
        sa.Column("parking_status", sa.String(length=24), nullable=False),
        sa.Column("parking_confidence", sa.String(length=16), nullable=False),
        sa.Column(
            "parking_details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("coverage_status", sa.String(length=40), nullable=False),
        sa.Column(
            "coverage_details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("regulation_status", sa.String(length=24), nullable=False),
        sa.Column(
            "regulation_context",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "validation_issues",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "validation_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "site_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.CheckConstraint(
            "plot_completeness between 0 and 100",
            name=op.f("ck_plot_analysis_snapshots_plot_completeness_range"),
        ),
        sa.CheckConstraint(
            "plot_health_score between 0 and 100",
            name=op.f("ck_plot_analysis_snapshots_plot_health_score_range"),
        ),
        sa.CheckConstraint(
            "profile_revision > 0",
            name=op.f("ck_plot_analysis_snapshots_profile_revision_positive"),
        ),
        sa.ForeignKeyConstraint(
            ["boundary_version_id"],
            ["plot_boundary_versions.id"],
            name=op.f("fk_plot_analysis_snapshots_boundary_version_id_plot_boundary_versions"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_plot_analysis_snapshots_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_plot_analysis_snapshots_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_plot_analysis_snapshots_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plot_analysis_snapshots")),
    )
    op.create_index(
        op.f("ix_plot_analysis_snapshots_organization_id"),
        "plot_analysis_snapshots",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_plot_analysis_snapshots_project_id"),
        "plot_analysis_snapshots",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_plot_analysis_snapshots_project_created",
        "plot_analysis_snapshots",
        ["project_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_plot_analysis_snapshots_project_input",
        "plot_analysis_snapshots",
        ["project_id", "input_checksum"],
        unique=False,
    )

    op.create_table(
        "plot_boundary_restore_actions",
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("restored_boundary_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "previous_active_boundary_version_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("undone_by_boundary_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_plot_boundary_restore_actions_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_plot_boundary_restore_actions_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["previous_active_boundary_version_id"],
            ["plot_boundary_versions.id"],
            name=op.f(
                "fk_plot_boundary_restore_actions_previous_active_boundary_version_id_plot_boundary_versions"
            ),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
            name=op.f("fk_plot_boundary_restore_actions_project_id_projects"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["restored_boundary_version_id"],
            ["plot_boundary_versions.id"],
            name=op.f(
                "fk_plot_boundary_restore_actions_restored_boundary_version_id_plot_boundary_versions"
            ),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["undone_by_boundary_version_id"],
            ["plot_boundary_versions.id"],
            name=op.f(
                "fk_plot_boundary_restore_actions_undone_by_boundary_version_id_plot_boundary_versions"
            ),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plot_boundary_restore_actions")),
    )
    op.create_index(
        op.f("ix_plot_boundary_restore_actions_organization_id"),
        "plot_boundary_restore_actions",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_plot_boundary_restore_actions_project_id"),
        "plot_boundary_restore_actions",
        ["project_id"],
        unique=False,
    )
    op.create_index(
        "ix_plot_boundary_restore_actions_project_created",
        "plot_boundary_restore_actions",
        ["project_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_plot_boundary_restore_actions_expires",
        "plot_boundary_restore_actions",
        ["expires_at"],
        unique=False,
    )

    _add_project_site_columns()
    _convert_existing_site_values_to_si()


def _add_project_site_columns() -> None:
    op.add_column(
        "project_sites",
        sa.Column("profile_revision", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "project_sites",
        sa.Column("area_source", sa.String(length=24), server_default="unknown", nullable=False),
    )
    op.add_column(
        "project_sites",
        sa.Column("orientation_degrees", sa.Numeric(precision=6, scale=3), nullable=True),
    )
    op.add_column(
        "project_sites",
        sa.Column("north_rotation_degrees", sa.Numeric(precision=6, scale=3), nullable=True),
    )
    op.add_column(
        "project_sites", sa.Column("north_reference", sa.String(length=16), nullable=True)
    )
    op.add_column(
        "project_sites",
        sa.Column("current_boundary_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "project_sites",
        sa.Column("current_analysis_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "project_sites",
        sa.Column("plot_completeness", sa.SmallInteger(), server_default="0", nullable=False),
    )
    op.add_column(
        "project_sites",
        sa.Column("plot_health_score", sa.SmallInteger(), server_default="0", nullable=False),
    )
    op.add_column(
        "project_sites",
        sa.Column(
            "plot_health_status",
            sa.String(length=24),
            server_default="insufficient_data",
            nullable=False,
        ),
    )
    op.add_column(
        "project_sites",
        sa.Column(
            "plot_feasibility_status",
            sa.String(length=32),
            server_default="insufficient_data",
            nullable=False,
        ),
    )
    op.add_column(
        "project_sites",
        sa.Column(
            "plot_validation_error_count", sa.SmallInteger(), server_default="0", nullable=False
        ),
    )
    op.add_column(
        "project_sites",
        sa.Column(
            "plot_validation_warning_count",
            sa.SmallInteger(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "project_sites",
        sa.Column(
            "pre_regulation_buildable_area_m2",
            sa.Numeric(precision=16, scale=3),
            nullable=True,
        ),
    )
    op.add_column(
        "project_sites",
        sa.Column(
            "parking_feasibility_status",
            sa.String(length=24),
            server_default="indeterminate",
            nullable=False,
        ),
    )
    op.add_column(
        "project_sites", sa.Column("analysis_updated_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_check_constraint(
        op.f("ck_project_sites_profile_revision_positive"),
        "project_sites",
        "profile_revision > 0",
    )
    op.create_check_constraint(
        op.f("ck_project_sites_orientation_degrees_range"),
        "project_sites",
        "orientation_degrees is null or (orientation_degrees >= 0 and orientation_degrees < 360)",
    )
    op.create_check_constraint(
        op.f("ck_project_sites_north_rotation_degrees_range"),
        "project_sites",
        "north_rotation_degrees is null or "
        "(north_rotation_degrees >= 0 and north_rotation_degrees < 360)",
    )
    op.create_check_constraint(
        op.f("ck_project_sites_plot_completeness_range"),
        "project_sites",
        "plot_completeness between 0 and 100",
    )
    op.create_check_constraint(
        op.f("ck_project_sites_plot_health_score_range"),
        "project_sites",
        "plot_health_score between 0 and 100",
    )
    op.create_foreign_key(
        op.f("fk_project_sites_current_boundary_version_id_plot_boundary_versions"),
        "project_sites",
        "plot_boundary_versions",
        ["current_boundary_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        op.f("fk_project_sites_current_analysis_id_plot_analysis_snapshots"),
        "project_sites",
        "plot_analysis_snapshots",
        ["current_analysis_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        op.f("ix_project_sites_current_boundary_version_id"),
        "project_sites",
        ["current_boundary_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_project_sites_current_analysis_id"),
        "project_sites",
        ["current_analysis_id"],
        unique=False,
    )


def _convert_existing_site_values_to_si() -> None:
    op.execute(
        """
        UPDATE project_sites AS site
        SET
            plot_length = CASE
                WHEN project.unit_system = 'imperial' AND site.plot_length IS NOT NULL
                    THEN site.plot_length * 0.3048
                ELSE site.plot_length
            END,
            plot_width = CASE
                WHEN project.unit_system = 'imperial' AND site.plot_width IS NOT NULL
                    THEN site.plot_width * 0.3048
                ELSE site.plot_width
            END,
            plot_area = CASE
                WHEN project.unit_system = 'imperial' AND site.plot_area IS NOT NULL
                    THEN site.plot_area * 0.09290304
                ELSE site.plot_area
            END,
            area_source = CASE
                WHEN site.plot_area IS NOT NULL THEN 'declared'
                ELSE 'unknown'
            END
        FROM projects AS project
        WHERE project.id = site.project_id
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE project_sites AS site
        SET
            plot_length = CASE
                WHEN project.unit_system = 'imperial' AND site.plot_length IS NOT NULL
                    THEN site.plot_length / 0.3048
                ELSE site.plot_length
            END,
            plot_width = CASE
                WHEN project.unit_system = 'imperial' AND site.plot_width IS NOT NULL
                    THEN site.plot_width / 0.3048
                ELSE site.plot_width
            END,
            plot_area = CASE
                WHEN project.unit_system = 'imperial' AND site.plot_area IS NOT NULL
                    THEN site.plot_area / 0.09290304
                ELSE site.plot_area
            END
        FROM projects AS project
        WHERE project.id = site.project_id
        """
    )
    op.drop_index(op.f("ix_project_sites_current_analysis_id"), table_name="project_sites")
    op.drop_index(op.f("ix_project_sites_current_boundary_version_id"), table_name="project_sites")
    op.drop_constraint(
        op.f("fk_project_sites_current_analysis_id_plot_analysis_snapshots"),
        "project_sites",
        type_="foreignkey",
    )
    op.drop_constraint(
        op.f("fk_project_sites_current_boundary_version_id_plot_boundary_versions"),
        "project_sites",
        type_="foreignkey",
    )
    for constraint in (
        "plot_health_score_range",
        "plot_completeness_range",
        "north_rotation_degrees_range",
        "orientation_degrees_range",
        "profile_revision_positive",
    ):
        op.drop_constraint(op.f(f"ck_project_sites_{constraint}"), "project_sites", type_="check")
    for column in (
        "analysis_updated_at",
        "parking_feasibility_status",
        "pre_regulation_buildable_area_m2",
        "plot_validation_warning_count",
        "plot_validation_error_count",
        "plot_feasibility_status",
        "plot_health_status",
        "plot_health_score",
        "plot_completeness",
        "current_analysis_id",
        "current_boundary_version_id",
        "north_reference",
        "north_rotation_degrees",
        "orientation_degrees",
        "area_source",
        "profile_revision",
    ):
        op.drop_column("project_sites", column)

    op.drop_index(
        "ix_plot_boundary_restore_actions_expires", table_name="plot_boundary_restore_actions"
    )
    op.drop_index(
        "ix_plot_boundary_restore_actions_project_created",
        table_name="plot_boundary_restore_actions",
    )
    op.drop_index(
        op.f("ix_plot_boundary_restore_actions_project_id"),
        table_name="plot_boundary_restore_actions",
    )
    op.drop_index(
        op.f("ix_plot_boundary_restore_actions_organization_id"),
        table_name="plot_boundary_restore_actions",
    )
    op.drop_table("plot_boundary_restore_actions")
    op.drop_index("ix_plot_analysis_snapshots_project_input", table_name="plot_analysis_snapshots")
    op.drop_index(
        "ix_plot_analysis_snapshots_project_created", table_name="plot_analysis_snapshots"
    )
    op.drop_index(
        op.f("ix_plot_analysis_snapshots_project_id"), table_name="plot_analysis_snapshots"
    )
    op.drop_index(
        op.f("ix_plot_analysis_snapshots_organization_id"),
        table_name="plot_analysis_snapshots",
    )
    op.drop_table("plot_analysis_snapshots")
    op.drop_index("ix_plot_boundary_versions_project_checksum", table_name="plot_boundary_versions")
    op.drop_index("ix_plot_boundary_versions_project_created", table_name="plot_boundary_versions")
    op.drop_index(op.f("ix_plot_boundary_versions_project_id"), table_name="plot_boundary_versions")
    op.drop_index(
        op.f("ix_plot_boundary_versions_organization_id"),
        table_name="plot_boundary_versions",
    )
    op.drop_table("plot_boundary_versions")
    op.drop_index("uq_project_plot_road_sides_primary_active", table_name="project_plot_road_sides")
    op.drop_index("ix_project_plot_road_sides_project_active", table_name="project_plot_road_sides")
    op.drop_index(
        op.f("ix_project_plot_road_sides_project_id"), table_name="project_plot_road_sides"
    )
    op.drop_index(
        op.f("ix_project_plot_road_sides_organization_id"),
        table_name="project_plot_road_sides",
    )
    op.drop_table("project_plot_road_sides")
