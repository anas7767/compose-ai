from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from compose_ai_api.domains.ai_architect.models import AIProposalTarget
from compose_ai_api.domains.ai_architect.providers.base import AIProviderError
from compose_ai_api.domains.ai_architect.schemas import ArchitectBriefOutput
from compose_ai_api.domains.projects.models import Project
from compose_ai_api.domains.projects.schemas import ProjectUpdateRequest

ACTIONABLE_PATHS: dict[str, AIProposalTarget] = {
    "/name": AIProposalTarget.PROJECT_FIELD,
    "/description": AIProposalTarget.PROJECT_FIELD,
    "/projectType": AIProposalTarget.PROJECT_FIELD,
    "/requirements/bedrooms": AIProposalTarget.REQUIREMENTS_FIELD,
    "/requirements/bathrooms": AIProposalTarget.REQUIREMENTS_FIELD,
    "/requirements/floors": AIProposalTarget.REQUIREMENTS_FIELD,
    "/requirements/parkingSpaces": AIProposalTarget.REQUIREMENTS_FIELD,
    "/requirements/budget": AIProposalTarget.REQUIREMENTS_FIELD,
    "/requirements/constructionQuality": AIProposalTarget.REQUIREMENTS_FIELD,
    "/requirements/preferredStyle": AIProposalTarget.REQUIREMENTS_FIELD,
    "/requirements/vastuPreference": AIProposalTarget.REQUIREMENTS_FIELD,
    "/requirements/notes": AIProposalTarget.REQUIREMENTS_FIELD,
    "/roomRequirements": AIProposalTarget.ROOM_REQUIREMENTS,
}


def validate_brief_quality(output: ArchitectBriefOutput) -> None:
    seen_paths: set[str] = set()
    for proposal in output.proposals:
        if proposal.target_type == AIProposalTarget.PLOT_RECOMMENDATION:
            if not proposal.target_path.startswith("/plotRecommendations/"):
                raise _schema_error("Plot recommendations must use a recommendation-only path.")
        elif ACTIONABLE_PATHS.get(proposal.target_path) != proposal.target_type:
            raise _schema_error(f"Unsupported proposal path: {proposal.target_path}.")
        if proposal.target_path in seen_paths:
            raise _schema_error(f"Duplicate proposal path: {proposal.target_path}.")
        seen_paths.add(proposal.target_path)
        if not proposal.explanation.strip():
            raise _schema_error("Every proposal requires an explanation.")
        if not proposal.source_references:
            raise _schema_error("Every proposal requires at least one source reference.")


def current_value_for_path(project: Project, path: str) -> Any:
    if path == "/name":
        return project.name
    if path == "/description":
        return project.description
    if path == "/projectType":
        return str(project.project_type) if project.project_type else None
    if path == "/roomRequirements":
        return [
            {
                "id": str(room.id),
                "name": room.name,
                "roomType": room.room_type,
                "quantity": room.quantity,
                "preferredFloor": room.preferred_floor,
                "minimumArea": float(room.minimum_area) if room.minimum_area is not None else None,
                "notes": room.notes,
                "sortOrder": room.sort_order,
            }
            for room in project.room_requirements
        ]
    if path.startswith("/requirements/"):
        requirements = project.requirements
        if requirements is None:
            return None
        attribute = {
            "bedrooms": "bedrooms",
            "bathrooms": "bathrooms",
            "floors": "floors",
            "parkingSpaces": "parking_spaces",
            "budget": "budget",
            "constructionQuality": "construction_quality",
            "preferredStyle": "preferred_style",
            "vastuPreference": "vastu_preference",
            "notes": "notes",
        }[path.removeprefix("/requirements/")]
        value = getattr(requirements, attribute)
        if hasattr(value, "value"):
            return value.value
        if value is not None and attribute in {"bathrooms", "budget"}:
            return float(value)
        return value
    return None


def build_project_update(values_by_path: dict[str, Any]) -> ProjectUpdateRequest:
    payload: dict[str, Any] = {}
    requirements: dict[str, Any] = {}
    for path, value in values_by_path.items():
        if path == "/name":
            payload["name"] = value
        elif path == "/description":
            payload["description"] = value
        elif path == "/projectType":
            payload["projectType"] = value
        elif path == "/roomRequirements":
            payload["roomRequirements"] = value
        elif path.startswith("/requirements/"):
            requirements[path.removeprefix("/requirements/")] = value
        else:
            raise _schema_error(f"Unsupported project update path: {path}.")
    if requirements:
        payload["requirements"] = requirements
    try:
        return ProjectUpdateRequest.model_validate(payload)
    except ValidationError as error:
        raise AIProviderError(
            "AI_PROPOSAL_VALIDATION_FAILED",
            "An approved proposal does not satisfy project validation.",
            retryable=False,
        ) from error


def has_blocking_conflict(output: ArchitectBriefOutput, target_path: str) -> bool:
    return any(
        conflict.severity == "blocking" and target_path in conflict.affected_paths
        for conflict in output.conflicts
    )


def _schema_error(message: str) -> AIProviderError:
    return AIProviderError("AI_SCHEMA_INVALID", message, retryable=False)
