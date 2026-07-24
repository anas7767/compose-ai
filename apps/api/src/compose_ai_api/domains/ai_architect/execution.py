from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from compose_ai_api.core.config import get_settings
from compose_ai_api.core.database import AsyncSessionFactory
from compose_ai_api.domains.ai_architect.context import memory_prompt_payload
from compose_ai_api.domains.ai_architect.models import (
    AIArchitectBriefVersion,
    AIBriefStatus,
    AIChatMessage,
    AIChatThread,
    AIJob,
    AIJobStatus,
    AIMessageMode,
    AIMessageRole,
    AIMessageStatus,
    AIProjectMemoryVersion,
    AIPromptTemplate,
    AIProposalStatus,
    AIRequirementProposal,
    AIResponseCache,
    AIRun,
    AIRunEvent,
    AIRunStatus,
    AIRunType,
)
from compose_ai_api.domains.ai_architect.provider_health import (
    ensure_provider_available,
    record_provider_failure,
    record_provider_success,
)
from compose_ai_api.domains.ai_architect.providers.base import (
    AIProviderError,
    ChatProviderRequest,
    ProviderUsage,
    StructuredProviderRequest,
)
from compose_ai_api.domains.ai_architect.providers.factory import (
    create_provider,
    model_for_alias,
)
from compose_ai_api.domains.ai_architect.quality import (
    current_value_for_path,
    has_blocking_conflict,
    validate_brief_quality,
)
from compose_ai_api.domains.ai_architect.schemas import ArchitectBriefOutput
from compose_ai_api.domains.ai_architect.service import append_run_event
from compose_ai_api.domains.ai_architect.token_usage import estimate_cost_microusd
from compose_ai_api.domains.ai_architect.usage import record_usage
from compose_ai_api.domains.projects.models import AuditLog, Project
from compose_ai_api.domains.projects.service import project_select


async def process_brief_job(job_id: UUID) -> None:
    claimed = await _claim_brief_job(job_id)
    if not claimed:
        return
    try:
        state = await _load_brief_execution(job_id)
        cached = await _load_cached_response(state.run)
        if cached is not None:
            output, source_run_id = cached
            await _complete_brief_job(
                job_id,
                output,
                ProviderUsage(),
                cache_hit=True,
                cache_source_run_id=source_run_id,
                latency_ms=0,
            )
            return
        started = monotonic()
        response, provider_name, model = await _generate_structured_with_fallback(state)
        await _complete_brief_job(
            job_id,
            ArchitectBriefOutput.model_validate(response.payload),
            response.usage,
            cache_hit=False,
            cache_source_run_id=None,
            latency_ms=int((monotonic() - started) * 1000),
            provider_name=provider_name,
            model=model,
        )
    except AIProviderError as error:
        await _fail_job(job_id, error)
    except Exception:
        await _fail_job(
            job_id,
            AIProviderError(
                "AI_RUN_FAILED",
                "The AI run could not be completed.",
                retryable=True,
            ),
        )


async def stream_chat_run(
    run_id: UUID,
    organization_id: UUID,
    *,
    after_sequence: int = 0,
) -> AsyncIterator[dict[str, Any]]:
    for event in await _stored_events(run_id, organization_id, after_sequence):
        yield event
        after_sequence = max(after_sequence, int(event["sequence"]))
    claimed = await _claim_chat_run(run_id, organization_id)
    if not claimed:
        async for event in _wait_for_run_events(run_id, organization_id, after_sequence):
            yield event
        return

    state = await _load_chat_execution(run_id, organization_id)
    settings = get_settings()
    emitted_content = False
    full_content = ""
    buffer = ""
    usage = ProviderUsage()
    provider_request_id: str | None = None
    started = monotonic()
    try:
        await _assert_run_not_cancelled(run_id)
        async with AsyncSessionFactory() as session:
            await ensure_provider_available(session, settings, state.run.provider, state.run.model)
            await session.commit()
        provider = create_provider(settings, state.run.provider)
        request = ChatProviderRequest(
            model=state.run.model,
            system_prompt=state.prompt.system_template,
            user_prompt=state.user_prompt,
            max_output_tokens=settings.ai_max_output_tokens,
        )
        async for provider_event in provider.stream_chat(request):
            await _assert_run_not_cancelled(run_id)
            if provider_event.event_type == "delta":
                emitted_content = True
                full_content += provider_event.delta
                buffer += provider_event.delta
                if len(buffer) >= 80:
                    event = await _persist_stream_delta(run_id, organization_id, buffer)
                    buffer = ""
                    yield event
            elif provider_event.event_type == "completed":
                usage = provider_event.usage
                provider_request_id = provider_event.provider_request_id
        if buffer:
            yield await _persist_stream_delta(run_id, organization_id, buffer)
        for event in await _complete_chat_run(
            state,
            full_content.strip(),
            usage,
            int((monotonic() - started) * 1000),
            provider_request_id,
        ):
            yield event
    except AIProviderError as error:
        if error.retryable and not emitted_content:
            retry_result = await _retry_chat_once(state)
            if retry_result is not None:
                content, usage, provider_request_id = retry_result
                if content:
                    yield await _persist_stream_delta(run_id, organization_id, content)
                for event in await _complete_chat_run(
                    state,
                    content,
                    usage,
                    int((monotonic() - started) * 1000),
                    provider_request_id,
                ):
                    yield event
                return
        yield await _fail_streaming_run(run_id, organization_id, error)
    except asyncio.CancelledError:
        await _fail_streaming_run(
            run_id,
            organization_id,
            AIProviderError(
                "AI_STREAM_INTERRUPTED",
                "The AI stream was interrupted.",
                retryable=True,
            ),
        )
        raise
    except Exception:
        yield await _fail_streaming_run(
            run_id,
            organization_id,
            AIProviderError(
                "AI_RUN_FAILED",
                "The AI response could not be completed.",
                retryable=True,
            ),
        )


class _BriefExecutionState:
    def __init__(
        self,
        run: AIRun,
        prompt: AIPromptTemplate,
        memory: AIProjectMemoryVersion,
    ) -> None:
        self.run = run
        self.prompt = prompt
        self.memory = memory


class _ChatExecutionState(_BriefExecutionState):
    def __init__(
        self,
        run: AIRun,
        prompt: AIPromptTemplate,
        memory: AIProjectMemoryVersion,
        user_prompt: str,
    ) -> None:
        super().__init__(run, prompt, memory)
        self.user_prompt = user_prompt


async def _claim_brief_job(job_id: UUID) -> bool:
    async with AsyncSessionFactory() as session:
        job = (
            await session.execute(
                select(AIJob).where(AIJob.id == job_id).with_for_update(skip_locked=True)
            )
        ).scalar_one_or_none()
        if job is None or job.status != AIJobStatus.QUEUED:
            return False
        run = await session.get(AIRun, job.ai_run_id, with_for_update=True)
        if run is None or run.status == AIRunStatus.CANCELLED:
            job.status = AIJobStatus.CANCELLED
            await session.commit()
            return False
        now = datetime.now(UTC)
        job.status = AIJobStatus.RUNNING
        job.locked_at = now
        job.locked_by = "api-background-worker"
        job.attempt_count += 1
        run.status = AIRunStatus.RUNNING
        run.started_at = now
        run.attempt_count += 1
        await append_run_event(session, run.id, "run.started", {"status": "running"})
        await session.commit()
        return True


async def _load_brief_execution(job_id: UUID) -> _BriefExecutionState:
    async with AsyncSessionFactory() as session:
        job = await session.get(AIJob, job_id)
        if job is None:
            raise AIProviderError("AI_JOB_NOT_FOUND", "AI job not found.", retryable=False)
        run = await session.get(AIRun, job.ai_run_id)
        if run is None:
            raise AIProviderError("AI_RUN_NOT_FOUND", "AI run not found.", retryable=False)
        prompt = await session.get(AIPromptTemplate, run.prompt_template_id)
        memory = await session.get(AIProjectMemoryVersion, run.memory_version_id)
        if prompt is None or memory is None:
            raise AIProviderError(
                "AI_CONTEXT_STALE",
                "The AI run context is no longer available.",
                retryable=False,
            )
        return _BriefExecutionState(run, prompt, memory)


async def _load_cached_response(
    run: AIRun,
) -> tuple[ArchitectBriefOutput, UUID] | None:
    if not run.cache_key:
        return None
    async with AsyncSessionFactory() as session:
        cache = (
            await session.execute(
                select(AIResponseCache)
                .where(
                    AIResponseCache.organization_id == run.organization_id,
                    AIResponseCache.cache_key == run.cache_key,
                    AIResponseCache.expires_at > datetime.now(UTC),
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if cache is None:
            return None
        cache.hit_count += 1
        cache.last_hit_at = datetime.now(UTC)
        output = ArchitectBriefOutput.model_validate(cache.response_payload)
        validate_brief_quality(output)
        await session.commit()
        return output, cache.source_run_id


async def _generate_structured_with_fallback(state: _BriefExecutionState):
    settings = get_settings()
    providers = [state.run.provider]
    if settings.ai_fallback_provider and settings.ai_fallback_provider not in providers:
        providers.append(settings.ai_fallback_provider)
    last_error: AIProviderError | None = None
    for provider_name in providers:
        model = (
            state.run.model
            if provider_name == state.run.provider
            else model_for_alias(settings, provider_name, state.run.model_alias)
        )
        try:
            async with AsyncSessionFactory() as session:
                await ensure_provider_available(session, settings, provider_name, model)
                await session.commit()
            provider = create_provider(settings, provider_name)
            user_prompt = state.prompt.input_template.format(
                project_context=memory_prompt_payload(state.memory),
                raw_requirements=state.run.input_payload["providerRequirements"],
            )
            request = StructuredProviderRequest(
                model=model,
                system_prompt=state.prompt.system_template,
                user_prompt=user_prompt,
                output_schema=ArchitectBriefOutput.model_json_schema(),
                output_schema_name="compose_architect_brief",
                max_output_tokens=settings.ai_max_output_tokens,
            )
            for attempt in range(settings.ai_max_retries + 1):
                try:
                    response = await provider.generate_structured(request)
                    output = ArchitectBriefOutput.model_validate(response.payload)
                    validate_brief_quality(output)
                    return response, provider_name, model
                except AIProviderError as error:
                    last_error = error
                    async with AsyncSessionFactory() as session:
                        await record_provider_failure(
                            session, settings, provider_name, model, error.code
                        )
                        await session.commit()
                    if not error.retryable or attempt >= settings.ai_max_retries:
                        break
                    await asyncio.sleep(min(2**attempt, 4) + 0.1)
        except AIProviderError as error:
            last_error = error
            continue
    raise last_error or AIProviderError(
        "AI_PROVIDER_UNAVAILABLE", "No AI provider is available.", retryable=True
    )


async def _complete_brief_job(
    job_id: UUID,
    output: ArchitectBriefOutput,
    usage: ProviderUsage,
    *,
    cache_hit: bool,
    cache_source_run_id: UUID | None,
    latency_ms: int,
    provider_name: str | None = None,
    model: str | None = None,
) -> None:
    validate_brief_quality(output)
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        job = await session.get(AIJob, job_id, with_for_update=True)
        if job is None:
            return
        run = await session.get(AIRun, job.ai_run_id, with_for_update=True)
        if run is None or run.status == AIRunStatus.CANCELLED:
            job.status = AIJobStatus.CANCELLED
            await session.commit()
            return
        memory = await session.get(AIProjectMemoryVersion, run.memory_version_id)
        prompt = await session.get(AIPromptTemplate, run.prompt_template_id)
        project = (
            await session.execute(
                project_select()
                .where(
                    Project.id == run.project_id,
                    Project.organization_id == run.organization_id,
                    Project.deleted_at.is_(None),
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if memory is None or prompt is None or project is None:
            raise AIProviderError(
                "AI_CONTEXT_STALE", "The AI run context is no longer available.", retryable=False
            )
        latest = (
            await session.execute(
                select(AIArchitectBriefVersion)
                .where(
                    AIArchitectBriefVersion.organization_id == run.organization_id,
                    AIArchitectBriefVersion.project_id == run.project_id,
                )
                .order_by(AIArchitectBriefVersion.version.desc())
                .limit(1)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if latest and latest.status in (AIBriefStatus.PROPOSED, AIBriefStatus.UNDER_REVIEW):
            latest.status = AIBriefStatus.SUPERSEDED
        brief = AIArchitectBriefVersion(
            id=uuid4(),
            organization_id=run.organization_id,
            project_id=run.project_id,
            version=(latest.version + 1) if latest else 1,
            source_run_id=run.id,
            memory_version_id=memory.id,
            status=AIBriefStatus.PROPOSED,
            original_input=str(run.input_payload["originalRequirements"]),
            summary=output.summary,
            goals=[item.model_dump(mode="json") for item in output.goals],
            priorities=[item.model_dump(mode="json") for item in output.priorities],
            constraints=[item.model_dump(mode="json") for item in output.constraints],
            normalized_requirements=output.normalized_requirements.model_dump(mode="json"),
            missing_information=[
                item.model_dump(mode="json") for item in output.missing_information
            ],
            conflicts=[item.model_dump(mode="json") for item in output.conflicts],
            clarification_questions=[
                item.model_dump(mode="json") for item in output.clarification_questions
            ],
            recommended_next_steps=[
                item.model_dump(mode="json") for item in output.recommended_next_steps
            ],
            warnings=[item.model_dump(mode="json") for item in output.warnings],
            assumptions=[item.model_dump(mode="json") for item in output.assumptions],
            aggregate_confidence=Decimal(str(output.aggregate_confidence)),
            schema_version=prompt.output_schema_version,
            based_on_project_version=memory.project_version,
            supersedes_id=latest.id if latest else None,
            created_by=run.created_by,
        )
        session.add(brief)
        await session.flush()
        for proposal_output in output.proposals:
            existing_value = current_value_for_path(project, proposal_output.target_path)
            if proposal_output.target_type != "plot_recommendation" and _json_equal(
                existing_value, proposal_output.proposed_value
            ):
                continue
            warnings = [item.model_dump(mode="json") for item in proposal_output.warnings]
            if has_blocking_conflict(output, proposal_output.target_path):
                warnings.append(
                    {
                        "code": "BLOCKING_CONFLICT",
                        "message": "Resolve the linked requirement conflict before approval.",
                        "target_path": proposal_output.target_path,
                    }
                )
            session.add(
                AIRequirementProposal(
                    id=uuid4(),
                    organization_id=run.organization_id,
                    brief_version_id=brief.id,
                    project_id=run.project_id,
                    target_type=str(proposal_output.target_type),
                    target_path=proposal_output.target_path,
                    existing_value=existing_value,
                    proposed_value=proposal_output.proposed_value,
                    source_references=[
                        item.model_dump(mode="json") for item in proposal_output.source_references
                    ],
                    explanation=proposal_output.explanation,
                    confidence=Decimal(str(proposal_output.confidence)),
                    warnings=warnings,
                    status=AIProposalStatus.PENDING,
                    expected_project_version=memory.project_version,
                )
            )
        now = datetime.now(UTC)
        actual_provider = provider_name or run.provider
        actual_model = model or run.model
        cost = (
            0
            if cache_hit
            else estimate_cost_microusd(
                usage.input_tokens,
                usage.output_tokens,
                settings.ai_input_price_per_1m_usd,
                settings.ai_output_price_per_1m_usd,
            )
        )
        run.provider = actual_provider
        run.model = actual_model
        run.status = AIRunStatus.COMPLETED
        run.input_tokens = usage.input_tokens
        run.output_tokens = usage.output_tokens
        run.cached_tokens = usage.cached_tokens
        run.actual_cost_microusd = cost
        run.latency_ms = latency_ms
        run.cache_hit = cache_hit
        run.cache_source_run_id = cache_source_run_id
        run.completed_at = now
        job.status = AIJobStatus.COMPLETED
        job.locked_at = None
        job.locked_by = None
        await append_run_event(
            session,
            run.id,
            "brief.created",
            {"briefId": str(brief.id), "briefVersion": brief.version},
        )
        await append_run_event(
            session,
            run.id,
            "run.usage",
            {
                "inputTokens": usage.input_tokens,
                "outputTokens": usage.output_tokens,
                "costMicrousd": cost,
                "cacheHit": cache_hit,
            },
        )
        await append_run_event(session, run.id, "run.completed", {"status": "completed"})
        await record_usage(
            session,
            organization_id=run.organization_id,
            user_id=run.created_by,
            provider=actual_provider,
            model=actual_model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_microusd=cost,
            cache_hit=cache_hit,
        )
        if not cache_hit:
            await record_provider_success(session, settings, actual_provider, actual_model)
            await _store_cache(session, run, prompt, output)
        session.add(
            AuditLog(
                id=uuid4(),
                organization_id=run.organization_id,
                actor_user_id=run.created_by,
                action="ai.brief.generated",
                entity_type="project",
                entity_id=run.project_id,
                before_data=None,
                after_data={
                    "briefId": str(brief.id),
                    "briefVersion": brief.version,
                    "runId": str(run.id),
                    "cacheHit": cache_hit,
                },
                created_at=now,
            )
        )
        await session.commit()


async def _store_cache(
    session,
    run: AIRun,
    prompt: AIPromptTemplate,
    output: ArchitectBriefOutput,
) -> None:
    if not run.cache_key:
        return
    settings = get_settings()
    statement = pg_insert(AIResponseCache).values(
        id=uuid4(),
        organization_id=run.organization_id,
        cache_key=run.cache_key,
        run_type=run.run_type,
        provider=run.provider,
        model=run.model,
        prompt_checksum=prompt.checksum,
        context_hash=run.context_hash,
        output_schema_version=prompt.output_schema_version,
        safety_policy_version=prompt.safety_policy_version,
        response_payload=output.model_dump(mode="json"),
        source_run_id=run.id,
        hit_count=0,
        expires_at=datetime.now(UTC) + timedelta(seconds=settings.ai_cache_ttl_seconds),
    )
    await session.execute(statement.on_conflict_do_nothing(constraint="uq_ai_cache_org_key"))


async def _fail_job(job_id: UUID, error: AIProviderError) -> None:
    async with AsyncSessionFactory() as session:
        job = await session.get(AIJob, job_id, with_for_update=True)
        if job is None:
            return
        run = await session.get(AIRun, job.ai_run_id, with_for_update=True)
        if run is None or run.status == AIRunStatus.CANCELLED:
            return
        run.status = AIRunStatus.FAILED
        run.failure_code = error.code
        run.failure_details_redacted = {
            "message": str(error)[:300],
            "retryable": error.retryable,
        }
        run.completed_at = datetime.now(UTC)
        job.status = AIJobStatus.FAILED
        job.failure_code = error.code
        job.locked_at = None
        job.locked_by = None
        await append_run_event(
            session,
            run.id,
            "run.failed",
            {"code": error.code, "retryable": error.retryable},
        )
        await session.commit()


async def _claim_chat_run(run_id: UUID, organization_id: UUID) -> bool:
    async with AsyncSessionFactory() as session:
        run = (
            await session.execute(
                select(AIRun)
                .where(AIRun.id == run_id, AIRun.organization_id == organization_id)
                .with_for_update(skip_locked=True)
            )
        ).scalar_one_or_none()
        if run is None or run.run_type != AIRunType.ARCHITECT_CHAT:
            return False
        if run.status != AIRunStatus.QUEUED:
            return False
        run.status = AIRunStatus.RUNNING
        run.started_at = datetime.now(UTC)
        run.attempt_count += 1
        event = await append_run_event(session, run.id, "run.started", {"status": "running"})
        await session.commit()
        return event is not None


async def _load_chat_execution(run_id: UUID, organization_id: UUID) -> _ChatExecutionState:
    async with AsyncSessionFactory() as session:
        run = (
            await session.execute(
                select(AIRun).where(
                    AIRun.id == run_id,
                    AIRun.organization_id == organization_id,
                )
            )
        ).scalar_one()
        prompt = await session.get(AIPromptTemplate, run.prompt_template_id)
        memory = await session.get(AIProjectMemoryVersion, run.memory_version_id)
        if prompt is None or memory is None:
            raise AIProviderError(
                "AI_CONTEXT_STALE", "The AI run context is no longer available.", retryable=False
            )
        user_prompt = prompt.input_template.format(
            project_context=memory_prompt_payload(memory),
            conversation=json.dumps(memory.context_payload.get("conversation", [])),
            message=run.input_payload["providerMessage"],
            mode=run.input_payload["mode"],
        )
        return _ChatExecutionState(run, prompt, memory, user_prompt)


async def _retry_chat_once(
    state: _ChatExecutionState,
) -> tuple[str, ProviderUsage, str | None] | None:
    settings = get_settings()
    if settings.ai_max_retries < 1:
        return None
    provider = create_provider(settings, state.run.provider)
    request = ChatProviderRequest(
        model=state.run.model,
        system_prompt=state.prompt.system_template,
        user_prompt=state.user_prompt,
        max_output_tokens=settings.ai_max_output_tokens,
    )
    content = ""
    usage = ProviderUsage()
    request_id: str | None = None
    async for event in provider.stream_chat(request):
        if event.event_type == "delta":
            content += event.delta
        elif event.event_type == "completed":
            usage = event.usage
            request_id = event.provider_request_id
    return content.strip(), usage, request_id


async def _persist_stream_delta(run_id: UUID, organization_id: UUID, delta: str) -> dict[str, Any]:
    async with AsyncSessionFactory() as session:
        run = (
            await session.execute(
                select(AIRun).where(
                    AIRun.id == run_id,
                    AIRun.organization_id == organization_id,
                )
            )
        ).scalar_one()
        if run.status == AIRunStatus.CANCELLED:
            raise AIProviderError("AI_RUN_CANCELLED", "The AI run was cancelled.", retryable=False)
        event = await append_run_event(session, run.id, "message.delta", {"delta": delta})
        await session.commit()
        return _event_payload(event)


async def _complete_chat_run(
    state: _ChatExecutionState,
    content: str,
    usage: ProviderUsage,
    latency_ms: int,
    provider_request_id: str | None,
) -> list[dict[str, Any]]:
    if not content:
        raise AIProviderError(
            "AI_EMPTY_RESPONSE", "The AI provider returned an empty response.", retryable=True
        )
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        run = await session.get(AIRun, state.run.id, with_for_update=True)
        if run is None:
            return []
        if run.status == AIRunStatus.CANCELLED:
            raise AIProviderError("AI_RUN_CANCELLED", "The AI run was cancelled.", retryable=False)
        next_sequence = (
            await session.execute(
                select(func.coalesce(func.max(AIChatMessage.sequence_number), 0)).where(
                    AIChatMessage.thread_id == run.thread_id
                )
            )
        ).scalar_one() + 1
        message = AIChatMessage(
            id=uuid4(),
            organization_id=run.organization_id,
            project_id=run.project_id,
            thread_id=run.thread_id,
            ai_run_id=run.id,
            role=AIMessageRole.ASSISTANT,
            mode=AIMessageMode(str(run.input_payload["mode"])),
            sequence_number=next_sequence,
            original_content=content,
            display_content=content,
            content_format="text",
            status=AIMessageStatus.COMPLETED,
            client_message_id=None,
            token_count=usage.output_tokens,
            created_by=None,
        )
        session.add(message)
        thread = await session.get(AIChatThread, run.thread_id, with_for_update=True)
        if thread:
            thread.last_message_at = datetime.now(UTC)
            thread.version += 1
        cost = estimate_cost_microusd(
            usage.input_tokens,
            usage.output_tokens,
            settings.ai_input_price_per_1m_usd,
            settings.ai_output_price_per_1m_usd,
        )
        run.status = AIRunStatus.COMPLETED
        run.input_tokens = usage.input_tokens
        run.output_tokens = usage.output_tokens
        run.cached_tokens = usage.cached_tokens
        run.actual_cost_microusd = cost
        run.latency_ms = latency_ms
        run.completed_at = datetime.now(UTC)
        message_event = await append_run_event(
            session,
            run.id,
            "message.completed",
            {
                "messageId": str(message.id),
                "sequenceNumber": next_sequence,
                "providerRequestId": provider_request_id,
            },
        )
        usage_event = await append_run_event(
            session,
            run.id,
            "run.usage",
            {
                "inputTokens": usage.input_tokens,
                "outputTokens": usage.output_tokens,
                "costMicrousd": cost,
                "cacheHit": False,
            },
        )
        completed_event = await append_run_event(
            session, run.id, "run.completed", {"status": "completed"}
        )
        await record_usage(
            session,
            organization_id=run.organization_id,
            user_id=run.created_by,
            provider=run.provider,
            model=run.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cost_microusd=cost,
            cache_hit=False,
        )
        await record_provider_success(session, settings, run.provider, run.model)
        await session.commit()
        return [
            _event_payload(message_event),
            _event_payload(usage_event),
            _event_payload(completed_event),
        ]


async def _fail_streaming_run(
    run_id: UUID,
    organization_id: UUID,
    error: AIProviderError,
) -> dict[str, Any]:
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        run = (
            await session.execute(
                select(AIRun)
                .where(AIRun.id == run_id, AIRun.organization_id == organization_id)
                .with_for_update()
            )
        ).scalar_one()
        if run.status != AIRunStatus.CANCELLED:
            run.status = AIRunStatus.FAILED
            run.failure_code = error.code
            run.failure_details_redacted = {"retryable": error.retryable}
            run.completed_at = datetime.now(UTC)
        await record_provider_failure(session, settings, run.provider, run.model, error.code)
        event = await append_run_event(
            session,
            run.id,
            "run.failed",
            {"code": error.code, "retryable": error.retryable},
        )
        await session.commit()
        return _event_payload(event)


async def _stored_events(
    run_id: UUID, organization_id: UUID, after_sequence: int
) -> list[dict[str, Any]]:
    async with AsyncSessionFactory() as session:
        run = (
            await session.execute(
                select(AIRun).where(
                    AIRun.id == run_id,
                    AIRun.organization_id == organization_id,
                )
            )
        ).scalar_one_or_none()
        if run is None:
            return []
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
        return [_event_payload(event) for event in events]


async def _wait_for_run_events(
    run_id: UUID, organization_id: UUID, after_sequence: int
) -> AsyncIterator[dict[str, Any]]:
    idle_rounds = 0
    while idle_rounds < 120:
        events = await _stored_events(run_id, organization_id, after_sequence)
        if events:
            idle_rounds = 0
            for event in events:
                after_sequence = int(event["sequence"])
                yield event
                if event["eventType"] in {"run.completed", "run.failed", "run.cancelled"}:
                    return
        else:
            idle_rounds += 1
            if idle_rounds % 30 == 0:
                yield {
                    "id": f"heartbeat-{idle_rounds}",
                    "runId": str(run_id),
                    "sequence": after_sequence,
                    "eventType": "heartbeat",
                    "payload": {},
                    "createdAt": datetime.now(UTC).isoformat(),
                }
            await asyncio.sleep(0.5)


async def _assert_run_not_cancelled(run_id: UUID) -> None:
    async with AsyncSessionFactory() as session:
        status_value = (
            await session.execute(select(AIRun.status).where(AIRun.id == run_id))
        ).scalar_one_or_none()
        if status_value == AIRunStatus.CANCELLED:
            raise AIProviderError("AI_RUN_CANCELLED", "The AI run was cancelled.", retryable=False)


def _event_payload(event: AIRunEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "runId": str(event.ai_run_id),
        "sequence": event.event_sequence,
        "eventType": event.event_type,
        "payload": event.payload,
        "createdAt": event.created_at.isoformat(),
    }


def _json_equal(left: Any, right: Any) -> bool:
    return json.dumps(left, sort_keys=True, default=str) == json.dumps(
        right, sort_keys=True, default=str
    )
