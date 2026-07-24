from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.auth import AuthContext, get_auth_context
from compose_ai_api.core.database import get_db_session
from compose_ai_api.domains.projects.schemas import (
    ProjectActivityResponse,
    ProjectCreateRequest,
    ProjectDashboardSummaryResponse,
    ProjectDetailResponse,
    ProjectDuplicateRequest,
    ProjectSummaryResponse,
    ProjectUpdateRequest,
)
from compose_ai_api.domains.projects.service import (
    archive_project,
    complete_project,
    create_project,
    duplicate_project,
    list_projects,
    load_project_detail,
    project_activity,
    project_dashboard_summary,
    project_error,
    project_tag_suggestions,
    restore_archived_project,
    restore_deleted_project,
    soft_delete_project,
    update_project,
)
from compose_ai_api.schemas.api import ApiEnvelope, ApiMeta, PaginationMeta

router = APIRouter(prefix="/projects", tags=["projects"])
AuthContextDependency = Annotated[AuthContext, Depends(get_auth_context)]
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=128),
]
IfMatch = Annotated[str, Header(alias="If-Match")]


@router.post(
    "",
    response_model=ApiEnvelope[ProjectDetailResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create(
    request: ProjectCreateRequest,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
    response: Response,
) -> ApiEnvelope[ProjectDetailResponse]:
    request_id = str(uuid4())
    project = await create_project(session, context, request, idempotency_key, request_id)
    response.headers["ETag"] = _etag(project.version)
    return ApiEnvelope(data=project, meta=ApiMeta(request_id=request_id))


@router.get("", response_model=ApiEnvelope[list[ProjectSummaryResponse]])
async def list_all(
    context: AuthContextDependency,
    session: SessionDependency,
    view: Annotated[str, Query(pattern=r"^(active|drafts|archived|trash)$")] = "active",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
    query: Annotated[str | None, Query(alias="q", max_length=160)] = None,
    project_type: Annotated[str | None, Query(alias="type", max_length=40)] = None,
    tag: Annotated[str | None, Query(max_length=30)] = None,
) -> ApiEnvelope[list[ProjectSummaryResponse]]:
    request_id = str(uuid4())
    projects, next_cursor, has_more = await list_projects(
        session,
        context,
        view,
        limit,
        cursor,
        query,
        project_type,
        tag,
    )
    return ApiEnvelope(
        data=projects,
        meta=ApiMeta(
            request_id=request_id,
            pagination=PaginationMeta(next_cursor=next_cursor, has_more=has_more, limit=limit),
        ),
    )


@router.get("/summary", response_model=ApiEnvelope[ProjectDashboardSummaryResponse])
async def summary(
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[ProjectDashboardSummaryResponse]:
    request_id = str(uuid4())
    project_summary = await project_dashboard_summary(session, context)
    return ApiEnvelope(data=project_summary, meta=ApiMeta(request_id=request_id))


@router.get("/activity", response_model=ApiEnvelope[list[ProjectActivityResponse]])
async def activity(
    context: AuthContextDependency,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> ApiEnvelope[list[ProjectActivityResponse]]:
    request_id = str(uuid4())
    events = await project_activity(session, context, limit)
    return ApiEnvelope(data=events, meta=ApiMeta(request_id=request_id))


@router.get("/tags", response_model=ApiEnvelope[list[str]])
async def tags(
    context: AuthContextDependency,
    session: SessionDependency,
    query: Annotated[str | None, Query(alias="q", max_length=30)] = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> ApiEnvelope[list[str]]:
    request_id = str(uuid4())
    suggestions = await project_tag_suggestions(session, context, query, limit)
    return ApiEnvelope(data=suggestions, meta=ApiMeta(request_id=request_id))


@router.get("/{project_id}", response_model=ApiEnvelope[ProjectDetailResponse])
async def detail(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    response: Response,
) -> ApiEnvelope[ProjectDetailResponse]:
    request_id = str(uuid4())
    project = await load_project_detail(session, context, project_id)
    response.headers["ETag"] = _etag(project.version)
    return ApiEnvelope(data=project, meta=ApiMeta(request_id=request_id))


@router.patch("/{project_id}", response_model=ApiEnvelope[ProjectDetailResponse])
async def update(
    project_id: UUID,
    request: ProjectUpdateRequest,
    context: AuthContextDependency,
    session: SessionDependency,
    if_match: IfMatch,
    response: Response,
) -> ApiEnvelope[ProjectDetailResponse]:
    request_id = str(uuid4())
    project = await update_project(
        session,
        context,
        project_id,
        request,
        _parse_etag(if_match),
        request_id,
    )
    response.headers["ETag"] = _etag(project.version)
    return ApiEnvelope(data=project, meta=ApiMeta(request_id=request_id))


@router.post("/{project_id}/complete", response_model=ApiEnvelope[ProjectDetailResponse])
async def complete(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    if_match: IfMatch,
    response: Response,
) -> ApiEnvelope[ProjectDetailResponse]:
    request_id = str(uuid4())
    project = await complete_project(
        session, context, project_id, _parse_etag(if_match), request_id
    )
    response.headers["ETag"] = _etag(project.version)
    return ApiEnvelope(data=project, meta=ApiMeta(request_id=request_id))


@router.post("/{project_id}/archive", response_model=ApiEnvelope[ProjectDetailResponse])
async def archive(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    if_match: IfMatch,
    response: Response,
) -> ApiEnvelope[ProjectDetailResponse]:
    request_id = str(uuid4())
    project = await archive_project(session, context, project_id, _parse_etag(if_match), request_id)
    response.headers["ETag"] = _etag(project.version)
    return ApiEnvelope(data=project, meta=ApiMeta(request_id=request_id))


@router.post("/{project_id}/restore", response_model=ApiEnvelope[ProjectDetailResponse])
async def restore(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    if_match: IfMatch,
    response: Response,
) -> ApiEnvelope[ProjectDetailResponse]:
    request_id = str(uuid4())
    project = await restore_archived_project(
        session, context, project_id, _parse_etag(if_match), request_id
    )
    response.headers["ETag"] = _etag(project.version)
    return ApiEnvelope(data=project, meta=ApiMeta(request_id=request_id))


@router.post(
    "/{project_id}/duplicate",
    response_model=ApiEnvelope[ProjectDetailResponse],
    status_code=status.HTTP_201_CREATED,
)
async def duplicate(
    project_id: UUID,
    request: ProjectDuplicateRequest,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
    response: Response,
) -> ApiEnvelope[ProjectDetailResponse]:
    request_id = str(uuid4())
    project = await duplicate_project(
        session,
        context,
        project_id,
        request,
        idempotency_key,
        request_id,
    )
    response.headers["ETag"] = _etag(project.version)
    return ApiEnvelope(data=project, meta=ApiMeta(request_id=request_id))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    if_match: IfMatch,
) -> Response:
    await soft_delete_project(
        session,
        context,
        project_id,
        _parse_etag(if_match),
        str(uuid4()),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{project_id}/restore-deleted", response_model=ApiEnvelope[ProjectDetailResponse])
async def restore_deleted(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    if_match: IfMatch,
    response: Response,
) -> ApiEnvelope[ProjectDetailResponse]:
    request_id = str(uuid4())
    project = await restore_deleted_project(
        session, context, project_id, _parse_etag(if_match), request_id
    )
    response.headers["ETag"] = _etag(project.version)
    return ApiEnvelope(data=project, meta=ApiMeta(request_id=request_id))


@router.get(
    "/{project_id}/activity",
    response_model=ApiEnvelope[list[ProjectActivityResponse]],
)
async def project_activity_history(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiEnvelope[list[ProjectActivityResponse]]:
    await load_project_detail(session, context, project_id)
    request_id = str(uuid4())
    events = await project_activity(session, context, limit, project_id)
    return ApiEnvelope(data=events, meta=ApiMeta(request_id=request_id))


def _etag(version: int) -> str:
    return f'"{version}"'


def _parse_etag(value: str) -> int:
    normalized = value.removeprefix("W/").strip().strip('"')
    try:
        version = int(normalized)
    except ValueError as error:
        raise project_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PROJECT_VERSION_INVALID",
            "If-Match must contain a project version.",
        ) from error
    if version < 1:
        raise project_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PROJECT_VERSION_INVALID",
            "Project versions must be positive.",
        )
    return version
