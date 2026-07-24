from __future__ import annotations

import copy
import hashlib
import json
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.auth import AuthContext
from compose_ai_api.domains.floor_plan_editor.models import (
    EditorAuditEvent,
    EditorCheckpoint,
    EditorCheckpointKind,
    EditorDocumentStatus,
    EditorOperationBatch,
    EditorValidationResult,
    FloorPlanEditorDocument,
)
from compose_ai_api.domains.floor_plan_editor.schemas import (
    EditorCheckpointResponse,
    EditorDocumentResponse,
    EditorHistoryItem,
    EditorHistoryResponse,
    EditorLayer,
    EditorOperationBatchRequest,
    EditorOperationBatchResponse,
    EditorOperationType,
    EditorSnapshot,
    EditorToolDefinition,
    EditorValidationIssue,
    EditorValidationRequest,
    EditorValidationResponse,
    EditorValidationSummary,
    EditorViewportState,
)
from compose_ai_api.domains.floor_plans.models import (
    FloorPlanDesignVersion,
    FloorPlanGeometrySnapshot,
)
from compose_ai_api.domains.floor_plans.schemas import CONCEPTUAL_DISCLAIMER
from compose_ai_api.domains.projects.models import Project
from compose_ai_api.domains.projects.service import (
    ensure_project_manage,
    ensure_project_read,
    project_error,
)

EDITOR_SCHEMA_VERSION = "compose-editor-v1"
RENDERER_CONTRACT_VERSION = "svg-renderer-contract-v1"
VALIDATION_ENGINE_VERSION = "compose-editor-validation-v1"
GEOMETRY_ENGINE_VERSION = "compose-editor-geometry-v1"


async def load_editor_document(
    session: AsyncSession, auth: AuthContext, project_id: UUID
) -> EditorDocumentResponse:
    ensure_project_read(auth)
    await _load_project(session, auth, project_id)
    document = await _get_or_create_document(session, auth, project_id)
    return await _document_response(session, document)


async def load_editor_snapshot(
    session: AsyncSession, auth: AuthContext, project_id: UUID
) -> EditorSnapshot:
    document = await _load_document(session, auth, project_id)
    return EditorSnapshot.model_validate(document.snapshot)


async def apply_operation_batch(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    request: EditorOperationBatchRequest,
    idempotency_key: str,
) -> EditorOperationBatchResponse:
    ensure_project_manage(auth)
    document = await _load_document(session, auth, project_id, for_update=True)

    existing = (
        await session.execute(
            select(EditorOperationBatch).where(
                EditorOperationBatch.organization_id == auth.membership.organization_id,
                EditorOperationBatch.created_by == auth.user.id,
                EditorOperationBatch.idempotency_key == idempotency_key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return _batch_response(existing, document)

    duplicate_batch = (
        await session.execute(
            select(EditorOperationBatch).where(
                EditorOperationBatch.document_id == document.id,
                EditorOperationBatch.client_batch_id == request.client_batch_id,
            )
        )
    ).scalar_one_or_none()
    if duplicate_batch is not None:
        return _batch_response(duplicate_batch, document)

    if request.base_revision != document.current_revision:
        document.status = EditorDocumentStatus.CONFLICTED
        await _audit(
            session,
            auth,
            project_id,
            document.id,
            "editor.conflict_detected",
            "floor_plan_editor_document",
            document.id,
            {"baseRevision": request.base_revision, "currentRevision": document.current_revision},
        )
        await session.commit()
        raise project_error(
            409,
            "EDITOR_REVISION_CONFLICT",
            "The editor document changed after this client loaded it.",
            {"baseRevision": request.base_revision, "currentRevision": document.current_revision},
        )

    snapshot = copy.deepcopy(document.snapshot)
    inverse_operations: list[dict[str, Any]] = []
    previous_revision = document.current_revision
    next_revision = previous_revision + 1
    for operation in request.operations:
        inverse_operations.append(
            _apply_operation(snapshot, operation.type, operation.payload, next_revision)
        )

    validation = validate_snapshot(EditorSnapshot.model_validate(snapshot))
    snapshot_hash = _hash_json(snapshot)
    document.snapshot = snapshot
    document.snapshot_hash = snapshot_hash
    document.current_revision = next_revision
    document.validation_summary = validation.summary.model_dump(mode="json", by_alias=True)
    document.status = EditorDocumentStatus.ACTIVE
    document.updated_by = auth.user.id

    batch = EditorOperationBatch(
        id=uuid4(),
        organization_id=auth.membership.organization_id,
        project_id=project_id,
        document_id=document.id,
        client_batch_id=request.client_batch_id,
        idempotency_key=idempotency_key,
        base_revision=previous_revision,
        result_revision=next_revision,
        operations=[
            operation.model_dump(mode="json", by_alias=True) for operation in request.operations
        ],
        inverse_operations=inverse_operations,
        validation_summary=validation.summary.model_dump(mode="json", by_alias=True),
        snapshot_hash=snapshot_hash,
        created_by=auth.user.id,
    )
    session.add(batch)
    await _store_validation(session, auth, document, validation)
    await _audit(
        session,
        auth,
        project_id,
        document.id,
        "editor.operations_applied",
        "floor_plan_editor_operation_batch",
        batch.id,
        {"operationCount": len(request.operations), "revision": next_revision},
    )
    await session.commit()
    return _batch_response(batch, document)


async def validate_editor_document(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    request: EditorValidationRequest,
) -> EditorValidationResponse:
    ensure_project_read(auth)
    document = await _load_document(session, auth, project_id)
    snapshot = request.snapshot or EditorSnapshot.model_validate(document.snapshot)
    validation = validate_snapshot(snapshot)
    await _store_validation(session, auth, document, validation)
    await session.commit()
    return validation


async def create_checkpoint(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    name: str,
    idempotency_key: str,
    *,
    kind: EditorCheckpointKind = EditorCheckpointKind.USER,
    metadata: dict[str, Any] | None = None,
) -> EditorCheckpointResponse:
    ensure_project_manage(auth)
    document = await _load_document(session, auth, project_id)
    existing = await _idempotent_checkpoint(session, auth, idempotency_key)
    if existing is not None:
        return _checkpoint_response(existing)

    validation = validate_snapshot(EditorSnapshot.model_validate(document.snapshot))
    checkpoint = EditorCheckpoint(
        id=uuid4(),
        organization_id=auth.membership.organization_id,
        project_id=project_id,
        document_id=document.id,
        source_revision=document.current_revision,
        name=name,
        kind=kind,
        snapshot=copy.deepcopy(document.snapshot),
        snapshot_hash=document.snapshot_hash,
        validation_summary=validation.summary.model_dump(mode="json", by_alias=True),
        checkpoint_metadata={"idempotencyKey": idempotency_key, **(metadata or {})},
        created_by=auth.user.id,
    )
    session.add(checkpoint)
    await _audit(
        session,
        auth,
        project_id,
        document.id,
        "editor.checkpoint_created",
        "floor_plan_editor_checkpoint",
        checkpoint.id,
        {"kind": kind, "revision": document.current_revision},
    )
    await session.commit()
    return _checkpoint_response(checkpoint)


async def restore_checkpoint(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    checkpoint_id: UUID,
    idempotency_key: str,
) -> EditorDocumentResponse:
    ensure_project_manage(auth)
    document = await _load_document(session, auth, project_id, for_update=True)
    checkpoint = (
        await session.execute(
            select(EditorCheckpoint).where(
                EditorCheckpoint.id == checkpoint_id,
                EditorCheckpoint.document_id == document.id,
                EditorCheckpoint.organization_id == auth.membership.organization_id,
            )
        )
    ).scalar_one_or_none()
    if checkpoint is None:
        raise project_error(404, "EDITOR_CHECKPOINT_NOT_FOUND", "Editor checkpoint not found.")

    document.current_revision += 1
    document.snapshot = copy.deepcopy(checkpoint.snapshot)
    document.snapshot_hash = checkpoint.snapshot_hash
    document.validation_summary = checkpoint.validation_summary
    document.status = EditorDocumentStatus.ACTIVE
    document.updated_by = auth.user.id
    restored = EditorCheckpoint(
        id=uuid4(),
        organization_id=auth.membership.organization_id,
        project_id=project_id,
        document_id=document.id,
        source_revision=document.current_revision,
        name=f"Restore: {checkpoint.name}",
        kind=EditorCheckpointKind.RESTORE,
        snapshot=copy.deepcopy(document.snapshot),
        snapshot_hash=document.snapshot_hash,
        validation_summary=document.validation_summary,
        checkpoint_metadata={
            "idempotencyKey": idempotency_key,
            "restoredCheckpointId": str(checkpoint.id),
        },
        created_by=auth.user.id,
    )
    session.add(restored)
    await _audit(
        session,
        auth,
        project_id,
        document.id,
        "editor.checkpoint_restored",
        "floor_plan_editor_checkpoint",
        restored.id,
        {"restoredCheckpointId": str(checkpoint.id), "revision": document.current_revision},
    )
    await session.commit()
    return await _document_response(session, document)


async def list_history(
    session: AsyncSession, auth: AuthContext, project_id: UUID
) -> EditorHistoryResponse:
    document = await _load_document(session, auth, project_id)
    return EditorHistoryResponse(items=await _history_items(session, document))


async def create_design_version_checkpoint(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    checkpoint_id: UUID,
    name: str | None,
    idempotency_key: str,
) -> EditorCheckpointResponse:
    document = await _load_document(session, auth, project_id)
    checkpoint = (
        await session.execute(
            select(EditorCheckpoint).where(
                EditorCheckpoint.id == checkpoint_id,
                EditorCheckpoint.document_id == document.id,
                EditorCheckpoint.organization_id == auth.membership.organization_id,
            )
        )
    ).scalar_one_or_none()
    if checkpoint is None:
        raise project_error(404, "EDITOR_CHECKPOINT_NOT_FOUND", "Editor checkpoint not found.")
    summary = EditorValidationSummary.model_validate(checkpoint.validation_summary)
    if summary.blocking_count:
        raise project_error(
            409,
            "EDITOR_CHECKPOINT_INVALID",
            "Resolve blocking validation issues before creating a design-version handoff.",
            {"blockingCount": summary.blocking_count},
        )
    return await create_checkpoint(
        session,
        auth,
        project_id,
        name or f"Design handoff r{checkpoint.source_revision}",
        idempotency_key,
        kind=EditorCheckpointKind.DESIGN_VERSION,
        metadata={"sourceCheckpointId": str(checkpoint.id), "disclaimer": CONCEPTUAL_DISCLAIMER},
    )


async def _load_project(session: AsyncSession, auth: AuthContext, project_id: UUID) -> Project:
    project = (
        await session.execute(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == auth.membership.organization_id,
                Project.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if project is None:
        raise project_error(404, "PROJECT_NOT_FOUND", "Project not found.")
    return project


async def _load_document(
    session: AsyncSession, auth: AuthContext, project_id: UUID, *, for_update: bool = False
) -> FloorPlanEditorDocument:
    ensure_project_read(auth)
    statement = select(FloorPlanEditorDocument).where(
        FloorPlanEditorDocument.project_id == project_id,
        FloorPlanEditorDocument.organization_id == auth.membership.organization_id,
        FloorPlanEditorDocument.deleted_at.is_(None),
    )
    if for_update:
        statement = statement.with_for_update()
    document = (await session.execute(statement)).scalar_one_or_none()
    if document is None:
        return await _get_or_create_document(session, auth, project_id)
    return document


async def _get_or_create_document(
    session: AsyncSession, auth: AuthContext, project_id: UUID
) -> FloorPlanEditorDocument:
    existing = (
        await session.execute(
            select(FloorPlanEditorDocument).where(
                FloorPlanEditorDocument.project_id == project_id,
                FloorPlanEditorDocument.organization_id == auth.membership.organization_id,
                FloorPlanEditorDocument.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    row = (
        await session.execute(
            select(FloorPlanDesignVersion, FloorPlanGeometrySnapshot)
            .join(
                FloorPlanGeometrySnapshot,
                FloorPlanGeometrySnapshot.id == FloorPlanDesignVersion.geometry_snapshot_id,
            )
            .where(
                FloorPlanDesignVersion.project_id == project_id,
                FloorPlanDesignVersion.organization_id == auth.membership.organization_id,
                FloorPlanDesignVersion.deleted_at.is_(None),
            )
            .order_by(FloorPlanDesignVersion.version.desc())
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        raise project_error(
            409,
            "EDITOR_REQUIRES_ACCEPTED_DESIGN",
            "Accept a conceptual floor-plan option before opening the 2D editor.",
        )
    design, source_snapshot = row
    snapshot = _editor_snapshot_from_floor_plan(source_snapshot.geometry, design, source_snapshot)
    validation = validate_snapshot(EditorSnapshot.model_validate(snapshot))
    document = FloorPlanEditorDocument(
        id=uuid4(),
        organization_id=auth.membership.organization_id,
        project_id=project_id,
        source_design_version_id=design.id,
        source_geometry_snapshot_id=source_snapshot.id,
        status=EditorDocumentStatus.ACTIVE,
        current_revision=0,
        schema_version=EDITOR_SCHEMA_VERSION,
        renderer_contract_version=RENDERER_CONTRACT_VERSION,
        snapshot=snapshot,
        snapshot_hash=_hash_json(snapshot),
        validation_summary=validation.summary.model_dump(mode="json", by_alias=True),
        view_state=EditorViewportState(
            active_floor_id=snapshot["floors"][0]["id"] if snapshot["floors"] else None
        ).model_dump(mode="json", by_alias=True),
        layer_state={"layers": snapshot["layers"]},
        editor_metadata={
            "source": "accepted_floor_plan_design",
            "disclaimer": CONCEPTUAL_DISCLAIMER,
        },
        created_by=auth.user.id,
        updated_by=auth.user.id,
    )
    session.add(document)
    await session.flush()
    checkpoint = EditorCheckpoint(
        id=uuid4(),
        organization_id=auth.membership.organization_id,
        project_id=project_id,
        document_id=document.id,
        source_revision=0,
        name="Initial accepted design",
        kind=EditorCheckpointKind.SYSTEM,
        snapshot=copy.deepcopy(snapshot),
        snapshot_hash=document.snapshot_hash,
        validation_summary=document.validation_summary,
        checkpoint_metadata={"sourceDesignVersionId": str(design.id)},
        created_by=auth.user.id,
    )
    session.add(checkpoint)
    await _store_validation(session, auth, document, validation)
    await _audit(
        session,
        auth,
        project_id,
        document.id,
        "editor.document_created",
        "floor_plan_editor_document",
        document.id,
        {"sourceDesignVersionId": str(design.id)},
    )
    await session.commit()
    await session.refresh(document)
    return document


def validate_snapshot(snapshot: EditorSnapshot) -> EditorValidationResponse:
    issues: list[EditorValidationIssue] = []
    object_ids = [item.id for item in snapshot.objects]
    duplicate_ids = {object_id for object_id in object_ids if object_ids.count(object_id) > 1}
    for object_id in sorted(duplicate_ids):
        issues.append(
            _issue(
                "DUPLICATE_OBJECT_ID",
                "blocking",
                object_id,
                None,
                "Object IDs must be stable and unique.",
            )
        )
    floor_ids = {floor.id for floor in snapshot.floors}
    walls = {item.id: item for item in snapshot.objects if item.type == "wall" and not item.deleted}
    rooms = [item for item in snapshot.objects if item.type == "room" and not item.deleted]
    for item in snapshot.objects:
        if item.deleted:
            continue
        if item.floor_id not in floor_ids:
            issues.append(
                _issue(
                    "INVALID_FLOOR_REFERENCE",
                    "blocking",
                    item.id,
                    item.type,
                    "Object floor does not exist.",
                )
            )
        if item.type in {"room", "stair"} and len(item.points) < 3:
            issues.append(
                _issue(
                    "INVALID_POLYGON",
                    "error",
                    item.id,
                    item.type,
                    "Polygon objects require at least three points.",
                )
            )
        if item.type == "wall" and len(item.points) != 2:
            issues.append(
                _issue(
                    "INVALID_WALL",
                    "error",
                    item.id,
                    item.type,
                    "Walls require exactly two endpoints.",
                )
            )
        if item.type == "opening" and (not item.wall_id or item.wall_id not in walls):
            issues.append(
                _issue(
                    "INVALID_OPENING_WALL",
                    "blocking",
                    item.id,
                    item.type,
                    "Openings must be attached to a valid wall.",
                )
            )
    for room in rooms:
        area = _polygon_area(room.points)
        if area <= 0:
            issues.append(
                _issue(
                    "ROOM_AREA_INVALID",
                    "error",
                    room.id,
                    room.type,
                    "Room area must be greater than zero.",
                )
            )
        target_area = room.metadata.get("areaM2") or room.metadata.get("targetAreaM2")
        if isinstance(target_area, int | float) and target_area > 0:
            delta = abs((area / 1_000_000) - float(target_area))
            if delta > max(2, float(target_area) * 0.15):
                issues.append(
                    _issue(
                        "AREA_MISMATCH",
                        "warning",
                        room.id,
                        room.type,
                        "Calculated room area differs from stored target area.",
                    )
                )

    counts = {
        "blocking": sum(1 for issue in issues if issue.severity == "blocking"),
        "error": sum(1 for issue in issues if issue.severity == "error"),
        "warning": sum(1 for issue in issues if issue.severity == "warning"),
        "info": sum(1 for issue in issues if issue.severity == "info"),
    }
    summary = EditorValidationSummary(
        status="invalid" if counts["blocking"] or counts["error"] else "valid",
        issue_count=len(issues),
        blocking_count=counts["blocking"],
        error_count=counts["error"],
        warning_count=counts["warning"],
        info_count=counts["info"],
    )
    return EditorValidationResponse(
        project_id=UUID(int=0),
        editor_document_id=UUID(int=0),
        revision=0,
        validation_engine_version=VALIDATION_ENGINE_VERSION,
        geometry_engine_version=GEOMETRY_ENGINE_VERSION,
        summary=summary,
        issues=issues,
    )


def _apply_operation(
    snapshot: dict[str, Any],
    operation_type: EditorOperationType,
    payload: dict[str, Any],
    revision: int,
) -> dict[str, Any]:
    if operation_type == "snapshot.replace":
        previous = copy.deepcopy(snapshot)
        replacement = payload.get("snapshot")
        if not isinstance(replacement, dict):
            raise project_error(
                422, "EDITOR_OPERATION_INVALID", "snapshot.replace requires a snapshot payload."
            )
        snapshot.clear()
        snapshot.update(replacement)
        return {"type": "snapshot.replace", "payload": {"snapshot": previous}}

    objects = snapshot.setdefault("objects", [])
    object_id = str(payload.get("id") or payload.get("objectId") or "")
    previous = copy.deepcopy(next((item for item in objects if item.get("id") == object_id), None))
    if operation_type in {
        "wall.create",
        "room.create",
        "opening.create",
        "stair.create",
        "dimension.create",
    }:
        new_object = copy.deepcopy(payload.get("object"))
        if not isinstance(new_object, dict) or not new_object.get("id"):
            raise project_error(
                422, "EDITOR_OPERATION_INVALID", f"{operation_type} requires an object payload."
            )
        new_object["revisionCreated"] = revision
        new_object["revisionUpdated"] = revision
        objects.append(new_object)
        return {"type": "object.delete", "payload": {"id": new_object["id"]}}
    if previous is None:
        raise project_error(
            422, "EDITOR_OBJECT_NOT_FOUND", "The requested editor object was not found."
        )
    target = next(item for item in objects if item.get("id") == object_id)
    if operation_type == "object.delete":
        target["deleted"] = True
    elif operation_type == "wall.move":
        target["points"] = payload.get("points", target.get("points", []))
    else:
        updates = payload.get("updates")
        if not isinstance(updates, dict):
            raise project_error(
                422, "EDITOR_OPERATION_INVALID", f"{operation_type} requires updates."
            )
        target.update(updates)
    target["revisionUpdated"] = revision
    return {"type": "object.update", "payload": {"id": object_id, "updates": previous}}


def _editor_snapshot_from_floor_plan(
    geometry: dict[str, Any], design: FloorPlanDesignVersion, source: FloorPlanGeometrySnapshot
) -> dict[str, Any]:
    layers = [
        {"id": "rooms", "label": "Rooms", "visible": True, "locked": False, "objectCount": 0},
        {"id": "walls", "label": "Walls", "visible": True, "locked": False, "objectCount": 0},
        {"id": "openings", "label": "Openings", "visible": True, "locked": False, "objectCount": 0},
        {"id": "stairs", "label": "Stairs", "visible": True, "locked": False, "objectCount": 0},
        {
            "id": "dimensions",
            "label": "Dimensions",
            "visible": True,
            "locked": False,
            "objectCount": 0,
        },
        {"id": "labels", "label": "Labels", "visible": True, "locked": False, "objectCount": 0},
    ]
    floors: list[dict[str, Any]] = []
    objects: list[dict[str, Any]] = []
    for floor in geometry.get("floors", []):
        floor_id = f"floor-{floor.get('index', len(floors))}"
        object_prefix = f"{floor_id}-"
        wall_id_map: dict[str, str] = {}
        bounds = _bounds(
            floor.get("envelope") or geometry.get("buildableEnvelope") or [[0, 0], [10000, 8000]]
        )
        floors.append(
            {
                "id": floor_id,
                "index": floor.get("index", len(floors)),
                "name": floor.get("name", f"Floor {len(floors) + 1}"),
                "elevationMm": floor.get("elevationMm", 0),
                "bounds": bounds,
            }
        )
        for room in floor.get("rooms", []):
            objects.append(_space_object(room, "room", floor_id, "rooms", object_prefix))
        for wall in floor.get("walls", []):
            source_wall_id = wall.get("id") or str(uuid4())
            wall_id = f"{object_prefix}{source_wall_id}"
            wall_id_map[source_wall_id] = wall_id
            objects.append(
                {
                    "id": wall_id,
                    "type": "wall",
                    "floorId": floor_id,
                    "layerId": "walls",
                    "name": "Wall",
                    "points": [_point(wall.get("start", [0, 0])), _point(wall.get("end", [0, 0]))],
                    "metadata": {
                        "sourceObjectId": source_wall_id,
                        "thicknessMm": wall.get("thicknessMm", 150),
                    },
                    "revisionCreated": 0,
                    "revisionUpdated": 0,
                    "deleted": False,
                }
            )
        for opening_type, layer_items in (
            ("door", floor.get("doors", [])),
            ("window", floor.get("windows", [])),
        ):
            for opening in layer_items:
                source_opening_id = opening.get("id") or str(uuid4())
                source_wall_id = opening.get("wallId")
                objects.append(
                    {
                        "id": f"{object_prefix}{source_opening_id}",
                        "type": "opening",
                        "floorId": floor_id,
                        "layerId": "openings",
                        "name": opening_type.title(),
                        "points": [
                            _point(opening.get("start", [0, 0])),
                            _point(opening.get("end", [0, 0])),
                        ],
                        "wallId": wall_id_map.get(source_wall_id, source_wall_id),
                        "width": opening.get("widthMm"),
                        "height": opening.get("heightMm"),
                        "metadata": {
                            "openingType": opening_type,
                            "sourceObjectId": source_opening_id,
                            "sourceWallId": source_wall_id,
                        },
                        "revisionCreated": 0,
                        "revisionUpdated": 0,
                        "deleted": False,
                    }
                )
        for stair in floor.get("stairs", []):
            objects.append(_space_object(stair, "stair", floor_id, "stairs", object_prefix))
    counts = {layer["id"]: 0 for layer in layers}
    for item in objects:
        counts[item["layerId"]] = counts.get(item["layerId"], 0) + 1
    for layer in layers:
        layer["objectCount"] = counts.get(layer["id"], 0)
    return {
        "schemaVersion": EDITOR_SCHEMA_VERSION,
        "unit": "mm",
        "coordinateSpace": source.coordinate_space,
        "floors": floors,
        "objects": objects,
        "layers": layers,
        "snapSettings": {
            "enabled": True,
            "grid": True,
            "corner": True,
            "wallIntersection": True,
            "parallel": True,
            "perpendicular": True,
            "center": True,
            "equalSpacingGuides": True,
        },
        "measurementOverlay": None,
        "source": {
            "designVersionId": str(design.id),
            "geometrySnapshotId": str(source.id),
            "geometryHash": source.geometry_hash,
        },
    }


def _space_object(
    space: dict[str, Any], object_type: str, floor_id: str, layer_id: str, object_prefix: str
) -> dict[str, Any]:
    source_object_id = space.get("id") or str(uuid4())
    return {
        "id": f"{object_prefix}{source_object_id}",
        "type": object_type,
        "floorId": floor_id,
        "layerId": layer_id,
        "name": space.get("name") or object_type.title(),
        "points": [_point(point) for point in space.get("polygon", [])],
        "metadata": {
            "roomType": space.get("roomType"),
            "areaM2": space.get("areaM2"),
            "sourceObjectId": source_object_id,
            "zone": space.get("zone"),
        },
        "revisionCreated": 0,
        "revisionUpdated": 0,
        "deleted": False,
    }


def _point(value: list[float] | tuple[float, float] | dict[str, Any]) -> dict[str, float]:
    if isinstance(value, dict):
        return {"x": float(value.get("x", 0)), "y": float(value.get("y", 0))}
    return {"x": float(value[0]), "y": float(value[1])}


def _bounds(points: list[Any]) -> dict[str, float]:
    normalized = [_point(point) for point in points]
    xs = [point["x"] for point in normalized] or [0]
    ys = [point["y"] for point in normalized] or [0]
    return {"minX": min(xs), "minY": min(ys), "maxX": max(xs), "maxY": max(ys)}


def _polygon_area(points: list[Any]) -> float:
    if len(points) < 3:
        return 0
    area = 0.0
    for index, point in enumerate(points):
        current = _point(point.model_dump() if hasattr(point, "model_dump") else point)
        following_raw = points[(index + 1) % len(points)]
        following = _point(
            following_raw.model_dump() if hasattr(following_raw, "model_dump") else following_raw
        )
        area += current["x"] * following["y"] - following["x"] * current["y"]
    return abs(area) / 2


def _issue(
    code: str,
    severity: str,
    object_id: str | None,
    object_type: str | None,
    message: str,
) -> EditorValidationIssue:
    return EditorValidationIssue(
        id=f"{code.lower()}-{object_id or 'document'}",
        code=code,
        severity=severity,  # type: ignore[arg-type]
        object_id=object_id,
        object_type=object_type,  # type: ignore[arg-type]
        message=message,
        reason=message,
        blocking=severity == "blocking",
    )


async def _store_validation(
    session: AsyncSession,
    auth: AuthContext,
    document: FloorPlanEditorDocument,
    validation: EditorValidationResponse,
) -> None:
    validation.project_id = document.project_id
    validation.editor_document_id = document.id
    validation.revision = document.current_revision
    session.add(
        EditorValidationResult(
            id=uuid4(),
            organization_id=auth.membership.organization_id,
            project_id=document.project_id,
            document_id=document.id,
            revision=document.current_revision,
            status=validation.summary.status,
            validation_engine_version=validation.validation_engine_version,
            geometry_engine_version=validation.geometry_engine_version,
            summary=validation.summary.model_dump(mode="json", by_alias=True),
            issues=[issue.model_dump(mode="json", by_alias=True) for issue in validation.issues],
            created_by=auth.user.id,
        )
    )


async def _document_response(
    session: AsyncSession, document: FloorPlanEditorDocument
) -> EditorDocumentResponse:
    latest_validation = (
        await session.execute(
            select(EditorValidationResult)
            .where(EditorValidationResult.document_id == document.id)
            .order_by(EditorValidationResult.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    issues = latest_validation.issues if latest_validation else []
    return EditorDocumentResponse(
        id=document.id,
        project_id=document.project_id,
        source_design_version_id=document.source_design_version_id,
        source_geometry_snapshot_id=document.source_geometry_snapshot_id,
        status=document.status,
        current_revision=document.current_revision,
        schema_version=document.schema_version,
        renderer_contract_version=document.renderer_contract_version,
        snapshot_hash=document.snapshot_hash,
        snapshot=EditorSnapshot.model_validate(document.snapshot),
        validation_summary=EditorValidationSummary.model_validate(document.validation_summary),
        validation_issues=[EditorValidationIssue.model_validate(issue) for issue in issues],
        view_state=EditorViewportState.model_validate(document.view_state),
        layers=[
            EditorLayer.model_validate(layer) for layer in document.layer_state.get("layers", [])
        ],
        tool_registry=_tool_registry(),
        inspector_tabs=["properties", "validation", "metadata", "history"],
        history=await _history_items(session, document),
        autosave={"status": "saved", "revision": document.current_revision},
        updated_at=document.updated_at,
    )


async def _history_items(
    session: AsyncSession, document: FloorPlanEditorDocument
) -> list[EditorHistoryItem]:
    batches = list(
        (
            await session.execute(
                select(EditorOperationBatch)
                .where(EditorOperationBatch.document_id == document.id)
                .order_by(EditorOperationBatch.created_at.desc())
                .limit(25)
            )
        )
        .scalars()
        .all()
    )
    checkpoints = list(
        (
            await session.execute(
                select(EditorCheckpoint)
                .where(EditorCheckpoint.document_id == document.id)
                .order_by(EditorCheckpoint.created_at.desc())
                .limit(25)
            )
        )
        .scalars()
        .all()
    )
    items: list[EditorHistoryItem] = [
        EditorHistoryItem(
            id=batch.id,
            item_type="operation_batch",
            title=f"{len(batch.operations)} operation{'s' if len(batch.operations) != 1 else ''}",
            revision=batch.result_revision,
            operation_count=len(batch.operations),
            created_at=batch.created_at,
        )
        for batch in batches
    ]
    items.extend(
        EditorHistoryItem(
            id=checkpoint.id,
            item_type="checkpoint",
            title=checkpoint.name,
            revision=checkpoint.source_revision,
            checkpoint_kind=checkpoint.kind,
            created_at=checkpoint.created_at,
        )
        for checkpoint in checkpoints
    )
    return sorted(items, key=lambda item: item.created_at, reverse=True)[:30]


async def _idempotent_checkpoint(
    session: AsyncSession, auth: AuthContext, idempotency_key: str
) -> EditorCheckpoint | None:
    return (
        await session.execute(
            select(EditorCheckpoint).where(
                EditorCheckpoint.organization_id == auth.membership.organization_id,
                EditorCheckpoint.created_by == auth.user.id,
                EditorCheckpoint.checkpoint_metadata["idempotencyKey"].astext == idempotency_key,
            )
        )
    ).scalar_one_or_none()


def _batch_response(
    batch: EditorOperationBatch, document: FloorPlanEditorDocument
) -> EditorOperationBatchResponse:
    return EditorOperationBatchResponse(
        project_id=batch.project_id,
        editor_document_id=batch.document_id,
        previous_revision=batch.base_revision,
        current_revision=batch.result_revision,
        applied_operation_ids=[
            str(operation.get("clientOperationId") or operation.get("client_operation_id"))
            for operation in batch.operations
        ],
        validation_summary=EditorValidationSummary.model_validate(batch.validation_summary),
        snapshot_hash=document.snapshot_hash,
    )


def _checkpoint_response(checkpoint: EditorCheckpoint) -> EditorCheckpointResponse:
    return EditorCheckpointResponse(
        id=checkpoint.id,
        project_id=checkpoint.project_id,
        editor_document_id=checkpoint.document_id,
        source_revision=checkpoint.source_revision,
        name=checkpoint.name,
        kind=checkpoint.kind,
        snapshot_hash=checkpoint.snapshot_hash,
        validation_summary=EditorValidationSummary.model_validate(checkpoint.validation_summary),
        metadata=checkpoint.checkpoint_metadata,
        created_at=checkpoint.created_at,
    )


def _tool_registry() -> list[EditorToolDefinition]:
    return [
        EditorToolDefinition(id="select", label="Select", shortcut="V", plugin_key="core.select"),
        EditorToolDefinition(id="pan", label="Pan", shortcut="Space", plugin_key="core.pan"),
        EditorToolDefinition(
            id="wall",
            label="Wall",
            shortcut="W",
            plugin_key="geometry.wall",
            supported_object_types=["wall"],
        ),
        EditorToolDefinition(
            id="room",
            label="Room",
            shortcut="R",
            plugin_key="geometry.room",
            supported_object_types=["room"],
        ),
        EditorToolDefinition(
            id="door",
            label="Door",
            shortcut="D",
            plugin_key="openings.door",
            supported_object_types=["opening"],
        ),
        EditorToolDefinition(
            id="window",
            label="Window",
            shortcut="N",
            plugin_key="openings.window",
            supported_object_types=["opening"],
        ),
        EditorToolDefinition(
            id="stair",
            label="Stair",
            shortcut="S",
            plugin_key="vertical.stair",
            supported_object_types=["stair"],
        ),
        EditorToolDefinition(
            id="dimension",
            label="Dimension",
            plugin_key="annotation.dimension",
            supported_object_types=["dimension"],
        ),
        EditorToolDefinition(
            id="label",
            label="Label",
            plugin_key="annotation.label",
            supported_object_types=["label"],
        ),
    ]


async def _audit(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    document_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: UUID | None,
    payload: dict[str, Any],
) -> None:
    session.add(
        EditorAuditEvent(
            id=uuid4(),
            organization_id=auth.membership.organization_id,
            project_id=project_id,
            document_id=document_id,
            actor_id=auth.user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
        )
    )


def _hash_json(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
