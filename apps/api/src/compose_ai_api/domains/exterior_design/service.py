from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from fastapi import status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.auth import AuthContext
from compose_ai_api.core.config import get_settings
from compose_ai_api.domains.ai_architect.provider_health import (
    ensure_provider_available,
    record_provider_failure,
    record_provider_success,
)
from compose_ai_api.domains.ai_architect.providers.base import AIProviderError, ImageProviderRequest
from compose_ai_api.domains.ai_architect.providers.factory import create_provider
from compose_ai_api.domains.ai_architect.usage import record_usage
from compose_ai_api.domains.exterior_design.constants import (
    CONCEPTUAL_DISCLAIMER,
    EXTERIOR_DESIGN_ENGINE_VERSION,
    EXTERIOR_PROMPT_VERSION,
    EXTERIOR_VALIDATION_ENGINE_VERSION,
    MATERIAL_CATEGORIES,
)
from compose_ai_api.domains.exterior_design.context_builder import (
    build_source_context,
    context_snapshot_payload,
)
from compose_ai_api.domains.exterior_design.models import (
    ExteriorDesignApprovalStatus,
    ExteriorDesignAsset,
    ExteriorDesignContextSnapshot,
    ExteriorDesignEvent,
    ExteriorDesignOption,
    ExteriorDesignOptionStatus,
    ExteriorDesignRun,
    ExteriorDesignRunStatus,
    ExteriorDesignStyle,
    ExteriorDesignValidationResult,
    ExteriorDesignViewType,
)
from compose_ai_api.domains.exterior_design.prompting import build_exterior_prompt
from compose_ai_api.domains.exterior_design.schemas import (
    ExteriorAsset,
    ExteriorGenerationAccepted,
    ExteriorGenerationRequest,
    ExteriorOption,
    ExteriorOptionActionRequest,
    ExteriorReadinessIssue,
    ExteriorReadinessResponse,
    ExteriorRun,
    ExteriorRunDetail,
    ExteriorRunEvent,
    ExteriorValidationResult,
)
from compose_ai_api.domains.exterior_design.storage import AssetStorageError, create_asset_storage
from compose_ai_api.domains.exterior_design.validation import validate_generated_option
from compose_ai_api.domains.projects.service import (
    ensure_project_manage,
    ensure_project_read,
    project_error,
)


async def load_readiness(
    session: AsyncSession, auth: AuthContext, project_id: UUID
) -> ExteriorReadinessResponse:
    ensure_project_read(auth)
    source = await build_source_context(session, auth, project_id)
    return ExteriorReadinessResponse(
        ready=not any(issue["severity"] == "blocking" for issue in source.issues),
        project_id=project_id,
        source_design_version_id=source.design_version.id if source.design_version else None,
        source_scene_version_id=source.scene_version.id if source.scene_version else None,
        source_editor_checkpoint_id=(
            source.scene_version.source_editor_checkpoint_id if source.scene_version else None
        ),
        source_brief_id=source.brief.id if source.brief else None,
        material_library=[item for item in MATERIAL_CATEGORIES],
        supported_styles=[item.value for item in ExteriorDesignStyle],
        supported_views=[item.value for item in ExteriorDesignViewType],
        issues=[ExteriorReadinessIssue.model_validate(issue) for issue in source.issues],
    )


async def create_generation(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    request: ExteriorGenerationRequest,
    idempotency_key: str,
) -> ExteriorGenerationAccepted:
    ensure_project_manage(auth)
    existing = await _idempotent_run(session, auth, idempotency_key)
    if existing is not None:
        return _accepted(existing)
    source = await build_source_context(session, auth, project_id)
    if any(issue["severity"] == "blocking" for issue in source.issues):
        raise project_error(
            status.HTTP_428_PRECONDITION_REQUIRED,
            "EXTERIOR_NOT_READY",
            "Exterior design generation prerequisites are missing.",
            {"issues": source.issues},
        )
    context_payload, source_versions, context_hash = context_snapshot_payload(
        source,
        style=request.style,
        view_type=request.view_type,
        material_preferences=request.material_preferences,
        user_instructions=request.user_instructions,
        negative_constraints=request.negative_constraints,
    )
    settings = get_settings()
    provider_name = settings.ai_provider
    model = (
        settings.exterior_design_image_model
        or settings.gemini_image_model
        or "compose-image-model-unconfigured"
    )
    cache_key = _cache_key(
        {
            "contextHash": context_hash,
            "provider": provider_name,
            "model": model,
            "style": request.style,
            "viewType": request.view_type,
            "materials": request.material_preferences,
            "optionCount": request.option_count,
            "seed": request.seed,
            "promptVersion": EXTERIOR_PROMPT_VERSION,
            "engineVersion": EXTERIOR_DESIGN_ENGINE_VERSION,
        }
    )
    cached = await _cached_successful_run(session, auth, cache_key)
    if cached is not None:
        return _accepted(cached)
    prompt = build_exterior_prompt(context_payload)
    snapshot = await _load_context_snapshot(session, auth, context_hash)
    if snapshot is None:
        snapshot = ExteriorDesignContextSnapshot(
            id=uuid4(),
            organization_id=auth.membership.organization_id,
            project_id=project_id,
            source_design_version_id=source.design_version.id,
            source_scene_version_id=source.scene_version.id,
            source_editor_checkpoint_id=source.scene_version.source_editor_checkpoint_id,
            source_brief_id=source.brief.id if source.brief else None,
            context_hash=context_hash,
            prompt_version=EXTERIOR_PROMPT_VERSION,
            engine_version=EXTERIOR_DESIGN_ENGINE_VERSION,
            snapshot=context_payload,
            source_versions=source_versions,
            created_by=auth.user.id,
        )
        session.add(snapshot)
        await session.flush()
    run = ExteriorDesignRun(
        id=uuid4(),
        organization_id=auth.membership.organization_id,
        project_id=project_id,
        context_snapshot_id=snapshot.id,
        source_design_version_id=source.design_version.id,
        source_scene_version_id=source.scene_version.id,
        source_editor_checkpoint_id=source.scene_version.source_editor_checkpoint_id,
        status=ExteriorDesignRunStatus.QUEUED,
        provider=provider_name,
        model=model,
        prompt_version=EXTERIOR_PROMPT_VERSION,
        engine_version=EXTERIOR_DESIGN_ENGINE_VERSION,
        requested_option_count=request.option_count,
        completed_option_count=0,
        style=request.style,
        view_type=request.view_type,
        material_preferences=request.material_preferences,
        user_instructions=request.user_instructions,
        negative_constraints=request.negative_constraints,
        seed=request.seed,
        idempotency_key=idempotency_key,
        context_hash=context_hash,
        cache_key=cache_key,
        cache_hit=False,
        sanitized_prompt=prompt,
        created_by=auth.user.id,
    )
    session.add(run)
    await session.flush()
    await append_event(session, run.id, "exterior.run.queued", {"progress": 0})
    await _execute_generation(session, auth, run, prompt, source_versions)
    await session.commit()
    return _accepted(run)


async def list_runs(
    session: AsyncSession, auth: AuthContext, project_id: UUID
) -> list[ExteriorRun]:
    ensure_project_read(auth)
    rows = (
        (
            await session.execute(
                select(ExteriorDesignRun)
                .where(
                    ExteriorDesignRun.project_id == project_id,
                    ExteriorDesignRun.organization_id == auth.membership.organization_id,
                    ExteriorDesignRun.deleted_at.is_(None),
                )
                .order_by(ExteriorDesignRun.created_at.desc(), ExteriorDesignRun.id.desc())
                .limit(50)
            )
        )
        .scalars()
        .all()
    )
    return [_run_response(row) for row in rows]


async def load_run(
    session: AsyncSession, auth: AuthContext, project_id: UUID, run_id: UUID
) -> ExteriorRunDetail:
    run = await _load_run(session, auth, project_id, run_id)
    options = await _options_for_run(session, auth, run.id)
    return ExteriorRunDetail(**_run_response(run).model_dump(), options=options)


async def list_events(
    session: AsyncSession, auth: AuthContext, project_id: UUID, run_id: UUID
) -> list[ExteriorRunEvent]:
    await _load_run(session, auth, project_id, run_id)
    rows = (
        (
            await session.execute(
                select(ExteriorDesignEvent)
                .where(ExteriorDesignEvent.run_id == run_id)
                .order_by(ExteriorDesignEvent.sequence)
            )
        )
        .scalars()
        .all()
    )
    return [ExteriorRunEvent.model_validate(row) for row in rows]


async def cancel_run(
    session: AsyncSession, auth: AuthContext, project_id: UUID, run_id: UUID
) -> ExteriorRun:
    ensure_project_manage(auth)
    run = await _load_run(session, auth, project_id, run_id)
    if run.status not in {
        ExteriorDesignRunStatus.SUCCEEDED,
        ExteriorDesignRunStatus.FAILED,
        ExteriorDesignRunStatus.CANCELLED,
    }:
        run.status = ExteriorDesignRunStatus.CANCELLED
        run.cancelled_at = datetime.now(UTC)
        await append_event(session, run.id, "exterior.run.cancelled", {"progress": 100})
        await session.commit()
    return _run_response(run)


async def list_options(
    session: AsyncSession, auth: AuthContext, project_id: UUID
) -> list[ExteriorOption]:
    ensure_project_read(auth)
    rows = (
        (
            await session.execute(
                select(ExteriorDesignOption)
                .where(
                    ExteriorDesignOption.project_id == project_id,
                    ExteriorDesignOption.organization_id == auth.membership.organization_id,
                    ExteriorDesignOption.deleted_at.is_(None),
                )
                .order_by(ExteriorDesignOption.created_at.desc(), ExteriorDesignOption.id.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    return [await _option_response(session, row) for row in rows]


async def load_option(
    session: AsyncSession, auth: AuthContext, project_id: UUID, option_id: UUID
) -> ExteriorOption:
    return await _option_response(session, await _load_option(session, auth, project_id, option_id))


async def approve_option(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    option_id: UUID,
) -> ExteriorOption:
    ensure_project_manage(auth)
    option = await _load_option(session, auth, project_id, option_id)
    option.status = ExteriorDesignOptionStatus.APPROVED
    option.approval_status = ExteriorDesignApprovalStatus.APPROVED
    option.approved_by = auth.user.id
    option.approved_at = datetime.now(UTC)
    await append_event(
        session, option.run_id, "exterior.option.approved", {"optionId": str(option.id)}
    )
    await session.commit()
    return await _option_response(session, option)


async def reject_option(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    option_id: UUID,
    request: ExteriorOptionActionRequest,
) -> ExteriorOption:
    ensure_project_manage(auth)
    option = await _load_option(session, auth, project_id, option_id)
    option.status = ExteriorDesignOptionStatus.REJECTED
    option.approval_status = ExteriorDesignApprovalStatus.REJECTED
    option.rejected_by = auth.user.id
    option.rejected_at = datetime.now(UTC)
    option.rejection_reason = request.reason
    await append_event(
        session, option.run_id, "exterior.option.rejected", {"optionId": str(option.id)}
    )
    await session.commit()
    return await _option_response(session, option)


async def delete_option(
    session: AsyncSession, auth: AuthContext, project_id: UUID, option_id: UUID
) -> None:
    ensure_project_manage(auth)
    option = await _load_option(session, auth, project_id, option_id)
    option.status = ExteriorDesignOptionStatus.HIDDEN
    option.deleted_at = datetime.now(UTC)
    await session.execute(
        update(ExteriorDesignAsset)
        .where(ExteriorDesignAsset.option_id == option.id)
        .values(deleted_at=datetime.now(UTC))
    )
    await append_event(
        session, option.run_id, "exterior.option.hidden", {"optionId": str(option.id)}
    )
    await session.commit()


async def load_asset_content(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    asset_id: UUID,
) -> tuple[bytes, str]:
    ensure_project_read(auth)
    asset = (
        await session.execute(
            select(ExteriorDesignAsset).where(
                ExteriorDesignAsset.id == asset_id,
                ExteriorDesignAsset.project_id == project_id,
                ExteriorDesignAsset.organization_id == auth.membership.organization_id,
                ExteriorDesignAsset.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if asset is None:
        raise project_error(404, "EXTERIOR_ASSET_NOT_FOUND", "Exterior design asset not found.")
    try:
        content = await create_asset_storage().read(asset.storage_key)
    except AssetStorageError as error:
        raise project_error(404, error.code, str(error)) from error
    return content, asset.mime_type


async def append_event(
    session: AsyncSession, run_id: UUID, event_type: str, payload: dict[str, Any]
) -> None:
    current = (
        await session.execute(
            select(ExteriorDesignEvent.sequence)
            .where(ExteriorDesignEvent.run_id == run_id)
            .order_by(ExteriorDesignEvent.sequence.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    session.add(
        ExteriorDesignEvent(
            id=uuid4(),
            run_id=run_id,
            sequence=int(current or 0) + 1,
            event_type=event_type,
            payload=payload,
        )
    )
    await session.flush()


async def _execute_generation(
    session: AsyncSession,
    auth: AuthContext,
    run: ExteriorDesignRun,
    prompt: dict[str, str],
    source_versions: dict[str, Any],
) -> None:
    settings = get_settings()
    run.status = ExteriorDesignRunStatus.RUNNING
    run.started_at = datetime.now(UTC)
    await append_event(session, run.id, "exterior.run.started", {"progress": 10})
    try:
        await ensure_provider_available(session, settings, run.provider, run.model)
        provider = create_provider(settings, run.provider)
        storage = create_asset_storage()
        for option_number in range(1, run.requested_option_count + 1):
            await append_event(
                session,
                run.id,
                "exterior.option.generating",
                {"progress": 20 + option_number * 10, "optionNumber": option_number},
            )
            result = await provider.generate_image(
                ImageProviderRequest(
                    model=run.model,
                    prompt=prompt["prompt"],
                    negative_prompt=prompt["negativePrompt"],
                    width=1024,
                    height=1024,
                    seed=(run.seed or 0) + option_number if run.seed is not None else None,
                    metadata={"runId": str(run.id), "optionNumber": option_number},
                )
            )
            option = ExteriorDesignOption(
                id=uuid4(),
                organization_id=run.organization_id,
                project_id=run.project_id,
                run_id=run.id,
                context_snapshot_id=run.context_snapshot_id,
                source_design_version_id=run.source_design_version_id,
                source_scene_version_id=run.source_scene_version_id,
                source_editor_checkpoint_id=run.source_editor_checkpoint_id,
                option_number=option_number,
                style=run.style,
                view_type=run.view_type,
                title=f"{run.style.replace('_', ' ').title()} front elevation {option_number}",
                explanation=(
                    "Generated from the accepted floor-plan design, compiled 3D scene, requested "
                    f"{run.style} style, and selected material preferences."
                ),
                status=ExteriorDesignOptionStatus.GENERATED,
                approval_status=ExteriorDesignApprovalStatus.PENDING,
                is_conceptual=True,
                disclaimer=CONCEPTUAL_DISCLAIMER,
                safety_metadata=result.safety_metadata,
                source_versions=source_versions,
            )
            session.add(option)
            await session.flush()
            stored = await storage.store_image(
                organization_id=run.organization_id,
                project_id=run.project_id,
                option_id=option.id,
                content=result.content,
                mime_type=result.mime_type,
            )
            asset = ExteriorDesignAsset(
                id=uuid4(),
                organization_id=run.organization_id,
                project_id=run.project_id,
                option_id=option.id,
                storage_provider=stored.storage_provider,
                storage_key=stored.storage_key,
                mime_type=stored.mime_type,
                width=result.width,
                height=result.height,
                byte_size=stored.byte_size,
                integrity_hash=stored.integrity_hash,
                provider_asset_metadata=result.provider_asset_metadata,
                delivery_reference=stored.delivery_reference,
            )
            session.add(asset)
            await session.flush()
            exists = await storage.exists(stored.storage_key)
            validation_status, summary, issues = validate_generated_option(
                asset_exists=exists,
                mime_type=stored.mime_type,
                byte_size=stored.byte_size,
                max_bytes=settings.asset_max_image_bytes,
                source_versions=source_versions,
                disclaimer=CONCEPTUAL_DISCLAIMER,
                safety_metadata=result.safety_metadata,
            )
            option.status = (
                ExteriorDesignOptionStatus.VALID
                if validation_status == "valid"
                else ExteriorDesignOptionStatus.INVALID
            )
            session.add(
                ExteriorDesignValidationResult(
                    id=uuid4(),
                    organization_id=run.organization_id,
                    project_id=run.project_id,
                    option_id=option.id,
                    status=validation_status,
                    validation_engine_version=EXTERIOR_VALIDATION_ENGINE_VERSION,
                    summary=summary,
                    issues=issues,
                )
            )
            run.input_tokens += result.usage.input_tokens
            run.output_tokens += result.usage.output_tokens
            run.completed_option_count += 1 if validation_status == "valid" else 0
        run.status = (
            ExteriorDesignRunStatus.SUCCEEDED
            if run.completed_option_count == run.requested_option_count
            else ExteriorDesignRunStatus.PARTIALLY_SUCCEEDED
        )
        run.completed_at = datetime.now(UTC)
        await record_provider_success(session, settings, run.provider, run.model)
        await record_usage(
            session,
            organization_id=run.organization_id,
            user_id=auth.user.id,
            provider=run.provider,
            model=run.model,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            cost_microusd=run.cost_microusd,
            cache_hit=False,
        )
        await append_event(session, run.id, "exterior.run.completed", {"progress": 100})
    except AIProviderError as error:
        await record_provider_failure(session, settings, run.provider, run.model, error.code)
        run.status = (
            ExteriorDesignRunStatus.RATE_LIMITED
            if error.code == "AI_PROVIDER_RATE_LIMITED"
            else ExteriorDesignRunStatus.TIMED_OUT
            if error.code == "AI_RUN_TIMEOUT"
            else ExteriorDesignRunStatus.FAILED
        )
        run.failure_code = error.code
        run.safe_failure_message = str(error)
        run.completed_at = datetime.now(UTC)
        await append_event(
            session, run.id, "exterior.run.failed", {"progress": 100, "code": error.code}
        )
    except AssetStorageError as error:
        run.status = ExteriorDesignRunStatus.FAILED
        run.failure_code = error.code
        run.safe_failure_message = str(error)
        run.completed_at = datetime.now(UTC)
        await append_event(
            session, run.id, "exterior.run.failed", {"progress": 100, "code": error.code}
        )


async def _idempotent_run(
    session: AsyncSession, auth: AuthContext, idempotency_key: str
) -> ExteriorDesignRun | None:
    return (
        await session.execute(
            select(ExteriorDesignRun).where(
                ExteriorDesignRun.organization_id == auth.membership.organization_id,
                ExteriorDesignRun.created_by == auth.user.id,
                ExteriorDesignRun.idempotency_key == idempotency_key,
            )
        )
    ).scalar_one_or_none()


async def _cached_successful_run(
    session: AsyncSession, auth: AuthContext, cache_key: str
) -> ExteriorDesignRun | None:
    return (
        await session.execute(
            select(ExteriorDesignRun)
            .where(
                ExteriorDesignRun.organization_id == auth.membership.organization_id,
                ExteriorDesignRun.cache_key == cache_key,
                ExteriorDesignRun.status == ExteriorDesignRunStatus.SUCCEEDED,
                ExteriorDesignRun.deleted_at.is_(None),
            )
            .order_by(ExteriorDesignRun.completed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _load_context_snapshot(
    session: AsyncSession, auth: AuthContext, context_hash: str
) -> ExteriorDesignContextSnapshot | None:
    return (
        await session.execute(
            select(ExteriorDesignContextSnapshot).where(
                ExteriorDesignContextSnapshot.organization_id == auth.membership.organization_id,
                ExteriorDesignContextSnapshot.context_hash == context_hash,
            )
        )
    ).scalar_one_or_none()


async def _load_run(
    session: AsyncSession, auth: AuthContext, project_id: UUID, run_id: UUID
) -> ExteriorDesignRun:
    ensure_project_read(auth)
    run = (
        await session.execute(
            select(ExteriorDesignRun).where(
                ExteriorDesignRun.id == run_id,
                ExteriorDesignRun.project_id == project_id,
                ExteriorDesignRun.organization_id == auth.membership.organization_id,
                ExteriorDesignRun.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if run is None:
        raise project_error(404, "EXTERIOR_RUN_NOT_FOUND", "Exterior design run not found.")
    return run


async def _load_option(
    session: AsyncSession, auth: AuthContext, project_id: UUID, option_id: UUID
) -> ExteriorDesignOption:
    ensure_project_read(auth)
    option = (
        await session.execute(
            select(ExteriorDesignOption).where(
                ExteriorDesignOption.id == option_id,
                ExteriorDesignOption.project_id == project_id,
                ExteriorDesignOption.organization_id == auth.membership.organization_id,
                ExteriorDesignOption.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if option is None:
        raise project_error(404, "EXTERIOR_OPTION_NOT_FOUND", "Exterior design option not found.")
    return option


async def _options_for_run(
    session: AsyncSession, auth: AuthContext, run_id: UUID
) -> list[ExteriorOption]:
    rows = (
        (
            await session.execute(
                select(ExteriorDesignOption)
                .where(
                    ExteriorDesignOption.run_id == run_id,
                    ExteriorDesignOption.organization_id == auth.membership.organization_id,
                    ExteriorDesignOption.deleted_at.is_(None),
                )
                .order_by(ExteriorDesignOption.option_number)
            )
        )
        .scalars()
        .all()
    )
    return [await _option_response(session, row) for row in rows]


async def _option_response(session: AsyncSession, option: ExteriorDesignOption) -> ExteriorOption:
    asset = (
        await session.execute(
            select(ExteriorDesignAsset)
            .where(
                ExteriorDesignAsset.option_id == option.id,
                ExteriorDesignAsset.deleted_at.is_(None),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    validation = (
        await session.execute(
            select(ExteriorDesignValidationResult)
            .where(ExteriorDesignValidationResult.option_id == option.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    return ExteriorOption(
        id=option.id,
        run_id=option.run_id,
        project_id=option.project_id,
        option_number=option.option_number,
        style=option.style,
        view_type=option.view_type,
        title=option.title,
        explanation=option.explanation,
        status=option.status,
        approval_status=option.approval_status,
        is_conceptual=option.is_conceptual,
        disclaimer=option.disclaimer,
        source_design_version_id=option.source_design_version_id,
        source_scene_version_id=option.source_scene_version_id,
        source_editor_checkpoint_id=option.source_editor_checkpoint_id,
        source_versions=option.source_versions,
        safety_metadata=option.safety_metadata,
        asset=ExteriorAsset.model_validate(asset) if asset else None,
        validation=ExteriorValidationResult.model_validate(validation) if validation else None,
        created_at=option.created_at,
        updated_at=option.updated_at,
        approved_at=option.approved_at,
        rejected_at=option.rejected_at,
        deleted_at=option.deleted_at,
    )


def _run_response(run: ExteriorDesignRun) -> ExteriorRun:
    return ExteriorRun(
        id=run.id,
        project_id=run.project_id,
        status=run.status,
        provider=run.provider,
        model=run.model,
        prompt_version=run.prompt_version,
        engine_version=run.engine_version,
        requested_option_count=run.requested_option_count,
        completed_option_count=run.completed_option_count,
        style=run.style,
        view_type=run.view_type,
        material_preferences=run.material_preferences,
        seed=run.seed,
        cache_hit=run.cache_hit,
        cache_source_run_id=run.cache_source_run_id,
        failure_code=run.failure_code,
        safe_failure_message=run.safe_failure_message,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        cost_microusd=run.cost_microusd,
        source_design_version_id=run.source_design_version_id,
        source_scene_version_id=run.source_scene_version_id,
        source_editor_checkpoint_id=run.source_editor_checkpoint_id,
        context_hash=run.context_hash,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        cancelled_at=run.cancelled_at,
    )


def _accepted(run: ExteriorDesignRun) -> ExteriorGenerationAccepted:
    return ExteriorGenerationAccepted(
        run=_run_response(run),
        status_url=f"/projects/{run.project_id}/exterior-design/generations/{run.id}",
        events_url=f"/projects/{run.project_id}/exterior-design/generations/{run.id}/events",
    )


def _cache_key(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
