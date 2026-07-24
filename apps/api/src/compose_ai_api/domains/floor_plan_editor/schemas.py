from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from compose_ai_api.domains.floor_plans.schemas import CONCEPTUAL_DISCLAIMER


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


EditorToolId = Literal[
    "select",
    "pan",
    "wall",
    "room",
    "door",
    "window",
    "stair",
    "dimension",
    "label",
]

EditorObjectType = Literal[
    "floor",
    "room",
    "wall",
    "opening",
    "stair",
    "dimension",
    "label",
    "furniture_placeholder",
    "structural_placeholder",
]

EditorOperationType = Literal[
    "wall.create",
    "wall.move",
    "room.create",
    "room.update",
    "opening.create",
    "opening.update",
    "stair.create",
    "object.update",
    "object.delete",
    "label.update",
    "dimension.create",
    "snapshot.replace",
]

ValidationSeverity = Literal["info", "warning", "error", "blocking"]


class EditorPoint(CamelModel):
    x: float
    y: float


class EditorBounds(CamelModel):
    min_x: float
    min_y: float
    max_x: float
    max_y: float


class EditorLayer(CamelModel):
    id: str
    label: str
    visible: bool = True
    locked: bool = False
    object_count: int = 0


class EditorViewportState(CamelModel):
    zoom: float = Field(default=1, ge=0.1, le=8)
    pan_x: float = 0
    pan_y: float = 0
    active_floor_id: str | None = None
    selected_object_ids: list[str] = Field(default_factory=list, max_length=100)
    active_tool: EditorToolId = "select"
    snap_enabled: bool = True
    grid_visible: bool = True


class EditorSnapSettings(CamelModel):
    enabled: bool = True
    grid: bool = True
    corner: bool = True
    wall_intersection: bool = True
    parallel: bool = True
    perpendicular: bool = True
    center: bool = True
    equal_spacing_guides: bool = True


class EditorMeasurementOverlay(CamelModel):
    length: float | None = None
    angle: float | None = None
    distance: float | None = None
    area: float | None = None
    unit: str = "mm"


class EditorToolDefinition(CamelModel):
    id: EditorToolId
    label: str
    shortcut: str | None = None
    cursor: str = "default"
    plugin_key: str
    supported_object_types: list[EditorObjectType] = Field(default_factory=list)


class EditorObject(CamelModel):
    id: str
    type: EditorObjectType
    floor_id: str
    layer_id: str
    name: str | None = None
    points: list[EditorPoint] = Field(default_factory=list)
    wall_id: str | None = None
    position: float | None = None
    width: float | None = None
    height: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    revision_created: int = Field(ge=0)
    revision_updated: int = Field(ge=0)
    deleted: bool = False


class EditorFloor(CamelModel):
    id: str
    index: int = Field(ge=0)
    name: str
    elevation_mm: float = 0
    bounds: EditorBounds


class EditorValidationIssue(CamelModel):
    id: str
    code: str
    severity: ValidationSeverity
    object_id: str | None = None
    object_type: EditorObjectType | None = None
    message: str
    reason: str
    blocking: bool = False


class EditorValidationSummary(CamelModel):
    status: Literal["valid", "invalid"]
    issue_count: int = Field(ge=0)
    blocking_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    info_count: int = Field(ge=0)


class EditorSnapshot(CamelModel):
    schema_version: str
    unit: str
    coordinate_space: str
    floors: list[EditorFloor]
    objects: list[EditorObject]
    layers: list[EditorLayer]
    snap_settings: EditorSnapSettings = Field(default_factory=EditorSnapSettings)
    measurement_overlay: EditorMeasurementOverlay | None = None
    source: dict[str, Any] = Field(default_factory=dict)


class EditorOperation(CamelModel):
    client_operation_id: str = Field(min_length=8, max_length=120)
    type: EditorOperationType
    object_id: str | None = Field(default=None, max_length=120)
    payload: dict[str, Any]
    created_at: datetime


class EditorOperationBatchRequest(CamelModel):
    base_revision: int = Field(ge=0)
    client_batch_id: str = Field(min_length=8, max_length=120)
    operations: list[EditorOperation] = Field(min_length=1, max_length=100)

    @field_validator("operations")
    @classmethod
    def unique_operations(cls, value: list[EditorOperation]) -> list[EditorOperation]:
        operation_ids = [operation.client_operation_id for operation in value]
        if len(operation_ids) != len(set(operation_ids)):
            raise ValueError("Operation IDs must be unique inside a batch.")
        return value


class EditorOperationBatchResponse(CamelModel):
    project_id: UUID
    editor_document_id: UUID
    previous_revision: int
    current_revision: int
    applied_operation_ids: list[str]
    validation_summary: EditorValidationSummary
    snapshot_hash: str


class EditorValidationRequest(CamelModel):
    snapshot: EditorSnapshot | None = None


class EditorValidationResponse(CamelModel):
    project_id: UUID
    editor_document_id: UUID
    revision: int
    validation_engine_version: str
    geometry_engine_version: str
    summary: EditorValidationSummary
    issues: list[EditorValidationIssue]


class EditorCheckpointCreateRequest(CamelModel):
    name: str = Field(min_length=2, max_length=160)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return " ".join(value.split())


class EditorCheckpointResponse(CamelModel):
    id: UUID
    project_id: UUID
    editor_document_id: UUID
    source_revision: int
    name: str
    kind: str
    snapshot_hash: str
    validation_summary: EditorValidationSummary
    metadata: dict[str, Any]
    created_at: datetime


class EditorHistoryItem(CamelModel):
    id: UUID
    item_type: Literal["operation_batch", "checkpoint"]
    title: str
    revision: int
    operation_count: int = 0
    checkpoint_kind: str | None = None
    created_at: datetime


class EditorHistoryResponse(CamelModel):
    items: list[EditorHistoryItem]


class EditorDocumentResponse(CamelModel):
    id: UUID
    project_id: UUID
    source_design_version_id: UUID
    source_geometry_snapshot_id: UUID
    status: str
    current_revision: int
    schema_version: str
    renderer_contract_version: str
    snapshot_hash: str
    snapshot: EditorSnapshot
    validation_summary: EditorValidationSummary
    validation_issues: list[EditorValidationIssue]
    view_state: EditorViewportState
    layers: list[EditorLayer]
    tool_registry: list[EditorToolDefinition]
    inspector_tabs: list[Literal["properties", "validation", "metadata", "history"]]
    history: list[EditorHistoryItem]
    autosave: dict[str, Any]
    disclaimer: str = CONCEPTUAL_DISCLAIMER
    updated_at: datetime


class EditorDesignVersionCreateRequest(CamelModel):
    checkpoint_id: UUID
    name: str | None = Field(default=None, max_length=160)
    confirmation: Literal["conceptual_editor_checkpoint_reviewed"]

    @model_validator(mode="after")
    def normalize_name(self) -> EditorDesignVersionCreateRequest:
        if self.name is not None:
            self.name = " ".join(self.name.split()) or None
        return self
