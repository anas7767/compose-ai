from __future__ import annotations

import base64
import hashlib
import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.auth import AuthContext
from compose_ai_api.domains.plot_intelligence.analysis import (
    AnalysisResult,
    BoundaryState,
    PlotState,
    RoadState,
    analyze_plot,
)
from compose_ai_api.domains.plot_intelligence.geometry import (
    GEOMETRY_ENGINE_VERSION,
    PlotGeometryError,
    geojson_from_canonical,
    normalize_geojson,
    tombstone_checksum,
)
from compose_ai_api.domains.plot_intelligence.models import (
    BoundarySource,
    CoordinateSpace,
    PlotAnalysisSnapshot,
    PlotBoundaryRestoreAction,
    PlotBoundaryVersion,
    PlotRoadSide,
)
from compose_ai_api.domains.plot_intelligence.repository import (
    load_active_roads,
    load_active_undo,
    load_analysis,
    load_boundary,
    load_plot_project,
    load_project_boundary,
    load_restore_action_for_update,
    next_boundary_version,
    plot_error,
)
from compose_ai_api.domains.plot_intelligence.schemas import (
    PlotAnalysisResponse,
    PlotBoundaryInput,
    PlotBoundaryVersionResponse,
    PlotIntelligenceResponse,
    PlotProfileResponse,
    PlotProfileUpdateRequest,
    PlotRestoreResponse,
    PlotRoadSideInput,
    PlotRoadSideResponse,
    PlotUndoActionResponse,
    PlotValidationIssueResponse,
    PlotValidationRequest,
)
from compose_ai_api.domains.plot_intelligence.units import (
    area_from_square_meters,
    area_to_square_meters,
    length_from_meters,
    length_to_meters,
)
from compose_ai_api.domains.projects.models import (
    AuditLog,
    IdempotencyRecord,
    Project,
    ProjectSite,
    UnitSystem,
)

RESTORE_UNDO_WINDOW = timedelta(minutes=5)


async def get_plot_intelligence(
    session: AsyncSession, context: AuthContext, project_id: UUID
) -> PlotIntelligenceResponse:
    project = await load_plot_project(session, context, project_id)
    return await _build_plot_response(session, context, project)


async def validate_plot_profile(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    request: PlotValidationRequest,
) -> PlotAnalysisResponse:
    project = await load_plot_project(session, context, project_id)
    roads = await load_active_roads(session, context, project_id)
    boundary = await load_boundary(
        session, context, project.site.current_boundary_version_id if project.site else None
    )
    state, effective_unit = _draft_state(project, request, roads, boundary)
    result = analyze_plot(state)
    return _analysis_response(
        result,
        snapshot=None,
        profile_revision=state.profile_revision,
        boundary_version_id=state.boundary.id if state.boundary else None,
        unit_system=effective_unit,
    )


async def update_plot_profile(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    request: PlotProfileUpdateRequest,
    expected_version: int,
    idempotency_key: str,
    request_id: str,
) -> PlotIntelligenceResponse:
    return await _save_plot_profile(
        session,
        context,
        project_id,
        request,
        expected_version,
        idempotency_key,
        request_id,
        "plot.profile.update",
    )


async def create_boundary_version(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    request: PlotBoundaryInput,
    expected_version: int,
    idempotency_key: str,
    request_id: str,
) -> PlotIntelligenceResponse:
    return await _save_plot_profile(
        session,
        context,
        project_id,
        PlotProfileUpdateRequest(boundary=request),
        expected_version,
        idempotency_key,
        request_id,
        "plot.boundary.create",
    )


async def restore_boundary_version(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    boundary_id: UUID,
    expected_version: int,
    idempotency_key: str,
    request_id: str,
) -> PlotRestoreResponse:
    project = await load_plot_project(session, context, project_id, for_update=True, manage=True)
    request_hash = _request_hash({"boundaryId": str(boundary_id)})
    replay = await _load_idempotency(
        session, context, "plot.boundary.restore", idempotency_key, request_hash
    )
    if replay is not None:
        return PlotRestoreResponse.model_validate(replay.response_body)
    _ensure_version(project, expected_version)
    site = _ensure_site(project)
    target = await load_project_boundary(session, context, project_id, boundary_id)
    current = await load_boundary(session, context, site.current_boundary_version_id)
    restored = await _clone_boundary(
        session,
        context,
        project,
        target,
        current,
        BoundarySource.RESTORE,
    )
    _activate_boundary(site, restored)
    site.profile_revision += 1
    analysis = await _record_current_analysis(session, context, project, restored)
    now = datetime.now(UTC)
    undo = PlotBoundaryRestoreAction(
        id=uuid4(),
        organization_id=context.membership.organization_id,
        project_id=project.id,
        restored_boundary_version_id=restored.id,
        previous_active_boundary_version_id=current.id if current else None,
        created_by=context.user.id,
        created_at=now,
        expires_at=now + RESTORE_UNDO_WINDOW,
    )
    session.add(undo)
    _touch_project(project, context)
    await _write_audit(
        session,
        context,
        project,
        "plot.boundary.restored",
        request_id,
        {
            "targetBoundaryVersionId": str(target.id),
            "newBoundaryVersionId": str(restored.id),
            "previousBoundaryVersionId": str(current.id) if current else None,
            "undoActionId": str(undo.id),
            "undoExpiresAt": undo.expires_at.isoformat(),
        },
    )
    await session.flush()
    plot = await _build_plot_response(
        session,
        context,
        project,
        roads=await load_active_roads(session, context, project.id),
        boundary=restored,
        analysis=analysis,
        active_undo=undo,
    )
    response = PlotRestoreResponse(plot=plot, undo=_undo_response(undo))
    await _store_idempotency(
        session,
        context,
        "plot.boundary.restore",
        idempotency_key,
        request_hash,
        status.HTTP_200_OK,
        response.model_dump(mode="json", by_alias=True),
    )
    await session.commit()
    return response


async def undo_boundary_restore(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    action_id: UUID,
    expected_version: int,
    idempotency_key: str,
    request_id: str,
) -> PlotIntelligenceResponse:
    project = await load_plot_project(session, context, project_id, for_update=True, manage=True)
    request_hash = _request_hash({"restoreActionId": str(action_id)})
    replay = await _load_idempotency(
        session, context, "plot.boundary.undo", idempotency_key, request_hash
    )
    if replay is not None:
        return PlotIntelligenceResponse.model_validate(replay.response_body)
    _ensure_version(project, expected_version)
    site = _ensure_site(project)
    action = await load_restore_action_for_update(session, context, project_id, action_id)
    now = datetime.now(UTC)
    if action.used_at is not None:
        raise plot_error(
            status.HTTP_409_CONFLICT,
            "PLOT_UNDO_ALREADY_USED",
            "This boundary restore has already been undone.",
        )
    if action.expires_at <= now:
        raise plot_error(
            status.HTTP_410_GONE,
            "PLOT_UNDO_EXPIRED",
            "The boundary restore undo window has expired.",
            {"expiredAt": action.expires_at.isoformat()},
        )
    if site.current_boundary_version_id != action.restored_boundary_version_id:
        raise plot_error(
            status.HTTP_409_CONFLICT,
            "PLOT_UNDO_NOT_CURRENT",
            "The restored boundary is no longer the active boundary.",
        )
    current = await load_boundary(session, context, action.restored_boundary_version_id)
    previous = await load_boundary(session, context, action.previous_active_boundary_version_id)
    undone = await _clone_boundary(
        session,
        context,
        project,
        previous,
        current,
        BoundarySource.UNDO,
    )
    _activate_boundary(site, undone)
    site.profile_revision += 1
    analysis = await _record_current_analysis(session, context, project, undone)
    action.used_at = now
    action.undone_by_boundary_version_id = undone.id
    _touch_project(project, context)
    await _write_audit(
        session,
        context,
        project,
        "plot.boundary.restore_undone",
        request_id,
        {
            "restoreActionId": str(action.id),
            "restoredBoundaryVersionId": str(action.restored_boundary_version_id),
            "newBoundaryVersionId": str(undone.id),
            "previousBoundaryVersionId": str(previous.id) if previous else None,
        },
    )
    await session.flush()
    response = await _build_plot_response(
        session,
        context,
        project,
        roads=await load_active_roads(session, context, project.id),
        boundary=undone,
        analysis=analysis,
        active_undo=None,
    )
    await _store_idempotency(
        session,
        context,
        "plot.boundary.undo",
        idempotency_key,
        request_hash,
        status.HTTP_200_OK,
        response.model_dump(mode="json", by_alias=True),
    )
    await session.commit()
    return response


async def clear_boundary(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    expected_version: int,
    idempotency_key: str,
    request_id: str,
) -> PlotIntelligenceResponse:
    project = await load_plot_project(session, context, project_id, for_update=True, manage=True)
    request_hash = _request_hash({"projectId": str(project_id), "clear": True})
    replay = await _load_idempotency(
        session, context, "plot.boundary.clear", idempotency_key, request_hash
    )
    if replay is not None:
        return PlotIntelligenceResponse.model_validate(replay.response_body)
    _ensure_version(project, expected_version)
    site = _ensure_site(project)
    current = await load_boundary(session, context, site.current_boundary_version_id)
    if current is not None and current.is_tombstone:
        response = await _build_plot_response(session, context, project, boundary=current)
    else:
        cleared = await _clone_boundary(
            session,
            context,
            project,
            None,
            current,
            BoundarySource.CLEAR,
        )
        _activate_boundary(site, cleared)
        site.profile_revision += 1
        analysis = await _record_current_analysis(session, context, project, cleared)
        _touch_project(project, context)
        await _write_audit(
            session,
            context,
            project,
            "plot.boundary.cleared",
            request_id,
            {
                "previousBoundaryVersionId": str(current.id) if current else None,
                "tombstoneBoundaryVersionId": str(cleared.id),
            },
        )
        await session.flush()
        response = await _build_plot_response(
            session,
            context,
            project,
            roads=await load_active_roads(session, context, project.id),
            boundary=cleared,
            analysis=analysis,
            active_undo=None,
        )
    await _store_idempotency(
        session,
        context,
        "plot.boundary.clear",
        idempotency_key,
        request_hash,
        status.HTTP_200_OK,
        response.model_dump(mode="json", by_alias=True),
    )
    await session.commit()
    return response


async def recalculate_plot_analysis(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    expected_version: int,
    idempotency_key: str,
    request_id: str,
) -> PlotIntelligenceResponse:
    project = await load_plot_project(session, context, project_id, for_update=True, manage=True)
    request_hash = _request_hash({"projectId": str(project_id), "recalculate": True})
    replay = await _load_idempotency(
        session, context, "plot.analysis.recalculate", idempotency_key, request_hash
    )
    if replay is not None:
        return PlotIntelligenceResponse.model_validate(replay.response_body)
    _ensure_version(project, expected_version)
    site = _ensure_site(project)
    boundary = await load_boundary(session, context, site.current_boundary_version_id)
    analysis = await _record_current_analysis(session, context, project, boundary)
    _ensure_analysis_valid(analysis.validation_issues)
    _touch_project(project, context)
    await _write_audit(
        session,
        context,
        project,
        "plot.analysis.recalculated",
        request_id,
        {
            "analysisSnapshotId": str(analysis.id),
            "analysisEngineVersion": analysis.analysis_engine_version,
            "geometryEngineVersion": analysis.geometry_engine_version,
        },
    )
    await session.flush()
    response = await _build_plot_response(
        session, context, project, boundary=boundary, analysis=analysis
    )
    await _store_idempotency(
        session,
        context,
        "plot.analysis.recalculate",
        idempotency_key,
        request_hash,
        status.HTTP_200_OK,
        response.model_dump(mode="json", by_alias=True),
    )
    await session.commit()
    return response


async def list_boundary_history(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    limit: int,
    cursor: str | None,
) -> tuple[list[PlotBoundaryVersionResponse], str | None, bool]:
    project = await load_plot_project(session, context, project_id)
    statement = select(PlotBoundaryVersion).where(
        PlotBoundaryVersion.project_id == project_id,
        PlotBoundaryVersion.organization_id == context.membership.organization_id,
    )
    if cursor:
        cursor_time, cursor_id = _decode_cursor(cursor)
        statement = statement.where(
            (PlotBoundaryVersion.created_at < cursor_time)
            | (
                (PlotBoundaryVersion.created_at == cursor_time)
                & (PlotBoundaryVersion.id < cursor_id)
            )
        )
    versions = list(
        (
            await session.execute(
                statement.order_by(
                    PlotBoundaryVersion.created_at.desc(), PlotBoundaryVersion.id.desc()
                ).limit(limit + 1)
            )
        )
        .scalars()
        .all()
    )
    has_more = len(versions) > limit
    visible = versions[:limit]
    next_cursor = _encode_cursor(visible[-1]) if has_more and visible else None
    return (
        [_boundary_response(version, project.unit_system) for version in visible],
        next_cursor,
        has_more,
    )


async def get_boundary_history_item(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    boundary_id: UUID,
) -> PlotBoundaryVersionResponse:
    project = await load_plot_project(session, context, project_id)
    boundary = await load_project_boundary(session, context, project_id, boundary_id)
    return _boundary_response(boundary, project.unit_system)


async def _save_plot_profile(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    request: PlotProfileUpdateRequest,
    expected_version: int,
    idempotency_key: str,
    request_id: str,
    scope: str,
) -> PlotIntelligenceResponse:
    project = await load_plot_project(session, context, project_id, for_update=True, manage=True)
    request_hash = _request_hash(request.model_dump(mode="json", by_alias=True))
    replay = await _load_idempotency(session, context, scope, idempotency_key, request_hash)
    if replay is not None:
        return PlotIntelligenceResponse.model_validate(replay.response_body)
    _ensure_version(project, expected_version)
    site = _ensure_site(project)
    current_boundary = await load_boundary(session, context, site.current_boundary_version_id)
    roads = await load_active_roads(session, context, project_id)
    effective_unit = _apply_profile_fields(project, site, request)
    if "road_sides" in request.model_fields_set:
        roads = await _apply_road_sides(
            session, context, project, request.road_sides or [], effective_unit, roads
        )
    boundary = current_boundary
    if request.boundary is not None:
        boundary = await _create_user_boundary(
            session, context, project, request.boundary, current_boundary, effective_unit
        )
        _activate_boundary(site, boundary)
        if site.area_source != "declared":
            site.plot_area = boundary.area_m2
            site.area_source = "boundary"
    _sync_compatibility_road_fields(site, roads)
    site.profile_revision += 1
    await session.flush()
    analysis = await _record_current_analysis(session, context, project, boundary, roads=roads)
    _ensure_analysis_valid(analysis.validation_issues)
    _touch_project(project, context)
    await _write_audit(
        session,
        context,
        project,
        "plot.profile.updated" if request.boundary is None else "plot.boundary.created",
        request_id,
        {
            "changedFields": sorted(request.model_fields_set),
            "profileRevision": site.profile_revision,
            "boundaryVersionId": str(boundary.id) if boundary else None,
            "analysisSnapshotId": str(analysis.id),
            "geometryEngineVersion": analysis.geometry_engine_version,
        },
    )
    await session.flush()
    response = await _build_plot_response(
        session,
        context,
        project,
        roads=roads,
        boundary=boundary,
        analysis=analysis,
    )
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


def _apply_profile_fields(
    project: Project, site: ProjectSite, request: PlotProfileUpdateRequest
) -> UnitSystem:
    if "unit_system" in request.model_fields_set and request.unit_system is not None:
        project.unit_system = request.unit_system
    unit_system = UnitSystem(str(project.unit_system))
    fields = request.model_fields_set
    if "plot_length" in fields:
        site.plot_length = length_to_meters(request.plot_length, unit_system)
    if "plot_width" in fields:
        site.plot_width = length_to_meters(request.plot_width, unit_system)
    if "plot_area" in fields:
        site.plot_area = area_to_square_meters(request.plot_area, unit_system)
        site.area_source = "declared" if request.plot_area is not None else "unknown"
    if "plot_shape" in fields:
        site.plot_shape = request.plot_shape
    if "open_sides" in fields and request.open_sides is not None:
        site.open_sides = request.open_sides
    if "corner_plot" in fields and request.corner_plot is not None:
        site.corner_plot = request.corner_plot
    if "orientation_degrees" in fields:
        site.orientation_degrees = request.orientation_degrees
    if "north_rotation_degrees" in fields:
        site.north_rotation_degrees = request.north_rotation_degrees
    if "north_reference" in fields:
        site.north_reference = request.north_reference
    if (
        site.plot_shape in {"rectangle", "square"}
        and site.plot_length is not None
        and site.plot_width is not None
        and site.area_source != "declared"
    ):
        site.plot_area = site.plot_length * site.plot_width
        site.area_source = "dimensions"
    return unit_system


async def _apply_road_sides(
    session: AsyncSession,
    context: AuthContext,
    project: Project,
    inputs: list[PlotRoadSideInput],
    unit_system: UnitSystem,
    existing: list[PlotRoadSide],
) -> list[PlotRoadSide]:
    existing_by_id = {road.id: road for road in existing}
    supplied_ids = {road.id for road in inputs if road.id is not None}
    now = datetime.now(UTC)
    for road in existing:
        road.is_primary = False
        if road.id not in supplied_ids:
            road.deleted_at = now
    await session.flush()

    result: list[PlotRoadSide] = []
    for road_input in inputs:
        if road_input.id is not None:
            road = existing_by_id.get(road_input.id)
            if road is None:
                raise plot_error(
                    status.HTTP_422_UNPROCESSABLE_CONTENT,
                    "PLOT_ROAD_SIDE_INVALID",
                    "A road side does not belong to this project.",
                    {"roadSideId": str(road_input.id)},
                )
        else:
            road = PlotRoadSide(
                id=uuid4(),
                organization_id=context.membership.organization_id,
                project_id=project.id,
            )
            session.add(road)
        road.deleted_at = None
        road.boundary_edge_index = road_input.boundary_edge_index
        road.label = road_input.label
        road.direction = str(road_input.direction)
        road.is_primary = road_input.is_primary
        road.road_name = road_input.road_name
        road.road_width_m = length_to_meters(road_input.road_width, unit_system)
        road.access_allowed = road_input.access_allowed
        road.sort_order = road_input.sort_order
        result.append(road)
    return sorted(result, key=lambda road: (road.sort_order, str(road.id)))


async def _create_user_boundary(
    session: AsyncSession,
    context: AuthContext,
    project: Project,
    request: PlotBoundaryInput,
    previous: PlotBoundaryVersion | None,
    unit_system: UnitSystem,
) -> PlotBoundaryVersion:
    try:
        normalized = normalize_geojson(request.geojson, request.coordinate_space, unit_system)
    except PlotGeometryError as error:
        raise plot_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            error.code,
            error.message,
            error.details,
        ) from error
    boundary = PlotBoundaryVersion(
        id=uuid4(),
        organization_id=context.membership.organization_id,
        project_id=project.id,
        version=await next_boundary_version(session, project.id),
        previous_boundary_version_id=previous.id if previous else None,
        restored_from_version_id=None,
        coordinate_space=request.coordinate_space.value,
        normalized_geojson=normalized.geojson,
        is_tombstone=False,
        source=request.source.value,
        schema_version=1,
        geometry_engine_version=normalized.geometry_engine_version,
        checksum=normalized.checksum,
        vertex_count=normalized.vertex_count,
        area_m2=normalized.area_m2,
        perimeter_m=normalized.perimeter_m,
        bounding_box=normalized.bounding_box,
        centroid=normalized.centroid,
        validation_status="warning" if normalized.warnings else "valid",
        validation_details=list(normalized.warnings),
        created_by=context.user.id,
        created_at=datetime.now(UTC),
    )
    session.add(boundary)
    return boundary


async def _clone_boundary(
    session: AsyncSession,
    context: AuthContext,
    project: Project,
    target: PlotBoundaryVersion | None,
    previous: PlotBoundaryVersion | None,
    source: BoundarySource,
) -> PlotBoundaryVersion:
    version = await next_boundary_version(session, project.id)
    boundary = PlotBoundaryVersion(
        id=uuid4(),
        organization_id=context.membership.organization_id,
        project_id=project.id,
        version=version,
        previous_boundary_version_id=previous.id if previous else None,
        restored_from_version_id=target.id if target else None,
        coordinate_space=(
            target.coordinate_space if target else CoordinateSpace.LOCAL_CARTESIAN.value
        ),
        normalized_geojson=target.normalized_geojson if target else None,
        is_tombstone=target is None or target.is_tombstone,
        source=source.value,
        schema_version=target.schema_version if target else 1,
        geometry_engine_version=(
            target.geometry_engine_version if target else GEOMETRY_ENGINE_VERSION
        ),
        checksum=(
            target.checksum
            if target and not target.is_tombstone
            else tombstone_checksum(str(previous.id) if previous else None, version)
        ),
        vertex_count=target.vertex_count if target and not target.is_tombstone else 0,
        area_m2=target.area_m2 if target and not target.is_tombstone else None,
        perimeter_m=target.perimeter_m if target and not target.is_tombstone else None,
        bounding_box=target.bounding_box if target and not target.is_tombstone else None,
        centroid=target.centroid if target and not target.is_tombstone else None,
        validation_status=(
            target.validation_status if target and not target.is_tombstone else "not_captured"
        ),
        validation_details=(
            target.validation_details if target and not target.is_tombstone else []
        ),
        created_by=context.user.id,
        created_at=datetime.now(UTC),
    )
    session.add(boundary)
    return boundary


def _activate_boundary(site: ProjectSite, boundary: PlotBoundaryVersion) -> None:
    site.current_boundary_version_id = boundary.id
    site.boundary_geojson = None if boundary.is_tombstone else boundary.normalized_geojson
    site.boundary_schema_version = boundary.schema_version


async def _record_current_analysis(
    session: AsyncSession,
    context: AuthContext,
    project: Project,
    boundary: PlotBoundaryVersion | None,
    *,
    roads: list[PlotRoadSide] | None = None,
) -> PlotAnalysisSnapshot:
    roads = roads if roads is not None else await load_active_roads(session, context, project.id)
    state = _build_state(project, roads, boundary)
    result = analyze_plot(state)
    now = datetime.now(UTC)
    snapshot = PlotAnalysisSnapshot(
        id=uuid4(),
        organization_id=context.membership.organization_id,
        project_id=project.id,
        boundary_version_id=boundary.id if boundary and not boundary.is_tombstone else None,
        profile_revision=state.profile_revision,
        analysis_engine_version=result.analysis_engine_version,
        geometry_engine_version=result.geometry_engine_version,
        input_checksum=result.input_checksum,
        plot_completeness=result.plot_completeness,
        plot_health_score=result.plot_health_score,
        plot_health_status=result.plot_health_status,
        feasibility_status=result.feasibility_status,
        pre_regulation_buildable_area_m2=result.pre_regulation_buildable_area_m2,
        parking_status=result.parking_status,
        parking_confidence=result.parking_confidence,
        parking_details=result.parking_details,
        coverage_status=result.coverage_status,
        coverage_details=result.coverage_details,
        regulation_status=result.regulation_status,
        regulation_context=result.regulation_context,
        validation_issues=list(result.issues),
        validation_summary=result.validation_summary,
        site_summary=result.site_summary,
        created_by=context.user.id,
        created_at=now,
    )
    session.add(snapshot)
    site = _ensure_site(project)
    site.current_analysis_id = snapshot.id
    site.plot_completeness = result.plot_completeness
    site.plot_health_score = result.plot_health_score
    site.plot_health_status = result.plot_health_status
    site.plot_feasibility_status = result.feasibility_status
    site.plot_validation_error_count = result.validation_summary["errorCount"]
    site.plot_validation_warning_count = result.validation_summary["warningCount"]
    site.pre_regulation_buildable_area_m2 = result.pre_regulation_buildable_area_m2
    site.parking_feasibility_status = result.parking_status
    site.analysis_updated_at = now
    return snapshot


def _build_state(
    project: Project,
    roads: list[PlotRoadSide],
    boundary: PlotBoundaryVersion | None,
) -> PlotState:
    site = _ensure_site(project)
    boundary_state = _boundary_state(boundary)
    return PlotState(
        project_id=project.id,
        profile_revision=site.profile_revision,
        plot_length_m=site.plot_length,
        plot_width_m=site.plot_width,
        plot_area_m2=site.plot_area,
        plot_shape=str(site.plot_shape) if site.plot_shape else None,
        open_sides=site.open_sides,
        corner_plot=site.corner_plot,
        orientation_degrees=site.orientation_degrees,
        north_rotation_degrees=site.north_rotation_degrees,
        north_reference=str(site.north_reference) if site.north_reference else None,
        latitude=site.latitude,
        longitude=site.longitude,
        has_address=bool(site.address_line_1 or site.city or site.region or site.postal_code),
        roads=tuple(_road_state(road) for road in roads),
        boundary=boundary_state,
        target_parking_spaces=(project.requirements.parking_spaces if project.requirements else 0),
    )


def _draft_state(
    project: Project,
    request: PlotValidationRequest,
    roads: list[PlotRoadSide],
    boundary: PlotBoundaryVersion | None,
) -> tuple[PlotState, UnitSystem]:
    site = _ensure_site(project)
    unit_system = request.unit_system or UnitSystem(str(project.unit_system))
    values: dict[str, Any] = {
        "plot_length_m": site.plot_length,
        "plot_width_m": site.plot_width,
        "plot_area_m2": site.plot_area,
        "plot_shape": str(site.plot_shape) if site.plot_shape else None,
        "open_sides": site.open_sides,
        "corner_plot": site.corner_plot,
        "orientation_degrees": site.orientation_degrees,
        "north_rotation_degrees": site.north_rotation_degrees,
        "north_reference": str(site.north_reference) if site.north_reference else None,
    }
    if "plot_length" in request.model_fields_set:
        values["plot_length_m"] = length_to_meters(request.plot_length, unit_system)
    if "plot_width" in request.model_fields_set:
        values["plot_width_m"] = length_to_meters(request.plot_width, unit_system)
    if "plot_area" in request.model_fields_set:
        values["plot_area_m2"] = area_to_square_meters(request.plot_area, unit_system)
    for request_field, value_field in (
        ("plot_shape", "plot_shape"),
        ("open_sides", "open_sides"),
        ("corner_plot", "corner_plot"),
        ("orientation_degrees", "orientation_degrees"),
        ("north_rotation_degrees", "north_rotation_degrees"),
        ("north_reference", "north_reference"),
    ):
        if request_field in request.model_fields_set:
            raw_value = getattr(request, request_field)
            values[value_field] = (
                str(raw_value)
                if value_field in {"plot_shape", "north_reference"} and raw_value is not None
                else raw_value
            )
    road_states = (
        tuple(_road_input_state(road, unit_system) for road in request.road_sides or [])
        if "road_sides" in request.model_fields_set
        else tuple(_road_state(road) for road in roads)
    )
    boundary_state = _boundary_state(boundary)
    if request.boundary is not None:
        try:
            normalized = normalize_geojson(
                request.boundary.geojson, request.boundary.coordinate_space, unit_system
            )
        except PlotGeometryError as error:
            raise plot_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                error.code,
                error.message,
                error.details,
            ) from error
        boundary_state = BoundaryState(
            id=None,
            version=None,
            area_m2=normalized.area_m2,
            perimeter_m=normalized.perimeter_m,
            vertex_count=normalized.vertex_count,
            edge_lengths_m=normalized.edge_lengths_m,
            warnings=normalized.warnings,
        )
    return (
        PlotState(
            project_id=project.id,
            profile_revision=site.profile_revision,
            plot_length_m=values["plot_length_m"],
            plot_width_m=values["plot_width_m"],
            plot_area_m2=values["plot_area_m2"],
            plot_shape=values["plot_shape"],
            open_sides=values["open_sides"] or 0,
            corner_plot=bool(values["corner_plot"]),
            orientation_degrees=values["orientation_degrees"],
            north_rotation_degrees=values["north_rotation_degrees"],
            north_reference=values["north_reference"],
            latitude=site.latitude,
            longitude=site.longitude,
            has_address=bool(site.address_line_1 or site.city or site.region or site.postal_code),
            roads=road_states,
            boundary=boundary_state,
            target_parking_spaces=(
                project.requirements.parking_spaces if project.requirements else 0
            ),
        ),
        UnitSystem(str(unit_system)),
    )


def _boundary_state(boundary: PlotBoundaryVersion | None) -> BoundaryState | None:
    if boundary is None or boundary.is_tombstone or boundary.normalized_geojson is None:
        return None
    normalized = normalize_geojson(
        boundary.normalized_geojson,
        CoordinateSpace(boundary.coordinate_space),
        UnitSystem.METRIC,
    )
    return BoundaryState(
        id=boundary.id,
        version=boundary.version,
        area_m2=boundary.area_m2 or normalized.area_m2,
        perimeter_m=boundary.perimeter_m or normalized.perimeter_m,
        vertex_count=boundary.vertex_count,
        edge_lengths_m=normalized.edge_lengths_m,
        warnings=tuple(boundary.validation_details),
    )


def _road_state(road: PlotRoadSide) -> RoadState:
    return RoadState(
        id=road.id,
        direction=road.direction,
        is_primary=road.is_primary,
        boundary_edge_index=road.boundary_edge_index,
        road_width_m=road.road_width_m,
        access_allowed=road.access_allowed,
    )


def _road_input_state(road: PlotRoadSideInput, unit_system: UnitSystem) -> RoadState:
    return RoadState(
        id=road.id,
        direction=str(road.direction),
        is_primary=road.is_primary,
        boundary_edge_index=road.boundary_edge_index,
        road_width_m=length_to_meters(road.road_width, unit_system),
        access_allowed=road.access_allowed,
    )


async def _build_plot_response(
    session: AsyncSession,
    context: AuthContext,
    project: Project,
    *,
    roads: list[PlotRoadSide] | None = None,
    boundary: PlotBoundaryVersion | None = None,
    analysis: PlotAnalysisSnapshot | None = None,
    active_undo: PlotBoundaryRestoreAction | None | object = ...,
) -> PlotIntelligenceResponse:
    site = _ensure_site(project)
    roads = roads if roads is not None else await load_active_roads(session, context, project.id)
    if boundary is None and site.current_boundary_version_id is not None:
        boundary = await load_boundary(session, context, site.current_boundary_version_id)
    if analysis is None:
        analysis = await load_analysis(session, context, site.current_analysis_id)
    unit_system = UnitSystem(str(project.unit_system))
    if analysis is None:
        transient = analyze_plot(_build_state(project, roads, boundary))
        analysis_response = _analysis_response(
            transient,
            snapshot=None,
            profile_revision=site.profile_revision,
            boundary_version_id=boundary.id if boundary and not boundary.is_tombstone else None,
            unit_system=unit_system,
        )
    else:
        analysis_response = _analysis_response_from_snapshot(analysis, unit_system)
    if active_undo is ...:
        active_undo = await load_active_undo(
            session, context, project.id, site.current_boundary_version_id
        )
    return PlotIntelligenceResponse(
        project_id=project.id,
        project_name=project.name,
        project_version=project.version,
        can_edit="projects:manage" in context.permissions and str(project.status) != "archived",
        profile=PlotProfileResponse(
            unit_system=unit_system.value,
            plot_length=length_from_meters(site.plot_length, unit_system),
            plot_width=length_from_meters(site.plot_width, unit_system),
            plot_area=area_from_square_meters(site.plot_area, unit_system),
            area_source=site.area_source,
            plot_shape=str(site.plot_shape) if site.plot_shape else None,
            open_sides=site.open_sides,
            corner_plot=site.corner_plot,
            orientation_degrees=site.orientation_degrees,
            north_rotation_degrees=site.north_rotation_degrees,
            north_reference=str(site.north_reference) if site.north_reference else None,
            profile_revision=site.profile_revision,
        ),
        road_sides=[_road_response(road, unit_system) for road in roads],
        boundary=_boundary_response(boundary, unit_system) if boundary else None,
        analysis=analysis_response,
        active_undo=(
            _undo_response(active_undo)
            if isinstance(active_undo, PlotBoundaryRestoreAction)
            else None
        ),
    )


def _analysis_response_from_snapshot(
    snapshot: PlotAnalysisSnapshot, unit_system: UnitSystem
) -> PlotAnalysisResponse:
    return PlotAnalysisResponse(
        id=snapshot.id,
        profile_revision=snapshot.profile_revision,
        boundary_version_id=snapshot.boundary_version_id,
        analysis_engine_version=snapshot.analysis_engine_version,
        geometry_engine_version=snapshot.geometry_engine_version,
        input_checksum=snapshot.input_checksum,
        plot_completeness=snapshot.plot_completeness,
        plot_health_score=snapshot.plot_health_score,
        plot_health_status=snapshot.plot_health_status,
        feasibility_status=snapshot.feasibility_status,
        pre_regulation_buildable_area=area_from_square_meters(
            snapshot.pre_regulation_buildable_area_m2, unit_system
        ),
        parking_status=snapshot.parking_status,
        parking_confidence=snapshot.parking_confidence,
        parking_details=snapshot.parking_details,
        coverage_status=snapshot.coverage_status,
        coverage_details=snapshot.coverage_details,
        regulation_status=snapshot.regulation_status,
        regulation_context=snapshot.regulation_context,
        validation_summary=snapshot.validation_summary,
        site_summary=snapshot.site_summary,
        issues=[
            PlotValidationIssueResponse.model_validate(issue)
            for issue in snapshot.validation_issues
        ],
        created_at=snapshot.created_at,
    )


def _analysis_response(
    result: AnalysisResult,
    *,
    snapshot: PlotAnalysisSnapshot | None,
    profile_revision: int,
    boundary_version_id: UUID | None,
    unit_system: UnitSystem,
) -> PlotAnalysisResponse:
    return PlotAnalysisResponse(
        id=snapshot.id if snapshot else None,
        profile_revision=profile_revision,
        boundary_version_id=boundary_version_id,
        analysis_engine_version=result.analysis_engine_version,
        geometry_engine_version=result.geometry_engine_version,
        input_checksum=result.input_checksum,
        plot_completeness=result.plot_completeness,
        plot_health_score=result.plot_health_score,
        plot_health_status=result.plot_health_status,
        feasibility_status=result.feasibility_status,
        pre_regulation_buildable_area=area_from_square_meters(
            result.pre_regulation_buildable_area_m2, unit_system
        ),
        parking_status=result.parking_status,
        parking_confidence=result.parking_confidence,
        parking_details=result.parking_details,
        coverage_status=result.coverage_status,
        coverage_details=result.coverage_details,
        regulation_status=result.regulation_status,
        regulation_context=result.regulation_context,
        validation_summary=result.validation_summary,
        site_summary=result.site_summary,
        issues=[PlotValidationIssueResponse.model_validate(issue) for issue in result.issues],
        created_at=snapshot.created_at if snapshot else None,
    )


def _boundary_response(
    boundary: PlotBoundaryVersion, unit_system: UnitSystem
) -> PlotBoundaryVersionResponse:
    coordinate_space = CoordinateSpace(boundary.coordinate_space)
    return PlotBoundaryVersionResponse(
        id=boundary.id,
        version=boundary.version,
        previous_boundary_version_id=boundary.previous_boundary_version_id,
        restored_from_version_id=boundary.restored_from_version_id,
        coordinate_space=coordinate_space.value,
        geojson=geojson_from_canonical(boundary.normalized_geojson, coordinate_space, unit_system),
        is_tombstone=boundary.is_tombstone,
        source=boundary.source,
        schema_version=boundary.schema_version,
        geometry_engine_version=boundary.geometry_engine_version,
        checksum=boundary.checksum,
        vertex_count=boundary.vertex_count,
        area=area_from_square_meters(boundary.area_m2, unit_system),
        perimeter=length_from_meters(boundary.perimeter_m, unit_system),
        bounding_box=_convert_coordinate_mapping(
            boundary.bounding_box, coordinate_space, unit_system
        ),
        centroid=_convert_coordinate_mapping(boundary.centroid, coordinate_space, unit_system),
        validation_status=boundary.validation_status,
        validation_details=boundary.validation_details,
        created_by=boundary.created_by,
        created_at=boundary.created_at,
    )


def _road_response(road: PlotRoadSide, unit_system: UnitSystem) -> PlotRoadSideResponse:
    return PlotRoadSideResponse(
        id=road.id,
        boundary_edge_index=road.boundary_edge_index,
        label=road.label,
        direction=road.direction,
        is_primary=road.is_primary,
        road_name=road.road_name,
        road_width=length_from_meters(road.road_width_m, unit_system),
        access_allowed=road.access_allowed,
        sort_order=road.sort_order,
    )


def _undo_response(action: PlotBoundaryRestoreAction) -> PlotUndoActionResponse:
    return PlotUndoActionResponse(
        id=action.id,
        restored_boundary_version_id=action.restored_boundary_version_id,
        previous_active_boundary_version_id=action.previous_active_boundary_version_id,
        expires_at=action.expires_at,
    )


def _convert_coordinate_mapping(
    value: dict[str, Any] | None,
    coordinate_space: CoordinateSpace,
    unit_system: UnitSystem,
) -> dict[str, Any] | None:
    if (
        value is None
        or coordinate_space == CoordinateSpace.WGS84
        or unit_system == UnitSystem.METRIC
    ):
        return value
    factor = float(Decimal("0.3048"))
    return {key: round(number / factor, 4) for key, number in value.items()}


def _sync_compatibility_road_fields(site: ProjectSite, roads: list[PlotRoadSide]) -> None:
    ordered = sorted(roads, key=lambda road: (not road.is_primary, road.sort_order))
    site.road_direction_primary = ordered[0].direction if ordered else None
    site.road_direction_secondary = ordered[1].direction if len(ordered) > 1 else None


def _ensure_site(project: Project) -> ProjectSite:
    if project.site is None:
        project.site = ProjectSite()
    return project.site


def _touch_project(project: Project, context: AuthContext) -> None:
    project.version += 1
    project.updated_by = context.user.id


def _ensure_version(project: Project, expected_version: int) -> None:
    if project.version != expected_version:
        raise plot_error(
            status.HTTP_409_CONFLICT,
            "PLOT_VERSION_CONFLICT",
            "The project changed after the plot was loaded.",
            {"expectedVersion": expected_version, "currentVersion": project.version},
        )


def _ensure_analysis_valid(issues: list[dict[str, Any]]) -> None:
    errors = [issue for issue in issues if issue["severity"] == "error"]
    if errors:
        raise plot_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "PLOT_PROFILE_INVALID",
            "Plot profile contains contradictory or impossible values.",
            {"issues": errors},
        )


async def _write_audit(
    session: AsyncSession,
    context: AuthContext,
    project: Project,
    action: str,
    request_id: str,
    after_data: dict[str, Any],
) -> None:
    session.add(
        AuditLog(
            id=uuid4(),
            organization_id=context.membership.organization_id,
            actor_user_id=context.user.id,
            action=action,
            entity_type="project",
            entity_id=project.id,
            request_id=request_id,
            before_data=None,
            after_data=after_data,
            created_at=datetime.now(UTC),
        )
    )


async def _load_idempotency(
    session: AsyncSession,
    context: AuthContext,
    scope: str,
    key: str,
    request_hash: str,
) -> IdempotencyRecord | None:
    record = (
        await session.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.organization_id == context.membership.organization_id,
                IdempotencyRecord.actor_user_id == context.user.id,
                IdempotencyRecord.scope == scope,
                IdempotencyRecord.idempotency_key == key,
                IdempotencyRecord.expires_at > datetime.now(UTC),
            )
        )
    ).scalar_one_or_none()
    if record and record.request_hash != request_hash:
        raise plot_error(
            status.HTTP_409_CONFLICT,
            "PLOT_IDEMPOTENCY_CONFLICT",
            "The idempotency key was already used with a different request.",
        )
    return record


async def _store_idempotency(
    session: AsyncSession,
    context: AuthContext,
    scope: str,
    key: str,
    request_hash: str,
    response_status: int,
    response_body: dict[str, Any],
) -> None:
    session.add(
        IdempotencyRecord(
            id=uuid4(),
            organization_id=context.membership.organization_id,
            actor_user_id=context.user.id,
            scope=scope,
            idempotency_key=key,
            request_hash=request_hash,
            response_status=response_status,
            response_body=response_body,
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )
    )


def _request_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _encode_cursor(boundary: PlotBoundaryVersion) -> str:
    payload = json.dumps({"createdAt": boundary.created_at.isoformat(), "id": str(boundary.id)})
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode())
        return datetime.fromisoformat(payload["createdAt"]), UUID(payload["id"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
        raise plot_error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "PAGINATION_CURSOR_INVALID",
            "The boundary history cursor is invalid.",
        ) from error
