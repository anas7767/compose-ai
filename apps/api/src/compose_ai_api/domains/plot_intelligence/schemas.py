from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from compose_ai_api.domains.plot_intelligence.models import (
    BoundarySource,
    CoordinateSpace,
    NorthReference,
)
from compose_ai_api.domains.projects.models import PlotShape, RoadDirection, UnitSystem


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class PlotRoadSideInput(CamelModel):
    id: UUID | None = None
    boundary_edge_index: int | None = Field(default=None, ge=0, le=499)
    label: str = Field(min_length=1, max_length=40)
    direction: RoadDirection
    is_primary: bool = False
    road_name: str | None = Field(default=None, max_length=120)
    road_width: Decimal | None = Field(default=None, gt=0, le=1000)
    access_allowed: bool = True
    sort_order: int = Field(default=0, ge=0, le=3)

    @field_validator("label")
    @classmethod
    def normalize_label(cls, value: str) -> str:
        return " ".join(value.split())


class PlotBoundaryInput(CamelModel):
    coordinate_space: CoordinateSpace
    geojson: dict[str, Any]
    source: BoundarySource = BoundarySource.MANUAL_VERTICES

    @field_validator("source")
    @classmethod
    def allow_user_sources(cls, value: BoundarySource) -> BoundarySource:
        if value not in {BoundarySource.MANUAL_VERTICES, BoundarySource.GEOJSON_IMPORT}:
            raise ValueError("Only manual vertices and GeoJSON import are accepted from clients.")
        return value


class PlotProfileUpdateRequest(CamelModel):
    unit_system: UnitSystem | None = None
    plot_length: Decimal | None = Field(default=None, gt=0, le=1000000)
    plot_width: Decimal | None = Field(default=None, gt=0, le=1000000)
    plot_area: Decimal | None = Field(default=None, gt=0, le=10000000000)
    plot_shape: PlotShape | None = None
    open_sides: int | None = Field(default=None, ge=0, le=4)
    corner_plot: bool | None = None
    orientation_degrees: Decimal | None = Field(default=None, ge=0, lt=360)
    north_rotation_degrees: Decimal | None = Field(default=None, ge=0, lt=360)
    north_reference: NorthReference | None = None
    road_sides: list[PlotRoadSideInput] | None = Field(default=None, max_length=4)
    boundary: PlotBoundaryInput | None = None

    @model_validator(mode="after")
    def validate_road_collection(self) -> PlotProfileUpdateRequest:
        if self.road_sides is None:
            return self
        ids = [road.id for road in self.road_sides if road.id is not None]
        if len(ids) != len(set(ids)):
            raise ValueError("Road-side identifiers must be unique.")
        directions = [road.direction for road in self.road_sides]
        if len(directions) != len(set(directions)):
            raise ValueError("Road-side directions must be unique.")
        if self.road_sides and sum(road.is_primary for road in self.road_sides) != 1:
            raise ValueError("Exactly one road side must be primary.")
        return self


class PlotValidationRequest(PlotProfileUpdateRequest):
    pass


class PlotValidationIssueResponse(CamelModel):
    code: str
    severity: str
    field: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class PlotRoadSideResponse(CamelModel):
    id: UUID
    boundary_edge_index: int | None
    label: str
    direction: str
    is_primary: bool
    road_name: str | None
    road_width: Decimal | None
    access_allowed: bool
    sort_order: int


class PlotBoundaryVersionResponse(CamelModel):
    id: UUID
    version: int
    previous_boundary_version_id: UUID | None
    restored_from_version_id: UUID | None
    coordinate_space: str
    geojson: dict[str, Any] | None
    is_tombstone: bool
    source: str
    schema_version: int
    geometry_engine_version: str
    checksum: str
    vertex_count: int
    area: Decimal | None
    perimeter: Decimal | None
    bounding_box: dict[str, Any] | None
    centroid: dict[str, Any] | None
    validation_status: str
    validation_details: list[dict[str, Any]]
    created_by: UUID | None
    created_at: datetime


class PlotAnalysisResponse(CamelModel):
    id: UUID | None
    profile_revision: int
    boundary_version_id: UUID | None
    analysis_engine_version: str
    geometry_engine_version: str
    input_checksum: str
    plot_completeness: int
    plot_health_score: int
    plot_health_status: str
    feasibility_status: str
    pre_regulation_buildable_area: Decimal | None
    parking_status: str
    parking_confidence: str
    parking_details: dict[str, Any]
    coverage_status: str
    coverage_details: dict[str, Any]
    regulation_status: str
    regulation_context: dict[str, Any]
    validation_summary: dict[str, Any]
    site_summary: dict[str, Any]
    issues: list[PlotValidationIssueResponse]
    created_at: datetime | None


class PlotUndoActionResponse(CamelModel):
    id: UUID
    restored_boundary_version_id: UUID
    previous_active_boundary_version_id: UUID | None
    expires_at: datetime


class PlotProfileResponse(CamelModel):
    unit_system: str
    plot_length: Decimal | None
    plot_width: Decimal | None
    plot_area: Decimal | None
    area_source: str
    plot_shape: str | None
    open_sides: int
    corner_plot: bool
    orientation_degrees: Decimal | None
    north_rotation_degrees: Decimal | None
    north_reference: str | None
    profile_revision: int


class PlotIntelligenceResponse(CamelModel):
    project_id: UUID
    project_name: str
    project_version: int
    can_edit: bool
    profile: PlotProfileResponse
    road_sides: list[PlotRoadSideResponse]
    boundary: PlotBoundaryVersionResponse | None
    analysis: PlotAnalysisResponse
    active_undo: PlotUndoActionResponse | None


class PlotRestoreResponse(CamelModel):
    plot: PlotIntelligenceResponse
    undo: PlotUndoActionResponse
