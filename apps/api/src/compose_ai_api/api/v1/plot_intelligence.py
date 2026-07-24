from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.auth import AuthContext, get_auth_context
from compose_ai_api.core.database import get_db_session
from compose_ai_api.domains.plot_intelligence.repository import plot_error
from compose_ai_api.domains.plot_intelligence.schemas import (
    PlotAnalysisResponse,
    PlotBoundaryInput,
    PlotBoundaryVersionResponse,
    PlotIntelligenceResponse,
    PlotProfileUpdateRequest,
    PlotRestoreResponse,
    PlotValidationRequest,
)
from compose_ai_api.domains.plot_intelligence.service import (
    clear_boundary,
    create_boundary_version,
    get_boundary_history_item,
    get_plot_intelligence,
    list_boundary_history,
    recalculate_plot_analysis,
    restore_boundary_version,
    undo_boundary_restore,
    update_plot_profile,
    validate_plot_profile,
)
from compose_ai_api.schemas.api import ApiEnvelope, ApiMeta, PaginationMeta

router = APIRouter(prefix="/projects/{project_id}/plot", tags=["plot-intelligence"])
AuthContextDependency = Annotated[AuthContext, Depends(get_auth_context)]
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=128),
]
IfMatch = Annotated[str, Header(alias="If-Match")]


@router.get("", response_model=ApiEnvelope[PlotIntelligenceResponse])
async def detail(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    response: Response,
) -> ApiEnvelope[PlotIntelligenceResponse]:
    request_id = str(uuid4())
    plot = await get_plot_intelligence(session, context, project_id)
    response.headers["ETag"] = _etag(plot.project_version)
    return ApiEnvelope(data=plot, meta=ApiMeta(request_id=request_id))


@router.patch("", response_model=ApiEnvelope[PlotIntelligenceResponse])
async def update(
    project_id: UUID,
    request: PlotProfileUpdateRequest,
    context: AuthContextDependency,
    session: SessionDependency,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    response: Response,
) -> ApiEnvelope[PlotIntelligenceResponse]:
    request_id = str(uuid4())
    plot = await update_plot_profile(
        session,
        context,
        project_id,
        request,
        _parse_etag(if_match),
        idempotency_key,
        request_id,
    )
    response.headers["ETag"] = _etag(plot.project_version)
    return ApiEnvelope(data=plot, meta=ApiMeta(request_id=request_id))


@router.post("/validate", response_model=ApiEnvelope[PlotAnalysisResponse])
async def validate(
    project_id: UUID,
    request: PlotValidationRequest,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[PlotAnalysisResponse]:
    request_id = str(uuid4())
    analysis = await validate_plot_profile(session, context, project_id, request)
    return ApiEnvelope(data=analysis, meta=ApiMeta(request_id=request_id))


@router.post(
    "/boundary-versions",
    response_model=ApiEnvelope[PlotIntelligenceResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_boundary(
    project_id: UUID,
    request: PlotBoundaryInput,
    context: AuthContextDependency,
    session: SessionDependency,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    response: Response,
) -> ApiEnvelope[PlotIntelligenceResponse]:
    request_id = str(uuid4())
    plot = await create_boundary_version(
        session,
        context,
        project_id,
        request,
        _parse_etag(if_match),
        idempotency_key,
        request_id,
    )
    response.headers["ETag"] = _etag(plot.project_version)
    return ApiEnvelope(data=plot, meta=ApiMeta(request_id=request_id))


@router.get(
    "/boundary-versions",
    response_model=ApiEnvelope[list[PlotBoundaryVersionResponse]],
)
async def boundary_history(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: str | None = None,
) -> ApiEnvelope[list[PlotBoundaryVersionResponse]]:
    request_id = str(uuid4())
    boundaries, next_cursor, has_more = await list_boundary_history(
        session, context, project_id, limit, cursor
    )
    return ApiEnvelope(
        data=boundaries,
        meta=ApiMeta(
            request_id=request_id,
            pagination=PaginationMeta(next_cursor=next_cursor, has_more=has_more, limit=limit),
        ),
    )


@router.get(
    "/boundary-versions/{boundary_id}",
    response_model=ApiEnvelope[PlotBoundaryVersionResponse],
)
async def boundary_history_item(
    project_id: UUID,
    boundary_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[PlotBoundaryVersionResponse]:
    request_id = str(uuid4())
    boundary = await get_boundary_history_item(session, context, project_id, boundary_id)
    return ApiEnvelope(data=boundary, meta=ApiMeta(request_id=request_id))


@router.post(
    "/boundary-versions/{boundary_id}/restore",
    response_model=ApiEnvelope[PlotRestoreResponse],
)
async def restore_boundary(
    project_id: UUID,
    boundary_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    response: Response,
) -> ApiEnvelope[PlotRestoreResponse]:
    request_id = str(uuid4())
    restored = await restore_boundary_version(
        session,
        context,
        project_id,
        boundary_id,
        _parse_etag(if_match),
        idempotency_key,
        request_id,
    )
    response.headers["ETag"] = _etag(restored.plot.project_version)
    return ApiEnvelope(data=restored, meta=ApiMeta(request_id=request_id))


@router.post(
    "/boundary-restores/{action_id}/undo",
    response_model=ApiEnvelope[PlotIntelligenceResponse],
)
async def undo_restore(
    project_id: UUID,
    action_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    response: Response,
) -> ApiEnvelope[PlotIntelligenceResponse]:
    request_id = str(uuid4())
    plot = await undo_boundary_restore(
        session,
        context,
        project_id,
        action_id,
        _parse_etag(if_match),
        idempotency_key,
        request_id,
    )
    response.headers["ETag"] = _etag(plot.project_version)
    return ApiEnvelope(data=plot, meta=ApiMeta(request_id=request_id))


@router.delete("/boundary", response_model=ApiEnvelope[PlotIntelligenceResponse])
async def remove_boundary(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    response: Response,
) -> ApiEnvelope[PlotIntelligenceResponse]:
    request_id = str(uuid4())
    plot = await clear_boundary(
        session,
        context,
        project_id,
        _parse_etag(if_match),
        idempotency_key,
        request_id,
    )
    response.headers["ETag"] = _etag(plot.project_version)
    return ApiEnvelope(data=plot, meta=ApiMeta(request_id=request_id))


@router.post("/recalculate", response_model=ApiEnvelope[PlotIntelligenceResponse])
async def recalculate(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
    response: Response,
) -> ApiEnvelope[PlotIntelligenceResponse]:
    request_id = str(uuid4())
    plot = await recalculate_plot_analysis(
        session,
        context,
        project_id,
        _parse_etag(if_match),
        idempotency_key,
        request_id,
    )
    response.headers["ETag"] = _etag(plot.project_version)
    return ApiEnvelope(data=plot, meta=ApiMeta(request_id=request_id))


def _etag(version: int) -> str:
    return f'"{version}"'


def _parse_etag(value: str) -> int:
    normalized = value.removeprefix("W/").strip().strip('"')
    try:
        version = int(normalized)
    except ValueError as error:
        raise plot_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "PLOT_VERSION_INVALID",
            "If-Match must contain a project version.",
        ) from error
    if version < 1:
        raise plot_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "PLOT_VERSION_INVALID",
            "Project versions must be positive.",
        )
    return version
