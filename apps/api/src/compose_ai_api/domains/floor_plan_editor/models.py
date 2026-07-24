from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
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


class EditorDocumentStatus(StrEnum):
    ACTIVE = "active"
    CONFLICTED = "conflicted"
    ARCHIVED = "archived"


class EditorCheckpointKind(StrEnum):
    SYSTEM = "system"
    USER = "user"
    RESTORE = "restore"
    DESIGN_VERSION = "design_version"


class EditorOperationBatch(UUIDPrimaryKeyMixin, TenantMixin, TimestampMixin, Base):
    __tablename__ = "floor_plan_editor_operation_batches"
    __table_args__ = (
        UniqueConstraint("document_id", "client_batch_id", name="uq_editor_batches_client_batch"),
        UniqueConstraint(
            "organization_id",
            "created_by",
            "idempotency_key",
            name="uq_editor_batches_org_actor_idempotency",
        ),
        CheckConstraint("base_revision >= 0", name="base_revision_non_negative"),
        CheckConstraint("result_revision > base_revision", name="result_revision_advances"),
        Index("ix_editor_batches_document_revision", "document_id", "result_revision"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_editor_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_batch_id: Mapped[str] = mapped_column(String(80), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    base_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    result_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    operations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    inverse_operations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    validation_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class FloorPlanEditorDocument(
    UUIDPrimaryKeyMixin,
    TenantMixin,
    TimestampMixin,
    SoftDeleteMixin,
    Base,
):
    __tablename__ = "floor_plan_editor_documents"
    __table_args__ = (
        UniqueConstraint("project_id", name="uq_editor_documents_project"),
        CheckConstraint("current_revision >= 0", name="current_revision_non_negative"),
        CheckConstraint("schema_version <> ''", name="schema_version_required"),
        CheckConstraint("renderer_contract_version <> ''", name="renderer_contract_required"),
        Index(
            "ix_editor_documents_org_active",
            "organization_id",
            "status",
            postgresql_where=text("deleted_at is null"),
        ),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_design_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_design_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    source_geometry_snapshot_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_geometry_snapshots.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default=EditorDocumentStatus.ACTIVE
    )
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    schema_version: Mapped[str] = mapped_column(String(40), nullable=False)
    renderer_contract_version: Mapped[str] = mapped_column(String(40), nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    view_state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    layer_state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    editor_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    updated_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )


class EditorValidationResult(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "floor_plan_editor_validation_results"
    __table_args__ = (
        Index("ix_editor_validation_document_revision", "document_id", "revision", "created_at"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_editor_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
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


class EditorCheckpoint(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "floor_plan_editor_checkpoints"
    __table_args__ = (
        CheckConstraint("source_revision >= 0", name="checkpoint_revision_non_negative"),
        Index("ix_editor_checkpoints_document_created", "document_id", "created_at", "id"),
        Index("ix_editor_checkpoints_project_created", "project_id", "created_at", "id"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_editor_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    snapshot_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    validation_summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    checkpoint_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class EditorAuditEvent(UUIDPrimaryKeyMixin, TenantMixin, Base):
    __tablename__ = "floor_plan_editor_audit_events"
    __table_args__ = (
        Index("ix_editor_audit_project_created", "project_id", "created_at", "id"),
        Index("ix_editor_audit_document_created", "document_id", "created_at", "id"),
    )

    project_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    document_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("floor_plan_editor_documents.id", ondelete="CASCADE"),
        nullable=True,
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
