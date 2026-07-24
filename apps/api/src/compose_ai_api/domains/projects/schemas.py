from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from compose_ai_api.domains.projects.models import (
    ConstructionQuality,
    PlotShape,
    ProjectStatus,
    ProjectType,
    RoadDirection,
    ThumbnailSource,
    UnitSystem,
    VastuPreference,
)


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class ProjectCreateRequest(CamelModel):
    name: str = Field(min_length=2, max_length=160)
    project_type: ProjectType | None = None
    unit_system: UnitSystem = UnitSystem.METRIC
    currency: str = Field(default="USD", min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    country: str | None = Field(default=None, min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Project name must contain at least two visible characters.")
        return normalized


class ProjectClientPatch(CamelModel):
    name: str | None = Field(default=None, max_length=160)
    company: str | None = Field(default=None, max_length=160)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32, pattern=r"^[0-9+().\-\s]*$")
    address: str | None = Field(default=None, max_length=1000)


class ProjectSitePatch(CamelModel):
    plot_length: Decimal | None = Field(default=None, gt=0, le=100000)
    plot_width: Decimal | None = Field(default=None, gt=0, le=100000)
    plot_area: Decimal | None = Field(default=None, gt=0, le=10000000000)
    plot_shape: PlotShape | None = None
    road_direction_primary: RoadDirection | None = None
    road_direction_secondary: RoadDirection | None = None
    open_sides: int | None = Field(default=None, ge=0, le=4)
    corner_plot: bool | None = None
    address_line_1: str | None = Field(default=None, max_length=255)
    address_line_2: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=120)
    region: str | None = Field(default=None, max_length=120)
    postal_code: str | None = Field(default=None, max_length=32)
    latitude: Decimal | None = Field(default=None, ge=-90, le=90)
    longitude: Decimal | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def validate_coordinates_and_roads(self) -> ProjectSitePatch:
        supplied = self.model_fields_set
        if ("latitude" in supplied) != ("longitude" in supplied):
            raise ValueError("Latitude and longitude must be supplied together.")
        if (
            self.road_direction_primary is not None
            and self.road_direction_primary == self.road_direction_secondary
        ):
            raise ValueError("Primary and secondary road directions must be different.")
        if self.corner_plot is True and self.open_sides is not None and self.open_sides < 2:
            raise ValueError("Corner plots require at least two open sides.")
        return self


class ProjectRequirementsPatch(CamelModel):
    bedrooms: int | None = Field(default=None, ge=0, le=50)
    bathrooms: Decimal | None = Field(default=None, ge=0, le=50, multiple_of=Decimal("0.5"))
    floors: int | None = Field(default=None, ge=1, le=100)
    parking_spaces: int | None = Field(default=None, ge=0, le=100)
    budget: Decimal | None = Field(default=None, ge=0, le=99999999999999)
    construction_quality: ConstructionQuality | None = None
    preferred_style: str | None = Field(default=None, max_length=80)
    vastu_preference: VastuPreference | None = None
    notes: str | None = Field(default=None, max_length=5000)


class ProjectRoomRequirementInput(CamelModel):
    id: UUID | None = None
    name: str = Field(min_length=1, max_length=80)
    room_type: str | None = Field(default=None, max_length=80)
    quantity: int = Field(default=1, ge=1, le=20)
    preferred_floor: int | None = Field(default=None, ge=-20, le=200)
    minimum_area: Decimal | None = Field(default=None, gt=0, le=1000000)
    notes: str | None = Field(default=None, max_length=1000)
    sort_order: int = Field(default=0, ge=0, le=1000)

    @field_validator("name")
    @classmethod
    def normalize_room_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Room name is required.")
        return normalized


class ProjectUpdateRequest(CamelModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    project_type: ProjectType | None = None
    description: str | None = Field(default=None, max_length=5000)
    unit_system: UnitSystem | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    country: str | None = Field(default=None, min_length=2, max_length=2, pattern=r"^[A-Z]{2}$")
    wizard_step: int | None = Field(default=None, ge=1, le=5)
    client: ProjectClientPatch | None = None
    site: ProjectSitePatch | None = None
    requirements: ProjectRequirementsPatch | None = None
    room_requirements: list[ProjectRoomRequirementInput] | None = Field(default=None, max_length=50)
    tags: list[str] | None = Field(default=None, max_length=10)

    @field_validator("name")
    @classmethod
    def normalize_optional_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if len(normalized) < 2:
            raise ValueError("Project name must contain at least two visible characters.")
        return normalized

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        result: list[str] = []
        seen: set[str] = set()
        for raw_tag in value:
            tag = " ".join(raw_tag.split())
            normalized = tag.casefold()
            if not tag or len(tag) > 30:
                raise ValueError("Tags must contain between 1 and 30 characters.")
            if normalized not in seen:
                seen.add(normalized)
                result.append(tag)
        return result


class ProjectDuplicateRequest(CamelModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)


class ProjectThumbnailResponse(CamelModel):
    source: ThumbnailSource
    url: str | None
    mime_type: str | None
    width: int | None
    height: int | None
    version: int
    generated_at: datetime | None
    metadata: dict[str, Any]


class ProjectClientResponse(CamelModel):
    name: str | None
    company: str | None
    email: str | None
    phone: str | None
    address: str | None


class ProjectSiteResponse(CamelModel):
    plot_length: Decimal | None
    plot_width: Decimal | None
    plot_area: Decimal | None
    plot_shape: PlotShape | None
    road_direction_primary: RoadDirection | None
    road_direction_secondary: RoadDirection | None
    open_sides: int
    corner_plot: bool
    address_line_1: str | None
    address_line_2: str | None
    city: str | None
    region: str | None
    postal_code: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    boundary_status: str
    orientation_degrees: Decimal | None
    north_rotation_degrees: Decimal | None
    north_reference: str | None
    profile_revision: int


class ProjectRequirementsResponse(CamelModel):
    bedrooms: int
    bathrooms: Decimal
    floors: int
    parking_spaces: int
    budget: Decimal | None
    construction_quality: ConstructionQuality | None
    preferred_style: str | None
    vastu_preference: VastuPreference
    notes: str | None


class ProjectRoomRequirementResponse(CamelModel):
    id: UUID
    name: str
    room_type: str | None
    quantity: int
    preferred_floor: int | None
    minimum_area: Decimal | None
    notes: str | None
    sort_order: int


class ProjectPlotSummaryResponse(CamelModel):
    completeness: int
    health_score: int
    health_status: str
    feasibility_status: str
    validation_error_count: int
    validation_warning_count: int
    pre_regulation_buildable_area: Decimal | None
    parking_status: str
    analysis_updated_at: datetime | None


class ProjectSummaryResponse(CamelModel):
    id: UUID
    organization_id: UUID
    name: str
    status: ProjectStatus
    project_type: ProjectType | None
    unit_system: UnitSystem
    currency: str
    country: str | None
    wizard_step: int
    profile_completeness: int
    version: int
    thumbnail: ProjectThumbnailResponse
    plot_summary: ProjectPlotSummaryResponse
    city: str | None
    tags: list[str]
    completed_at: datetime | None
    archived_at: datetime | None
    deleted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProjectDetailResponse(ProjectSummaryResponse):
    description: str | None
    client: ProjectClientResponse
    site: ProjectSiteResponse
    requirements: ProjectRequirementsResponse
    room_requirements: list[ProjectRoomRequirementResponse]
    duplicate_source_id: UUID | None


class ProjectDashboardSummaryResponse(CamelModel):
    active_count: int
    draft_count: int
    archived_count: int
    deleted_count: int
    used_project_slots: int


class ProjectActivityResponse(CamelModel):
    id: UUID
    project_id: UUID
    project_name: str
    action: str
    actor_name: str | None
    created_at: datetime
