from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    Query,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.auth import AuthContext, get_auth_context
from compose_ai_api.core.config import get_settings
from compose_ai_api.core.database import get_db_session
from compose_ai_api.domains.floor_plans.execution import (
    process_generation_job,
    stream_generation_events,
)
from compose_ai_api.domains.floor_plans.schemas import (
    FloorPlanAcceptRequest,
    FloorPlanCompareRequest,
    FloorPlanCompareResponse,
    FloorPlanDesignVersionResponse,
    FloorPlanGenerationAcceptedResponse,
    FloorPlanGenerationRequest,
    FloorPlanOptionResponse,
    FloorPlanReadinessResponse,
    FloorPlanRejectRequest,
    FloorPlanRestoreVersionRequest,
    FloorPlanRunResponse,
    FloorPlanValidationResponse,
)
from compose_ai_api.domains.floor_plans.service import (
    accept_option,
    cancel_run,
    compare_options,
    delete_design_version,
    enqueue_generation,
    floor_plan_readiness,
    list_design_versions,
    list_options,
    list_runs,
    load_design_version,
    load_option,
    load_run,
    reject_option,
    restore_design_version,
    retry_generation,
    validate_option,
)
from compose_ai_api.domains.projects.service import project_error
from compose_ai_api.schemas.api import ApiEnvelope, ApiMeta

router = APIRouter(prefix="/projects/{project_id}/floor-plans", tags=["floor-plans"])
AuthContextDependency = Annotated[AuthContext, Depends(get_auth_context)]
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=128),
]
IfMatch = Annotated[str, Header(alias="If-Match")]


@router.get("/readiness", response_model=ApiEnvelope[FloorPlanReadinessResponse])
async def readiness(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[FloorPlanReadinessResponse]:
    return ApiEnvelope(
        data=await floor_plan_readiness(session, context, project_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post(
    "/generations",
    response_model=ApiEnvelope[FloorPlanGenerationAcceptedResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_generation(
    project_id: UUID,
    request: FloorPlanGenerationRequest,
    background_tasks: BackgroundTasks,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
) -> ApiEnvelope[FloorPlanGenerationAcceptedResponse]:
    accepted = await enqueue_generation(
        session,
        get_settings(),
        context,
        project_id,
        request,
        idempotency_key,
    )
    background_tasks.add_task(process_generation_job, accepted.job_id)
    return ApiEnvelope(data=accepted, meta=ApiMeta(request_id=str(uuid4())))


@router.get("/generations", response_model=ApiEnvelope[list[FloorPlanRunResponse]])
async def generations(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiEnvelope[list[FloorPlanRunResponse]]:
    return ApiEnvelope(
        data=await list_runs(session, context, project_id, limit),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get(
    "/generations/{run_id}",
    response_model=ApiEnvelope[FloorPlanRunResponse],
)
async def generation(
    project_id: UUID,
    run_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[FloorPlanRunResponse]:
    return ApiEnvelope(
        data=await load_run(session, context, project_id, run_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post(
    "/generations/{run_id}/retry",
    response_model=ApiEnvelope[FloorPlanGenerationAcceptedResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry(
    project_id: UUID,
    run_id: UUID,
    background_tasks: BackgroundTasks,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
) -> ApiEnvelope[FloorPlanGenerationAcceptedResponse]:
    accepted = await retry_generation(
        session,
        get_settings(),
        context,
        project_id,
        run_id,
        idempotency_key,
    )
    background_tasks.add_task(process_generation_job, accepted.job_id)
    return ApiEnvelope(data=accepted, meta=ApiMeta(request_id=str(uuid4())))


@router.post(
    "/generations/{run_id}/cancel",
    response_model=ApiEnvelope[FloorPlanRunResponse],
)
async def cancel(
    project_id: UUID,
    run_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[FloorPlanRunResponse]:
    return ApiEnvelope(
        data=await cancel_run(session, context, project_id, run_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get("/generations/{run_id}/events", response_class=StreamingResponse)
async def generation_events(
    project_id: UUID,
    run_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    await load_run(session, context, project_id, run_id)
    after_sequence = _parse_event_cursor(last_event_id)

    async def event_stream() -> AsyncIterator[str]:
        async for event in stream_generation_events(
            run_id,
            context.membership.organization_id,
            after_sequence=after_sequence,
        ):
            yield (
                f"id: {event['sequence']}\n"
                f"event: {event['eventType']}\n"
                f"data: {json.dumps(event, separators=(',', ':'))}\n\n"
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/generations/{run_id}/options",
    response_model=ApiEnvelope[list[FloorPlanOptionResponse]],
)
async def generation_options(
    project_id: UUID,
    run_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[list[FloorPlanOptionResponse]]:
    return ApiEnvelope(
        data=await list_options(session, context, project_id, run_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post("/options/compare", response_model=ApiEnvelope[FloorPlanCompareResponse])
async def compare(
    project_id: UUID,
    request: FloorPlanCompareRequest,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[FloorPlanCompareResponse]:
    return ApiEnvelope(
        data=await compare_options(session, context, project_id, request.option_ids),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get("/options/{option_id}", response_model=ApiEnvelope[FloorPlanOptionResponse])
async def option(
    project_id: UUID,
    option_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[FloorPlanOptionResponse]:
    return ApiEnvelope(
        data=await load_option(session, context, project_id, option_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post(
    "/options/{option_id}/validate",
    response_model=ApiEnvelope[FloorPlanValidationResponse],
)
async def validate(
    project_id: UUID,
    option_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[FloorPlanValidationResponse]:
    return ApiEnvelope(
        data=await validate_option(session, context, project_id, option_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post(
    "/options/{option_id}/accept",
    response_model=ApiEnvelope[FloorPlanDesignVersionResponse],
)
async def accept(
    project_id: UUID,
    option_id: UUID,
    request: FloorPlanAcceptRequest,
    context: AuthContextDependency,
    session: SessionDependency,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
) -> ApiEnvelope[FloorPlanDesignVersionResponse]:
    del idempotency_key
    return ApiEnvelope(
        data=await accept_option(
            session,
            context,
            project_id,
            option_id,
            expected_version=_parse_etag(if_match),
            name=request.name,
        ),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post(
    "/options/{option_id}/reject",
    response_model=ApiEnvelope[FloorPlanOptionResponse],
)
async def reject(
    project_id: UUID,
    option_id: UUID,
    request: FloorPlanRejectRequest,
    context: AuthContextDependency,
    session: SessionDependency,
    if_match: IfMatch,
    idempotency_key: IdempotencyKey,
) -> ApiEnvelope[FloorPlanOptionResponse]:
    del idempotency_key
    return ApiEnvelope(
        data=await reject_option(
            session,
            context,
            project_id,
            option_id,
            expected_version=_parse_etag(if_match),
            reason=request.reason,
        ),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get(
    "/design-versions",
    response_model=ApiEnvelope[list[FloorPlanDesignVersionResponse]],
)
async def design_versions(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[list[FloorPlanDesignVersionResponse]]:
    return ApiEnvelope(
        data=await list_design_versions(session, context, project_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get(
    "/design-versions/{design_version_id}",
    response_model=ApiEnvelope[FloorPlanDesignVersionResponse],
)
async def design_version(
    project_id: UUID,
    design_version_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[FloorPlanDesignVersionResponse]:
    return ApiEnvelope(
        data=await load_design_version(session, context, project_id, design_version_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post(
    "/design-versions/{design_version_id}/restore",
    response_model=ApiEnvelope[FloorPlanDesignVersionResponse],
)
async def restore_design(
    project_id: UUID,
    design_version_id: UUID,
    request: FloorPlanRestoreVersionRequest,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
) -> ApiEnvelope[FloorPlanDesignVersionResponse]:
    return ApiEnvelope(
        data=await restore_design_version(
            session,
            context,
            project_id,
            design_version_id,
            name=request.name,
            idempotency_key=idempotency_key,
        ),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.delete("/design-versions/{design_version_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_design(
    project_id: UUID,
    design_version_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> None:
    await delete_design_version(session, context, project_id, design_version_id)


def _parse_event_cursor(value: str | None) -> int:
    if not value:
        return 0
    try:
        return max(0, int(value))
    except ValueError as error:
        raise project_error(
            422,
            "FLOOR_PLAN_EVENT_CURSOR_INVALID",
            "Last-Event-ID must contain an event sequence number.",
        ) from error


def _parse_etag(value: str) -> int:
    normalized = value.removeprefix("W/").strip().strip('"')
    try:
        version = int(normalized)
    except ValueError as error:
        raise project_error(
            422,
            "FLOOR_PLAN_VERSION_INVALID",
            "If-Match must contain a positive option version.",
        ) from error
    if version < 1:
        raise project_error(
            422,
            "FLOOR_PLAN_VERSION_INVALID",
            "If-Match must contain a positive option version.",
        )
    return version
