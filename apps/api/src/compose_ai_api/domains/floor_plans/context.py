from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.auth import AuthContext
from compose_ai_api.domains.ai_architect.context import build_project_memory
from compose_ai_api.domains.ai_architect.models import (
    AIArchitectBriefVersion,
    AIBriefStatus,
    AIProjectMemoryVersion,
)
from compose_ai_api.domains.floor_plans.geometry import CanonicalPlot, canonicalize_boundary
from compose_ai_api.domains.floor_plans.schemas import FloorPlanGenerationRequest
from compose_ai_api.domains.plot_intelligence.models import (
    PlotAnalysisSnapshot,
    PlotBoundaryVersion,
)
from compose_ai_api.domains.projects.models import Project
from compose_ai_api.domains.projects.service import (
    ensure_project_read,
    project_error,
    project_select,
)


@dataclass(frozen=True)
class FloorPlanContext:
    project: Project
    brief: AIArchitectBriefVersion
    memory: AIProjectMemoryVersion
    boundary: PlotBoundaryVersion
    analysis: PlotAnalysisSnapshot
    canonical_plot: CanonicalPlot
    source_versions: dict[str, Any]
    provider_payload: dict[str, Any]


async def load_generation_context(
    session: AsyncSession,
    auth: AuthContext,
    project_id: UUID,
    request: FloorPlanGenerationRequest,
) -> FloorPlanContext:
    ensure_project_read(auth)
    project = (
        await session.execute(
            project_select()
            .where(
                Project.id == project_id,
                Project.organization_id == auth.membership.organization_id,
                Project.deleted_at.is_(None),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if project is None:
        raise project_error(404, "PROJECT_NOT_FOUND", "Project not found.")
    if project.status == "archived":
        raise project_error(
            409,
            "FLOOR_PLAN_PROJECT_ARCHIVED",
            "Restore the project before generating a floor plan.",
        )
    if project.site is None:
        raise _not_ready(["plotProfile"])

    brief = await _approved_brief(session, auth, project_id)
    if brief is None:
        raise _not_ready(["approvedBrief"])
    if project.site.current_boundary_version_id is None:
        raise _not_ready(["plotBoundary"])
    if project.site.current_analysis_id is None:
        raise _not_ready(["plotAnalysis"])

    boundary = await session.get(PlotBoundaryVersion, project.site.current_boundary_version_id)
    analysis = await session.get(PlotAnalysisSnapshot, project.site.current_analysis_id)
    if boundary is None or boundary.is_tombstone or boundary.validation_status == "invalid":
        raise _not_ready(["validPlotBoundary"])
    if analysis is None or analysis.boundary_version_id != boundary.id:
        raise _not_ready(["currentPlotAnalysis"])
    if (
        int(
            analysis.validation_summary.get(
                "errorCount", analysis.validation_summary.get("errors", 0)
            )
        )
        > 0
    ):
        raise _not_ready(["plotValidation"])

    memory_result = await build_project_memory(session, auth, project_id)
    memory = memory_result.memory
    canonical_plot = canonicalize_boundary(boundary)
    source_versions = {
        "projectVersion": project.version,
        "plotProfileRevision": project.site.profile_revision,
        "briefId": str(brief.id),
        "briefVersion": brief.version,
        "memoryVersionId": str(memory.id),
        "memoryVersion": memory.version,
        "boundaryVersionId": str(boundary.id),
        "boundaryVersion": boundary.version,
        "boundaryChecksum": boundary.checksum,
        "analysisSnapshotId": str(analysis.id),
        "analysisInputChecksum": analysis.input_checksum,
        "analysisEngineVersion": analysis.analysis_engine_version,
        "plotGeometryEngineVersion": analysis.geometry_engine_version,
    }
    provider_payload = _provider_payload(project, brief, analysis, request)
    return FloorPlanContext(
        project=project,
        brief=brief,
        memory=memory,
        boundary=boundary,
        analysis=analysis,
        canonical_plot=canonical_plot,
        source_versions=source_versions,
        provider_payload=provider_payload,
    )


async def _approved_brief(
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


def _provider_payload(
    project: Project,
    brief: AIArchitectBriefVersion,
    analysis: PlotAnalysisSnapshot,
    request: FloorPlanGenerationRequest,
) -> dict[str, Any]:
    requirements = project.requirements
    return {
        "project": {
            "type": str(project.project_type) if project.project_type else None,
            "unitSystem": str(project.unit_system),
            "country": project.country,
            "currency": project.currency,
        },
        "approvedBrief": {
            "id": str(brief.id),
            "version": brief.version,
            "summary": brief.summary,
            "goals": brief.goals,
            "priorities": brief.priorities,
            "constraints": brief.constraints,
            "normalizedRequirements": brief.normalized_requirements,
        },
        "requirements": {
            "bedrooms": requirements.bedrooms if requirements else 0,
            "bathrooms": float(requirements.bathrooms) if requirements else 0,
            "floors": requirements.floors if requirements else 1,
            "parkingSpaces": requirements.parking_spaces if requirements else 0,
            "budget": float(requirements.budget) if requirements and requirements.budget else None,
            "constructionQuality": str(requirements.construction_quality)
            if requirements and requirements.construction_quality
            else None,
            "preferredStyle": request.preferred_style
            or (requirements.preferred_style if requirements else None),
            "vastuPreference": request.vastu_preference,
        },
        "roomRequirements": [
            {
                "name": room.name,
                "roomType": room.room_type,
                "quantity": room.quantity,
                "preferredFloor": room.preferred_floor,
                "minimumArea": float(room.minimum_area) if room.minimum_area else None,
                "notes": room.notes,
            }
            for room in project.room_requirements
        ],
        "plotIntelligence": {
            "plotAreaM2": float(project.site.plot_area)
            if project.site and project.site.plot_area
            else None,
            "buildableAreaM2": float(analysis.pre_regulation_buildable_area_m2)
            if analysis.pre_regulation_buildable_area_m2
            else None,
            "shape": str(project.site.plot_shape)
            if project.site and project.site.plot_shape
            else None,
            "roadDirection": str(project.site.road_direction_primary)
            if project.site and project.site.road_direction_primary
            else None,
            "openSides": project.site.open_sides if project.site else 0,
            "cornerPlot": project.site.corner_plot if project.site else False,
            "siteSummary": analysis.site_summary,
            "validationSummary": analysis.validation_summary,
        },
        "generationPreferences": {
            "budgetMode": request.budget_mode,
            "preferredStyle": request.preferred_style,
            "userConstraints": [
                item.model_dump(mode="json", by_alias=True) for item in request.user_constraints
            ],
        },
    }


def _not_ready(missing: list[str]) -> Exception:
    return project_error(
        422,
        "FLOOR_PLAN_NOT_READY",
        "Complete the required project, brief, and plot inputs before generation.",
        {"missing": missing},
    )
