from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from compose_ai_api.core.config import get_settings
from compose_ai_api.core.database import AsyncSessionFactory
from compose_ai_api.domains.ai_architect.provider_health import (
    ensure_provider_available,
    record_provider_failure,
    record_provider_success,
)
from compose_ai_api.domains.ai_architect.providers.base import (
    AIProviderError,
    ProviderUsage,
)
from compose_ai_api.domains.ai_architect.token_usage import estimate_cost_microusd
from compose_ai_api.domains.ai_architect.usage import record_usage
from compose_ai_api.domains.floor_plans.constraints import (
    build_constraint_trace,
    confidence_from_trace,
)
from compose_ai_api.domains.floor_plans.diversity import (
    topology_diversity,
    topology_signature,
)
from compose_ai_api.domains.floor_plans.geometry import (
    FLOOR_PLAN_GEOMETRY_ENGINE_VERSION,
    FLOOR_PLAN_VALIDATION_VERSION,
    canonicalize_boundary,
    geometry_hash,
    stable_seed,
)
from compose_ai_api.domains.floor_plans.models import (
    FloorPlanGenerationJob,
    FloorPlanGenerationRun,
    FloorPlanGeometrySnapshot,
    FloorPlanJobStatus,
    FloorPlanOption,
    FloorPlanOptionStatus,
    FloorPlanRunStatus,
    FloorPlanValidationResult,
    FloorPlanValidationStatus,
)
from compose_ai_api.domains.floor_plans.providers.base import (
    FloorPlanProgramRequest,
    FloorPlanProgramResponse,
)
from compose_ai_api.domains.floor_plans.providers.factory import create_floor_plan_provider
from compose_ai_api.domains.floor_plans.schemas import FloorPlanGenerationRequest
from compose_ai_api.domains.floor_plans.service import (
    append_generation_event,
    list_generation_events,
)
from compose_ai_api.domains.floor_plans.solver import (
    FloorPlanSolveError,
    solve_floor_plan,
)
from compose_ai_api.domains.floor_plans.validation import validate_floor_plan
from compose_ai_api.domains.plot_intelligence.models import PlotBoundaryVersion

TERMINAL_EVENTS = {"run.completed", "run.partial", "run.failed", "run.cancelled"}


async def process_generation_job(job_id: UUID) -> None:
    started = monotonic()
    if not await _claim_job(job_id):
        return
    run = await _load_run_for_job(job_id)
    try:
        if await _clone_cached_run(job_id, run):
            return
        await _set_stage(run.id, FloorPlanRunStatus.BUILDING_CONTEXT, "run.context_ready", 15)
        program_response, provider_name, model, retry_count = await _generate_program(run, started)
        await _store_provider_result(
            run.id,
            provider_name,
            model,
            retry_count,
            program_response.usage,
        )
        await _set_stage(run.id, FloorPlanRunStatus.SOLVING, "run.solving", 30)
        await _generate_options(job_id, run.id, program_response, started)
    except AIProviderError as error:
        await _fail_job(job_id, error.code, {"retryable": error.retryable})
    except Exception as error:
        await _fail_job(
            job_id,
            "FLOOR_PLAN_RUN_FAILED",
            {"errorType": type(error).__name__, "retryable": True},
        )


async def stream_generation_events(
    run_id: UUID, organization_id: UUID, *, after_sequence: int = 0
) -> AsyncIterator[dict[str, Any]]:
    idle_rounds = 0
    while idle_rounds < 3_600:
        async with AsyncSessionFactory() as session:
            events = await list_generation_events(session, organization_id, run_id, after_sequence)
        if events:
            idle_rounds = 0
            for event in events:
                after_sequence = event.sequence
                payload = {
                    "id": str(event.id),
                    "runId": str(event.run_id),
                    "sequence": event.sequence,
                    "eventType": event.event_type,
                    "payload": event.payload,
                    "createdAt": event.created_at.isoformat(),
                }
                yield payload
                if event.event_type in TERMINAL_EVENTS:
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


async def _claim_job(job_id: UUID) -> bool:
    async with AsyncSessionFactory() as session:
        job = (
            await session.execute(
                select(FloorPlanGenerationJob)
                .where(FloorPlanGenerationJob.id == job_id)
                .with_for_update(skip_locked=True)
            )
        ).scalar_one_or_none()
        if job is None or job.status != FloorPlanJobStatus.QUEUED:
            return False
        run = await session.get(FloorPlanGenerationRun, job.run_id, with_for_update=True)
        if run is None or run.status == FloorPlanRunStatus.CANCELLED:
            job.status = FloorPlanJobStatus.CANCELLED
            await session.commit()
            return False
        now = datetime.now(UTC)
        job.status = FloorPlanJobStatus.RUNNING
        job.attempt_count += 1
        job.locked_at = now
        job.locked_by = "api-background-worker"
        run.status = FloorPlanRunStatus.PREFLIGHTING
        run.started_at = now
        run.version += 1
        await append_generation_event(
            session, run.id, "run.started", {"status": "preflighting", "progressPercent": 8}
        )
        await session.commit()
        return True


async def _load_run_for_job(job_id: UUID) -> FloorPlanGenerationRun:
    async with AsyncSessionFactory() as session:
        job = await session.get(FloorPlanGenerationJob, job_id)
        if job is None:
            raise AIProviderError(
                "FLOOR_PLAN_JOB_NOT_FOUND", "Generation job not found.", retryable=False
            )
        run = await session.get(FloorPlanGenerationRun, job.run_id)
        if run is None:
            raise AIProviderError(
                "FLOOR_PLAN_RUN_NOT_FOUND", "Generation run not found.", retryable=False
            )
        return run


async def _clone_cached_run(job_id: UUID, run: FloorPlanGenerationRun) -> bool:
    async with AsyncSessionFactory() as session:
        source = (
            await session.execute(
                select(FloorPlanGenerationRun)
                .where(
                    FloorPlanGenerationRun.organization_id == run.organization_id,
                    FloorPlanGenerationRun.cache_key == run.cache_key,
                    FloorPlanGenerationRun.id != run.id,
                    FloorPlanGenerationRun.status == FloorPlanRunStatus.COMPLETED,
                    FloorPlanGenerationRun.completed_option_count >= run.requested_option_count,
                    FloorPlanGenerationRun.deleted_at.is_(None),
                )
                .order_by(FloorPlanGenerationRun.completed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if source is None:
            return False
        source_rows = (
            await session.execute(
                select(FloorPlanOption, FloorPlanGeometrySnapshot, FloorPlanValidationResult)
                .join(
                    FloorPlanGeometrySnapshot,
                    FloorPlanGeometrySnapshot.option_id == FloorPlanOption.id,
                )
                .join(
                    FloorPlanValidationResult,
                    FloorPlanValidationResult.option_id == FloorPlanOption.id,
                )
                .where(
                    FloorPlanOption.run_id == source.id,
                    FloorPlanOption.status.in_(
                        (FloorPlanOptionStatus.VALID, FloorPlanOptionStatus.ACCEPTED)
                    ),
                    FloorPlanOption.deleted_at.is_(None),
                )
                .order_by(FloorPlanOption.option_number)
                .limit(run.requested_option_count)
            )
        ).all()
        if len(source_rows) < run.requested_option_count:
            return False
        target = await session.get(FloorPlanGenerationRun, run.id, with_for_update=True)
        job = await session.get(FloorPlanGenerationJob, job_id, with_for_update=True)
        if target is None or job is None or target.status == FloorPlanRunStatus.CANCELLED:
            return True
        for source_option, source_geometry, source_validation in source_rows:
            option = FloorPlanOption(
                id=uuid4(),
                organization_id=target.organization_id,
                project_id=target.project_id,
                run_id=target.id,
                option_number=source_option.option_number,
                status=FloorPlanOptionStatus.VALID,
                deterministic_seed=source_option.deterministic_seed,
                title=source_option.title,
                summary=source_option.summary,
                provider_program=source_option.provider_program,
                major_decisions=source_option.major_decisions,
                constraint_trace=source_option.constraint_trace,
                area_summary=source_option.area_summary,
                warnings=source_option.warnings,
                confidence=source_option.confidence,
                topology_signature=source_option.topology_signature,
                topology_features=source_option.topology_features,
                diversity_score=source_option.diversity_score,
                solver_attempt=source_option.solver_attempt,
                version=1,
            )
            session.add(option)
            await session.flush()
            session.add_all(
                [
                    FloorPlanGeometrySnapshot(
                        id=uuid4(),
                        organization_id=target.organization_id,
                        project_id=target.project_id,
                        option_id=option.id,
                        coordinate_space=source_geometry.coordinate_space,
                        unit=source_geometry.unit,
                        schema_version=source_geometry.schema_version,
                        geometry_engine_version=source_geometry.geometry_engine_version,
                        geometry_hash=source_geometry.geometry_hash,
                        geometry=source_geometry.geometry,
                        bounding_box=source_geometry.bounding_box,
                        gross_area_m2=source_geometry.gross_area_m2,
                        source_versions=target.source_versions,
                    ),
                    FloorPlanValidationResult(
                        id=uuid4(),
                        organization_id=target.organization_id,
                        project_id=target.project_id,
                        option_id=option.id,
                        status=source_validation.status,
                        validation_engine_version=source_validation.validation_engine_version,
                        geometry_engine_version=source_validation.geometry_engine_version,
                        summary=source_validation.summary,
                        checks=source_validation.checks,
                        errors=source_validation.errors,
                        warnings=source_validation.warnings,
                    ),
                ]
            )
        now = datetime.now(UTC)
        target.status = FloorPlanRunStatus.COMPLETED
        target.completed_option_count = len(source_rows)
        target.cache_hit = True
        target.cache_source_run_id = source.id
        target.provider = source.provider
        target.model = source.model
        target.completed_at = now
        target.version += 1
        job.status = FloorPlanJobStatus.COMPLETED
        job.locked_at = None
        job.locked_by = None
        await append_generation_event(
            session,
            target.id,
            "run.cache_hit",
            {"sourceRunId": str(source.id), "optionCount": len(source_rows)},
        )
        await append_generation_event(
            session, target.id, "run.completed", {"status": "completed", "cacheHit": True}
        )
        await record_usage(
            session,
            organization_id=target.organization_id,
            user_id=target.created_by,
            provider=target.provider,
            model=target.model,
            input_tokens=0,
            output_tokens=0,
            cost_microusd=0,
            cache_hit=True,
        )
        await session.commit()
        return True


async def _generate_program(
    run: FloorPlanGenerationRun, started: float
) -> tuple[FloorPlanProgramResponse, str, str, int]:
    settings = get_settings()
    candidates = [run.provider]
    for retry_index in range(run.max_provider_retries):
        fallback = settings.ai_fallback_provider
        if fallback and retry_index == run.max_provider_retries - 1:
            candidates.append(fallback)
        else:
            candidates.append(run.provider)
    last_error: AIProviderError | None = None
    for attempt, provider_name in enumerate(candidates):
        await _assert_active(run.id)
        remaining = run.max_processing_seconds - (monotonic() - started)
        if remaining <= 0:
            raise AIProviderError(
                "FLOOR_PLAN_PROCESSING_TIMEOUT",
                "The generation processing time budget was exhausted.",
                retryable=False,
            )
        try:
            provider, model = create_floor_plan_provider(settings, provider_name)
            async with AsyncSessionFactory() as session:
                await ensure_provider_available(session, settings, provider_name, model)
                await session.commit()
            request = FloorPlanProgramRequest(
                model=model,
                context=dict(run.input_payload["providerContext"]),
                deterministic_seed=run.deterministic_seed,
                max_output_tokens=min(settings.ai_max_output_tokens, 4_000),
            )
            response = await asyncio.wait_for(
                provider.generate_program(request),
                timeout=max(0.1, min(settings.ai_request_timeout_seconds, remaining)),
            )
            async with AsyncSessionFactory() as session:
                await record_provider_success(session, settings, provider_name, model)
                await session.commit()
            return response, provider_name, model, attempt
        except TimeoutError:
            last_error = AIProviderError(
                "AI_PROVIDER_TIMEOUT", "The floor-plan provider timed out.", retryable=True
            )
        except AIProviderError as error:
            last_error = error
        except Exception:
            last_error = AIProviderError(
                "AI_PROVIDER_RESPONSE_INVALID",
                "The floor-plan provider returned an invalid spatial program.",
                retryable=True,
            )
        async with AsyncSessionFactory() as session:
            model_for_health = locals().get("model", run.model)
            await record_provider_failure(
                session, settings, provider_name, str(model_for_health), last_error.code
            )
            tracked_run = await session.get(FloorPlanGenerationRun, run.id, with_for_update=True)
            if tracked_run:
                tracked_run.provider_retry_count = attempt
                tracked_run.version += 1
            await session.commit()
        if not last_error.retryable and provider_name == candidates[-1]:
            break
        await asyncio.sleep(min(2**attempt, 3) * 0.1)
    raise last_error or AIProviderError(
        "AI_PROVIDER_UNAVAILABLE", "No floor-plan provider is available.", retryable=True
    )


async def _store_provider_result(
    run_id: UUID,
    provider_name: str,
    model: str,
    retry_count: int,
    usage: ProviderUsage,
) -> None:
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        run = await session.get(FloorPlanGenerationRun, run_id, with_for_update=True)
        if run is None:
            return
        run.provider = provider_name
        run.model = model
        run.provider_retry_count = retry_count
        run.input_tokens = usage.input_tokens
        run.output_tokens = usage.output_tokens
        run.actual_cost_microusd = estimate_cost_microusd(
            usage.input_tokens,
            usage.output_tokens,
            settings.ai_input_price_per_1m_usd,
            settings.ai_output_price_per_1m_usd,
        )
        run.version += 1
        await append_generation_event(
            session,
            run.id,
            "program.completed",
            {
                "provider": provider_name,
                "model": model,
                "inputTokens": usage.input_tokens,
                "outputTokens": usage.output_tokens,
            },
        )
        await session.commit()


async def _generate_options(
    job_id: UUID,
    run_id: UUID,
    program_response: FloorPlanProgramResponse,
    started: float,
) -> None:
    async with AsyncSessionFactory() as session:
        run = await session.get(FloorPlanGenerationRun, run_id)
        if run is None:
            return
        boundary = await session.get(PlotBoundaryVersion, run.boundary_version_id)
    if boundary is None:
        raise AIProviderError(
            "FLOOR_PLAN_CONTEXT_STALE", "The source plot boundary is unavailable.", retryable=False
        )
    canonical = canonicalize_boundary(boundary)
    request = FloorPlanGenerationRequest.model_validate(run.input_payload["request"])
    existing_features: list[dict[str, Any]] = []
    stop_code = "FLOOR_PLAN_FAILURE_BUDGET_EXHAUSTED"
    while True:
        current = await _load_run(run_id)
        if current.status == FloorPlanRunStatus.CANCELLED:
            return
        if current.completed_option_count >= current.requested_option_count:
            stop_code = ""
            break
        if current.solver_attempt_count >= current.max_solver_attempts:
            stop_code = "FLOOR_PLAN_SOLVER_ATTEMPT_LIMIT"
            break
        if current.invalid_candidate_count >= current.max_invalid_candidates:
            stop_code = "FLOOR_PLAN_INVALID_CANDIDATE_LIMIT"
            break
        remaining = current.max_processing_seconds - (monotonic() - started)
        if remaining <= 0:
            stop_code = "FLOOR_PLAN_PROCESSING_TIMEOUT"
            break

        attempt = await _begin_solver_attempt(current.id)
        option_seed = stable_seed(current.deterministic_seed, attempt)
        try:
            solved = await asyncio.to_thread(
                solve_floor_plan,
                canonical.polygon_mm,
                program_response.program,
                deterministic_seed=option_seed,
                solver_time_limit_seconds=min(5.0, max(0.1, remaining)),
            )
            solved.geometry["coordinateTransform"] = canonical.transform
            solved.geometry["sourceVersions"] = current.source_versions
            validation = validate_floor_plan(solved.geometry, canonical.polygon_mm)
            if not validation.valid:
                await _record_invalid_candidate(
                    current.id,
                    attempt,
                    option_seed,
                    "DETERMINISTIC_VALIDATION_FAILED",
                    {"errors": validation.errors[:10]},
                )
                continue
            diversity = topology_diversity(solved.topology_features, existing_features)
            if diversity < float(current.diversity_threshold):
                await _record_invalid_candidate(
                    current.id,
                    attempt,
                    option_seed,
                    "TOPOLOGY_DIVERSITY_BELOW_THRESHOLD",
                    {"score": diversity, "threshold": float(current.diversity_threshold)},
                )
                continue
            trace = build_constraint_trace(
                request,
                program_response.program,
                solved.geometry,
                solved.topology_features,
                validation,
            )
            blocking_violations = [
                item for item in trace if item.severity == "blocking" and item.status == "violated"
            ]
            if blocking_violations:
                await _record_invalid_candidate(
                    current.id,
                    attempt,
                    option_seed,
                    "BLOCKING_CONSTRAINT_VIOLATION",
                    {"constraintCodes": [item.code for item in blocking_violations]},
                )
                continue
            await _persist_option(
                current.id,
                attempt,
                option_seed,
                program_response,
                solved.geometry,
                solved.topology_features,
                solved.area_summary,
                validation,
                trace,
                diversity,
            )
            existing_features.append(solved.topology_features)
        except FloorPlanSolveError as error:
            await _record_invalid_candidate(
                current.id,
                attempt,
                option_seed,
                error.code,
                error.details,
            )

    await _finalize_generation(job_id, run_id, stop_code)


async def _persist_option(
    run_id: UUID,
    attempt: int,
    option_seed: int,
    program_response: FloorPlanProgramResponse,
    geometry: dict[str, Any],
    features: dict[str, Any],
    area_summary: dict[str, Any],
    validation: Any,
    trace: list[Any],
    diversity: float,
) -> None:
    async with AsyncSessionFactory() as session:
        run = await session.get(FloorPlanGenerationRun, run_id, with_for_update=True)
        if run is None or run.status == FloorPlanRunStatus.CANCELLED:
            return
        option_number = run.completed_option_count + 1
        signature = topology_signature(features)
        orientation = str(features.get("orientation", "balanced")).replace("_", " ").title()
        decisions = [
            item.model_dump(mode="json") for item in program_response.program.major_decisions
        ]
        decisions.append(
            {
                "code": "DETERMINISTIC_TOPOLOGY",
                "title": f"{orientation} circulation topology",
                "explanation": (
                    "This option uses a materially distinct room order, circulation axis, "
                    "or entrance "
                    "relationship selected by the deterministic seed."
                ),
                "confidence": 0.9,
            }
        )
        geometry_digest = geometry_hash(geometry)
        option = FloorPlanOption(
            id=uuid4(),
            organization_id=run.organization_id,
            project_id=run.project_id,
            run_id=run.id,
            option_number=option_number,
            status=FloorPlanOptionStatus.VALID,
            deterministic_seed=option_seed,
            title=f"Option {option_number} · {orientation} plan",
            summary=(
                f"A {program_response.program.floors}-floor conceptual plan with a "
                f"{features.get('orientation')} circulation spine and "
                f"{features.get('entranceSide')} entrance."
            ),
            provider_program=program_response.program.model_dump(mode="json"),
            major_decisions=decisions,
            constraint_trace=[item.model_dump(mode="json", by_alias=True) for item in trace],
            area_summary=area_summary,
            warnings=[*program_response.program.warnings, *validation.warnings],
            confidence=Decimal(str(confidence_from_trace(trace, validation))),
            topology_signature=signature,
            topology_features=features,
            diversity_score=Decimal(str(diversity)),
            solver_attempt=attempt,
            version=1,
        )
        session.add(option)
        await session.flush()
        envelope = geometry["buildableEnvelope"]
        x_values = [point[0] for point in envelope]
        y_values = [point[1] for point in envelope]
        session.add_all(
            [
                FloorPlanGeometrySnapshot(
                    id=uuid4(),
                    organization_id=run.organization_id,
                    project_id=run.project_id,
                    option_id=option.id,
                    coordinate_space="local_cartesian",
                    unit="millimeter",
                    schema_version=run.schema_version,
                    geometry_engine_version=run.geometry_engine_version,
                    geometry_hash=geometry_digest,
                    geometry=geometry,
                    bounding_box={
                        "minX": min(x_values),
                        "minY": min(y_values),
                        "maxX": max(x_values),
                        "maxY": max(y_values),
                    },
                    gross_area_m2=Decimal(str(area_summary["grossAreaM2"])),
                    source_versions=run.source_versions,
                ),
                FloorPlanValidationResult(
                    id=uuid4(),
                    organization_id=run.organization_id,
                    project_id=run.project_id,
                    option_id=option.id,
                    status=FloorPlanValidationStatus.VALID,
                    validation_engine_version=FLOOR_PLAN_VALIDATION_VERSION,
                    geometry_engine_version=FLOOR_PLAN_GEOMETRY_ENGINE_VERSION,
                    summary=validation.summary,
                    checks=validation.checks,
                    errors=validation.errors,
                    warnings=validation.warnings,
                ),
            ]
        )
        run.completed_option_count = option_number
        run.status = FloorPlanRunStatus.VALIDATING
        run.version += 1
        await append_generation_event(
            session,
            run.id,
            "option.completed",
            {
                "optionId": str(option.id),
                "optionNumber": option_number,
                "deterministicSeed": option_seed,
                "diversityScore": diversity,
                "topologySignature": signature,
                "geometryHash": geometry_digest,
            },
        )
        await session.commit()


async def _begin_solver_attempt(run_id: UUID) -> int:
    async with AsyncSessionFactory() as session:
        run = await session.get(FloorPlanGenerationRun, run_id, with_for_update=True)
        if run is None:
            return 0
        run.solver_attempt_count += 1
        run.status = FloorPlanRunStatus.SOLVING
        run.version += 1
        attempt = run.solver_attempt_count
        await append_generation_event(
            session,
            run.id,
            "candidate.started",
            {"attempt": attempt, "deterministicSeed": stable_seed(run.deterministic_seed, attempt)},
        )
        await session.commit()
        return attempt


async def _record_invalid_candidate(
    run_id: UUID,
    attempt: int,
    option_seed: int,
    code: str,
    details: dict[str, Any],
) -> None:
    async with AsyncSessionFactory() as session:
        run = await session.get(FloorPlanGenerationRun, run_id, with_for_update=True)
        if run is None:
            return
        run.invalid_candidate_count += 1
        run.version += 1
        await append_generation_event(
            session,
            run.id,
            "candidate.invalid",
            {
                "attempt": attempt,
                "deterministicSeed": option_seed,
                "code": code,
                "details": details,
            },
        )
        await session.commit()


async def _finalize_generation(job_id: UUID, run_id: UUID, stop_code: str) -> None:
    settings = get_settings()
    async with AsyncSessionFactory() as session:
        run = await session.get(FloorPlanGenerationRun, run_id, with_for_update=True)
        job = await session.get(FloorPlanGenerationJob, job_id, with_for_update=True)
        if run is None or job is None:
            return
        if run.status == FloorPlanRunStatus.CANCELLED:
            job.status = FloorPlanJobStatus.CANCELLED
            await session.commit()
            return
        now = datetime.now(UTC)
        if run.completed_option_count >= run.requested_option_count:
            run.status = FloorPlanRunStatus.COMPLETED
            event_type = "run.completed"
            run.failure_code = None
            run.failure_details = None
            job.status = FloorPlanJobStatus.COMPLETED
        elif run.completed_option_count > 0:
            run.status = FloorPlanRunStatus.PARTIAL
            event_type = "run.partial"
            run.failure_code = stop_code
            run.failure_details = {"partialResults": True}
            job.status = FloorPlanJobStatus.COMPLETED
        else:
            run.status = FloorPlanRunStatus.FAILED
            event_type = "run.failed"
            run.failure_code = stop_code or "FLOOR_PLAN_NO_VALID_OPTIONS"
            run.failure_details = {"partialResults": False}
            job.status = FloorPlanJobStatus.FAILED
            job.failure_code = run.failure_code
        run.completed_at = now
        run.version += 1
        job.locked_at = None
        job.locked_by = None
        await append_generation_event(
            session,
            run.id,
            event_type,
            {
                "status": str(run.status),
                "optionCount": run.completed_option_count,
                "requestedOptionCount": run.requested_option_count,
                "failureCode": run.failure_code,
            },
        )
        await record_usage(
            session,
            organization_id=run.organization_id,
            user_id=run.created_by,
            provider=run.provider,
            model=run.model,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            cost_microusd=run.actual_cost_microusd,
            cache_hit=False,
        )
        await record_provider_success(session, settings, run.provider, run.model)
        await session.commit()


async def _set_stage(
    run_id: UUID, stage: FloorPlanRunStatus, event_type: str, progress: int
) -> None:
    async with AsyncSessionFactory() as session:
        run = await session.get(FloorPlanGenerationRun, run_id, with_for_update=True)
        if run is None or run.status == FloorPlanRunStatus.CANCELLED:
            return
        run.status = stage
        run.version += 1
        await append_generation_event(
            session,
            run.id,
            event_type,
            {"status": str(stage), "progressPercent": progress},
        )
        await session.commit()


async def _assert_active(run_id: UUID) -> None:
    run = await _load_run(run_id)
    if run.status == FloorPlanRunStatus.CANCELLED:
        raise AIProviderError(
            "FLOOR_PLAN_RUN_CANCELLED", "The generation run was cancelled.", retryable=False
        )


async def _load_run(run_id: UUID) -> FloorPlanGenerationRun:
    async with AsyncSessionFactory() as session:
        run = await session.get(FloorPlanGenerationRun, run_id)
        if run is None:
            raise AIProviderError(
                "FLOOR_PLAN_RUN_NOT_FOUND", "Generation run not found.", retryable=False
            )
        return run


async def _fail_job(job_id: UUID, code: str, details: dict[str, Any]) -> None:
    async with AsyncSessionFactory() as session:
        job = await session.get(FloorPlanGenerationJob, job_id, with_for_update=True)
        if job is None:
            return
        run = await session.get(FloorPlanGenerationRun, job.run_id, with_for_update=True)
        if run is None:
            return
        if run.status == FloorPlanRunStatus.CANCELLED:
            job.status = FloorPlanJobStatus.CANCELLED
            await session.commit()
            return
        run.status = FloorPlanRunStatus.FAILED
        run.failure_code = code
        run.failure_details = details
        run.completed_at = datetime.now(UTC)
        run.version += 1
        job.status = FloorPlanJobStatus.FAILED
        job.failure_code = code
        job.locked_at = None
        job.locked_by = None
        await append_generation_event(
            session, run.id, "run.failed", {"status": "failed", "code": code, **details}
        )
        await session.commit()
