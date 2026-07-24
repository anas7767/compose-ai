from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.auth import AuthContext
from compose_ai_api.domains.ai_architect.cache import stable_hash
from compose_ai_api.domains.ai_architect.models import (
    AIArchitectBriefVersion,
    AIBriefStatus,
    AIChatMessage,
    AIProjectMemoryVersion,
    AIProposalStatus,
    AIRequirementProposal,
)
from compose_ai_api.domains.ai_architect.safety import prepare_untrusted_text
from compose_ai_api.domains.ai_architect.token_usage import estimate_tokens
from compose_ai_api.domains.plot_intelligence.models import PlotAnalysisSnapshot
from compose_ai_api.domains.projects.models import Project, ProjectStatus, UnitSystem
from compose_ai_api.domains.projects.service import (
    ensure_project_read,
    project_error,
    project_select,
)

MEMORY_SCHEMA_VERSION = "project-memory.v1"
MAX_CONTEXT_MESSAGES = 16
MAX_CONTEXT_CHARACTERS = 48_000


@dataclass(frozen=True)
class ProjectMemoryResult:
    project: Project
    memory: AIProjectMemoryVersion


async def build_project_memory(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    *,
    thread_id: UUID | None = None,
) -> ProjectMemoryResult:
    ensure_project_read(context)
    project = (
        await session.execute(
            project_select()
            .where(
                Project.id == project_id,
                Project.organization_id == context.membership.organization_id,
                Project.deleted_at.is_(None),
            )
            .with_for_update()
        )
    ).scalar_one_or_none()
    if project is None:
        raise project_error(404, "PROJECT_NOT_FOUND", "Project not found.")

    analysis = await _load_analysis(session, project)
    approved_brief = await _load_approved_brief(session, context, project_id)
    decisions = await _load_applied_decisions(session, context, project_id)
    conversation, message_redactions = await _load_conversation(
        session, context, project_id, thread_id
    )
    payload, redaction_summary, sources = _context_payload(
        project,
        analysis,
        approved_brief,
        decisions,
        conversation,
        message_redactions,
    )
    requirements_hash = stable_hash(
        {"requirements": payload["requirements"], "rooms": payload["roomRequirements"]}
    )
    context_hash = stable_hash(payload)
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    if len(serialized) > MAX_CONTEXT_CHARACTERS:
        payload["conversation"] = payload["conversation"][-6:]
        payload["contextManagement"] = {
            "truncated": True,
            "reason": "Conversation history was reduced to fit the context budget.",
        }
        context_hash = stable_hash(payload)
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)

    existing = (
        await session.execute(
            select(AIProjectMemoryVersion)
            .where(
                AIProjectMemoryVersion.organization_id == context.membership.organization_id,
                AIProjectMemoryVersion.project_id == project_id,
                AIProjectMemoryVersion.context_hash == context_hash,
            )
            .order_by(AIProjectMemoryVersion.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return ProjectMemoryResult(project=project, memory=existing)

    latest = (
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
    memory = AIProjectMemoryVersion(
        id=uuid4(),
        organization_id=context.membership.organization_id,
        project_id=project.id,
        version=(latest.version + 1) if latest else 1,
        project_version=project.version,
        plot_profile_revision=project.site.profile_revision if project.site else None,
        boundary_version_id=project.site.current_boundary_version_id if project.site else None,
        analysis_snapshot_id=project.site.current_analysis_id if project.site else None,
        requirements_hash=requirements_hash,
        context_payload=payload,
        context_summary=_memory_summary(project, analysis, approved_brief),
        included_sources=sources,
        redaction_summary=redaction_summary,
        token_estimate=estimate_tokens(serialized),
        context_hash=context_hash,
        schema_version=MEMORY_SCHEMA_VERSION,
        supersedes_id=latest.id if latest else None,
        created_by=context.user.id,
    )
    session.add(memory)
    await session.flush()
    return ProjectMemoryResult(project=project, memory=memory)


def memory_prompt_payload(memory: AIProjectMemoryVersion) -> str:
    return json.dumps(memory.context_payload, sort_keys=True, separators=(",", ":"), default=str)


async def _load_analysis(session: AsyncSession, project: Project) -> PlotAnalysisSnapshot | None:
    if project.site is None or project.site.current_analysis_id is None:
        return None
    return await session.get(PlotAnalysisSnapshot, project.site.current_analysis_id)


async def _load_approved_brief(
    session: AsyncSession, context: AuthContext, project_id: UUID
) -> AIArchitectBriefVersion | None:
    return (
        await session.execute(
            select(AIArchitectBriefVersion)
            .where(
                AIArchitectBriefVersion.organization_id == context.membership.organization_id,
                AIArchitectBriefVersion.project_id == project_id,
                AIArchitectBriefVersion.status.in_((AIBriefStatus.APPROVED, AIBriefStatus.APPLIED)),
            )
            .order_by(AIArchitectBriefVersion.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _load_applied_decisions(
    session: AsyncSession, context: AuthContext, project_id: UUID
) -> list[dict[str, Any]]:
    proposals = list(
        (
            await session.execute(
                select(AIRequirementProposal)
                .where(
                    AIRequirementProposal.organization_id == context.membership.organization_id,
                    AIRequirementProposal.project_id == project_id,
                    AIRequirementProposal.status == AIProposalStatus.APPLIED,
                )
                .order_by(AIRequirementProposal.applied_at.desc())
                .limit(40)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "targetPath": proposal.target_path,
            "value": proposal.proposed_value,
            "explanation": proposal.explanation,
            "appliedAt": proposal.applied_at.isoformat() if proposal.applied_at else None,
        }
        for proposal in reversed(proposals)
    ]


async def _load_conversation(
    session: AsyncSession,
    context: AuthContext,
    project_id: UUID,
    thread_id: UUID | None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    if thread_id is None:
        return [], {"emails": 0, "phones": 0}
    messages = list(
        (
            await session.execute(
                select(AIChatMessage)
                .where(
                    AIChatMessage.organization_id == context.membership.organization_id,
                    AIChatMessage.project_id == project_id,
                    AIChatMessage.thread_id == thread_id,
                    AIChatMessage.deleted_at.is_(None),
                )
                .order_by(AIChatMessage.sequence_number.desc())
                .limit(MAX_CONTEXT_MESSAGES)
            )
        )
        .scalars()
        .all()
    )
    redactions = {"emails": 0, "phones": 0}
    output: list[dict[str, Any]] = []
    for message in reversed(messages):
        prepared = prepare_untrusted_text(message.display_content)
        redactions["emails"] += prepared.redacted_email_count
        redactions["phones"] += prepared.redacted_phone_count
        output.append(
            {
                "id": str(message.id),
                "role": str(message.role),
                "mode": str(message.mode),
                "content": prepared.provider_text,
                "sequence": message.sequence_number,
            }
        )
    return output, redactions


def _context_payload(
    project: Project,
    analysis: PlotAnalysisSnapshot | None,
    approved_brief: AIArchitectBriefVersion | None,
    decisions: list[dict[str, Any]],
    conversation: list[dict[str, Any]],
    message_redactions: dict[str, int],
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    requirements = project.requirements
    site = project.site
    client = project.client
    payload: dict[str, Any] = {
        "project": {
            "id": str(project.id),
            "name": project.name,
            "status": str(project.status),
            "projectType": str(project.project_type) if project.project_type else None,
            "description": project.description,
            "unitSystem": str(project.unit_system),
            "currency": project.currency,
            "country": project.country,
            "version": project.version,
        },
        "client": {
            "name": client.name if client else None,
            "company": client.company if client else None,
        },
        "site": {
            "plotLengthMeters": _decimal(site.plot_length) if site else None,
            "plotWidthMeters": _decimal(site.plot_width) if site else None,
            "plotAreaSquareMeters": _decimal(site.plot_area) if site else None,
            "shape": str(site.plot_shape) if site and site.plot_shape else None,
            "city": site.city if site else None,
            "region": site.region if site else None,
            "country": project.country,
            "openSides": site.open_sides if site else 0,
            "cornerPlot": site.corner_plot if site else False,
            "orientationDegrees": _decimal(site.orientation_degrees) if site else None,
            "northReference": site.north_reference if site else None,
            "profileRevision": site.profile_revision if site else None,
            "boundaryVersionId": str(site.current_boundary_version_id)
            if site and site.current_boundary_version_id
            else None,
        },
        "plotIntelligence": {
            "analysisSnapshotId": str(analysis.id) if analysis else None,
            "plotCompleteness": analysis.plot_completeness if analysis else 0,
            "plotHealthScore": analysis.plot_health_score if analysis else 0,
            "feasibilityStatus": analysis.feasibility_status if analysis else "insufficient_data",
            "preRegulationBuildableAreaSquareMeters": _decimal(
                analysis.pre_regulation_buildable_area_m2
            )
            if analysis
            else None,
            "parkingStatus": analysis.parking_status if analysis else "indeterminate",
            "validationSummary": analysis.validation_summary if analysis else {},
            "siteSummary": analysis.site_summary if analysis else {},
            "analysisEngineVersion": analysis.analysis_engine_version if analysis else None,
            "geometryEngineVersion": analysis.geometry_engine_version if analysis else None,
        },
        "requirements": {
            "bedrooms": requirements.bedrooms if requirements else 0,
            "bathrooms": _decimal(requirements.bathrooms) if requirements else 0,
            "floors": requirements.floors if requirements else 1,
            "parkingSpaces": requirements.parking_spaces if requirements else 0,
            "budget": _decimal(requirements.budget) if requirements else None,
            "constructionQuality": str(requirements.construction_quality)
            if requirements and requirements.construction_quality
            else None,
            "preferredStyle": requirements.preferred_style if requirements else None,
            "vastuPreference": str(requirements.vastu_preference)
            if requirements
            else "not_required",
            "notes": requirements.notes if requirements else None,
        },
        "roomRequirements": [
            {
                "id": str(room.id),
                "name": room.name,
                "roomType": room.room_type,
                "quantity": room.quantity,
                "preferredFloor": room.preferred_floor,
                "minimumArea": _decimal(room.minimum_area),
                "notes": room.notes,
            }
            for room in project.room_requirements
        ],
        "approvedBrief": (
            {
                "id": str(approved_brief.id),
                "version": approved_brief.version,
                "summary": approved_brief.summary,
                "goals": approved_brief.goals,
                "priorities": approved_brief.priorities,
                "constraints": approved_brief.constraints,
            }
            if approved_brief
            else None
        ),
        "approvedDecisions": decisions,
        "conversation": conversation,
    }
    redaction_summary = {
        "clientEmailExcluded": bool(client and client.email),
        "clientPhoneExcluded": bool(client and client.phone),
        "clientAddressExcluded": bool(client and client.address),
        "exactSiteAddressExcluded": bool(site and (site.address_line_1 or site.address_line_2)),
        "coordinatesExcluded": bool(
            site and (site.latitude is not None or site.longitude is not None)
        ),
        "conversationEmailsRedacted": message_redactions["emails"],
        "conversationPhonesRedacted": message_redactions["phones"],
    }
    sources = [
        {"type": "project", "version": project.version},
        {
            "type": "requirements",
            "updatedAt": requirements.updated_at.isoformat() if requirements else None,
        },
        {
            "type": "site",
            "profileRevision": site.profile_revision if site else None,
            "boundaryVersionId": str(site.current_boundary_version_id)
            if site and site.current_boundary_version_id
            else None,
        },
        {"type": "plotAnalysis", "id": str(analysis.id) if analysis else None},
        {"type": "approvedBrief", "id": str(approved_brief.id) if approved_brief else None},
        {"type": "conversation", "messageCount": len(conversation)},
    ]
    return payload, redaction_summary, sources


def _memory_summary(
    project: Project,
    analysis: PlotAnalysisSnapshot | None,
    approved_brief: AIArchitectBriefVersion | None,
) -> str:
    status = ProjectStatus(str(project.status)).value
    units = UnitSystem(str(project.unit_system)).value
    parts = [f"{project.name} is a {status} project using {units} units."]
    if project.project_type:
        parts.append(f"Project type: {str(project.project_type).replace('_', ' ')}.")
    if analysis:
        parts.append(
            f"Plot health is {analysis.plot_health_score}/100 with "
            f"{analysis.feasibility_status.replace('_', ' ')} feasibility."
        )
    if approved_brief:
        parts.append(f"Approved brief version {approved_brief.version} is included.")
    return " ".join(parts)


def _decimal(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None
