from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.auth import AuthContext
from compose_ai_api.domains.building_visualization.compiler import (
    MATERIAL_SCHEMA_VERSION,
    RENDERER_CONTRACT_VERSION,
    SCENE_ENGINE_VERSION,
    SCENE_GEOMETRY_ENGINE_VERSION,
    SCENE_SCHEMA_VERSION,
    compile_scene_from_checkpoint,
    material_library,
    scene_graph,
)
from compose_ai_api.domains.building_visualization.models import (
    SceneAuditEvent,
    SceneCameraView,
    SceneCompilationEvent,
    SceneCompilationJob,
    SceneCompilationJobStatus,
    SceneValidationResult,
    SceneVersion,
    SceneVersionStatus,
)
from compose_ai_api.domains.building_visualization.models import (
    SceneMaterial as SceneMaterialModel,
)
from compose_ai_api.domains.building_visualization.models import (
    SceneObject as SceneObjectModel,
)
from compose_ai_api.domains.building_visualization.schemas import (
    SceneCameraViewCreateRequest,
    SceneCameraViewResponse,
    SceneCameraViewsResponse,
    SceneCompilationJobResponse,
    SceneCompileRequest,
    SceneMaterialsResponse,
    SceneObject,
    SceneObjectsResponse,
    SceneValidationIssue,
    SceneValidationResponse,
    SceneValidationSummary,
    SceneVersionResponse,
    SceneWorkspaceResponse,
)
from compose_ai_api.domains.floor_plan_editor.models import (
    EditorCheckpoint,
    EditorDocumentStatus,
    FloorPlanEditorDocument,
)
from compose_ai_api.domains.floor_plans.schemas import CONCEPTUAL_DISCLAIMER
from compose_ai_api.domains.projects.models import Project
from compose_ai_api.domains.projects.service import (
    ensure_project_manage,
    ensure_project_read,
    project_error,
)


async def load_scene_workspace(
    session: AsyncSession, auth: AuthContext, project_id: UUID
) -> SceneWorkspaceResponse:
    ensure_project_read(auth)
    await _load_project(session, auth, project_id)
    checkpoint = await _latest_checkpoint(session, auth, project_id)
    scene = await _latest_scene(session, auth, project_id)
    job = await _latest_job(session, auth, project_id)
    active_response = await _scene_response(session, scene) if scene is not None else None
    graph = []
    if scene is not None:
        objects = await _scene_objects(session, auth, scene.id)
        graph = scene_graph([_scene_object_response(item) for item in objects])
    return SceneWorkspaceResponse(
        project_id=project_id,
        active_scene=active_response,
        latest_job=_job_response(job, scene.id if scene else None) if job else None,
        has_validated_checkpoint=checkpoint is not None,
        source_checkpoint_id=checkpoint.id if checkpoint else None,
        source_editor_revision=checkpoint.source_revision if checkpoint else None,
        is_stale=_is_scene_stale(scene, checkpoint),
        material_library=material_library(),
        scene_graph=graph,
        empty_reason=None if checkpoint else "Create a validated 2D editor checkpoint first.",
    )


async def compile_scene(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    request: SceneCompileRequest,
    idempotency_key: str,
) -> SceneCompilationJobResponse:
    ensure_project_manage(auth)
    await _load_project(session, auth, project_id)
    existing = await _idempotent_job(session, auth, idempotency_key)
    if existing is not None:
        scene = await _scene_for_job(session, existing.id)
        return _job_response(existing, scene.id if scene else None)

    checkpoint = await _select_checkpoint(session, auth, project_id, request.checkpoint_id)
    document = await _load_document(session, auth, project_id, checkpoint.document_id)
    scene_version_id = uuid4()
    job = SceneCompilationJob(
        id=uuid4(),
        organization_id=auth.membership.organization_id,
        project_id=project_id,
        source_editor_document_id=document.id,
        source_editor_checkpoint_id=checkpoint.id,
        source_design_version_id=document.source_design_version_id,
        source_editor_revision=checkpoint.source_revision,
        status=SceneCompilationJobStatus.QUEUED,
        progress=0,
        idempotency_key=idempotency_key,
        input_hash=checkpoint.snapshot_hash,
        scene_engine_version=SCENE_ENGINE_VERSION,
        geometry_engine_version=SCENE_GEOMETRY_ENGINE_VERSION,
        scene_schema_version=SCENE_SCHEMA_VERSION,
        renderer_contract_version=RENDERER_CONTRACT_VERSION,
        created_by=auth.user.id,
    )
    session.add(job)
    await session.flush()
    await _event(session, job.id, 1, "scene.compile.started", {"progress": 0})
    await _advance_job(session, job, SceneCompilationJobStatus.VALIDATING_SOURCE, 15)

    compiled = compile_scene_from_checkpoint(
        project_id=project_id,
        scene_version_id=scene_version_id,
        source_design_version_id=document.source_design_version_id,
        source_editor_document_id=document.id,
        source_editor_checkpoint_id=checkpoint.id,
        source_editor_revision=checkpoint.source_revision,
        checkpoint_hash=checkpoint.snapshot_hash,
        snapshot=checkpoint.snapshot,
        validation_summary=checkpoint.validation_summary,
        quality_preset=request.quality_preset,
    )
    if compiled.validation.summary.blocking_count:
        job.status = SceneCompilationJobStatus.FAILED
        job.progress = 100
        job.failure_code = "SCENE_SOURCE_INVALID"
        job.failure_details = compiled.validation.model_dump(mode="json", by_alias=True)
        job.completed_at = datetime.now(UTC)
        await _event(
            session,
            job.id,
            2,
            "scene.compile.failed",
            {"progress": 100, "code": job.failure_code},
        )
        await _store_validation(session, auth, project_id, None, job.id, compiled.validation)
        await session.commit()
        return _job_response(job, None)

    await _advance_job(session, job, SceneCompilationJobStatus.COMPILING_GEOMETRY, 45)
    await _advance_job(session, job, SceneCompilationJobStatus.GENERATING_MATERIALS, 65)
    await _advance_job(session, job, SceneCompilationJobStatus.VALIDATING_SCENE, 82)
    version = await _next_scene_version(session, auth, project_id)
    await session.execute(
        update(SceneVersion)
        .where(
            SceneVersion.project_id == project_id,
            SceneVersion.organization_id == auth.membership.organization_id,
            SceneVersion.deleted_at.is_(None),
        )
        .values(status=SceneVersionStatus.STALE, is_stale=True)
    )
    scene = SceneVersion(
        id=scene_version_id,
        organization_id=auth.membership.organization_id,
        project_id=project_id,
        compilation_job_id=job.id,
        source_editor_document_id=document.id,
        source_editor_checkpoint_id=checkpoint.id,
        source_design_version_id=document.source_design_version_id,
        source_editor_revision=checkpoint.source_revision,
        version=version,
        status=SceneVersionStatus.ACTIVE,
        is_stale=False,
        manifest=compiled.manifest.model_dump(mode="json", by_alias=True),
        object_count=len(compiled.objects),
        triangle_count=sum(item.triangle_count for item in compiled.objects),
        bounding_box=compiled.manifest.bounding_box.model_dump(mode="json", by_alias=True),
        scene_schema_version=SCENE_SCHEMA_VERSION,
        geometry_engine_version=SCENE_GEOMETRY_ENGINE_VERSION,
        scene_engine_version=SCENE_ENGINE_VERSION,
        material_schema_version=MATERIAL_SCHEMA_VERSION,
        renderer_contract_version=RENDERER_CONTRACT_VERSION,
        source_versions=compiled.manifest.source_versions,
        disclaimer=CONCEPTUAL_DISCLAIMER,
        created_by=auth.user.id,
    )
    session.add(scene)
    await session.flush()
    for material in compiled.materials:
        session.add(
            SceneMaterialModel(
                id=uuid4(),
                organization_id=auth.membership.organization_id,
                project_id=project_id,
                scene_version_id=scene.id,
                material_id=material.material_id,
                name=material.name,
                category=material.category,
                properties=material.model_dump(mode="json", by_alias=True),
            )
        )
    for item in compiled.objects:
        session.add(
            SceneObjectModel(
                id=item.id,
                organization_id=auth.membership.organization_id,
                project_id=project_id,
                scene_version_id=scene.id,
                stable_object_id=item.stable_object_id,
                source_2d_object_id=item.source_2d_object_id,
                source_2d_object_type=item.source_2d_object_type,
                object_type=item.object_type,
                floor_id=item.floor_id,
                parent_object_id=item.parent_object_id,
                name=item.name,
                geometry_kind=item.geometry_kind,
                transform=item.transform.model_dump(mode="json", by_alias=True),
                geometry=item.geometry.model_dump(mode="json", by_alias=True),
                bounding_box=item.bounding_box.model_dump(mode="json", by_alias=True),
                material_id=item.material_id,
                triangle_count=item.triangle_count,
                object_metadata=item.metadata,
            )
        )
    await _store_validation(session, auth, project_id, scene.id, job.id, compiled.validation)
    await _advance_job(session, job, SceneCompilationJobStatus.SAVING_SCENE, 94)
    job.status = SceneCompilationJobStatus.COMPLETED
    job.progress = 100
    job.input_hash = compiled.input_hash
    job.completed_at = datetime.now(UTC)
    await _event(
        session,
        job.id,
        6,
        "scene.compile.completed",
        {"progress": 100, "sceneVersionId": str(scene.id)},
    )
    await _audit(
        session,
        auth,
        project_id,
        "scene.compiled",
        "building_scene_version",
        scene.id,
        {"checkpointId": str(checkpoint.id), "version": version},
    )
    await session.commit()
    return _job_response(job, scene.id)


async def load_scene_version(
    session: AsyncSession, auth: AuthContext, project_id: UUID, scene_version_id: UUID
) -> SceneVersionResponse:
    ensure_project_read(auth)
    scene = await _load_scene(session, auth, project_id, scene_version_id)
    return await _scene_response(session, scene)


async def list_scene_versions(
    session: AsyncSession, auth: AuthContext, project_id: UUID
) -> list[SceneVersionResponse]:
    ensure_project_read(auth)
    rows = (
        (
            await session.execute(
                select(SceneVersion)
                .where(
                    SceneVersion.project_id == project_id,
                    SceneVersion.organization_id == auth.membership.organization_id,
                    SceneVersion.deleted_at.is_(None),
                )
                .order_by(SceneVersion.version.desc())
            )
        )
        .scalars()
        .all()
    )
    return [await _scene_response(session, scene) for scene in rows]


async def load_scene_objects(
    session: AsyncSession, auth: AuthContext, project_id: UUID, scene_version_id: UUID
) -> SceneObjectsResponse:
    scene = await _load_scene(session, auth, project_id, scene_version_id)
    objects = await _scene_objects(session, auth, scene.id)
    responses = [_scene_object_response(item) for item in objects]
    return SceneObjectsResponse(
        scene_version_id=scene.id,
        objects=responses,
        graph=scene_graph(responses),
    )


async def load_scene_materials(
    session: AsyncSession, auth: AuthContext, project_id: UUID, scene_version_id: UUID
) -> SceneMaterialsResponse:
    scene = await _load_scene(session, auth, project_id, scene_version_id)
    rows = (
        (
            await session.execute(
                select(SceneMaterialModel)
                .where(SceneMaterialModel.scene_version_id == scene.id)
                .order_by(SceneMaterialModel.category, SceneMaterialModel.name)
            )
        )
        .scalars()
        .all()
    )
    return SceneMaterialsResponse(
        scene_version_id=scene.id,
        materials=[material.properties | {"materialId": material.material_id} for material in rows],
        library=material_library(),
    )


async def load_scene_validation(
    session: AsyncSession, auth: AuthContext, project_id: UUID, scene_version_id: UUID
) -> SceneValidationResponse:
    scene = await _load_scene(session, auth, project_id, scene_version_id)
    row = (
        await session.execute(
            select(SceneValidationResult)
            .where(SceneValidationResult.scene_version_id == scene.id)
            .order_by(SceneValidationResult.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return SceneValidationResponse(
            scene_version_id=scene.id,
            validation_engine_version="compose-scene-validation-v1",
            geometry_engine_version=scene.geometry_engine_version,
            summary=SceneValidationSummary(
                status="valid",
                issue_count=0,
                blocking_count=0,
                error_count=0,
                warning_count=0,
                info_count=0,
            ),
            issues=[],
        )
    return SceneValidationResponse(
        scene_version_id=scene.id,
        validation_engine_version=row.validation_engine_version,
        geometry_engine_version=row.geometry_engine_version,
        summary=SceneValidationSummary.model_validate(row.summary),
        issues=[SceneValidationIssue.model_validate(issue) for issue in row.issues],
    )


async def load_scene_job(
    session: AsyncSession, auth: AuthContext, project_id: UUID, job_id: UUID
) -> SceneCompilationJobResponse:
    ensure_project_read(auth)
    job = await _load_job(session, auth, project_id, job_id)
    scene = await _scene_for_job(session, job.id)
    return _job_response(job, scene.id if scene else None)


async def cancel_scene_job(
    session: AsyncSession, auth: AuthContext, project_id: UUID, job_id: UUID
) -> SceneCompilationJobResponse:
    ensure_project_manage(auth)
    job = await _load_job(session, auth, project_id, job_id)
    if job.status in {
        SceneCompilationJobStatus.COMPLETED,
        SceneCompilationJobStatus.FAILED,
        SceneCompilationJobStatus.CANCELLED,
    }:
        return _job_response(job, None)
    job.status = SceneCompilationJobStatus.CANCELLED
    job.cancelled_at = datetime.now(UTC)
    await _event(session, job.id, 99, "scene.compile.cancelled", {"progress": job.progress})
    await session.commit()
    return _job_response(job, None)


async def list_scene_events(
    session: AsyncSession, auth: AuthContext, project_id: UUID, job_id: UUID
) -> list[SceneCompilationEvent]:
    await _load_job(session, auth, project_id, job_id)
    return list(
        (
            await session.execute(
                select(SceneCompilationEvent)
                .where(SceneCompilationEvent.job_id == job_id)
                .order_by(SceneCompilationEvent.sequence)
            )
        )
        .scalars()
        .all()
    )


async def create_camera_view(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    scene_version_id: UUID,
    request: SceneCameraViewCreateRequest,
) -> SceneCameraViewResponse:
    ensure_project_manage(auth)
    scene = await _load_scene(session, auth, project_id, scene_version_id)
    view = SceneCameraView(
        id=uuid4(),
        organization_id=auth.membership.organization_id,
        project_id=project_id,
        scene_version_id=scene.id,
        name=request.name,
        camera=request.camera.model_dump(mode="json", by_alias=True),
        created_by=auth.user.id,
    )
    session.add(view)
    await _audit(
        session,
        auth,
        project_id,
        "scene.camera_view_created",
        "building_scene_camera_view",
        view.id,
        {"sceneVersionId": str(scene.id)},
    )
    await session.commit()
    return _camera_response(view)


async def list_camera_views(
    session: AsyncSession, auth: AuthContext, project_id: UUID, scene_version_id: UUID
) -> SceneCameraViewsResponse:
    scene = await _load_scene(session, auth, project_id, scene_version_id)
    rows = (
        (
            await session.execute(
                select(SceneCameraView)
                .where(
                    SceneCameraView.scene_version_id == scene.id,
                    SceneCameraView.deleted_at.is_(None),
                )
                .order_by(SceneCameraView.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return SceneCameraViewsResponse(views=[_camera_response(view) for view in rows])


def sse_payload(events: list[SceneCompilationEvent]) -> str:
    chunks = []
    for event in events:
        chunks.append(
            f"id: {event.sequence}\nevent: {event.event_type}\ndata: "
            f"{json.dumps(event.payload, default=str)}\n\n"
        )
    return "".join(chunks)


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


async def _latest_checkpoint(
    session: AsyncSession, auth: AuthContext, project_id: UUID
) -> EditorCheckpoint | None:
    return (
        await session.execute(
            select(EditorCheckpoint)
            .where(
                EditorCheckpoint.project_id == project_id,
                EditorCheckpoint.organization_id == auth.membership.organization_id,
            )
            .order_by(EditorCheckpoint.created_at.desc(), EditorCheckpoint.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _select_checkpoint(
    session: AsyncSession, auth: AuthContext, project_id: UUID, checkpoint_id: UUID | None
) -> EditorCheckpoint:
    if checkpoint_id is None:
        checkpoint = await _latest_checkpoint(session, auth, project_id)
    else:
        checkpoint = (
            await session.execute(
                select(EditorCheckpoint).where(
                    EditorCheckpoint.id == checkpoint_id,
                    EditorCheckpoint.project_id == project_id,
                    EditorCheckpoint.organization_id == auth.membership.organization_id,
                )
            )
        ).scalar_one_or_none()
    if checkpoint is None:
        raise project_error(
            409,
            "SCENE_REQUIRES_EDITOR_CHECKPOINT",
            "Create a validated 2D editor checkpoint before compiling a 3D scene.",
        )
    return checkpoint


async def _load_document(
    session: AsyncSession, auth: AuthContext, project_id: UUID, document_id: UUID
) -> FloorPlanEditorDocument:
    document = (
        await session.execute(
            select(FloorPlanEditorDocument).where(
                FloorPlanEditorDocument.id == document_id,
                FloorPlanEditorDocument.project_id == project_id,
                FloorPlanEditorDocument.organization_id == auth.membership.organization_id,
                FloorPlanEditorDocument.deleted_at.is_(None),
                FloorPlanEditorDocument.status != EditorDocumentStatus.ARCHIVED,
            )
        )
    ).scalar_one_or_none()
    if document is None:
        raise project_error(404, "EDITOR_DOCUMENT_NOT_FOUND", "Editor document not found.")
    return document


async def _latest_scene(
    session: AsyncSession, auth: AuthContext, project_id: UUID
) -> SceneVersion | None:
    return (
        await session.execute(
            select(SceneVersion)
            .where(
                SceneVersion.project_id == project_id,
                SceneVersion.organization_id == auth.membership.organization_id,
                SceneVersion.deleted_at.is_(None),
            )
            .order_by(SceneVersion.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _latest_job(
    session: AsyncSession, auth: AuthContext, project_id: UUID
) -> SceneCompilationJob | None:
    return (
        await session.execute(
            select(SceneCompilationJob)
            .where(
                SceneCompilationJob.project_id == project_id,
                SceneCompilationJob.organization_id == auth.membership.organization_id,
            )
            .order_by(SceneCompilationJob.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _load_scene(
    session: AsyncSession, auth: AuthContext, project_id: UUID, scene_version_id: UUID
) -> SceneVersion:
    ensure_project_read(auth)
    scene = (
        await session.execute(
            select(SceneVersion).where(
                SceneVersion.id == scene_version_id,
                SceneVersion.project_id == project_id,
                SceneVersion.organization_id == auth.membership.organization_id,
                SceneVersion.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if scene is None:
        raise project_error(404, "SCENE_VERSION_NOT_FOUND", "Scene version not found.")
    return scene


async def _load_job(
    session: AsyncSession, auth: AuthContext, project_id: UUID, job_id: UUID
) -> SceneCompilationJob:
    job = (
        await session.execute(
            select(SceneCompilationJob).where(
                SceneCompilationJob.id == job_id,
                SceneCompilationJob.project_id == project_id,
                SceneCompilationJob.organization_id == auth.membership.organization_id,
            )
        )
    ).scalar_one_or_none()
    if job is None:
        raise project_error(404, "SCENE_JOB_NOT_FOUND", "Scene compilation job not found.")
    return job


async def _idempotent_job(
    session: AsyncSession, auth: AuthContext, idempotency_key: str
) -> SceneCompilationJob | None:
    return (
        await session.execute(
            select(SceneCompilationJob).where(
                SceneCompilationJob.organization_id == auth.membership.organization_id,
                SceneCompilationJob.created_by == auth.user.id,
                SceneCompilationJob.idempotency_key == idempotency_key,
            )
        )
    ).scalar_one_or_none()


async def _scene_for_job(session: AsyncSession, job_id: UUID) -> SceneVersion | None:
    return (
        await session.execute(select(SceneVersion).where(SceneVersion.compilation_job_id == job_id))
    ).scalar_one_or_none()


async def _next_scene_version(session: AsyncSession, auth: AuthContext, project_id: UUID) -> int:
    current = (
        await session.execute(
            select(func.max(SceneVersion.version)).where(
                SceneVersion.project_id == project_id,
                SceneVersion.organization_id == auth.membership.organization_id,
            )
        )
    ).scalar_one_or_none()
    return int(current or 0) + 1


async def _scene_response(session: AsyncSession, scene: SceneVersion) -> SceneVersionResponse:
    validation = await load_scene_validation_for_scene(session, scene)
    return SceneVersionResponse(
        id=scene.id,
        project_id=scene.project_id,
        version=scene.version,
        status=scene.status,
        is_stale=scene.is_stale,
        manifest=scene.manifest,
        validation_summary=validation.summary,
        created_at=scene.created_at,
        updated_at=scene.updated_at,
        disclaimer=scene.disclaimer,
    )


async def load_scene_validation_for_scene(
    session: AsyncSession, scene: SceneVersion
) -> SceneValidationResponse:
    row = (
        await session.execute(
            select(SceneValidationResult)
            .where(SceneValidationResult.scene_version_id == scene.id)
            .order_by(SceneValidationResult.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return SceneValidationResponse(
            scene_version_id=scene.id,
            validation_engine_version="compose-scene-validation-v1",
            geometry_engine_version=scene.geometry_engine_version,
            summary=SceneValidationSummary(
                status="valid",
                issue_count=0,
                blocking_count=0,
                error_count=0,
                warning_count=0,
                info_count=0,
            ),
            issues=[],
        )
    return SceneValidationResponse(
        scene_version_id=scene.id,
        validation_engine_version=row.validation_engine_version,
        geometry_engine_version=row.geometry_engine_version,
        summary=SceneValidationSummary.model_validate(row.summary),
        issues=[SceneValidationIssue.model_validate(issue) for issue in row.issues],
    )


async def _scene_objects(
    session: AsyncSession, auth: AuthContext, scene_version_id: UUID
) -> list[SceneObjectModel]:
    return list(
        (
            await session.execute(
                select(SceneObjectModel)
                .where(
                    SceneObjectModel.scene_version_id == scene_version_id,
                    SceneObjectModel.organization_id == auth.membership.organization_id,
                )
                .order_by(SceneObjectModel.object_type, SceneObjectModel.name)
            )
        )
        .scalars()
        .all()
    )


def _scene_object_response(item: SceneObjectModel) -> SceneObject:
    return SceneObject.model_validate(
        {
            "id": item.id,
            "stableObjectId": item.stable_object_id,
            "source2dObjectId": item.source_2d_object_id,
            "source2dObjectType": item.source_2d_object_type,
            "objectType": item.object_type,
            "floorId": item.floor_id,
            "parentObjectId": item.parent_object_id,
            "name": item.name,
            "geometryKind": item.geometry_kind,
            "transform": item.transform,
            "geometry": item.geometry,
            "boundingBox": item.bounding_box,
            "materialId": item.material_id,
            "triangleCount": item.triangle_count,
            "metadata": item.object_metadata,
        }
    )


def _job_response(
    job: SceneCompilationJob, scene_version_id: UUID | None
) -> SceneCompilationJobResponse:
    return SceneCompilationJobResponse(
        id=job.id,
        project_id=job.project_id,
        status=job.status,
        progress=job.progress,
        source_editor_checkpoint_id=job.source_editor_checkpoint_id,
        source_editor_revision=job.source_editor_revision,
        scene_version_id=scene_version_id,
        failure_code=job.failure_code,
        failure_details=job.failure_details,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        cancelled_at=job.cancelled_at,
    )


def _camera_response(view: SceneCameraView) -> SceneCameraViewResponse:
    return SceneCameraViewResponse(
        id=view.id,
        scene_version_id=view.scene_version_id,
        name=view.name,
        camera=view.camera,
        created_at=view.created_at,
    )


def _is_scene_stale(scene: SceneVersion | None, checkpoint: EditorCheckpoint | None) -> bool:
    if scene is None or checkpoint is None:
        return False
    return (
        scene.source_editor_checkpoint_id != checkpoint.id
        or scene.source_editor_revision != checkpoint.source_revision
        or scene.scene_engine_version != SCENE_ENGINE_VERSION
        or scene.scene_schema_version != SCENE_SCHEMA_VERSION
    )


async def _advance_job(
    session: AsyncSession,
    job: SceneCompilationJob,
    status: SceneCompilationJobStatus,
    progress: int,
) -> None:
    job.status = status
    job.progress = progress
    if job.started_at is None:
        job.started_at = datetime.now(UTC)
    await _event(
        session,
        job.id,
        progress,
        f"scene.compile.{status.value}",
        {"progress": progress, "status": status.value},
    )


async def _event(
    session: AsyncSession,
    job_id: UUID,
    sequence: int,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    session.add(
        SceneCompilationEvent(
            id=uuid4(),
            job_id=job_id,
            sequence=sequence,
            event_type=event_type,
            payload=payload,
        )
    )


async def _store_validation(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    scene_version_id: UUID | None,
    job_id: UUID | None,
    validation: SceneValidationResponse,
) -> None:
    session.add(
        SceneValidationResult(
            id=uuid4(),
            organization_id=auth.membership.organization_id,
            project_id=project_id,
            scene_version_id=scene_version_id,
            compilation_job_id=job_id,
            status=validation.summary.status,
            validation_engine_version=validation.validation_engine_version,
            geometry_engine_version=validation.geometry_engine_version,
            summary=validation.summary.model_dump(mode="json", by_alias=True),
            issues=[issue.model_dump(mode="json", by_alias=True) for issue in validation.issues],
            created_by=auth.user.id,
        )
    )


async def _audit(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    action: str,
    entity_type: str,
    entity_id: UUID | None,
    payload: dict[str, Any],
) -> None:
    session.add(
        SceneAuditEvent(
            id=uuid4(),
            organization_id=auth.membership.organization_id,
            project_id=project_id,
            actor_id=auth.user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
        )
    )
