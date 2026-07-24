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
    Response,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.auth import AuthContext, get_auth_context
from compose_ai_api.core.config import get_settings
from compose_ai_api.core.database import get_db_session
from compose_ai_api.domains.ai_architect.execution import (
    process_brief_job,
    stream_chat_run,
)
from compose_ai_api.domains.ai_architect.schemas import (
    AIBriefAcceptedResponse,
    AIBriefGenerateRequest,
    AIBriefResponse,
    AIMemoryResponse,
    AIMessageAcceptedResponse,
    AIMessageCreateRequest,
    AIMessageResponse,
    AIProposalApplyRequest,
    AIProposalApplyResponse,
    AIProposalResponse,
    AIRunResponse,
    AIRunRetryResponse,
    AISuggestedPromptResponse,
    AIThreadCreateRequest,
    AIThreadResponse,
    AIThreadUpdateRequest,
    AIUsageResponse,
)
from compose_ai_api.domains.ai_architect.service import (
    apply_proposals,
    cancel_run,
    create_message,
    create_thread,
    enqueue_brief,
    list_briefs,
    list_memory_versions,
    list_messages,
    list_threads,
    load_brief,
    load_current_brief,
    load_current_memory,
    load_run,
    load_thread,
    retry_run,
    review_brief,
    review_proposal,
    set_thread_archived,
    suggested_prompts,
    update_thread,
)
from compose_ai_api.domains.ai_architect.usage import load_usage_summary
from compose_ai_api.domains.projects.service import project_error
from compose_ai_api.schemas.api import ApiEnvelope, ApiMeta, PaginationMeta

router = APIRouter(prefix="/projects/{project_id}/ai", tags=["ai-architect"])
AuthContextDependency = Annotated[AuthContext, Depends(get_auth_context)]
SessionDependency = Annotated[AsyncSession, Depends(get_db_session)]
IdempotencyKey = Annotated[
    str,
    Header(alias="Idempotency-Key", min_length=1, max_length=128),
]
IfMatch = Annotated[str, Header(alias="If-Match")]


@router.post(
    "/threads",
    response_model=ApiEnvelope[AIThreadResponse],
    status_code=status.HTTP_201_CREATED,
)
async def create_conversation(
    project_id: UUID,
    request: AIThreadCreateRequest,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
) -> ApiEnvelope[AIThreadResponse]:
    request_id = str(uuid4())
    thread = await create_thread(session, context, project_id, request, idempotency_key)
    return ApiEnvelope(data=thread, meta=ApiMeta(request_id=request_id))


@router.get("/threads", response_model=ApiEnvelope[list[AIThreadResponse]])
async def conversations(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    include_archived: Annotated[bool, Query(alias="includeArchived")] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    cursor: str | None = None,
) -> ApiEnvelope[list[AIThreadResponse]]:
    items, next_cursor, has_more = await list_threads(
        session,
        context,
        project_id,
        include_archived=include_archived,
        limit=limit,
        cursor=cursor,
    )
    return ApiEnvelope(
        data=items,
        meta=ApiMeta(
            request_id=str(uuid4()),
            pagination=PaginationMeta(
                next_cursor=next_cursor,
                has_more=has_more,
                limit=limit,
            ),
        ),
    )


@router.get("/threads/{thread_id}", response_model=ApiEnvelope[AIThreadResponse])
async def conversation(
    project_id: UUID,
    thread_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[AIThreadResponse]:
    return ApiEnvelope(
        data=await load_thread(session, context, project_id, thread_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.patch("/threads/{thread_id}", response_model=ApiEnvelope[AIThreadResponse])
async def rename_conversation(
    project_id: UUID,
    thread_id: UUID,
    request: AIThreadUpdateRequest,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[AIThreadResponse]:
    return ApiEnvelope(
        data=await update_thread(session, context, project_id, thread_id, request),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post("/threads/{thread_id}/archive", response_model=ApiEnvelope[AIThreadResponse])
async def archive_conversation(
    project_id: UUID,
    thread_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[AIThreadResponse]:
    return ApiEnvelope(
        data=await set_thread_archived(session, context, project_id, thread_id, archived=True),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post("/threads/{thread_id}/restore", response_model=ApiEnvelope[AIThreadResponse])
async def restore_conversation(
    project_id: UUID,
    thread_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[AIThreadResponse]:
    return ApiEnvelope(
        data=await set_thread_archived(session, context, project_id, thread_id, archived=False),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get(
    "/threads/{thread_id}/messages",
    response_model=ApiEnvelope[list[AIMessageResponse]],
)
async def messages(
    project_id: UUID,
    thread_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    before_sequence: Annotated[int | None, Query(alias="beforeSequence", ge=1)] = None,
) -> ApiEnvelope[list[AIMessageResponse]]:
    return ApiEnvelope(
        data=await list_messages(
            session,
            context,
            project_id,
            thread_id,
            limit=limit,
            before_sequence=before_sequence,
        ),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post(
    "/threads/{thread_id}/messages",
    response_model=ApiEnvelope[AIMessageAcceptedResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def send_message(
    project_id: UUID,
    thread_id: UUID,
    request: AIMessageCreateRequest,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
) -> ApiEnvelope[AIMessageAcceptedResponse]:
    accepted = await create_message(
        session,
        get_settings(),
        context,
        project_id,
        thread_id,
        request,
        idempotency_key,
    )
    return ApiEnvelope(data=accepted, meta=ApiMeta(request_id=str(uuid4())))


@router.get("/runs/{run_id}", response_model=ApiEnvelope[AIRunResponse])
async def run_status(
    project_id: UUID,
    run_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[AIRunResponse]:
    return ApiEnvelope(
        data=await load_run(session, context, project_id, run_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get("/runs/{run_id}/events", response_class=StreamingResponse)
async def run_events(
    project_id: UUID,
    run_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    await load_run(session, context, project_id, run_id)
    after_sequence = _parse_last_event_id(last_event_id)

    async def event_stream() -> AsyncIterator[str]:
        async for event in stream_chat_run(
            run_id,
            context.membership.organization_id,
            after_sequence=after_sequence,
        ):
            event_type = str(event["eventType"])
            sequence = event["sequence"]
            yield (
                f"id: {sequence}\n"
                f"event: {event_type}\n"
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


@router.post("/runs/{run_id}/cancel", response_model=ApiEnvelope[AIRunResponse])
async def cancel(
    project_id: UUID,
    run_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[AIRunResponse]:
    return ApiEnvelope(
        data=await cancel_run(session, context, project_id, run_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post(
    "/runs/{run_id}/retry",
    response_model=ApiEnvelope[AIRunRetryResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry(
    project_id: UUID,
    run_id: UUID,
    background_tasks: BackgroundTasks,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
) -> ApiEnvelope[AIRunRetryResponse]:
    retried = await retry_run(
        session,
        get_settings(),
        context,
        project_id,
        run_id,
        idempotency_key=idempotency_key,
    )
    if retried.job_id:
        background_tasks.add_task(process_brief_job, retried.job_id)
    return ApiEnvelope(data=retried, meta=ApiMeta(request_id=str(uuid4())))


@router.post(
    "/briefs/generate",
    response_model=ApiEnvelope[AIBriefAcceptedResponse],
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_brief(
    project_id: UUID,
    request: AIBriefGenerateRequest,
    background_tasks: BackgroundTasks,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
) -> ApiEnvelope[AIBriefAcceptedResponse]:
    accepted = await enqueue_brief(
        session,
        get_settings(),
        context,
        project_id,
        request,
        idempotency_key,
    )
    background_tasks.add_task(process_brief_job, accepted.job_id)
    return ApiEnvelope(data=accepted, meta=ApiMeta(request_id=str(uuid4())))


@router.get("/briefs", response_model=ApiEnvelope[list[AIBriefResponse]])
async def briefs(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiEnvelope[list[AIBriefResponse]]:
    return ApiEnvelope(
        data=await list_briefs(session, context, project_id, limit=limit),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get("/briefs/current", response_model=ApiEnvelope[AIBriefResponse | None])
async def current_brief(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[AIBriefResponse | None]:
    return ApiEnvelope(
        data=await load_current_brief(session, context, project_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get("/briefs/{brief_id}", response_model=ApiEnvelope[AIBriefResponse])
async def brief(
    project_id: UUID,
    brief_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[AIBriefResponse]:
    return ApiEnvelope(
        data=await load_brief(session, context, project_id, brief_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get(
    "/briefs/{brief_id}/proposals",
    response_model=ApiEnvelope[list[AIProposalResponse]],
)
async def brief_proposals(
    project_id: UUID,
    brief_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[list[AIProposalResponse]]:
    loaded = await load_brief(session, context, project_id, brief_id)
    return ApiEnvelope(data=loaded.proposals, meta=ApiMeta(request_id=str(uuid4())))


@router.post("/briefs/{brief_id}/approve", response_model=ApiEnvelope[AIBriefResponse])
async def approve_brief(
    project_id: UUID,
    brief_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
) -> ApiEnvelope[AIBriefResponse]:
    request_id = str(uuid4())
    result = await review_brief(
        session,
        context,
        project_id,
        brief_id,
        approved=True,
        idempotency_key=idempotency_key,
        request_id=request_id,
    )
    return ApiEnvelope(data=result, meta=ApiMeta(request_id=request_id))


@router.post("/briefs/{brief_id}/reject", response_model=ApiEnvelope[AIBriefResponse])
async def reject_brief(
    project_id: UUID,
    brief_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
) -> ApiEnvelope[AIBriefResponse]:
    request_id = str(uuid4())
    result = await review_brief(
        session,
        context,
        project_id,
        brief_id,
        approved=False,
        idempotency_key=idempotency_key,
        request_id=request_id,
    )
    return ApiEnvelope(data=result, meta=ApiMeta(request_id=request_id))


@router.post(
    "/proposals/{proposal_id}/approve",
    response_model=ApiEnvelope[AIProposalResponse],
)
async def approve_proposal(
    project_id: UUID,
    proposal_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
) -> ApiEnvelope[AIProposalResponse]:
    return ApiEnvelope(
        data=await review_proposal(
            session,
            context,
            project_id,
            proposal_id,
            approved=True,
            idempotency_key=idempotency_key,
        ),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post(
    "/proposals/{proposal_id}/reject",
    response_model=ApiEnvelope[AIProposalResponse],
)
async def reject_proposal(
    project_id: UUID,
    proposal_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
) -> ApiEnvelope[AIProposalResponse]:
    return ApiEnvelope(
        data=await review_proposal(
            session,
            context,
            project_id,
            proposal_id,
            approved=False,
            idempotency_key=idempotency_key,
        ),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.post("/proposals/apply", response_model=ApiEnvelope[AIProposalApplyResponse])
async def apply_approved_proposals(
    project_id: UUID,
    request: AIProposalApplyRequest,
    context: AuthContextDependency,
    session: SessionDependency,
    idempotency_key: IdempotencyKey,
    if_match: IfMatch,
    response: Response,
) -> ApiEnvelope[AIProposalApplyResponse]:
    request_id = str(uuid4())
    applied = await apply_proposals(
        session,
        context,
        project_id,
        request,
        expected_project_version=_parse_etag(if_match),
        idempotency_key=idempotency_key,
        request_id=request_id,
    )
    response.headers["ETag"] = f'"{applied.project_version}"'
    return ApiEnvelope(data=applied, meta=ApiMeta(request_id=request_id))


@router.get("/memory/current", response_model=ApiEnvelope[AIMemoryResponse | None])
async def current_memory(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[AIMemoryResponse | None]:
    return ApiEnvelope(
        data=await load_current_memory(session, context, project_id),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get("/memory/versions", response_model=ApiEnvelope[list[AIMemoryResponse]])
async def memory_versions(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiEnvelope[list[AIMemoryResponse]]:
    return ApiEnvelope(
        data=await list_memory_versions(session, context, project_id, limit=limit),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get("/usage", response_model=ApiEnvelope[AIUsageResponse])
async def usage(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[AIUsageResponse]:
    await load_current_memory(session, context, project_id)
    return ApiEnvelope(
        data=await load_usage_summary(session, get_settings(), context),
        meta=ApiMeta(request_id=str(uuid4())),
    )


@router.get(
    "/suggested-prompts",
    response_model=ApiEnvelope[list[AISuggestedPromptResponse]],
)
async def prompts(
    project_id: UUID,
    context: AuthContextDependency,
    session: SessionDependency,
) -> ApiEnvelope[list[AISuggestedPromptResponse]]:
    await load_current_brief(session, context, project_id)
    return ApiEnvelope(data=suggested_prompts(), meta=ApiMeta(request_id=str(uuid4())))


def _parse_last_event_id(value: str | None) -> int:
    if not value:
        return 0
    try:
        return max(0, int(value))
    except ValueError as error:
        raise project_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "AI_EVENT_CURSOR_INVALID",
            "Last-Event-ID must be an event sequence number.",
        ) from error


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
