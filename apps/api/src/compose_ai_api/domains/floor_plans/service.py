from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.auth import AuthContext
from compose_ai_api.core.config import Settings
from compose_ai_api.domains.ai_architect.models import (
    AIArchitectBriefVersion,
    AIBriefStatus,
    AIProjectMemoryVersion,
)
from compose_ai_api.domains.ai_architect.usage import (
    enforce_usage_preflight,
    estimate_request_usage,
)
from compose_ai_api.domains.floor_plans.context import load_generation_context
from compose_ai_api.domains.floor_plans.geometry import (
    FLOOR_PLAN_ENGINE_VERSION,
    FLOOR_PLAN_GEOMETRY_ENGINE_VERSION,
    FLOOR_PLAN_PROMPT_VERSION,
    FLOOR_PLAN_SCHEMA_VERSION,
    FLOOR_PLAN_SOLVER_VERSION,
)
from compose_ai_api.domains.floor_plans.models import (
    FloorPlanDesignVersion,
    FloorPlanGenerationEvent,
    FloorPlanGenerationJob,
    FloorPlanGenerationRun,
    FloorPlanGeometrySnapshot,
    FloorPlanJobStatus,
    FloorPlanOption,
    FloorPlanOptionStatus,
    FloorPlanRunStatus,
    FloorPlanValidationResult,
)
from compose_ai_api.domains.floor_plans.providers.factory import create_floor_plan_provider
from compose_ai_api.domains.floor_plans.schemas import (
    CONCEPTUAL_DISCLAIMER,
    FloorPlanCompareResponse,
    FloorPlanComparisonMetric,
    FloorPlanDesignVersionResponse,
    FloorPlanGenerationAcceptedResponse,
    FloorPlanGenerationRequest,
    FloorPlanOptionResponse,
    FloorPlanOptionSummaryResponse,
    FloorPlanReadinessIssue,
    FloorPlanReadinessResponse,
    FloorPlanRunEventResponse,
    FloorPlanRunResponse,
    FloorPlanValidationResponse,
)
from compose_ai_api.domains.plot_intelligence.models import (
    PlotAnalysisSnapshot,
    PlotBoundaryVersion,
)
from compose_ai_api.domains.projects.models import AuditLog, Project
from compose_ai_api.domains.projects.service import (
    ensure_project_manage,
    ensure_project_read,
    project_error,
    project_select,
)

ACTIVE_RUN_STATUSES = (
    FloorPlanRunStatus.QUEUED,
    FloorPlanRunStatus.PREFLIGHTING,
    FloorPlanRunStatus.BUILDING_CONTEXT,
    FloorPlanRunStatus.GENERATING,
    FloorPlanRunStatus.SOLVING,
    FloorPlanRunStatus.VALIDATING,
)


async def floor_plan_readiness(
    session: AsyncSession, auth: AuthContext, project_id: UUID
) -> FloorPlanReadinessResponse:
    ensure_project_read(auth)
    project = (
        await session.execute(
            project_select().where(
                Project.id == project_id,
                Project.organization_id == auth.membership.organization_id,
                Project.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if project is None:
        raise project_error(404, "PROJECT_NOT_FOUND", "Project not found.")
    brief = await _latest_approved_brief(session, auth, project_id)
    memory = await _latest_memory(session, auth, project_id)
    boundary = (
        await session.get(PlotBoundaryVersion, project.site.current_boundary_version_id)
        if project.site and project.site.current_boundary_version_id
        else None
    )
    analysis = (
        await session.get(PlotAnalysisSnapshot, project.site.current_analysis_id)
        if project.site and project.site.current_analysis_id
        else None
    )
    issues: list[FloorPlanReadinessIssue] = []
    if project.status == "archived":
        issues.append(
            FloorPlanReadinessIssue(
                code="PROJECT_ARCHIVED",
                severity="blocking",
                message="Restore this project before generating conceptual plans.",
                action_url=f"/projects/{project_id}",
            )
        )
    if brief is None:
        issues.append(
            FloorPlanReadinessIssue(
                code="APPROVED_BRIEF_REQUIRED",
                severity="blocking",
                message="Approve an AI Architect brief before generation.",
                action_url=f"/projects/{project_id}/architect",
            )
        )
    if boundary is None or boundary.is_tombstone or boundary.validation_status == "invalid":
        issues.append(
            FloorPlanReadinessIssue(
                code="VALID_BOUNDARY_REQUIRED",
                severity="blocking",
                message="Create and validate an active plot boundary.",
                action_url=f"/projects/{project_id}/plot",
            )
        )
    if analysis is None or (boundary and analysis.boundary_version_id != boundary.id):
        issues.append(
            FloorPlanReadinessIssue(
                code="CURRENT_PLOT_ANALYSIS_REQUIRED",
                severity="blocking",
                message="Recalculate Plot Intelligence for the active boundary.",
                action_url=f"/projects/{project_id}/plot",
            )
        )
    elif _analysis_error_count(analysis) > 0:
        issues.append(
            FloorPlanReadinessIssue(
                code="PLOT_VALIDATION_ERRORS",
                severity="blocking",
                message="Resolve plot validation errors before generation.",
                action_url=f"/projects/{project_id}/plot",
            )
        )
    elif analysis.feasibility_status not in {
        "feasible",
        "likely_feasible",
        "preliminarily_feasible",
    }:
        issues.append(
            FloorPlanReadinessIssue(
                code="PLOT_FEASIBILITY_REVIEW",
                severity="warning",
                message="Plot feasibility is not confirmed and requires professional review.",
                action_url=f"/projects/{project_id}/plot",
            )
        )
    source_versions = {
        "projectVersion": project.version,
        "plotProfileRevision": project.site.profile_revision if project.site else None,
        "briefId": str(brief.id) if brief else None,
        "briefVersion": brief.version if brief else None,
        "memoryVersionId": str(memory.id) if memory else None,
        "memoryVersion": memory.version if memory else None,
        "boundaryVersionId": str(boundary.id) if boundary else None,
        "boundaryVersion": boundary.version if boundary else None,
        "analysisSnapshotId": str(analysis.id) if analysis else None,
    }
    return FloorPlanReadinessResponse(
        ready=not any(issue.severity == "blocking" for issue in issues),
        issues=issues,
        project_id=project.id,
        project_version=project.version,
        approved_brief_id=brief.id if brief else None,
        approved_brief_version=brief.version if brief else None,
        memory_version_id=memory.id if memory else None,
        boundary_version_id=boundary.id if boundary else None,
        analysis_snapshot_id=analysis.id if analysis else None,
        source_versions=source_versions,
        buildable_area_m2=analysis.pre_regulation_buildable_area_m2 if analysis else None,
    )


async def enqueue_generation(
    session: AsyncSession,
    settings: Settings,
    auth: AuthContext,
    project_id: UUID,
    request: FloorPlanGenerationRequest,
    idempotency_key: str,
) -> FloorPlanGenerationAcceptedResponse:
    ensure_project_manage(auth)
    context = await load_generation_context(session, auth, project_id, request)
    provider_name = settings.ai_provider
    _, model = create_floor_plan_provider(settings, provider_name)
    seed = request.deterministic_seed
    if seed is None:
        seed = secrets.randbits(63)
    effective_request = request.model_copy(update={"deterministic_seed": seed})
    input_payload = {
        "request": effective_request.model_dump(mode="json", by_alias=True),
        "providerContext": context.provider_payload,
    }
    input_hash = _stable_hash({"input": input_payload, "sources": context.source_versions})
    existing = (
        await session.execute(
            select(FloorPlanGenerationRun).where(
                FloorPlanGenerationRun.organization_id == auth.membership.organization_id,
                FloorPlanGenerationRun.created_by == auth.user.id,
                FloorPlanGenerationRun.idempotency_key == idempotency_key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        if existing.input_hash != input_hash:
            raise project_error(
                409,
                "IDEMPOTENCY_CONFLICT",
                "The idempotency key was already used with different floor-plan inputs.",
            )
        job = (
            await session.execute(
                select(FloorPlanGenerationJob).where(FloorPlanGenerationJob.run_id == existing.id)
            )
        ).scalar_one()
        return _accepted_response(existing, job)

    active_count = (
        await session.execute(
            select(func.count(FloorPlanGenerationRun.id)).where(
                FloorPlanGenerationRun.organization_id == auth.membership.organization_id,
                FloorPlanGenerationRun.status.in_(ACTIVE_RUN_STATUSES),
                FloorPlanGenerationRun.deleted_at.is_(None),
            )
        )
    ).scalar_one()
    if active_count >= settings.floor_plan_max_concurrent_runs_per_org:
        raise project_error(
            429,
            "FLOOR_PLAN_CONCURRENCY_LIMIT",
            "The organization has too many floor-plan runs in progress.",
            {"limit": settings.floor_plan_max_concurrent_runs_per_org},
        )
    serialized_context = json.dumps(context.provider_payload, sort_keys=True, default=str)
    estimate = estimate_request_usage(
        settings,
        "Compose conceptual floor-plan spatial programming",
        serialized_context,
        min(settings.ai_max_output_tokens, 4_000),
    )
    await enforce_usage_preflight(session, settings, auth, estimate)
    failure_budget = effective_request.failure_budget
    max_solver_attempts = min(
        failure_budget.max_solver_attempts, settings.floor_plan_max_solver_attempts
    )
    max_provider_retries = min(
        failure_budget.max_provider_retries, settings.floor_plan_max_provider_retries
    )
    max_processing_seconds = min(
        failure_budget.max_processing_seconds, settings.floor_plan_max_processing_seconds
    )
    max_invalid_candidates = min(
        failure_budget.max_invalid_candidates, settings.floor_plan_max_invalid_candidates
    )
    cache_key = _stable_hash(
        {
            "inputHash": input_hash,
            "seed": seed,
            "provider": provider_name,
            "model": model,
            "engine": FLOOR_PLAN_ENGINE_VERSION,
            "solver": FLOOR_PLAN_SOLVER_VERSION,
            "geometry": FLOOR_PLAN_GEOMETRY_ENGINE_VERSION,
            "schema": FLOOR_PLAN_SCHEMA_VERSION,
            "prompt": FLOOR_PLAN_PROMPT_VERSION,
            "diversity": str(effective_request.diversity_threshold),
            "optionCount": effective_request.option_count,
        }
    )
    run = FloorPlanGenerationRun(
        id=uuid4(),
        organization_id=auth.membership.organization_id,
        project_id=project_id,
        source_brief_id=context.brief.id,
        memory_version_id=context.memory.id,
        boundary_version_id=context.boundary.id,
        analysis_snapshot_id=context.analysis.id,
        status=FloorPlanRunStatus.QUEUED,
        requested_option_count=effective_request.option_count,
        completed_option_count=0,
        deterministic_seed=seed,
        input_payload=input_payload,
        input_hash=input_hash,
        source_versions=context.source_versions,
        engine_version=FLOOR_PLAN_ENGINE_VERSION,
        solver_version=FLOOR_PLAN_SOLVER_VERSION,
        geometry_engine_version=FLOOR_PLAN_GEOMETRY_ENGINE_VERSION,
        schema_version=FLOOR_PLAN_SCHEMA_VERSION,
        prompt_version=FLOOR_PLAN_PROMPT_VERSION,
        provider=provider_name,
        model=model,
        cache_key=cache_key,
        idempotency_key=idempotency_key,
        diversity_threshold=effective_request.diversity_threshold,
        max_solver_attempts=max_solver_attempts,
        max_provider_retries=max_provider_retries,
        max_processing_seconds=max_processing_seconds,
        max_invalid_candidates=max_invalid_candidates,
        estimated_input_tokens=estimate.input_tokens,
        estimated_output_tokens=estimate.output_tokens,
        estimated_cost_microusd=estimate.cost_microusd,
        version=1,
        created_by=auth.user.id,
    )
    job = FloorPlanGenerationJob(
        id=uuid4(),
        organization_id=auth.membership.organization_id,
        project_id=project_id,
        run_id=run.id,
        status=FloorPlanJobStatus.QUEUED,
        priority=100,
        attempt_count=0,
        available_at=datetime.now(UTC),
    )
    session.add(run)
    await session.flush()
    session.add(job)
    await session.flush()
    await append_generation_event(
        session,
        run.id,
        "run.queued",
        {
            "status": "queued",
            "optionCount": run.requested_option_count,
            "deterministicSeed": run.deterministic_seed,
            "failureBudget": _failure_budget(run),
        },
    )
    await _audit(
        session,
        auth,
        "floor_plan.generation_queued",
        "floor_plan_generation_run",
        run.id,
        {"projectId": str(project_id), "seed": seed, "optionCount": run.requested_option_count},
    )
    await session.commit()
    return _accepted_response(run, job)


async def load_run(
    session: AsyncSession, auth: AuthContext, project_id: UUID, run_id: UUID
) -> FloorPlanRunResponse:
    return _run_response(await _load_run_model(session, auth, project_id, run_id))


async def retry_generation(
    session: AsyncSession,
    settings: Settings,
    auth: AuthContext,
    project_id: UUID,
    run_id: UUID,
    idempotency_key: str,
) -> FloorPlanGenerationAcceptedResponse:
    previous = await _load_run_model(session, auth, project_id, run_id)
    if previous.status in ACTIVE_RUN_STATUSES:
        raise project_error(
            409,
            "FLOOR_PLAN_RUN_ACTIVE",
            "An active generation run cannot be retried.",
        )
    request = FloorPlanGenerationRequest.model_validate(previous.input_payload["request"])
    return await enqueue_generation(
        session,
        settings,
        auth,
        project_id,
        request,
        idempotency_key,
    )


async def list_runs(
    session: AsyncSession, auth: AuthContext, project_id: UUID, limit: int
) -> list[FloorPlanRunResponse]:
    ensure_project_read(auth)
    runs = list(
        (
            await session.execute(
                select(FloorPlanGenerationRun)
                .where(
                    FloorPlanGenerationRun.organization_id == auth.membership.organization_id,
                    FloorPlanGenerationRun.project_id == project_id,
                    FloorPlanGenerationRun.deleted_at.is_(None),
                )
                .order_by(FloorPlanGenerationRun.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [_run_response(run) for run in runs]


async def list_options(
    session: AsyncSession, auth: AuthContext, project_id: UUID, run_id: UUID
) -> list[FloorPlanOptionResponse]:
    await _load_run_model(session, auth, project_id, run_id)
    rows = (
        await session.execute(
            select(FloorPlanOption, FloorPlanGeometrySnapshot, FloorPlanValidationResult)
            .join(
                FloorPlanGeometrySnapshot, FloorPlanGeometrySnapshot.option_id == FloorPlanOption.id
            )
            .join(
                FloorPlanValidationResult, FloorPlanValidationResult.option_id == FloorPlanOption.id
            )
            .where(
                FloorPlanOption.organization_id == auth.membership.organization_id,
                FloorPlanOption.project_id == project_id,
                FloorPlanOption.run_id == run_id,
                FloorPlanOption.deleted_at.is_(None),
            )
            .order_by(FloorPlanOption.option_number)
        )
    ).all()
    return [_option_response(*row) for row in rows]


async def load_option(
    session: AsyncSession, auth: AuthContext, project_id: UUID, option_id: UUID
) -> FloorPlanOptionResponse:
    option, snapshot, validation = await _load_option_models(session, auth, project_id, option_id)
    return _option_response(option, snapshot, validation)


async def compare_options(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    option_ids: list[UUID],
) -> FloorPlanCompareResponse:
    loaded = [
        await _load_option_models(session, auth, project_id, option_id) for option_id in option_ids
    ]
    summaries = [_option_summary(option, validation) for option, _, validation in loaded]
    metrics = [
        _comparison_metric(
            "gross_area", "Gross area", loaded, "grossAreaM2", higher_is_better=False
        ),
        _comparison_metric(
            "efficiency", "Planning efficiency", loaded, "efficiencyPercent", higher_is_better=True
        ),
        FloorPlanComparisonMetric(
            code="confidence",
            label="Confidence",
            values={str(option.id): float(option.confidence) for option, _, _ in loaded},
            best_option_id=max(loaded, key=lambda row: row[0].confidence)[0].id,
        ),
        FloorPlanComparisonMetric(
            code="diversity",
            label="Topology diversity",
            values={str(option.id): float(option.diversity_score) for option, _, _ in loaded},
            best_option_id=max(loaded, key=lambda row: row[0].diversity_score)[0].id,
        ),
    ]
    return FloorPlanCompareResponse(options=summaries, metrics=metrics)


async def cancel_run(
    session: AsyncSession, auth: AuthContext, project_id: UUID, run_id: UUID
) -> FloorPlanRunResponse:
    ensure_project_manage(auth)
    run = await _load_run_model(session, auth, project_id, run_id, for_update=True)
    if run.status in {
        FloorPlanRunStatus.COMPLETED,
        FloorPlanRunStatus.PARTIAL,
        FloorPlanRunStatus.FAILED,
    }:
        return _run_response(run)
    run.status = FloorPlanRunStatus.CANCELLED
    run.cancelled_at = datetime.now(UTC)
    run.completed_at = run.cancelled_at
    run.version += 1
    job = (
        await session.execute(
            select(FloorPlanGenerationJob).where(FloorPlanGenerationJob.run_id == run.id)
        )
    ).scalar_one_or_none()
    if job:
        job.status = FloorPlanJobStatus.CANCELLED
    await append_generation_event(session, run.id, "run.cancelled", {"status": "cancelled"})
    await session.commit()
    return _run_response(run)


async def accept_option(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    option_id: UUID,
    *,
    expected_version: int,
    name: str | None,
) -> FloorPlanDesignVersionResponse:
    ensure_project_manage(auth)
    option, snapshot, validation = await _load_option_models(
        session, auth, project_id, option_id, for_update=True
    )
    existing = (
        await session.execute(
            select(FloorPlanDesignVersion).where(
                FloorPlanDesignVersion.source_option_id == option.id,
                FloorPlanDesignVersion.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return _design_response(existing)
    if option.version != expected_version:
        raise project_error(
            409,
            "FLOOR_PLAN_OPTION_VERSION_CONFLICT",
            "The option changed after it was loaded.",
            {"expectedVersion": expected_version, "currentVersion": option.version},
        )
    if option.status not in {FloorPlanOptionStatus.VALID, FloorPlanOptionStatus.ACCEPTED}:
        raise project_error(
            409, "FLOOR_PLAN_OPTION_NOT_ACCEPTABLE", "Only valid options can be accepted."
        )
    if validation.status != "valid":
        raise project_error(
            409,
            "FLOOR_PLAN_VALIDATION_REQUIRED",
            "The option must pass deterministic validation before acceptance.",
        )
    run = await session.get(FloorPlanGenerationRun, option.run_id)
    if run is None:
        raise project_error(404, "FLOOR_PLAN_RUN_NOT_FOUND", "Generation run not found.")
    await _assert_sources_current(session, auth, project_id, run)
    latest_version = (
        await session.execute(
            select(func.max(FloorPlanDesignVersion.version)).where(
                FloorPlanDesignVersion.organization_id == auth.membership.organization_id,
                FloorPlanDesignVersion.project_id == project_id,
            )
        )
    ).scalar_one()
    generation_time_ms = None
    if run.started_at and run.completed_at:
        generation_time_ms = max(
            0, round((run.completed_at - run.started_at).total_seconds() * 1000)
        )
    design = FloorPlanDesignVersion(
        id=uuid4(),
        organization_id=auth.membership.organization_id,
        project_id=project_id,
        source_run_id=run.id,
        source_option_id=option.id,
        geometry_snapshot_id=snapshot.id,
        validation_result_id=validation.id,
        restored_from_design_version_id=None,
        version=(latest_version or 0) + 1,
        name=name or f"Conceptual design {int(latest_version or 0) + 1}",
        geometry_hash=snapshot.geometry_hash,
        source_versions=run.source_versions,
        engine_versions={
            "generation": run.engine_version,
            "solver": run.solver_version,
            "geometry": run.geometry_engine_version,
            "validation": validation.validation_engine_version,
        },
        version_metadata={
            "generatedAt": run.completed_at.isoformat() if run.completed_at else None,
            "acceptedSource": "floor_plan_option",
            "inputHash": run.input_hash,
            "cacheHit": run.cache_hit,
            "cacheSourceRunId": str(run.cache_source_run_id) if run.cache_source_run_id else None,
        },
        source_provider=run.provider,
        source_model=run.model,
        generation_cost_microusd=run.actual_cost_microusd,
        generation_time_ms=generation_time_ms,
        disclaimer=CONCEPTUAL_DISCLAIMER,
        accepted_by=auth.user.id,
        accepted_at=datetime.now(UTC),
    )
    option.status = FloorPlanOptionStatus.ACCEPTED
    option.version += 1
    session.add(design)
    await _audit(
        session,
        auth,
        "floor_plan.design_accepted",
        "floor_plan_design_version",
        design.id,
        {"projectId": str(project_id), "optionId": str(option.id), "version": design.version},
    )
    await session.commit()
    return _design_response(design)


async def reject_option(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    option_id: UUID,
    *,
    expected_version: int,
    reason: str,
) -> FloorPlanOptionResponse:
    ensure_project_manage(auth)
    option, snapshot, validation = await _load_option_models(
        session, auth, project_id, option_id, for_update=True
    )
    if option.status == FloorPlanOptionStatus.REJECTED and option.rejection_reason == reason:
        return _option_response(option, snapshot, validation)
    if option.version != expected_version:
        raise project_error(
            409, "FLOOR_PLAN_OPTION_VERSION_CONFLICT", "The option changed after it was loaded."
        )
    if option.status == FloorPlanOptionStatus.ACCEPTED:
        raise project_error(
            409, "FLOOR_PLAN_OPTION_ACCEPTED", "Accepted design versions cannot be rejected."
        )
    option.status = FloorPlanOptionStatus.REJECTED
    option.rejection_reason = reason
    option.rejected_by = auth.user.id
    option.rejected_at = datetime.now(UTC)
    option.version += 1
    await session.commit()
    return _option_response(option, snapshot, validation)


async def list_design_versions(
    session: AsyncSession, auth: AuthContext, project_id: UUID
) -> list[FloorPlanDesignVersionResponse]:
    ensure_project_read(auth)
    designs = list(
        (
            await session.execute(
                select(FloorPlanDesignVersion)
                .where(
                    FloorPlanDesignVersion.organization_id == auth.membership.organization_id,
                    FloorPlanDesignVersion.project_id == project_id,
                    FloorPlanDesignVersion.deleted_at.is_(None),
                )
                .order_by(FloorPlanDesignVersion.version.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_design_response(design) for design in designs]


async def load_design_version(
    session: AsyncSession, auth: AuthContext, project_id: UUID, design_version_id: UUID
) -> FloorPlanDesignVersionResponse:
    return _design_response(
        await _load_design_version_model(session, auth, project_id, design_version_id)
    )


async def validate_option(
    session: AsyncSession, auth: AuthContext, project_id: UUID, option_id: UUID
) -> FloorPlanValidationResponse:
    _, _, validation = await _load_option_models(session, auth, project_id, option_id)
    return _validation_response(validation)


async def restore_design_version(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    design_version_id: UUID,
    *,
    name: str | None,
    idempotency_key: str,
) -> FloorPlanDesignVersionResponse:
    ensure_project_manage(auth)
    existing = await _idempotent_restored_design(session, auth, idempotency_key)
    if existing is not None:
        return _design_response(existing)
    source = await _load_design_version_model(session, auth, project_id, design_version_id)
    next_version = await _next_design_version(session, auth, project_id)
    restored = FloorPlanDesignVersion(
        id=uuid4(),
        organization_id=auth.membership.organization_id,
        project_id=project_id,
        source_run_id=source.source_run_id,
        source_option_id=source.source_option_id,
        geometry_snapshot_id=source.geometry_snapshot_id,
        validation_result_id=source.validation_result_id,
        restored_from_design_version_id=source.id,
        version=next_version,
        name=name or f"Restored {source.name}",
        geometry_hash=source.geometry_hash,
        source_versions=source.source_versions,
        engine_versions=source.engine_versions,
        version_metadata={
            **source.version_metadata,
            "restore": {
                "idempotencyKey": idempotency_key,
                "restoredFromDesignVersionId": str(source.id),
                "restoredFromVersion": source.version,
                "restoredAt": datetime.now(UTC).isoformat(),
            },
        },
        source_provider=source.source_provider,
        source_model=source.source_model,
        generation_cost_microusd=source.generation_cost_microusd,
        generation_time_ms=source.generation_time_ms,
        disclaimer=source.disclaimer,
        accepted_by=auth.user.id,
        accepted_at=datetime.now(UTC),
    )
    session.add(restored)
    await _audit(
        session,
        auth,
        "floor_plan.design_restored",
        "floor_plan_design_version",
        restored.id,
        {"projectId": str(project_id), "restoredFromDesignVersionId": str(source.id)},
    )
    await session.commit()
    return _design_response(restored)


async def delete_design_version(
    session: AsyncSession, auth: AuthContext, project_id: UUID, design_version_id: UUID
) -> None:
    ensure_project_manage(auth)
    design = await _load_design_version_model(
        session, auth, project_id, design_version_id, for_update=True
    )
    if design.deleted_at is not None:
        return
    design.deleted_at = datetime.now(UTC)
    await _audit(
        session,
        auth,
        "floor_plan.design_deleted",
        "floor_plan_design_version",
        design.id,
        {"projectId": str(project_id), "version": design.version},
    )
    await session.commit()


async def list_generation_events(
    session: AsyncSession,
    organization_id: UUID,
    run_id: UUID,
    after_sequence: int,
) -> list[FloorPlanRunEventResponse]:
    owned = (
        await session.execute(
            select(FloorPlanGenerationRun.id).where(
                FloorPlanGenerationRun.id == run_id,
                FloorPlanGenerationRun.organization_id == organization_id,
            )
        )
    ).scalar_one_or_none()
    if owned is None:
        return []
    events = list(
        (
            await session.execute(
                select(FloorPlanGenerationEvent)
                .where(
                    FloorPlanGenerationEvent.run_id == run_id,
                    FloorPlanGenerationEvent.sequence > after_sequence,
                )
                .order_by(FloorPlanGenerationEvent.sequence)
            )
        )
        .scalars()
        .all()
    )
    return [_event_response(event) for event in events]


async def append_generation_event(
    session: AsyncSession, run_id: UUID, event_type: str, payload: dict[str, Any]
) -> FloorPlanGenerationEvent:
    sequence = (
        await session.execute(
            select(func.coalesce(func.max(FloorPlanGenerationEvent.sequence), 0)).where(
                FloorPlanGenerationEvent.run_id == run_id
            )
        )
    ).scalar_one()
    event = FloorPlanGenerationEvent(
        id=uuid4(),
        run_id=run_id,
        sequence=int(sequence) + 1,
        event_type=event_type,
        payload=payload,
        created_at=datetime.now(UTC),
    )
    session.add(event)
    await session.flush()
    return event


async def _load_run_model(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    run_id: UUID,
    *,
    for_update: bool = False,
) -> FloorPlanGenerationRun:
    ensure_project_read(auth)
    statement = select(FloorPlanGenerationRun).where(
        FloorPlanGenerationRun.id == run_id,
        FloorPlanGenerationRun.organization_id == auth.membership.organization_id,
        FloorPlanGenerationRun.project_id == project_id,
        FloorPlanGenerationRun.deleted_at.is_(None),
    )
    if for_update:
        statement = statement.with_for_update()
    run = (await session.execute(statement)).scalar_one_or_none()
    if run is None:
        raise project_error(404, "FLOOR_PLAN_RUN_NOT_FOUND", "Generation run not found.")
    return run


async def _load_option_models(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    option_id: UUID,
    *,
    for_update: bool = False,
) -> tuple[FloorPlanOption, FloorPlanGeometrySnapshot, FloorPlanValidationResult]:
    ensure_project_read(auth)
    statement = (
        select(FloorPlanOption, FloorPlanGeometrySnapshot, FloorPlanValidationResult)
        .join(FloorPlanGeometrySnapshot, FloorPlanGeometrySnapshot.option_id == FloorPlanOption.id)
        .join(FloorPlanValidationResult, FloorPlanValidationResult.option_id == FloorPlanOption.id)
        .where(
            FloorPlanOption.id == option_id,
            FloorPlanOption.organization_id == auth.membership.organization_id,
            FloorPlanOption.project_id == project_id,
            FloorPlanOption.deleted_at.is_(None),
        )
    )
    if for_update:
        statement = statement.with_for_update()
    row = (await session.execute(statement)).one_or_none()
    if row is None:
        raise project_error(404, "FLOOR_PLAN_OPTION_NOT_FOUND", "Floor-plan option not found.")
    return row


async def _load_design_version_model(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    design_version_id: UUID,
    *,
    for_update: bool = False,
) -> FloorPlanDesignVersion:
    ensure_project_read(auth)
    statement = select(FloorPlanDesignVersion).where(
        FloorPlanDesignVersion.id == design_version_id,
        FloorPlanDesignVersion.organization_id == auth.membership.organization_id,
        FloorPlanDesignVersion.project_id == project_id,
        FloorPlanDesignVersion.deleted_at.is_(None),
    )
    if for_update:
        statement = statement.with_for_update()
    design = (await session.execute(statement)).scalar_one_or_none()
    if design is None:
        raise project_error(404, "FLOOR_PLAN_DESIGN_VERSION_NOT_FOUND", "Design version not found.")
    return design


async def _assert_sources_current(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    run: FloorPlanGenerationRun,
) -> None:
    project = (
        await session.execute(
            project_select().where(
                Project.id == project_id,
                Project.organization_id == auth.membership.organization_id,
                Project.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    brief = await _latest_approved_brief(session, auth, project_id)
    current = {
        "projectVersion": project.version if project else None,
        "plotProfileRevision": project.site.profile_revision if project and project.site else None,
        "briefId": str(brief.id) if brief else None,
        "boundaryVersionId": str(project.site.current_boundary_version_id)
        if project and project.site and project.site.current_boundary_version_id
        else None,
        "analysisSnapshotId": str(project.site.current_analysis_id)
        if project and project.site and project.site.current_analysis_id
        else None,
    }
    stale = {
        key: {"generatedFrom": run.source_versions.get(key), "current": value}
        for key, value in current.items()
        if run.source_versions.get(key) != value
    }
    if stale:
        raise project_error(
            409,
            "FLOOR_PLAN_SOURCES_STALE",
            "Project inputs changed after this option was generated. Regenerate before acceptance.",
            {"changedSources": stale},
        )


async def _latest_approved_brief(
    session: AsyncSession, auth: AuthContext, project_id: UUID
) -> AIArchitectBriefVersion | None:
    return (
        await session.execute(
            select(AIArchitectBriefVersion)
            .where(
                AIArchitectBriefVersion.organization_id == auth.membership.organization_id,
                AIArchitectBriefVersion.project_id == project_id,
                AIArchitectBriefVersion.status.in_((AIBriefStatus.APPROVED, AIBriefStatus.APPLIED)),
            )
            .order_by(AIArchitectBriefVersion.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _next_design_version(session: AsyncSession, auth: AuthContext, project_id: UUID) -> int:
    latest_version = (
        await session.execute(
            select(func.max(FloorPlanDesignVersion.version)).where(
                FloorPlanDesignVersion.organization_id == auth.membership.organization_id,
                FloorPlanDesignVersion.project_id == project_id,
            )
        )
    ).scalar_one()
    return int(latest_version or 0) + 1


async def _idempotent_restored_design(
    session: AsyncSession, auth: AuthContext, idempotency_key: str
) -> FloorPlanDesignVersion | None:
    return (
        await session.execute(
            select(FloorPlanDesignVersion).where(
                FloorPlanDesignVersion.organization_id == auth.membership.organization_id,
                FloorPlanDesignVersion.version_metadata["restore"]["idempotencyKey"].astext
                == idempotency_key,
                FloorPlanDesignVersion.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()


async def _latest_memory(
    session: AsyncSession, auth: AuthContext, project_id: UUID
) -> AIProjectMemoryVersion | None:
    return (
        await session.execute(
            select(AIProjectMemoryVersion)
            .where(
                AIProjectMemoryVersion.organization_id == auth.membership.organization_id,
                AIProjectMemoryVersion.project_id == project_id,
            )
            .order_by(AIProjectMemoryVersion.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _audit(
    session: AsyncSession,
    auth: AuthContext,
    action: str,
    entity_type: str,
    entity_id: UUID,
    after_data: dict[str, Any],
) -> None:
    session.add(
        AuditLog(
            id=uuid4(),
            organization_id=auth.membership.organization_id,
            actor_user_id=auth.user.id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            request_id=None,
            before_data=None,
            after_data=after_data,
            created_at=datetime.now(UTC),
        )
    )


def _accepted_response(
    run: FloorPlanGenerationRun, job: FloorPlanGenerationJob
) -> FloorPlanGenerationAcceptedResponse:
    return FloorPlanGenerationAcceptedResponse(
        run=_run_response(run),
        job_id=job.id,
        status_url=f"/api/v1/projects/{run.project_id}/floor-plans/generations/{run.id}",
        events_url=f"/api/v1/projects/{run.project_id}/floor-plans/generations/{run.id}/events",
    )


def _run_response(run: FloorPlanGenerationRun) -> FloorPlanRunResponse:
    stage_progress = {
        FloorPlanRunStatus.QUEUED: 3,
        FloorPlanRunStatus.PREFLIGHTING: 8,
        FloorPlanRunStatus.BUILDING_CONTEXT: 15,
        FloorPlanRunStatus.GENERATING: 25,
        FloorPlanRunStatus.SOLVING: 40,
        FloorPlanRunStatus.VALIDATING: 70,
        FloorPlanRunStatus.COMPLETED: 100,
        FloorPlanRunStatus.PARTIAL: 100,
        FloorPlanRunStatus.FAILED: 100,
        FloorPlanRunStatus.CANCELLED: 100,
    }
    base = stage_progress.get(FloorPlanRunStatus(str(run.status)), 0)
    if run.requested_option_count and str(run.status) in {"solving", "validating"}:
        base = max(base, 40 + round((run.completed_option_count / run.requested_option_count) * 50))
    return FloorPlanRunResponse(
        id=run.id,
        project_id=run.project_id,
        status=run.status,
        requested_option_count=run.requested_option_count,
        completed_option_count=run.completed_option_count,
        deterministic_seed=run.deterministic_seed,
        source_versions=run.source_versions,
        engine_version=run.engine_version,
        solver_version=run.solver_version,
        geometry_engine_version=run.geometry_engine_version,
        provider=run.provider,
        model=run.model,
        cache_hit=run.cache_hit,
        cache_source_run_id=run.cache_source_run_id,
        diversity_threshold=run.diversity_threshold,
        failure_budget=_failure_budget(run),
        failure_usage={
            "solverAttempts": run.solver_attempt_count,
            "providerRetries": run.provider_retry_count,
            "invalidCandidates": run.invalid_candidate_count,
        },
        estimated_input_tokens=run.estimated_input_tokens,
        estimated_output_tokens=run.estimated_output_tokens,
        estimated_cost_microusd=run.estimated_cost_microusd,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        actual_cost_microusd=run.actual_cost_microusd,
        failure_code=run.failure_code,
        failure_details=run.failure_details,
        version=run.version,
        progress_percent=min(100, base),
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
    )


def _option_summary(
    option: FloorPlanOption, validation: FloorPlanValidationResult
) -> FloorPlanOptionSummaryResponse:
    return FloorPlanOptionSummaryResponse(
        id=option.id,
        run_id=option.run_id,
        option_number=option.option_number,
        status=option.status,
        deterministic_seed=option.deterministic_seed,
        title=option.title,
        summary=option.summary,
        major_decisions=option.major_decisions,
        constraint_trace=option.constraint_trace,
        area_summary=option.area_summary,
        warnings=option.warnings,
        confidence=option.confidence,
        topology_signature=option.topology_signature,
        topology_features=option.topology_features,
        diversity_score=option.diversity_score,
        version=option.version,
        validation=_validation_response(validation),
        created_at=option.created_at,
    )


def _option_response(
    option: FloorPlanOption,
    snapshot: FloorPlanGeometrySnapshot,
    validation: FloorPlanValidationResult,
) -> FloorPlanOptionResponse:
    return FloorPlanOptionResponse(
        **_option_summary(option, validation).model_dump(),
        geometry_snapshot_id=snapshot.id,
        geometry_hash=snapshot.geometry_hash,
        geometry_engine_version=snapshot.geometry_engine_version,
        geometry=snapshot.geometry,
    )


def _validation_response(value: FloorPlanValidationResult) -> FloorPlanValidationResponse:
    return FloorPlanValidationResponse(
        status=value.status,
        validation_engine_version=value.validation_engine_version,
        geometry_engine_version=value.geometry_engine_version,
        summary=value.summary,
        checks=value.checks,
        errors=value.errors,
        warnings=value.warnings,
    )


def _design_response(value: FloorPlanDesignVersion) -> FloorPlanDesignVersionResponse:
    return FloorPlanDesignVersionResponse(
        id=value.id,
        project_id=value.project_id,
        source_run_id=value.source_run_id,
        source_option_id=value.source_option_id,
        geometry_snapshot_id=value.geometry_snapshot_id,
        validation_result_id=value.validation_result_id,
        restored_from_design_version_id=value.restored_from_design_version_id,
        version=value.version,
        name=value.name,
        geometry_hash=value.geometry_hash,
        source_versions=value.source_versions,
        engine_versions=value.engine_versions,
        version_metadata=value.version_metadata,
        source_provider=value.source_provider,
        source_model=value.source_model,
        generation_cost_microusd=value.generation_cost_microusd,
        generation_time_ms=value.generation_time_ms,
        disclaimer=value.disclaimer,
        accepted_at=value.accepted_at,
        created_at=value.created_at,
    )


def _event_response(value: FloorPlanGenerationEvent) -> FloorPlanRunEventResponse:
    return FloorPlanRunEventResponse(
        id=value.id,
        run_id=value.run_id,
        sequence=value.sequence,
        event_type=value.event_type,
        payload=value.payload,
        created_at=value.created_at,
    )


def _comparison_metric(
    code: str,
    label: str,
    loaded: list[tuple[FloorPlanOption, FloorPlanGeometrySnapshot, FloorPlanValidationResult]],
    area_key: str,
    *,
    higher_is_better: bool,
) -> FloorPlanComparisonMetric:
    values = {str(option.id): option.area_summary.get(area_key) for option, _, _ in loaded}
    chooser = max if higher_is_better else min
    best = chooser(loaded, key=lambda row: float(row[0].area_summary.get(area_key, 0)))[0]
    return FloorPlanComparisonMetric(code=code, label=label, values=values, best_option_id=best.id)


def _failure_budget(run: FloorPlanGenerationRun) -> dict[str, int]:
    return {
        "maxSolverAttempts": run.max_solver_attempts,
        "maxProviderRetries": run.max_provider_retries,
        "maxProcessingSeconds": run.max_processing_seconds,
        "maxInvalidCandidates": run.max_invalid_candidates,
    }


def _analysis_error_count(analysis: PlotAnalysisSnapshot) -> int:
    return int(
        analysis.validation_summary.get("errorCount", analysis.validation_summary.get("errors", 0))
    )


def _stable_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
