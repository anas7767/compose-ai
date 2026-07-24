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
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from compose_ai_api.models.base import Base
from compose_ai_api.models.mixins import (
    AuditMixin,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
    UUIDPrimaryKeyMixin,
)


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ProjectType(StrEnum):
    RESIDENTIAL_HOUSE = "residential_house"
    VILLA = "villa"
    APARTMENT = "apartment"
    COMMERCIAL = "commercial"
    OFFICE = "office"
    RETAIL = "retail"
    HOSPITALITY = "hospitality"
    INSTITUTIONAL = "institutional"
    INDUSTRIAL = "industrial"
    RENOVATION = "renovation"
    INTERIOR_ONLY = "interior_only"
    LANDSCAPE = "landscape"
    OTHER = "other"


class UnitSystem(StrEnum):
    METRIC = "metric"
    IMPERIAL = "imperial"


class PlotShape(StrEnum):
    RECTANGLE = "rectangle"
    SQUARE = "square"
    L_SHAPED = "l_shaped"
    TRAPEZOID = "trapezoid"
    IRREGULAR = "irregular"
    OTHER = "other"


class RoadDirection(StrEnum):
    NORTH = "north"
    NORTHEAST = "northeast"
    EAST = "east"
    SOUTHEAST = "southeast"
    SOUTH = "south"
    SOUTHWEST = "southwest"
    WEST = "west"
    NORTHWEST = "northwest"


class ConstructionQuality(StrEnum):
    ECONOMY = "economy"
    STANDARD = "standard"
    PREMIUM = "premium"
    LUXURY = "luxury"


class VastuPreference(StrEnum):
    NOT_REQUIRED = "not_required"
    PREFERRED = "preferred"
    STRICT = "strict"


class ThumbnailSource(StrEnum):
    PLACEHOLDER = "placeholder"
    UPLOAD = "upload"
    AI_GENERATED = "ai_generated"
    FLOOR_PLAN = "floor_plan"
    RENDER = "render"


class Project(UUIDPrimaryKeyMixin, TenantMixin, AuditMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("wizard_step between 1 and 5", name="wizard_step_range"),
        CheckConstraint("version > 0", name="version_positive"),
        Index(
            "ix_projects_org_status_updated",
            "organization_id",
            "status",
            "updated_at",
            "id",
            postgresql_where=text("deleted_at is null"),
        ),
        Index(
            "ix_projects_org_visible_updated",
            "organization_id",
            "updated_at",
            "id",
            postgresql_where=text("deleted_at is null"),
        ),
        Index(
            "ix_projects_org_deleted_updated",
            "organization_id",
            "updated_at",
            "id",
            postgresql_where=text("deleted_at is not null"),
        ),
    )

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[ProjectStatus] = mapped_column(
        String(24), nullable=False, default=ProjectStatus.DRAFT, index=True
    )
    project_type: Mapped[ProjectType | None] = mapped_column(String(40), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    unit_system: Mapped[UnitSystem] = mapped_column(
        String(16), nullable=False, default=UnitSystem.METRIC
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    country: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    wizard_step: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    deleted_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    duplicate_source_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    thumbnail_source: Mapped[ThumbnailSource] = mapped_column(
        String(32), nullable=False, default=ThumbnailSource.PLACEHOLDER
    )
    thumbnail_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    thumbnail_mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    thumbnail_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    thumbnail_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    thumbnail_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    thumbnail_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    client: Mapped[ProjectClient | None] = relationship(
        back_populates="project", cascade="all, delete-orphan", uselist=False
    )
    site: Mapped[ProjectSite | None] = relationship(
        back_populates="project", cascade="all, delete-orphan", uselist=False
    )
    requirements: Mapped[ProjectRequirements | None] = relationship(
        back_populates="project", cascade="all, delete-orphan", uselist=False
    )
    room_requirements: Mapped[list[ProjectRoomRequirement]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="ProjectRoomRequirement.sort_order",
    )
    tag_assignments: Mapped[list[ProjectTagAssignment]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class ProjectClient(TimestampMixin, Base):
    __tablename__ = "project_clients"

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    company: Mapped[str | None] = mapped_column(String(160), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship(back_populates="client")


class ProjectSite(TimestampMixin, Base):
    __tablename__ = "project_sites"
    __table_args__ = (
        CheckConstraint("plot_length is null or plot_length > 0", name="plot_length_positive"),
        CheckConstraint("plot_width is null or plot_width > 0", name="plot_width_positive"),
        CheckConstraint("plot_area is null or plot_area > 0", name="plot_area_positive"),
        CheckConstraint("open_sides between 0 and 4", name="open_sides_range"),
        CheckConstraint("latitude is null or latitude between -90 and 90", name="latitude_range"),
        CheckConstraint(
            "longitude is null or longitude between -180 and 180", name="longitude_range"
        ),
        CheckConstraint("profile_revision > 0", name="profile_revision_positive"),
        CheckConstraint(
            "orientation_degrees is null or "
            "(orientation_degrees >= 0 and orientation_degrees < 360)",
            name="orientation_degrees_range",
        ),
        CheckConstraint(
            "north_rotation_degrees is null or "
            "(north_rotation_degrees >= 0 and north_rotation_degrees < 360)",
            name="north_rotation_degrees_range",
        ),
        CheckConstraint("plot_completeness between 0 and 100", name="plot_completeness_range"),
        CheckConstraint("plot_health_score between 0 and 100", name="plot_health_score_range"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    plot_length: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    plot_width: Mapped[Decimal | None] = mapped_column(Numeric(14, 3), nullable=True)
    plot_area: Mapped[Decimal | None] = mapped_column(Numeric(16, 3), nullable=True)
    plot_shape: Mapped[PlotShape | None] = mapped_column(String(24), nullable=True)
    road_direction_primary: Mapped[RoadDirection | None] = mapped_column(String(16), nullable=True)
    road_direction_secondary: Mapped[RoadDirection | None] = mapped_column(
        String(16), nullable=True
    )
    open_sides: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    corner_plot: Mapped[bool] = mapped_column(nullable=False, default=False)
    address_line_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    region: Mapped[str | None] = mapped_column(String(120), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6), nullable=True)
    boundary_geojson: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    boundary_schema_version: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    profile_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    area_source: Mapped[str] = mapped_column(String(24), nullable=False, default="unknown")
    orientation_degrees: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    north_rotation_degrees: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    north_reference: Mapped[str | None] = mapped_column(String(16), nullable=True)
    current_boundary_version_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("plot_boundary_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    current_analysis_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("plot_analysis_snapshots.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    plot_completeness: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    plot_health_score: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    plot_health_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="insufficient_data"
    )
    plot_feasibility_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="insufficient_data"
    )
    plot_validation_error_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0
    )
    plot_validation_warning_count: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, default=0
    )
    pre_regulation_buildable_area_m2: Mapped[Decimal | None] = mapped_column(
        Numeric(16, 3), nullable=True
    )
    parking_feasibility_status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="indeterminate"
    )
    analysis_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    project: Mapped[Project] = relationship(back_populates="site")


class ProjectRequirements(TimestampMixin, Base):
    __tablename__ = "project_requirements"
    __table_args__ = (
        CheckConstraint("bedrooms between 0 and 50", name="bedrooms_range"),
        CheckConstraint("bathrooms between 0 and 50", name="bathrooms_range"),
        CheckConstraint("floors between 1 and 100", name="floors_range"),
        CheckConstraint("parking_spaces between 0 and 100", name="parking_range"),
        CheckConstraint("budget is null or budget >= 0", name="budget_non_negative"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    bedrooms: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    bathrooms: Mapped[Decimal] = mapped_column(Numeric(4, 1), nullable=False, default=0)
    floors: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    parking_spaces: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    budget: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    construction_quality: Mapped[ConstructionQuality | None] = mapped_column(
        String(24), nullable=True
    )
    preferred_style: Mapped[str | None] = mapped_column(String(80), nullable=True)
    vastu_preference: Mapped[VastuPreference] = mapped_column(
        String(24), nullable=False, default=VastuPreference.NOT_REQUIRED
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    project: Mapped[Project] = relationship(back_populates="requirements")


class ProjectRoomRequirement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "project_room_requirements"
    __table_args__ = (
        CheckConstraint("quantity between 1 and 20", name="quantity_range"),
        CheckConstraint("minimum_area is null or minimum_area > 0", name="minimum_area_positive"),
        CheckConstraint("sort_order >= 0", name="sort_order_non_negative"),
        Index("ix_project_room_requirements_project_sort", "project_id", "sort_order"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    room_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    quantity: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    preferred_floor: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    minimum_area: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)

    project: Mapped[Project] = relationship(back_populates="room_requirements")


class Tag(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("organization_id", "normalized_name", name="uq_tags_org_normalized_name"),
        Index("ix_tags_org_display_name", "organization_id", "display_name"),
    )

    normalized_name: Mapped[str] = mapped_column(String(30), nullable=False)
    display_name: Mapped[str] = mapped_column(String(30), nullable=False)

    project_assignments: Mapped[list[ProjectTagAssignment]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )


class ProjectTagAssignment(Base):
    __tablename__ = "project_tag_assignments"

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    tag_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )

    project: Mapped[Project] = relationship(back_populates="tag_assignments")
    tag: Mapped[Tag] = relationship(back_populates="project_assignments")


class AuditLog(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_org_created", "organization_id", "created_at", "id"),
        Index("ix_audit_logs_entity_created", "entity_type", "entity_id", "created_at"),
    )

    actor_user_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IdempotencyRecord(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "actor_user_id",
            "scope",
            "idempotency_key",
            name="uq_idempotency_org_actor_scope_key",
        ),
        Index("ix_idempotency_records_expires_at", "expires_at"),
    )

    actor_user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    response_status: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
