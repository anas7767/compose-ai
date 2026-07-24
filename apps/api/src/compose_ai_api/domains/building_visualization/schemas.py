from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from compose_ai_api.domains.floor_plans.schemas import CONCEPTUAL_DISCLAIMER


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


SceneStatus = Literal["active", "stale", "archived"]
SceneJobStatus = Literal[
    "queued",
    "validating_source",
    "compiling_geometry",
    "generating_materials",
    "validating_scene",
    "saving_scene",
    "completed",
    "failed",
    "cancelled",
]
SceneObjectKind = Literal[
    "building",
    "floor",
    "room",
    "wall",
    "door",
    "window",
    "stair",
    "slab",
    "roof",
    "balcony",
    "parking",
    "plot_boundary",
]
MaterialCategory = Literal[
    "paint",
    "brick",
    "concrete",
    "marble",
    "granite",
    "wood",
    "glass",
    "metal",
    "tiles",
]
ValidationSeverity = Literal["info", "warning", "error", "blocking"]
EnvironmentPreset = Literal["morning", "noon", "evening", "night"]
QualityPreset = Literal["low", "balanced", "high"]


class SceneVector3(CamelModel):
    x: float
    y: float
    z: float


class SceneBoundingBox(CamelModel):
    min: SceneVector3
    max: SceneVector3


class SceneTransform(CamelModel):
    position: SceneVector3
    rotation: SceneVector3
    scale: SceneVector3 = Field(default_factory=lambda: SceneVector3(x=1, y=1, z=1))


class SceneGeometry(CamelModel):
    kind: Literal["box", "extrusion", "plane", "polyline", "placeholder"]
    vertices: list[SceneVector3] = Field(default_factory=list)
    indices: list[int] = Field(default_factory=list)
    dimensions: dict[str, float] = Field(default_factory=dict)
    source_polygon: list[dict[str, float]] = Field(default_factory=list)


class SceneMaterial(CamelModel):
    material_id: str
    name: str
    category: MaterialCategory
    color: str
    opacity: float = Field(default=1, ge=0, le=1)
    roughness: float = Field(default=0.75, ge=0, le=1)
    metalness: float = Field(default=0, ge=0, le=1)
    transparent: bool = False
    properties: dict[str, Any] = Field(default_factory=dict)


class SceneObject(CamelModel):
    id: UUID
    stable_object_id: str
    source_2d_object_id: str | None = None
    source_2d_object_type: str | None = None
    object_type: SceneObjectKind
    floor_id: str | None = None
    parent_object_id: str | None = None
    name: str
    geometry_kind: str
    transform: SceneTransform
    geometry: SceneGeometry
    bounding_box: SceneBoundingBox
    material_id: str
    triangle_count: int = Field(ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SceneCamera(CamelModel):
    position: SceneVector3
    target: SceneVector3
    fov: float = Field(default=45, ge=15, le=90)


class SceneCameraPreset(CamelModel):
    id: str
    label: str
    camera: SceneCamera


class SceneLighting(CamelModel):
    environment_preset: EnvironmentPreset = "noon"
    ambient_intensity: float = Field(ge=0, le=5)
    sun_intensity: float = Field(ge=0, le=10)
    sun_direction: SceneVector3
    background: str


class SceneClipBox(CamelModel):
    enabled: bool = False
    min_x: float | None = None
    max_x: float | None = None
    min_y: float | None = None
    max_y: float | None = None
    min_z: float | None = None
    max_z: float | None = None


class SceneGraphNode(CamelModel):
    id: str
    label: str
    object_type: str
    source_2d_object_id: str | None = None
    children: list[SceneGraphNode] = Field(default_factory=list)


class SceneValidationIssue(CamelModel):
    id: str
    code: str
    severity: ValidationSeverity
    object_id: str | None = None
    source_2d_object_id: str | None = None
    message: str
    reason: str
    blocking: bool = False


class SceneValidationSummary(CamelModel):
    status: Literal["valid", "invalid"]
    issue_count: int = Field(ge=0)
    blocking_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    info_count: int = Field(ge=0)


class SceneManifest(CamelModel):
    scene_version_id: UUID
    project_id: UUID
    source_design_version_id: UUID
    source_editor_document_id: UUID
    source_editor_checkpoint_id: UUID
    source_editor_revision: int
    scene_schema_version: str
    geometry_engine_version: str
    scene_engine_version: str
    material_schema_version: str
    renderer_contract_version: str
    unit: str
    coordinate_space: str
    bounding_box: SceneBoundingBox
    object_count: int
    triangle_count: int
    camera_presets: list[SceneCameraPreset]
    lighting: SceneLighting
    environment_presets: list[EnvironmentPreset]
    quality_presets: list[QualityPreset]
    section_box: SceneClipBox
    source_versions: dict[str, Any]
    disclaimer: str = CONCEPTUAL_DISCLAIMER


class SceneVersionResponse(CamelModel):
    id: UUID
    project_id: UUID
    version: int
    status: SceneStatus
    is_stale: bool
    manifest: SceneManifest
    validation_summary: SceneValidationSummary
    created_at: datetime
    updated_at: datetime
    disclaimer: str = CONCEPTUAL_DISCLAIMER


class SceneWorkspaceResponse(CamelModel):
    project_id: UUID
    active_scene: SceneVersionResponse | None = None
    latest_job: SceneCompilationJobResponse | None = None
    has_validated_checkpoint: bool
    source_checkpoint_id: UUID | None = None
    source_editor_revision: int | None = None
    is_stale: bool
    material_library: list[SceneMaterial]
    scene_graph: list[SceneGraphNode]
    empty_reason: str | None = None
    disclaimer: str = CONCEPTUAL_DISCLAIMER


class SceneCompileRequest(CamelModel):
    checkpoint_id: UUID | None = None
    quality_preset: QualityPreset = "balanced"


class SceneCompilationJobResponse(CamelModel):
    id: UUID
    project_id: UUID
    status: SceneJobStatus
    progress: int = Field(ge=0, le=100)
    source_editor_checkpoint_id: UUID
    source_editor_revision: int
    scene_version_id: UUID | None = None
    failure_code: str | None = None
    failure_details: dict[str, Any] | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None


class SceneObjectsResponse(CamelModel):
    scene_version_id: UUID
    objects: list[SceneObject]
    graph: list[SceneGraphNode]


class SceneMaterialsResponse(CamelModel):
    scene_version_id: UUID
    materials: list[SceneMaterial]
    library: list[SceneMaterial]


class SceneCameraViewCreateRequest(CamelModel):
    name: str = Field(min_length=2, max_length=120)
    camera: SceneCamera

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.split())


class SceneCameraViewResponse(CamelModel):
    id: UUID
    scene_version_id: UUID
    name: str
    camera: SceneCamera
    created_at: datetime


class SceneCameraViewsResponse(CamelModel):
    views: list[SceneCameraViewResponse]


class SceneValidationResponse(CamelModel):
    scene_version_id: UUID | None = None
    compilation_job_id: UUID | None = None
    validation_engine_version: str
    geometry_engine_version: str
    summary: SceneValidationSummary
    issues: list[SceneValidationIssue]
