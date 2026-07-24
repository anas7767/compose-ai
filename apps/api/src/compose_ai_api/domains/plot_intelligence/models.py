from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
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


class CoordinateSpace(StrEnum):
    LOCAL_CARTESIAN = "local_cartesian"
    WGS84 = "wgs84"


class NorthReference(StrEnum):
    TRUE = "true"
    MAGNETIC = "magnetic"
    ASSUMED = "assumed"


class BoundarySource(StrEnum):
    MANUAL_VERTICES = "manual_vertices"
    GEOJSON_IMPORT = "geojson_import"
    RESTORE = "restore"
    UNDO = "undo"
    CLEAR = "clear"


class PlotRoadSide(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "project_plot_road_sides"
    __table_args__ = (
        CheckConstraint(
            "boundary_edge_index is null or boundary_edge_index >= 0",
            name="boundary_edge_index_non_negative",
        ),
        CheckConstraint("road_width_m is null or road_width_m > 0", name="road_width_positive"),
        CheckConstraint("sort_order between 0 and 3", name="sort_order_range"),
        Index("ix_project_plot_road_sides_project_active", "project_id", "sort_order"),
        Index(
            "uq_project_plot_road_sides_primary_active",
            "project_id",
            unique=True,
            postgresql_where=text("is_primary and deleted_at is null"),
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    boundary_edge_index: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    label: Mapped[str] = mapped_column(String(40), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    is_primary: Mapped[bool] = mapped_column(nullable=False, default=False)
    road_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    road_width_m: Mapped[Decimal | None] = mapped_column(Numeric(10, 3), nullable=True)
    access_allowed: Mapped[bool] = mapped_column(nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)


class PlotBoundaryVersion(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "plot_boundary_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_plot_boundary_versions_project_version"),
        CheckConstraint("version > 0", name="version_positive"),
        CheckConstraint("schema_version > 0", name="schema_version_positive"),
        CheckConstraint("vertex_count >= 0", name="vertex_count_non_negative"),
        CheckConstraint("area_m2 is null or area_m2 > 0", name="area_positive"),
        CheckConstraint("perimeter_m is null or perimeter_m > 0", name="perimeter_positive"),
        Index("ix_plot_boundary_versions_project_created", "project_id", "created_at", "id"),
        Index("ix_plot_boundary_versions_project_checksum", "project_id", "checksum"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_boundary_version_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("plot_boundary_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    restored_from_version_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("plot_boundary_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    coordinate_space: Mapped[str] = mapped_column(String(24), nullable=False)
    normalized_geojson: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_tombstone: Mapped[bool] = mapped_column(nullable=False, default=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    geometry_engine_version: Mapped[str] = mapped_column(String(120), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    vertex_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    area_m2: Mapped[Decimal | None] = mapped_column(Numeric(16, 3), nullable=True)
    perimeter_m: Mapped[Decimal | None] = mapped_column(Numeric(16, 3), nullable=True)
    bounding_box: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    centroid: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(24), nullable=False)
    validation_details: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PlotAnalysisSnapshot(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "plot_analysis_snapshots"
    __table_args__ = (
        CheckConstraint("profile_revision > 0", name="profile_revision_positive"),
        CheckConstraint("plot_completeness between 0 and 100", name="plot_completeness_range"),
        CheckConstraint("plot_health_score between 0 and 100", name="plot_health_score_range"),
        Index("ix_plot_analysis_snapshots_project_created", "project_id", "created_at", "id"),
        Index("ix_plot_analysis_snapshots_project_input", "project_id", "input_checksum"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    boundary_version_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("plot_boundary_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    profile_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    analysis_engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    geometry_engine_version: Mapped[str] = mapped_column(String(120), nullable=False)
    input_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    plot_completeness: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    plot_health_score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    plot_health_status: Mapped[str] = mapped_column(String(24), nullable=False)
    feasibility_status: Mapped[str] = mapped_column(String(32), nullable=False)
    pre_regulation_buildable_area_m2: Mapped[Decimal | None] = mapped_column(
        Numeric(16, 3), nullable=True
    )
    parking_status: Mapped[str] = mapped_column(String(24), nullable=False)
    parking_confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    parking_details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    coverage_status: Mapped[str] = mapped_column(String(40), nullable=False)
    coverage_details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    regulation_status: Mapped[str] = mapped_column(String(24), nullable=False)
    regulation_context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    validation_issues: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list
    )
    validation_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    site_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PlotBoundaryRestoreAction(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "plot_boundary_restore_actions"
    __table_args__ = (
        Index("ix_plot_boundary_restore_actions_project_created", "project_id", "created_at"),
        Index("ix_plot_boundary_restore_actions_expires", "expires_at"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    restored_boundary_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("plot_boundary_versions.id", ondelete="CASCADE"),
        nullable=False,
    )
    previous_active_boundary_version_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("plot_boundary_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    undone_by_boundary_version_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("plot_boundary_versions.id", ondelete="SET NULL"),
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
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
