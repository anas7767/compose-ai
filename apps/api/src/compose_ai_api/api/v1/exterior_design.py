from __future__ import annotations

import json
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.auth import AuthContext, get_auth_context
from compose_ai_api.core.database import get_db_session
from compose_ai_api.domains.exterior_design.schemas import (
    ExteriorGenerationAccepted,
    ExteriorGenerationRequest,
    ExteriorOption,
    ExteriorOptionActionRequest,
    ExteriorReadinessResponse,
    ExteriorRun,
    ExteriorRunDetail,
)
from compose_ai_api.domains.exterior_design.service import (
    approve_option,
    cancel_run,
    create_generation,
    delete_option,
    list_events,
    list_options,
    list_runs,
    load_asset_content,
    load_option,
    load_readiness,
    load_run,
    reject_option,
)
from compose_ai_api.schemas.api import ApiEnvelope, ApiMeta

router = APIRouter(prefix="/projects/{project_id}/exterior-design", tags=["exterior-design"])
AuthContextDependency = Annotated[AuthContext, Depends(get_auth_context)]
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


@router.get("/readiness", response_model=ApiEnvelope[ExteriorReadinessResponse])
async def exterior_readiness(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[ExteriorReadinessResponse]:
    return ApiEnvelope(
        data=await load_readiness(session, context, project_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post(
    "/generations",
    response_model=ApiEnvelope[ExteriorGenerationAccepted],
    status_code=status.HTTP_202_ACCEPTED,
)
async def exterior_generation_create(
    project_id: UUID,
    request: ExteriorGenerationRequest,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
) -> ApiEnvelope[ExteriorGenerationAccepted]:
    return ApiEnvelope(
        data=await create_generation(session, context, project_id, request, idempotency_key),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get("/generations", response_model=ApiEnvelope[list[ExteriorRun]])
async def exterior_generations(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[list[ExteriorRun]]:
    return ApiEnvelope(
        data=await list_runs(session, context, project_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get("/generations/{run_id}", response_model=ApiEnvelope[ExteriorRunDetail])
async def exterior_generation(
    project_id: UUID,
    run_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[ExteriorRunDetail]:
    return ApiEnvelope(
        data=await load_run(session, context, project_id, run_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get("/generations/{run_id}/events")
async def exterior_generation_events(
    project_id: UUID,
    run_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> Response:
    events = await list_events(session, context, project_id, run_id)
    chunks = [
        f"id: {event.sequence}\nevent: {event.event_type}\ndata: "
        f"{json.dumps(event.payload, default=str)}\n\n"
        for event in events
    ]
    return Response(content="".join(chunks), media_type="text/event-stream")


@router.post("/generations/{run_id}/cancel", response_model=ApiEnvelope[ExteriorRun])
async def exterior_generation_cancel(
    project_id: UUID,
    run_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[ExteriorRun]:
    return ApiEnvelope(
        data=await cancel_run(session, context, project_id, run_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get("/options", response_model=ApiEnvelope[list[ExteriorOption]])
async def exterior_options(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[list[ExteriorOption]]:
    return ApiEnvelope(
        data=await list_options(session, context, project_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get("/options/{option_id}", response_model=ApiEnvelope[ExteriorOption])
async def exterior_option(
    project_id: UUID,
    option_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[ExteriorOption]:
    return ApiEnvelope(
        data=await load_option(session, context, project_id, option_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post("/options/{option_id}/approve", response_model=ApiEnvelope[ExteriorOption])
async def exterior_option_approve(
    project_id: UUID,
    option_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[ExteriorOption]:
    return ApiEnvelope(
        data=await approve_option(session, context, project_id, option_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post("/options/{option_id}/reject", response_model=ApiEnvelope[ExteriorOption])
async def exterior_option_reject(
    project_id: UUID,
    option_id: UUID,
    request: ExteriorOptionActionRequest,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[ExteriorOption]:
    return ApiEnvelope(
        data=await reject_option(session, context, project_id, option_id, request),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.delete("/options/{option_id}", status_code=status.HTTP_204_NO_CONTENT)
async def exterior_option_delete(
    project_id: UUID,
    option_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> None:
    await delete_option(session, context, project_id, option_id)


@router.get("/assets/{asset_id}")
async def exterior_asset(
    project_id: UUID,
    asset_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> Response:
    content, mime_type = await load_asset_content(session, context, project_id, asset_id)
    return Response(content=content, media_type=mime_type)
