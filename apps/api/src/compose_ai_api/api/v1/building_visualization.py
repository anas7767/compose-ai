from __future__ import annotations

from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.auth import AuthContext, get_auth_context
from compose_ai_api.core.database import get_db_session
from compose_ai_api.domains.building_visualization.schemas import (
    SceneCameraViewCreateRequest,
    SceneCameraViewResponse,
    SceneCameraViewsResponse,
    SceneCompilationJobResponse,
    SceneCompileRequest,
    SceneMaterialsResponse,
    SceneObjectsResponse,
    SceneValidationResponse,
    SceneVersionResponse,
    SceneWorkspaceResponse,
)
from compose_ai_api.domains.building_visualization.service import (
    cancel_scene_job,
    compile_scene,
    create_camera_view,
    list_camera_views,
    list_scene_events,
    list_scene_versions,
    load_scene_job,
    load_scene_materials,
    load_scene_objects,
    load_scene_validation,
    load_scene_version,
    load_scene_workspace,
    sse_payload,
)
from compose_ai_api.schemas.api import ApiEnvelope, ApiMeta

router = APIRouter(prefix="/projects/{project_id}/visualization", tags=["building-visualization"])
AuthContextDependency = Annotated[AuthContext, Depends(get_auth_context)]
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=128),
]


@router.get("", response_model=ApiEnvelope[SceneWorkspaceResponse])
async def scene_workspace(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[SceneWorkspaceResponse]:
    return ApiEnvelope(
        data=await load_scene_workspace(session, context, project_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post(
    "/compile",
    response_model=ApiEnvelope[SceneCompilationJobResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def scene_compile(
    project_id: UUID,
    request: SceneCompileRequest,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
) -> ApiEnvelope[SceneCompilationJobResponse]:
    return ApiEnvelope(
        data=await compile_scene(session, context, project_id, request, idempotency_key),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get("/jobs/{job_id}", response_model=ApiEnvelope[SceneCompilationJobResponse])
async def scene_job(
    project_id: UUID,
    job_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[SceneCompilationJobResponse]:
    return ApiEnvelope(
        data=await load_scene_job(session, context, project_id, job_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get("/jobs/{job_id}/events")
async def scene_job_events(
    project_id: UUID,
    job_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> Response:
    events = await list_scene_events(session, context, project_id, job_id)
    return Response(content=sse_payload(events), media_type="text/event-stream")


@router.post("/jobs/{job_id}/cancel", response_model=ApiEnvelope[SceneCompilationJobResponse])
async def scene_job_cancel(
    project_id: UUID,
    job_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[SceneCompilationJobResponse]:
    return ApiEnvelope(
        data=await cancel_scene_job(session, context, project_id, job_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get("/versions", response_model=ApiEnvelope[list[SceneVersionResponse]])
async def scene_versions(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[list[SceneVersionResponse]]:
    return ApiEnvelope(
        data=await list_scene_versions(session, context, project_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get("/versions/{scene_version_id}", response_model=ApiEnvelope[SceneVersionResponse])
async def scene_version(
    project_id: UUID,
    scene_version_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[SceneVersionResponse]:
    return ApiEnvelope(
        data=await load_scene_version(session, context, project_id, scene_version_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get(
    "/versions/{scene_version_id}/objects", response_model=ApiEnvelope[SceneObjectsResponse]
)
async def scene_objects(
    project_id: UUID,
    scene_version_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[SceneObjectsResponse]:
    return ApiEnvelope(
        data=await load_scene_objects(session, context, project_id, scene_version_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get(
    "/versions/{scene_version_id}/materials",
    response_model=ApiEnvelope[SceneMaterialsResponse],
)
async def scene_materials(
    project_id: UUID,
    scene_version_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[SceneMaterialsResponse]:
    return ApiEnvelope(
        data=await load_scene_materials(session, context, project_id, scene_version_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get(
    "/versions/{scene_version_id}/validation",
    response_model=ApiEnvelope[SceneValidationResponse],
)
async def scene_validation(
    project_id: UUID,
    scene_version_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[SceneValidationResponse]:
    return ApiEnvelope(
        data=await load_scene_validation(session, context, project_id, scene_version_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get(
    "/versions/{scene_version_id}/camera-views",
    response_model=ApiEnvelope[SceneCameraViewsResponse],
)
async def scene_camera_views(
    project_id: UUID,
    scene_version_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[SceneCameraViewsResponse]:
    return ApiEnvelope(
        data=await list_camera_views(session, context, project_id, scene_version_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post(
    "/versions/{scene_version_id}/camera-views",
    response_model=ApiEnvelope[SceneCameraViewResponse],
    status_code=status.HTTP_201_CREATED,
)
async def scene_camera_view_create(
    project_id: UUID,
    scene_version_id: UUID,
    request: SceneCameraViewCreateRequest,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[SceneCameraViewResponse]:
    return ApiEnvelope(
        data=await create_camera_view(session, context, project_id, scene_version_id, request),
        meta=ApiMeta(request_id=str(uuid4())),
    )
