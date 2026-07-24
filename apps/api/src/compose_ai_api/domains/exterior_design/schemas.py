from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from compose_ai_api.domains.exterior_design.constants import (
    CONCEPTUAL_DISCLAIMER,
    MATERIAL_CATEGORIES,
)


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        from_attributes=True,
    )


ExteriorDesignRunStatus = Literal[
    "pending",
    "queued",
    "running",
    "succeeded",
    "partially_succeeded",
    "failed",
    "cancelled",
    "rate_limited",
    "timed_out",
]
ExteriorDesignStyle = Literal[
    "modern",
    "contemporary",
    "minimal",
    "traditional",
    "tropical",
    "colonial",
    "industrial",
]
ExteriorDesignViewType = Literal["front", "left", "right", "rear"]
ExteriorApprovalStatus = Literal["pending", "approved", "rejected"]
ExteriorOptionStatus = Literal["generated", "valid", "invalid", "approved", "rejected", "hidden"]
ExteriorValidationStatus = Literal["valid", "invalid"]
ExteriorMaterialCategory = Literal[
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


class ExteriorReadinessIssue(CamelModel):
    code: str
    severity: Literal["blocking", "warning"]
    message: str
    action_url: str | None = None


class ExteriorReadinessResponse(CamelModel):
    ready: bool
    project_id: UUID
    source_design_version_id: UUID | None = None
    source_scene_version_id: UUID | None = None
    source_editor_checkpoint_id: UUID | None = None
    source_brief_id: UUID | None = None
    material_library: list[ExteriorMaterialCategory]
    supported_styles: list[ExteriorDesignStyle]
    supported_views: list[ExteriorDesignViewType]
    issues: list[ExteriorReadinessIssue]
    disclaimer: str = CONCEPTUAL_DISCLAIMER


class ExteriorGenerationRequest(CamelModel):
    style: ExteriorDesignStyle
    view_type: ExteriorDesignViewType = "front"
    material_preferences: list[ExteriorMaterialCategory] = Field(default_factory=list, max_length=9)
    option_count: int = Field(default=1, ge=1, le=4)
    user_instructions: str | None = Field(default=None, max_length=1500)
    negative_constraints: str | None = Field(default=None, max_length=1000)
    seed: int | None = Field(default=None, ge=0)

    @field_validator("view_type")
    @classmethod
    def phase_10a_front_only(cls, value: str) -> str:
        if value != "front":
            raise ValueError("Only front elevation generation is supported in Phase 10A.")
        return value

    @field_validator("material_preferences")
    @classmethod
    def normalize_materials(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in values:
            if value not in MATERIAL_CATEGORIES:
                raise ValueError(f"Unsupported material preference: {value}")
            if value not in normalized:
                normalized.append(value)
        return normalized

    @field_validator("user_instructions", "negative_constraints")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class ExteriorAsset(CamelModel):
    id: UUID
    option_id: UUID
    storage_provider: str
    storage_key: str
    thumbnail_storage_key: str | None = None
    mime_type: str
    width: int
    height: int
    byte_size: int
    integrity_hash: str
    delivery_reference: str
    created_at: datetime


class ExteriorValidationResult(CamelModel):
    id: UUID
    option_id: UUID
    status: ExteriorValidationStatus
    validation_engine_version: str
    summary: dict[str, Any]
    issues: list[dict[str, Any]]
    created_at: datetime


class ExteriorOption(CamelModel):
    id: UUID
    run_id: UUID
    project_id: UUID
    option_number: int
    style: ExteriorDesignStyle
    view_type: ExteriorDesignViewType
    title: str
    explanation: str
    status: ExteriorOptionStatus
    approval_status: ExteriorApprovalStatus
    is_conceptual: bool
    disclaimer: str
    source_design_version_id: UUID
    source_scene_version_id: UUID
    source_editor_checkpoint_id: UUID
    source_versions: dict[str, Any]
    safety_metadata: dict[str, Any]
    asset: ExteriorAsset | None = None
    validation: ExteriorValidationResult | None = None
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None = None
    rejected_at: datetime | None = None
    deleted_at: datetime | None = None


class ExteriorRun(CamelModel):
    id: UUID
    project_id: UUID
    status: ExteriorDesignRunStatus
    provider: str
    model: str
    prompt_version: str
    engine_version: str
    requested_option_count: int
    completed_option_count: int
    style: ExteriorDesignStyle
    view_type: ExteriorDesignViewType
    material_preferences: list[ExteriorMaterialCategory]
    seed: int | None = None
    cache_hit: bool
    cache_source_run_id: UUID | None = None
    failure_code: str | None = None
    safe_failure_message: str | None = None
    input_tokens: int
    output_tokens: int
    cost_microusd: int
    source_design_version_id: UUID
    source_scene_version_id: UUID
    source_editor_checkpoint_id: UUID
    context_hash: str
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    cancelled_at: datetime | None = None
    disclaimer: str = CONCEPTUAL_DISCLAIMER


class ExteriorRunDetail(ExteriorRun):
    options: list[ExteriorOption] = Field(default_factory=list)


class ExteriorRunEvent(CamelModel):
    id: UUID
    run_id: UUID
    sequence: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime


class ExteriorGenerationAccepted(CamelModel):
    run: ExteriorRun
    status_url: str
    events_url: str


class ExteriorOptionActionRequest(CamelModel):
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None
