from __future__ import annotations

import base64
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.auth import AuthContext
from compose_ai_api.core.config import Settings
from compose_ai_api.domains.ai_architect.cache import build_cache_key, stable_hash
from compose_ai_api.domains.ai_architect.context import build_project_memory, memory_prompt_payload
from compose_ai_api.domains.ai_architect.models import (
    AIArchitectBriefVersion,
    AIBriefStatus,
    AIChatMessage,
    AIChatThread,
    AIJob,
    AIJobStatus,
    AIMessageRole,
    AIMessageStatus,
    AIProjectMemoryVersion,
    AIPromptStatus,
    AIPromptTemplate,
    AIProposalStatus,
    AIProposalTarget,
    AIRequirementProposal,
    AIRun,
    AIRunEvent,
    AIRunStatus,
    AIRunType,
    AIThreadStatus,
)
from compose_ai_api.domains.ai_architect.prompts import PROMPTS, PromptDefinition
from compose_ai_api.domains.ai_architect.providers.factory import model_for_alias
from compose_ai_api.domains.ai_architect.safety import prepare_untrusted_text
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
    AIRunEventResponse,
    AIRunResponse,
    AIRunRetryResponse,
    AISuggestedPromptResponse,
    AIThreadCreateRequest,
    AIThreadResponse,
    AIThreadUpdateRequest,
)
from compose_ai_api.domains.ai_architect.usage import (
    AIUsageEstimate,
    enforce_usage_preflight,
    estimate_request_usage,
)
from compose_ai_api.domains.projects.models import Project, ProjectStatus
from compose_ai_api.domains.projects.service import (
    _apply_project_fields,
    _apply_requirements,
    _apply_room_requirements,
    _ensure_version,
    _load_idempotency,
    _load_project_model,
    _request_hash,
    _store_idempotency,
    _validate_project_completion,
    _validate_site,
    _write_audit,
    ensure_project_manage,
    ensure_project_read,
    project_error,
)


async def create_thread(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    request: AIThreadCreateRequest,
    idempotency_key: str,
) -> AIThreadResponse:
    ensure_project_manage(context)
    project = await _load_project_model(session, context, project_id)
    _ensure_project_editable(project)
    request_hash = _request_hash(request.model_dump(mode="json", by_alias=True))
    existing = await _load_idempotency(
        session, context, "ai.thread.create", idempotency_key, request_hash
    )
    if existing is not None:
        return AIThreadResponse.model_validate(existing.response_body)
    thread = AIChatThread(
        id=uuid4(),
        organization_id=context.membership.organization_id,
        project_id=project_id,
        title=request.title,
        status=AIThreadStatus.ACTIVE,
        version=1,
        created_by=context.user.id,
    )
    session.add(thread)
    await session.flush()
    response = _thread_response(thread, 0)
    await _store_idempotency(
        session,
        context,
        "ai.thread.create",
        idempotency_key,
        request_hash,
        status.HTTP_201_CREATED,
        response.model_dump(mode="json", by_alias=True),
    )
    await _write_audit(
        session,
        context,
        project,
        "ai.thread.created",
        str(uuid4()),
        after_data={"threadId": str(thread.id), "title": thread.title},
    )
    await session.commit()
    return response


async def list_threads(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    *,
    include_archived: bool,
    limit: int,
    cursor: str | None,
) -> tuple[list[AIThreadResponse], str | None, bool]:
    ensure_project_read(context)
    await _load_project_model(session, context, project_id)
    message_count = (
        select(func.count(AIChatMessage.id))
        .where(
            AIChatMessage.thread_id == AIChatThread.id,
            AIChatMessage.deleted_at.is_(None),
        )
        .correlate(AIChatThread)
        .scalar_subquery()
    )
    statement = select(AIChatThread, message_count.label("message_count")).where(
        AIChatThread.organization_id == context.membership.organization_id,
        AIChatThread.project_id == project_id,
        AIChatThread.deleted_at.is_(None),
    )
    if not include_archived:
        statement = statement.where(AIChatThread.status == AIThreadStatus.ACTIVE)
    if cursor:
        cursor_time, cursor_id = _decode_cursor(cursor)
        statement = statement.where(
            or_(
                AIChatThread.updated_at < cursor_time,
                (AIChatThread.updated_at == cursor_time) & (AIChatThread.id < cursor_id),
            )
        )
    rows = (
        await session.execute(
            statement.order_by(AIChatThread.updated_at.desc(), AIChatThread.id.desc()).limit(
                limit + 1
            )
        )
    ).all()
    has_more = len(rows) > limit
    visible = rows[:limit]
    next_cursor = _encode_cursor(visible[-1][0]) if has_more and visible else None
    return (
        [_thread_response(thread, int(count)) for thread, count in visible],
        next_cursor,
        has_more,
    )


async def load_thread(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    thread_id: UUID,
) -> AIThreadResponse:
    ensure_project_read(context)
    await _load_project_model(session, context, project_id)
    thread = await _load_thread_model(session, context, project_id, thread_id)
    count = (
        await session.execute(
            select(func.count(AIChatMessage.id)).where(
                AIChatMessage.thread_id == thread.id,
                AIChatMessage.deleted_at.is_(None),
            )
        )
    ).scalar_one()
    return _thread_response(thread, int(count))


async def update_thread(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    thread_id: UUID,
    request: AIThreadUpdateRequest,
) -> AIThreadResponse:
    ensure_project_manage(context)
    project = await _load_project_model(session, context, project_id)
    _ensure_project_editable(project)
    thread = await _load_thread_model(session, context, project_id, thread_id, for_update=True)
    thread.title = request.title
    thread.version += 1
    await session.commit()
    return await load_thread(session, context, project_id, thread_id)


async def set_thread_archived(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    thread_id: UUID,
    *,
    archived: bool,
) -> AIThreadResponse:
    ensure_project_manage(context)
    project = await _load_project_model(session, context, project_id)
    _ensure_project_editable(project)
    thread = await _load_thread_model(session, context, project_id, thread_id, for_update=True)
    thread.status = AIThreadStatus.ARCHIVED if archived else AIThreadStatus.ACTIVE
    thread.version += 1
    await session.commit()
    return await load_thread(session, context, project_id, thread_id)


async def list_messages(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    thread_id: UUID,
    *,
    limit: int,
    before_sequence: int | None,
) -> list[AIMessageResponse]:
    ensure_project_read(context)
    await _load_thread_model(session, context, project_id, thread_id)
    statement = select(AIChatMessage).where(
        AIChatMessage.organization_id == context.membership.organization_id,
        AIChatMessage.project_id == project_id,
        AIChatMessage.thread_id == thread_id,
        AIChatMessage.deleted_at.is_(None),
        AIChatMessage.role.in_((AIMessageRole.USER, AIMessageRole.ASSISTANT)),
    )
    if before_sequence is not None:
        statement = statement.where(AIChatMessage.sequence_number < before_sequence)
    messages = list(
        (
            await session.execute(
                statement.order_by(AIChatMessage.sequence_number.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [_message_response(message) for message in reversed(messages)]


async def create_message(
    session: AsyncSession,
    settings: Settings,
    context: AuthContext,
    project_id: UUID,
    thread_id: UUID,
    request: AIMessageCreateRequest,
    idempotency_key: str,
) -> AIMessageAcceptedResponse:
    ensure_project_manage(context)
    thread = await _load_thread_model(session, context, project_id, thread_id, for_update=True)
    if thread.status == AIThreadStatus.ARCHIVED:
        raise project_error(
            status.HTTP_409_CONFLICT,
            "AI_THREAD_ARCHIVED",
            "Restore the conversation before sending a message.",
        )
    memory_result = await build_project_memory(session, context, project_id, thread_id=thread_id)
    _ensure_project_editable(memory_result.project)
    request_hash = _request_hash(request.model_dump(mode="json", by_alias=True))
    existing = await _load_idempotency(
        session, context, "ai.message.create", idempotency_key, request_hash
    )
    if existing is not None:
        return AIMessageAcceptedResponse.model_validate(existing.response_body)

    prompt = await ensure_prompt_template(session, context, PROMPTS["architect_chat"])
    provider_name = settings.ai_provider
    model = model_for_alias(settings, provider_name, "architect_chat")
    prepared = prepare_untrusted_text(request.content)
    user_prompt = prompt.input_template.format(
        project_context=memory_prompt_payload(memory_result.memory),
        conversation=json.dumps(memory_result.memory.context_payload.get("conversation", [])),
        message=prepared.provider_text,
        mode=request.mode,
    )
    estimate = estimate_request_usage(settings, prompt.system_template, user_prompt)
    await enforce_usage_preflight(session, settings, context, estimate)
    next_sequence = (
        await session.execute(
            select(func.coalesce(func.max(AIChatMessage.sequence_number), 0)).where(
                AIChatMessage.thread_id == thread.id
            )
        )
    ).scalar_one() + 1
    run_id = uuid4()
    message_id = uuid4()
    message = AIChatMessage(
        id=message_id,
        organization_id=context.membership.organization_id,
        project_id=project_id,
        thread_id=thread.id,
        ai_run_id=run_id,
        role=AIMessageRole.USER,
        mode=request.mode,
        sequence_number=next_sequence,
        original_content=request.content,
        display_content=request.content,
        content_format="text",
        status=AIMessageStatus.COMPLETED,
        client_message_id=request.client_message_id,
        token_count=estimate.input_tokens,
        created_by=context.user.id,
    )
    run = AIRun(
        id=run_id,
        organization_id=context.membership.organization_id,
        project_id=project_id,
        thread_id=thread.id,
        run_type=AIRunType.ARCHITECT_CHAT,
        status=AIRunStatus.QUEUED,
        provider=provider_name,
        model=model,
        model_alias="architect_chat",
        prompt_template_id=prompt.id,
        memory_version_id=memory_result.memory.id,
        input_payload={
            "messageId": str(message_id),
            "providerMessage": prepared.provider_text,
            "mode": str(request.mode),
        },
        input_hash=stable_hash({"message": prepared.provider_text, "mode": str(request.mode)}),
        context_hash=memory_result.memory.context_hash,
        idempotency_key=idempotency_key,
        estimated_input_tokens=estimate.input_tokens,
        estimated_output_tokens=estimate.output_tokens,
        estimated_cost_microusd=estimate.cost_microusd,
        input_tokens=0,
        output_tokens=0,
        cached_tokens=0,
        actual_cost_microusd=0,
        cache_hit=False,
        attempt_count=0,
        safety_flags=[{"code": "PROMPT_INJECTION_SIGNAL", "count": len(prepared.injection_signals)}]
        if prepared.injection_signals
        else [],
        created_by=context.user.id,
    )
    thread.last_message_at = datetime.now(UTC)
    thread.version += 1
    session.add(run)
    await session.flush()
    session.add(message)
    await session.flush()
    await append_run_event(session, run.id, "run.queued", {"status": "queued"})
    response = AIMessageAcceptedResponse(
        message=_message_response(message),
        run=_run_response(run),
        stream_url=f"/api/v1/projects/{project_id}/ai/runs/{run.id}/events",
    )
    await _store_idempotency(
        session,
        context,
        "ai.message.create",
        idempotency_key,
        request_hash,
        status.HTTP_202_ACCEPTED,
        response.model_dump(mode="json", by_alias=True),
    )
    await session.commit()
    return response


async def enqueue_brief(
    session: AsyncSession,
    settings: Settings,
    context: AuthContext,
    project_id: UUID,
    request: AIBriefGenerateRequest,
    idempotency_key: str,
) -> AIBriefAcceptedResponse:
    ensure_project_manage(context)
    if request.thread_id:
        await _load_thread_model(session, context, project_id, request.thread_id)
    memory_result = await build_project_memory(
        session, context, project_id, thread_id=request.thread_id
    )
    _ensure_project_editable(memory_result.project)
    request_hash = _request_hash(request.model_dump(mode="json", by_alias=True))
    existing = await _load_idempotency(
        session, context, "ai.brief.generate", idempotency_key, request_hash
    )
    if existing is not None:
        return AIBriefAcceptedResponse.model_validate(existing.response_body)

    prompt = await ensure_prompt_template(session, context, PROMPTS["architect_brief"])
    provider_name = settings.ai_provider
    model = model_for_alias(settings, provider_name, "architect_brief")
    prepared = prepare_untrusted_text(request.raw_requirements)
    user_prompt = prompt.input_template.format(
        project_context=memory_prompt_payload(memory_result.memory),
        raw_requirements=prepared.provider_text,
    )
    estimate = estimate_request_usage(settings, prompt.system_template, user_prompt)
    await enforce_usage_preflight(session, settings, context, estimate)
    input_hash = stable_hash({"rawRequirements": prepared.provider_text})
    cache_key = build_cache_key(
        run_type=AIRunType.ARCHITECT_BRIEF,
        provider=provider_name,
        model=model,
        prompt_checksum=prompt.checksum,
        context_hash=memory_result.memory.context_hash,
        input_hash=input_hash,
        output_schema_version=prompt.output_schema_version,
        safety_policy_version=prompt.safety_policy_version,
    )
    run = AIRun(
        id=uuid4(),
        organization_id=context.membership.organization_id,
        project_id=project_id,
        thread_id=request.thread_id,
        run_type=AIRunType.ARCHITECT_BRIEF,
        status=AIRunStatus.QUEUED,
        provider=provider_name,
        model=model,
        model_alias="architect_brief",
        prompt_template_id=prompt.id,
        memory_version_id=memory_result.memory.id,
        input_payload={
            "originalRequirements": request.raw_requirements,
            "providerRequirements": prepared.provider_text,
            "redactionSummary": {
                "emails": prepared.redacted_email_count,
                "phones": prepared.redacted_phone_count,
            },
        },
        input_hash=input_hash,
        context_hash=memory_result.memory.context_hash,
        cache_key=cache_key,
        idempotency_key=idempotency_key,
        estimated_input_tokens=estimate.input_tokens,
        estimated_output_tokens=estimate.output_tokens,
        estimated_cost_microusd=estimate.cost_microusd,
        input_tokens=0,
        output_tokens=0,
        cached_tokens=0,
        actual_cost_microusd=0,
        cache_hit=False,
        attempt_count=0,
        safety_flags=[{"code": "PROMPT_INJECTION_SIGNAL", "count": len(prepared.injection_signals)}]
        if prepared.injection_signals
        else [],
        created_by=context.user.id,
    )
    job = AIJob(
        id=uuid4(),
        organization_id=context.membership.organization_id,
        project_id=project_id,
        ai_run_id=run.id,
        job_type=AIRunType.ARCHITECT_BRIEF,
        status=AIJobStatus.QUEUED,
        priority=100,
        attempt_count=0,
        available_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    session.add(job)
    await session.flush()
    await append_run_event(session, run.id, "run.queued", {"status": "queued"})
    response = AIBriefAcceptedResponse(
        run=_run_response(run),
        job_id=job.id,
        status_url=f"/api/v1/projects/{project_id}/ai/runs/{run.id}",
    )
    await _store_idempotency(
        session,
        context,
        "ai.brief.generate",
        idempotency_key,
        request_hash,
        status.HTTP_202_ACCEPTED,
        response.model_dump(mode="json", by_alias=True),
    )
    await session.commit()
    return response


async def ensure_prompt_template(
    session: AsyncSession,
    context: AuthContext,
    definition: PromptDefinition,
) -> AIPromptTemplate:
    prompt = (
        await session.execute(
            select(AIPromptTemplate).where(
                AIPromptTemplate.prompt_key == definition.key,
                AIPromptTemplate.version == definition.version,
            )
        )
    ).scalar_one_or_none()
    if prompt is not None:
        if prompt.checksum != definition.checksum:
            raise project_error(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "AI_PROMPT_VERSION_CONFLICT",
                "The immutable prompt version does not match the application prompt.",
            )
        return prompt
    prompt = AIPromptTemplate(
        id=uuid4(),
        prompt_key=definition.key,
        version=definition.version,
        task_type=definition.task_type,
        system_template=definition.system_template,
        input_template=definition.input_template,
        output_schema_version=definition.output_schema_version,
        safety_policy_version=definition.safety_policy_version,
        checksum=definition.checksum,
        status=AIPromptStatus.ACTIVE,
        created_by=context.user.id,
    )
    session.add(prompt)
    await session.flush()
    return prompt


async def load_run(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    run_id: UUID,
) -> AIRunResponse:
    ensure_project_read(context)
    run = await _load_run_model(session, context, project_id, run_id)
    return _run_response(run)


async def cancel_run(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    run_id: UUID,
) -> AIRunResponse:
    ensure_project_manage(context)
    project = await _load_project_model(session, context, project_id)
    _ensure_project_editable(project)
    run = await _load_run_model(session, context, project_id, run_id, for_update=True)
    if run.status in (AIRunStatus.COMPLETED, AIRunStatus.FAILED, AIRunStatus.CANCELLED):
        return _run_response(run)
    run.status = AIRunStatus.CANCELLED
    run.cancelled_at = datetime.now(UTC)
    job = (
        await session.execute(select(AIJob).where(AIJob.ai_run_id == run.id).with_for_update())
    ).scalar_one_or_none()
    if job is not None:
        job.status = AIJobStatus.CANCELLED
    await append_run_event(session, run.id, "run.cancelled", {"status": "cancelled"})
    await session.commit()
    return _run_response(run)


async def retry_run(
    session: AsyncSession,
    settings: Settings,
    context: AuthContext,
    project_id: UUID,
    run_id: UUID,
    *,
    idempotency_key: str,
) -> AIRunRetryResponse:
    ensure_project_manage(context)
    project = await _load_project_model(session, context, project_id)
    _ensure_project_editable(project)
    previous = await _load_run_model(session, context, project_id, run_id, for_update=True)
    if previous.status not in (AIRunStatus.FAILED, AIRunStatus.CANCELLED):
        raise project_error(
            status.HTTP_409_CONFLICT,
            "AI_RUN_NOT_RETRYABLE",
            "Only failed or cancelled AI runs can be retried.",
        )
    request_hash = _request_hash({"runId": str(run_id)})
    existing = await _load_idempotency(
        session, context, "ai.run.retry", idempotency_key, request_hash
    )
    if existing is not None:
        return AIRunRetryResponse.model_validate(existing.response_body)
    await enforce_usage_preflight(
        session,
        settings,
        context,
        AIUsageEstimate(
            input_tokens=previous.estimated_input_tokens,
            output_tokens=previous.estimated_output_tokens,
            cost_microusd=previous.estimated_cost_microusd,
        ),
    )
    run = AIRun(
        id=uuid4(),
        organization_id=previous.organization_id,
        project_id=previous.project_id,
        thread_id=previous.thread_id,
        run_type=previous.run_type,
        status=AIRunStatus.QUEUED,
        provider=previous.provider,
        model=previous.model,
        model_alias=previous.model_alias,
        prompt_template_id=previous.prompt_template_id,
        memory_version_id=previous.memory_version_id,
        input_payload=previous.input_payload,
        input_hash=previous.input_hash,
        context_hash=previous.context_hash,
        cache_key=previous.cache_key,
        idempotency_key=idempotency_key,
        estimated_input_tokens=previous.estimated_input_tokens,
        estimated_output_tokens=previous.estimated_output_tokens,
        estimated_cost_microusd=previous.estimated_cost_microusd,
        input_tokens=0,
        output_tokens=0,
        cached_tokens=0,
        actual_cost_microusd=0,
        cache_hit=False,
        attempt_count=0,
        safety_flags=previous.safety_flags,
        created_by=context.user.id,
    )
    session.add(run)
    job_id: UUID | None = None
    if previous.run_type == AIRunType.ARCHITECT_BRIEF:
        job_id = uuid4()
        session.add(
            AIJob(
                id=job_id,
                organization_id=run.organization_id,
                project_id=run.project_id,
                ai_run_id=run.id,
                job_type=run.run_type,
                status=AIJobStatus.QUEUED,
                priority=100,
                attempt_count=0,
                available_at=datetime.now(UTC),
            )
        )
    await session.flush()
    await append_run_event(session, run.id, "run.queued", {"status": "queued"})
    response = AIRunRetryResponse(
        run=_run_response(run),
        job_id=job_id,
        stream_url=(
            f"/api/v1/projects/{project_id}/ai/runs/{run.id}/events"
            if previous.run_type == AIRunType.ARCHITECT_CHAT
            else None
        ),
    )
    await _store_idempotency(
        session,
        context,
        "ai.run.retry",
        idempotency_key,
        request_hash,
        status.HTTP_202_ACCEPTED,
        response.model_dump(mode="json", by_alias=True),
    )
    await session.commit()
    return response


async def list_run_events(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    run_id: UUID,
    *,
    after_sequence: int = 0,
) -> list[AIRunEventResponse]:
    ensure_project_read(context)
    await _load_run_model(session, context, project_id, run_id)
    events = list(
        (
            await session.execute(
                select(AIRunEvent)
                .where(
                    AIRunEvent.ai_run_id == run_id,
                    AIRunEvent.event_sequence > after_sequence,
                )
                .order_by(AIRunEvent.event_sequence)
            )
        )
        .scalars()
        .all()
    )
    return [_run_event_response(event) for event in events]


async def append_run_event(
    session: AsyncSession,
    run_id: UUID,
    event_type: str,
    payload: dict[str, Any],
) -> AIRunEvent:
    sequence = (
        await session.execute(
            select(func.coalesce(func.max(AIRunEvent.event_sequence), 0)).where(
                AIRunEvent.ai_run_id == run_id
            )
        )
    ).scalar_one() + 1
    event = AIRunEvent(
        id=uuid4(),
        ai_run_id=run_id,
        event_sequence=sequence,
        event_type=event_type,
        payload=payload,
    )
    session.add(event)
    await session.flush()
    return event


async def list_briefs(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    *,
    limit: int,
) -> list[AIBriefResponse]:
    ensure_project_read(context)
    await _load_project_model(session, context, project_id)
    briefs = list(
        (
            await session.execute(
                select(AIArchitectBriefVersion)
                .where(
                    AIArchitectBriefVersion.organization_id == context.membership.organization_id,
                    AIArchitectBriefVersion.project_id == project_id,
                )
                .order_by(AIArchitectBriefVersion.version.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [await _brief_response(session, brief) for brief in briefs]


async def load_current_brief(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
) -> AIBriefResponse | None:
    ensure_project_read(context)
    await _load_project_model(session, context, project_id)
    brief = (
        await session.execute(
            select(AIArchitectBriefVersion)
            .where(
                AIArchitectBriefVersion.organization_id == context.membership.organization_id,
                AIArchitectBriefVersion.project_id == project_id,
                AIArchitectBriefVersion.status.notin_(
                    (AIBriefStatus.REJECTED, AIBriefStatus.SUPERSEDED, AIBriefStatus.FAILED)
                ),
            )
            .order_by(
                AIArchitectBriefVersion.version.desc(),
                AIArchitectBriefVersion.created_at.desc(),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return await _brief_response(session, brief) if brief else None


async def load_brief(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    brief_id: UUID,
) -> AIBriefResponse:
    ensure_project_read(context)
    brief = await _load_brief_model(session, context, project_id, brief_id)
    return await _brief_response(session, brief)


async def review_brief(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    brief_id: UUID,
    *,
    approved: bool,
    idempotency_key: str,
    request_id: str,
) -> AIBriefResponse:
    ensure_project_manage(context)
    project = await _load_project_model(session, context, project_id)
    _ensure_project_editable(project)
    request_hash = _request_hash({"briefId": str(brief_id), "approved": approved})
    scope = "ai.brief.approve" if approved else "ai.brief.reject"
    existing = await _load_idempotency(session, context, scope, idempotency_key, request_hash)
    if existing is not None:
        return AIBriefResponse.model_validate(existing.response_body)
    brief = await _load_brief_model(session, context, project_id, brief_id, for_update=True)
    if brief.status not in (
        AIBriefStatus.PROPOSED,
        AIBriefStatus.UNDER_REVIEW,
        AIBriefStatus.APPROVED,
    ):
        raise project_error(
            status.HTTP_409_CONFLICT,
            "AI_BRIEF_NOT_REVIEWABLE",
            "This brief version cannot be reviewed in its current state.",
        )
    now = datetime.now(UTC)
    if approved:
        brief.status = AIBriefStatus.APPROVED
        brief.approved_by = context.user.id
        brief.approved_at = now
        previous_approved = list(
            (
                await session.execute(
                    select(AIArchitectBriefVersion).where(
                        AIArchitectBriefVersion.organization_id
                        == context.membership.organization_id,
                        AIArchitectBriefVersion.project_id == project_id,
                        AIArchitectBriefVersion.id != brief.id,
                        AIArchitectBriefVersion.status == AIBriefStatus.APPROVED,
                    )
                )
            )
            .scalars()
            .all()
        )
        for previous in previous_approved:
            previous.status = AIBriefStatus.SUPERSEDED
    else:
        brief.status = AIBriefStatus.REJECTED
    await _write_audit(
        session,
        context,
        project,
        "ai.brief.approved" if approved else "ai.brief.rejected",
        request_id,
        after_data={"briefId": str(brief.id), "briefVersion": brief.version},
    )
    await session.flush()
    response = await _brief_response(session, brief)
    await _store_idempotency(
        session,
        context,
        scope,
        idempotency_key,
        request_hash,
        status.HTTP_200_OK,
        response.model_dump(mode="json", by_alias=True),
    )
    await session.commit()
    return response


async def review_proposal(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    proposal_id: UUID,
    *,
    approved: bool,
    idempotency_key: str,
) -> AIProposalResponse:
    ensure_project_manage(context)
    project = await _load_project_model(session, context, project_id)
    _ensure_project_editable(project)
    request_hash = _request_hash({"proposalId": str(proposal_id), "approved": approved})
    scope = "ai.proposal.approve" if approved else "ai.proposal.reject"
    existing = await _load_idempotency(session, context, scope, idempotency_key, request_hash)
    if existing is not None:
        return AIProposalResponse.model_validate(existing.response_body)
    proposal = await _load_proposal_model(
        session, context, project_id, proposal_id, for_update=True
    )
    if proposal.status in (AIProposalStatus.APPLIED, AIProposalStatus.STALE):
        raise project_error(
            status.HTTP_409_CONFLICT,
            "AI_PROPOSAL_NOT_REVIEWABLE",
            "This proposal can no longer be reviewed.",
        )
    if approved and proposal.target_type == AIProposalTarget.PLOT_RECOMMENDATION:
        raise project_error(
            status.HTTP_409_CONFLICT,
            "AI_UNSUPPORTED_PROPOSAL_TARGET",
            "Plot recommendations are advisory in this phase and cannot be "
            "approved for application.",
        )
    if approved and any(
        warning.get("code") == "BLOCKING_CONFLICT" for warning in proposal.warnings
    ):
        raise project_error(
            status.HTTP_409_CONFLICT,
            "AI_PROPOSAL_CONFLICT",
            "Resolve the blocking requirement conflict before approving this proposal.",
        )
    proposal.status = AIProposalStatus.APPROVED if approved else AIProposalStatus.REJECTED
    proposal.reviewed_by = context.user.id
    proposal.reviewed_at = datetime.now(UTC)
    await session.flush()
    response = _proposal_response(proposal)
    await _store_idempotency(
        session,
        context,
        scope,
        idempotency_key,
        request_hash,
        status.HTTP_200_OK,
        response.model_dump(mode="json", by_alias=True),
    )
    await session.commit()
    return response


async def apply_proposals(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    request: AIProposalApplyRequest,
    *,
    expected_project_version: int,
    idempotency_key: str,
    request_id: str,
) -> AIProposalApplyResponse:
    ensure_project_manage(context)
    request_hash = _request_hash(
        {
            "proposalIds": [str(value) for value in request.proposal_ids],
            "expectedProjectVersion": expected_project_version,
        }
    )
    existing = await _load_idempotency(
        session, context, "ai.proposals.apply", idempotency_key, request_hash
    )
    if existing is not None:
        return AIProposalApplyResponse.model_validate(existing.response_body)
    project = await _load_project_model(session, context, project_id, for_update=True)
    _ensure_project_editable(project)
    try:
        _ensure_version(project, expected_project_version)
    except Exception as error:
        raise project_error(
            status.HTTP_409_CONFLICT,
            "AI_APPROVAL_CONFLICT",
            "The project changed after these AI proposals were generated.",
            {"expectedVersion": expected_project_version, "currentVersion": project.version},
        ) from error
    proposals = list(
        (
            await session.execute(
                select(AIRequirementProposal)
                .where(
                    AIRequirementProposal.organization_id == context.membership.organization_id,
                    AIRequirementProposal.project_id == project_id,
                    AIRequirementProposal.id.in_(request.proposal_ids),
                )
                .with_for_update()
            )
        )
        .scalars()
        .all()
    )
    if len(proposals) != len(set(request.proposal_ids)):
        raise project_error(
            status.HTTP_404_NOT_FOUND,
            "AI_PROPOSAL_NOT_FOUND",
            "One or more proposals were not found.",
        )
    brief_ids = {proposal.brief_version_id for proposal in proposals}
    if len(brief_ids) != 1:
        raise project_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "AI_PROPOSAL_SET_INVALID",
            "Applied proposals must belong to one brief version.",
        )
    for proposal in proposals:
        if proposal.status != AIProposalStatus.APPROVED:
            raise project_error(
                status.HTTP_409_CONFLICT,
                "AI_PROPOSAL_NOT_APPROVED",
                "Every selected proposal must be approved before application.",
                {"proposalId": str(proposal.id)},
            )
        if proposal.expected_project_version != project.version:
            raise project_error(
                status.HTTP_409_CONFLICT,
                "AI_APPROVAL_CONFLICT",
                "A selected proposal was generated for an older project version.",
                {"proposalId": str(proposal.id)},
            )
        if proposal.target_type == AIProposalTarget.PLOT_RECOMMENDATION:
            raise project_error(
                status.HTTP_409_CONFLICT,
                "AI_UNSUPPORTED_PROPOSAL_TARGET",
                "Plot recommendations cannot modify Plot Intelligence in this phase.",
            )
    from compose_ai_api.domains.ai_architect.quality import build_project_update

    update = build_project_update(
        {proposal.target_path: proposal.proposed_value for proposal in proposals}
    )
    before = {proposal.target_path: proposal.existing_value for proposal in proposals}
    _apply_project_fields(project, update)
    _apply_requirements(project, update)
    _apply_room_requirements(project, update)
    _validate_site(project.site)
    if project.status == ProjectStatus.ACTIVE:
        _validate_project_completion(project)
    project.updated_by = context.user.id
    project.version += 1
    now = datetime.now(UTC)
    for proposal in proposals:
        proposal.status = AIProposalStatus.APPLIED
        proposal.applied_at = now
    brief = await _load_brief_model(
        session, context, project_id, next(iter(brief_ids)), for_update=True
    )
    remaining = (
        await session.execute(
            select(func.count(AIRequirementProposal.id)).where(
                AIRequirementProposal.brief_version_id == brief.id,
                AIRequirementProposal.target_type != AIProposalTarget.PLOT_RECOMMENDATION,
                AIRequirementProposal.id.notin_(request.proposal_ids),
                AIRequirementProposal.status.in_(
                    (AIProposalStatus.PENDING, AIProposalStatus.APPROVED)
                ),
            )
        )
    ).scalar_one()
    if remaining == 0:
        brief.status = AIBriefStatus.APPLIED
        brief.applied_at = now
    await _write_audit(
        session,
        context,
        project,
        "ai.proposals.applied",
        request_id,
        before_data=before,
        after_data={
            "proposalIds": [str(proposal.id) for proposal in proposals],
            "projectVersion": project.version,
        },
    )
    response = AIProposalApplyResponse(
        project_id=project.id,
        project_version=project.version,
        applied_proposal_ids=[proposal.id for proposal in proposals],
        brief_status=AIBriefStatus(str(brief.status)),
    )
    await _store_idempotency(
        session,
        context,
        "ai.proposals.apply",
        idempotency_key,
        request_hash,
        status.HTTP_200_OK,
        response.model_dump(mode="json", by_alias=True),
    )
    await session.commit()
    return response


async def load_current_memory(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
) -> AIMemoryResponse | None:
    ensure_project_read(context)
    await _load_project_model(session, context, project_id)
    memory = (
        await session.execute(
            select(AIProjectMemoryVersion)
            .where(
                AIProjectMemoryVersion.organization_id == context.membership.organization_id,
                AIProjectMemoryVersion.project_id == project_id,
            )
            .order_by(AIProjectMemoryVersion.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return _memory_response(memory) if memory else None


async def list_memory_versions(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    *,
    limit: int,
) -> list[AIMemoryResponse]:
    ensure_project_read(context)
    await _load_project_model(session, context, project_id)
    memories = list(
        (
            await session.execute(
                select(AIProjectMemoryVersion)
                .where(
                    AIProjectMemoryVersion.organization_id == context.membership.organization_id,
                    AIProjectMemoryVersion.project_id == project_id,
                )
                .order_by(AIProjectMemoryVersion.version.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [_memory_response(memory) for memory in memories]


def suggested_prompts() -> list[AISuggestedPromptResponse]:
    return [
        AISuggestedPromptResponse(
            id="normalize",
            label="Structure requirements",
            prompt="Turn my current project requirements into a structured architectural brief.",
            mode="proposal",
        ),
        AISuggestedPromptResponse(
            id="missing",
            label="Find missing information",
            prompt="What important information is still missing from this project brief?",
            mode="advice",
        ),
        AISuggestedPromptResponse(
            id="conflicts",
            label="Check conflicts",
            prompt="Review the project requirements and identify contradictions or constraints.",
            mode="advice",
        ),
        AISuggestedPromptResponse(
            id="priorities",
            label="Prioritize the brief",
            prompt="Help me rank the project's functional and design priorities.",
            mode="advice",
        ),
    ]


async def _load_thread_model(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    thread_id: UUID,
    *,
    for_update: bool = False,
) -> AIChatThread:
    statement = select(AIChatThread).where(
        AIChatThread.id == thread_id,
        AIChatThread.organization_id == context.membership.organization_id,
        AIChatThread.project_id == project_id,
        AIChatThread.deleted_at.is_(None),
    )
    if for_update:
        statement = statement.with_for_update()
    thread = (await session.execute(statement)).scalar_one_or_none()
    if thread is None:
        raise project_error(
            status.HTTP_404_NOT_FOUND,
            "AI_THREAD_NOT_FOUND",
            "Conversation not found.",
        )
    return thread


async def _load_run_model(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    run_id: UUID,
    *,
    for_update: bool = False,
) -> AIRun:
    statement = select(AIRun).where(
        AIRun.id == run_id,
        AIRun.organization_id == context.membership.organization_id,
        AIRun.project_id == project_id,
    )
    if for_update:
        statement = statement.with_for_update()
    run = (await session.execute(statement)).scalar_one_or_none()
    if run is None:
        raise project_error(status.HTTP_404_NOT_FOUND, "AI_RUN_NOT_FOUND", "AI run not found.")
    return run


async def _load_brief_model(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    brief_id: UUID,
    *,
    for_update: bool = False,
) -> AIArchitectBriefVersion:
    statement = select(AIArchitectBriefVersion).where(
        AIArchitectBriefVersion.id == brief_id,
        AIArchitectBriefVersion.organization_id == context.membership.organization_id,
        AIArchitectBriefVersion.project_id == project_id,
    )
    if for_update:
        statement = statement.with_for_update()
    brief = (await session.execute(statement)).scalar_one_or_none()
    if brief is None:
        raise project_error(
            status.HTTP_404_NOT_FOUND,
            "AI_BRIEF_NOT_FOUND",
            "Architectural brief not found.",
        )
    return brief


async def _load_proposal_model(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    proposal_id: UUID,
    *,
    for_update: bool = False,
) -> AIRequirementProposal:
    statement = select(AIRequirementProposal).where(
        AIRequirementProposal.id == proposal_id,
        AIRequirementProposal.organization_id == context.membership.organization_id,
        AIRequirementProposal.project_id == project_id,
    )
    if for_update:
        statement = statement.with_for_update()
    proposal = (await session.execute(statement)).scalar_one_or_none()
    if proposal is None:
        raise project_error(
            status.HTTP_404_NOT_FOUND,
            "AI_PROPOSAL_NOT_FOUND",
            "AI proposal not found.",
        )
    return proposal


def _ensure_project_editable(project: Project) -> None:
    if project.status == ProjectStatus.ARCHIVED:
        raise project_error(
            status.HTTP_409_CONFLICT,
            "PROJECT_ARCHIVED",
            "Archived projects are read-only. Restore the project before using AI Architect.",
        )


def _thread_response(thread: AIChatThread, message_count: int) -> AIThreadResponse:
    return AIThreadResponse(
        id=thread.id,
        project_id=thread.project_id,
        title=thread.title,
        status=AIThreadStatus(str(thread.status)),
        version=thread.version,
        message_count=message_count,
        last_message_at=thread.last_message_at,
        created_at=thread.created_at,
        updated_at=thread.updated_at,
    )


def _message_response(message: AIChatMessage) -> AIMessageResponse:
    return AIMessageResponse(
        id=message.id,
        thread_id=message.thread_id,
        run_id=message.ai_run_id,
        role=AIMessageRole(str(message.role)),
        mode=str(message.mode),
        sequence_number=message.sequence_number,
        content=message.display_content,
        status=AIMessageStatus(str(message.status)),
        created_at=message.created_at,
    )


def _run_response(run: AIRun) -> AIRunResponse:
    return AIRunResponse(
        id=run.id,
        project_id=run.project_id,
        thread_id=run.thread_id,
        run_type=AIRunType(str(run.run_type)),
        status=AIRunStatus(str(run.status)),
        provider=run.provider,
        model_alias=run.model_alias,
        estimated_input_tokens=run.estimated_input_tokens,
        estimated_output_tokens=run.estimated_output_tokens,
        estimated_cost_microusd=run.estimated_cost_microusd,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        actual_cost_microusd=run.actual_cost_microusd,
        cache_hit=run.cache_hit,
        failure_code=run.failure_code,
        failure_details=run.failure_details_redacted,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def _run_event_response(event: AIRunEvent) -> AIRunEventResponse:
    return AIRunEventResponse(
        id=event.id,
        run_id=event.ai_run_id,
        sequence=event.event_sequence,
        event_type=event.event_type,
        payload=event.payload,
        created_at=event.created_at,
    )


async def _brief_response(session: AsyncSession, brief: AIArchitectBriefVersion) -> AIBriefResponse:
    proposals = list(
        (
            await session.execute(
                select(AIRequirementProposal)
                .where(AIRequirementProposal.brief_version_id == brief.id)
                .order_by(AIRequirementProposal.created_at, AIRequirementProposal.id)
            )
        )
        .scalars()
        .all()
    )
    return AIBriefResponse(
        id=brief.id,
        project_id=brief.project_id,
        version=brief.version,
        source_run_id=brief.source_run_id,
        status=AIBriefStatus(str(brief.status)),
        original_input=brief.original_input,
        summary=brief.summary,
        goals=brief.goals,
        priorities=brief.priorities,
        constraints=brief.constraints,
        normalized_requirements=brief.normalized_requirements,
        missing_information=brief.missing_information,
        conflicts=brief.conflicts,
        clarification_questions=brief.clarification_questions,
        recommended_next_steps=brief.recommended_next_steps,
        warnings=brief.warnings,
        assumptions=brief.assumptions,
        aggregate_confidence=brief.aggregate_confidence,
        based_on_project_version=brief.based_on_project_version,
        approved_at=brief.approved_at,
        applied_at=brief.applied_at,
        created_at=brief.created_at,
        proposals=[_proposal_response(proposal) for proposal in proposals],
    )


def _proposal_response(proposal: AIRequirementProposal) -> AIProposalResponse:
    return AIProposalResponse(
        id=proposal.id,
        brief_version_id=proposal.brief_version_id,
        target_type=AIProposalTarget(str(proposal.target_type)),
        target_path=proposal.target_path,
        existing_value=proposal.existing_value,
        proposed_value=proposal.proposed_value,
        explanation=proposal.explanation,
        confidence=proposal.confidence,
        source_references=proposal.source_references,
        warnings=proposal.warnings,
        status=AIProposalStatus(str(proposal.status)),
        expected_project_version=proposal.expected_project_version,
        reviewed_at=proposal.reviewed_at,
        applied_at=proposal.applied_at,
    )


def _memory_response(memory: AIProjectMemoryVersion) -> AIMemoryResponse:
    return AIMemoryResponse(
        id=memory.id,
        version=memory.version,
        project_version=memory.project_version,
        context_summary=memory.context_summary,
        included_sources=memory.included_sources,
        redaction_summary=memory.redaction_summary,
        token_estimate=memory.token_estimate,
        context_hash=memory.context_hash,
        schema_version=memory.schema_version,
        created_at=memory.created_at,
    )


def _encode_cursor(thread: AIChatThread) -> str:
    payload = json.dumps({"updatedAt": thread.updated_at.isoformat(), "id": str(thread.id)})
    return base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        return datetime.fromisoformat(payload["updatedAt"]), UUID(payload["id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise project_error(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "PAGINATION_CURSOR_INVALID",
            "The conversation cursor is invalid.",
        ) from error
