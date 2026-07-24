from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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


class SceneVersionStatus(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    ARCHIVED = "archived"


class SceneCompilationJobStatus(StrEnum):
    QUEUED = "queued"
    VALIDATING_SOURCE = "validating_source"
    COMPILING_GEOMETRY = "compiling_geometry"
    GENERATING_MATERIALS = "generating_materials"
    VALIDATING_SCENE = "validating_scene"
    SAVING_SCENE = "saving_scene"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SceneObjectType(StrEnum):
    BUILDING = "building"
    FLOOR = "floor"
    ROOM = "room"
    WALL = "wall"
    DOOR = "door"
    WINDOW = "window"
    STAIR = "stair"
    SLAB = "slab"
    ROOF = "roof"
    BALCONY = "balcony"
    PARKING = "parking"
    PLOT_BOUNDARY = "plot_boundary"


class SceneValidationSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    BLOCKING = "blocking"


class SceneCompilationJob(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "building_scene_compilation_jobs"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "created_by",
            "idempotency_key",
            name="uq_scene_jobs_org_actor_idempotency",
        ),
        CheckConstraint("progress >= 0 and progress <= 100", name="scene_job_progress_range"),
        CheckConstraint("source_editor_revision >= 0", name="scene_job_revision_non_negative"),
        Index("ix_scene_jobs_project_created", "project_id", "created_at", "id"),
        Index("ix_scene_jobs_org_status_created", "organization_id", "status", "created_at"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_editor_document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_editor_documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_editor_checkpoint_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_editor_checkpoints.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_design_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_design_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_editor_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SceneCompilationJobStatus.QUEUED, index=True
    )
    progress: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    scene_engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    geometry_engine_version: Mapped[str] = mapped_column(String(160), nullable=False)
    scene_schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    renderer_contract_version: Mapped[str] = mapped_column(String(60), nullable=False)
    failure_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    failure_details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SceneVersion(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "building_scene_versions"
    __table_args__ = (
        UniqueConstraint("project_id", "version", name="uq_scene_versions_project_version"),
        UniqueConstraint("compilation_job_id", name="uq_scene_versions_job"),
        CheckConstraint("version > 0", name="scene_version_positive"),
        CheckConstraint("object_count >= 0", name="scene_object_count_non_negative"),
        CheckConstraint("triangle_count >= 0", name="scene_triangle_count_non_negative"),
        Index("ix_scene_versions_project_created", "project_id", "created_at", "id"),
        Index(
            "ix_scene_versions_project_active",
            "project_id",
            "status",
            postgresql_where=text("deleted_at is null"),
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    compilation_job_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("building_scene_compilation_jobs.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_editor_document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_editor_documents.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_editor_checkpoint_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_editor_checkpoints.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_design_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_design_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_editor_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=SceneVersionStatus.ACTIVE
    )
    is_stale: Mapped[bool] = mapped_column(nullable=False, default=False)
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    object_count: Mapped[int] = mapped_column(Integer, nullable=False)
    triangle_count: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bounding_box: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    scene_schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    geometry_engine_version: Mapped[str] = mapped_column(String(160), nullable=False)
    scene_engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    material_schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    renderer_contract_version: Mapped[str] = mapped_column(String(60), nullable=False)
    source_versions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    disclaimer: Mapped[str] = mapped_column(String(160), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class SceneObject(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "building_scene_objects"
    __table_args__ = (
        UniqueConstraint("scene_version_id", "stable_object_id", name="uq_scene_objects_stable"),
        CheckConstraint("triangle_count >= 0", name="scene_object_triangle_count_non_negative"),
        Index("ix_scene_objects_version_type", "scene_version_id", "object_type"),
        Index("ix_scene_objects_source_2d", "source_2d_object_id"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    scene_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("building_scene_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stable_object_id: Mapped[str] = mapped_column(String(160), nullable=False)
    source_2d_object_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source_2d_object_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    floor_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    parent_object_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    geometry_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    transform: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    geometry: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    bounding_box: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    material_id: Mapped[str] = mapped_column(String(80), nullable=False)
    triangle_count: Mapped[int] = mapped_column(Integer, nullable=False)
    object_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SceneMaterial(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "building_scene_materials"
    __table_args__ = (
        UniqueConstraint("scene_version_id", "material_id", name="uq_scene_materials_key"),
        Index("ix_scene_materials_version_category", "scene_version_id", "category"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    scene_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("building_scene_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    material_id: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    properties: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SceneCameraView(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "building_scene_camera_views"
    __table_args__ = (
        Index("ix_scene_camera_views_version_created", "scene_version_id", "created_at", "id"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    scene_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("building_scene_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    camera: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class SceneValidationResult(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "building_scene_validation_results"
    __table_args__ = (
        Index("ix_scene_validation_version_created", "scene_version_id", "created_at", "id"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    scene_version_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("building_scene_versions.id", ondelete="CASCADE"),
        nullable=True,
    )
    compilation_job_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("building_scene_compilation_jobs.id", ondelete="CASCADE"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    validation_engine_version: Mapped[str] = mapped_column(String(80), nullable=False)
    geometry_engine_version: Mapped[str] = mapped_column(String(160), nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    issues: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SceneCompilationEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "building_scene_compilation_events"
    __table_args__ = (
        UniqueConstraint("job_id", "sequence", name="uq_scene_events_job_sequence"),
        CheckConstraint("sequence > 0", name="scene_event_sequence_positive"),
        Index("ix_scene_events_job_sequence", "job_id", "sequence"),
    )

    job_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("building_scene_compilation_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SceneAuditEvent(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "building_scene_audit_events"
    __table_args__ = (
        Index("ix_scene_audit_project_created", "project_id", "created_at", "id"),
        Index("ix_scene_audit_entity", "entity_type", "entity_id"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
