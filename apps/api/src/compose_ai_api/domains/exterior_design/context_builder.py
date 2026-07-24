from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from compose_ai_api.core.auth import AuthContext
from compose_ai_api.domains.ai_architect.models import AIArchitectBriefVersion, AIBriefStatus
from compose_ai_api.domains.building_visualization.models import (
    SceneMaterial,
    SceneObject,
    SceneVersion,
)
from compose_ai_api.domains.exterior_design.constants import (
    EXTERIOR_DESIGN_ENGINE_VERSION,
    EXTERIOR_PROMPT_VERSION,
    MATERIAL_CATEGORIES,
)
from compose_ai_api.domains.floor_plans.models import FloorPlanDesignVersion
from compose_ai_api.domains.projects.models import Project
from compose_ai_api.domains.projects.service import project_error


@dataclass(frozen=True)
class ExteriorSourceContext:
    project: Project
    design_version: FloorPlanDesignVersion | None
    scene_version: SceneVersion | None
    brief: AIArchitectBriefVersion | None
    materials: list[str]
    objects: list[dict[str, Any]]
    issues: list[dict[str, str]]


async def build_source_context(
    session: AsyncSession, auth: AuthContext, project_id: UUID
) -> ExteriorSourceContext:
    project = (
        await session.execute(
            select(Project).where(
                Project.id == project_id,
                Project.organization_id == auth.membership.organization_id,
                Project.deleted_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if project is None:
        raise project_error(404, "PROJECT_NOT_FOUND", "Project not found.")

    design = (
        await session.execute(
            select(FloorPlanDesignVersion)
            .where(
                FloorPlanDesignVersion.project_id == project_id,
                FloorPlanDesignVersion.organization_id == auth.membership.organization_id,
                FloorPlanDesignVersion.deleted_at.is_(None),
            )
            .order_by(FloorPlanDesignVersion.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    scene = None
    if design is not None:
        scene = (
            await session.execute(
                select(SceneVersion)
                .where(
                    SceneVersion.project_id == project_id,
                    SceneVersion.organization_id == auth.membership.organization_id,
                    SceneVersion.source_design_version_id == design.id,
                    SceneVersion.deleted_at.is_(None),
                )
                .order_by(SceneVersion.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    brief = (
        await session.execute(
            select(AIArchitectBriefVersion)
            .where(
                AIArchitectBriefVersion.project_id == project_id,
                AIArchitectBriefVersion.organization_id == auth.membership.organization_id,
                AIArchitectBriefVersion.status.in_((AIBriefStatus.APPROVED, AIBriefStatus.APPLIED)),
            )
            .order_by(AIArchitectBriefVersion.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    materials: list[str] = []
    objects: list[dict[str, Any]] = []
    if scene is not None:
        materials = list(
            (
                await session.execute(
                    select(SceneMaterial.category)
                    .where(SceneMaterial.scene_version_id == scene.id)
                    .order_by(SceneMaterial.category)
                )
            )
            .scalars()
            .all()
        )
        object_rows = (
            await session.execute(
                select(SceneObject)
                .where(SceneObject.scene_version_id == scene.id)
                .order_by(SceneObject.object_type, SceneObject.name)
                .limit(80)
            )
        ).scalars()
        objects = [
            {
                "type": row.object_type,
                "name": row.name,
                "floorId": row.floor_id,
                "source2dObjectId": row.source_2d_object_id,
                "boundingBox": row.bounding_box,
                "materialId": row.material_id,
            }
            for row in object_rows
        ]
    issues: list[dict[str, str]] = []
    if design is None:
        issues.append(
            {
                "code": "EXTERIOR_REQUIRES_ACCEPTED_DESIGN",
                "severity": "blocking",
                "message": (
                    "Accept a floor-plan design version before generating an exterior elevation."
                ),
                "actionUrl": f"/projects/{project_id}/floor-plans",
            }
        )
    if scene is None:
        issues.append(
            {
                "code": "EXTERIOR_REQUIRES_SCENE",
                "severity": "blocking",
                "message": (
                    "Compile a 3D scene from the accepted floor plan before generating an "
                    "exterior elevation."
                ),
                "actionUrl": f"/projects/{project_id}/visualization",
            }
        )
    return ExteriorSourceContext(
        project=project,
        design_version=design,
        scene_version=scene,
        brief=brief,
        materials=materials or list(MATERIAL_CATEGORIES),
        objects=objects,
        issues=issues,
    )


def context_snapshot_payload(
    source: ExteriorSourceContext,
    *,
    style: str,
    view_type: str,
    material_preferences: list[str],
    user_instructions: str | None,
    negative_constraints: str | None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    if source.design_version is None or source.scene_version is None:
        raise project_error(409, "EXTERIOR_NOT_READY", "Exterior design generation is not ready.")
    source_versions = {
        "projectVersion": getattr(source.project, "version", None),
        "floorPlanDesignVersion": source.design_version.version,
        "sceneVersion": source.scene_version.version,
        "sceneEngineVersion": source.scene_version.scene_engine_version,
        "sceneSchemaVersion": source.scene_version.scene_schema_version,
        "editorCheckpointId": str(source.scene_version.source_editor_checkpoint_id),
        "aiBriefVersion": source.brief.version if source.brief else None,
    }
    payload = {
        "project": {
            "id": str(source.project.id),
            "name": source.project.name,
            "projectType": str(source.project.project_type)
            if source.project.project_type
            else None,
            "country": source.project.country,
            "unitSystem": source.project.unit_system,
            "currency": source.project.currency,
            "description": source.project.description,
        },
        "floorPlan": {
            "designVersionId": str(source.design_version.id),
            "version": source.design_version.version,
            "name": source.design_version.name,
            "geometryHash": source.design_version.geometry_hash,
        },
        "scene": {
            "sceneVersionId": str(source.scene_version.id),
            "version": source.scene_version.version,
            "boundingBox": source.scene_version.bounding_box,
            "objectCount": source.scene_version.object_count,
            "triangleCount": source.scene_version.triangle_count,
            "objects": source.objects,
        },
        "architectBrief": {
            "id": str(source.brief.id) if source.brief else None,
            "summary": source.brief.summary if source.brief else None,
            "constraints": source.brief.constraints if source.brief else [],
            "priorities": source.brief.priorities if source.brief else [],
        },
        "generation": {
            "style": style,
            "viewType": view_type,
            "materialPreferences": material_preferences,
            "userInstructions": user_instructions,
            "negativeConstraints": negative_constraints,
            "promptVersion": EXTERIOR_PROMPT_VERSION,
            "engineVersion": EXTERIOR_DESIGN_ENGINE_VERSION,
        },
        "sourceVersions": source_versions,
    }
    context_hash = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()
    return payload, source_versions, context_hash
