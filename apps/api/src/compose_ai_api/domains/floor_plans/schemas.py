from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from compose_ai_api.domains.floor_plans.models import (
    FloorPlanOptionStatus,
    FloorPlanRunStatus,
    FloorPlanValidationStatus,
)

CONCEPTUAL_DISCLAIMER = "Conceptual Design — Not for Construction."


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(word.capitalize() for word in rest)


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FloorPlanFailureBudgetRequest(CamelModel):
    max_solver_attempts: int = Field(default=20, ge=1, le=100)
    max_provider_retries: int = Field(default=2, ge=0, le=10)
    max_processing_seconds: int = Field(default=180, ge=10, le=1800)
    max_invalid_candidates: int = Field(default=12, ge=1, le=100)


class FloorPlanUserConstraint(CamelModel):
    code: str = Field(min_length=2, max_length=80, pattern=r"^[A-Z][A-Z0-9_]+$")
    title: str = Field(min_length=2, max_length=160)
    category: str = Field(min_length=2, max_length=80)
    priority: Literal["hard", "preferred", "informational"]
    value: Any
    explanation: str = Field(min_length=4, max_length=800)


class FloorPlanGenerationRequest(CamelModel):
    option_count: int = Field(default=3, ge=3, le=5)
    deterministic_seed: int | None = Field(default=None, ge=0, le=9_223_372_036_854_775_807)
    preferred_style: str | None = Field(default=None, max_length=80)
    budget_mode: Literal["economy", "balanced", "premium"] = "balanced"
    vastu_preference: Literal["not_required", "preferred", "strict"] = "not_required"
    user_constraints: list[FloorPlanUserConstraint] = Field(default_factory=list, max_length=30)
    diversity_threshold: Decimal = Field(default=Decimal("0.250"), ge=0, le=1)
    failure_budget: FloorPlanFailureBudgetRequest = Field(
        default_factory=FloorPlanFailureBudgetRequest
    )

    @field_validator("preferred_style")
    @classmethod
    def normalize_style(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None

    @model_validator(mode="after")
    def unique_constraints(self) -> FloorPlanGenerationRequest:
        codes = [item.code for item in self.user_constraints]
        if len(codes) != len(set(codes)):
            raise ValueError("User constraint codes must be unique.")
        return self


class FloorPlanReadinessIssue(CamelModel):
    code: str
    severity: Literal["blocking", "warning"]
    message: str
    action_url: str | None = None


class FloorPlanReadinessResponse(CamelModel):
    ready: bool
    issues: list[FloorPlanReadinessIssue]
    project_id: UUID
    project_version: int
    approved_brief_id: UUID | None
    approved_brief_version: int | None
    memory_version_id: UUID | None
    boundary_version_id: UUID | None
    analysis_snapshot_id: UUID | None
    source_versions: dict[str, Any]
    buildable_area_m2: Decimal | None
    disclaimer: str = CONCEPTUAL_DISCLAIMER


class FloorPlanDecision(StrictModel):
    code: str = Field(min_length=2, max_length=80)
    title: str = Field(min_length=2, max_length=160)
    explanation: str = Field(min_length=8, max_length=1000)
    confidence: float = Field(ge=0, le=1)


class FloorPlanProgramRoom(StrictModel):
    key: str = Field(min_length=2, max_length=80)
    name: str = Field(min_length=2, max_length=80)
    room_type: str = Field(min_length=2, max_length=80)
    floor_index: int = Field(ge=0, le=99)
    target_area_m2: float = Field(gt=0, le=1000)
    minimum_width_m: float = Field(ge=0.9, le=30)
    zone: Literal["public", "private", "service", "circulation"]
    requires_exterior: bool = True
    adjacency_preferences: list[str] = Field(default_factory=list, max_length=12)


class FloorPlanProgramOutput(StrictModel):
    floors: int = Field(ge=1, le=100)
    rooms: list[FloorPlanProgramRoom] = Field(min_length=1, max_length=120)
    circulation_width_m: float = Field(default=1.2, ge=0.9, le=4)
    parking_spaces: int = Field(default=0, ge=0, le=100)
    entrance_side: Literal["north", "east", "south", "west"]
    major_decisions: list[FloorPlanDecision] = Field(min_length=1, max_length=20)
    warnings: list[dict[str, Any]] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def floor_indices_exist(self) -> FloorPlanProgramOutput:
        if any(room.floor_index >= self.floors for room in self.rooms):
            raise ValueError("Program room floor indices must exist in the program.")
        keys = [room.key for room in self.rooms]
        if len(keys) != len(set(keys)):
            raise ValueError("Program room keys must be unique.")
        return self


class ConstraintTraceItem(CamelModel):
    code: str
    category: str
    status: Literal["satisfied", "partially_satisfied", "violated"]
    severity: Literal["blocking", "warning", "informational"]
    target: Any | None = None
    actual: Any | None = None
    reason_code: str
    reason: str


class FloorPlanValidationResponse(CamelModel):
    status: FloorPlanValidationStatus
    validation_engine_version: str
    geometry_engine_version: str
    summary: dict[str, Any]
    checks: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]


class FloorPlanOptionSummaryResponse(CamelModel):
    id: UUID
    run_id: UUID
    option_number: int
    status: FloorPlanOptionStatus
    deterministic_seed: int
    title: str
    summary: str
    major_decisions: list[dict[str, Any]]
    constraint_trace: list[ConstraintTraceItem]
    area_summary: dict[str, Any]
    warnings: list[dict[str, Any]]
    confidence: Decimal
    topology_signature: str
    topology_features: dict[str, Any]
    diversity_score: Decimal
    version: int
    validation: FloorPlanValidationResponse
    created_at: datetime
    disclaimer: str = CONCEPTUAL_DISCLAIMER


class FloorPlanOptionResponse(FloorPlanOptionSummaryResponse):
    geometry_snapshot_id: UUID
    geometry_hash: str
    geometry_engine_version: str
    geometry: dict[str, Any]


class FloorPlanRunResponse(CamelModel):
    id: UUID
    project_id: UUID
    status: FloorPlanRunStatus
    requested_option_count: int
    completed_option_count: int
    deterministic_seed: int
    source_versions: dict[str, Any]
    engine_version: str
    solver_version: str
    geometry_engine_version: str
    provider: str
    model: str
    cache_hit: bool
    cache_source_run_id: UUID | None
    diversity_threshold: Decimal
    failure_budget: dict[str, int]
    failure_usage: dict[str, int]
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_microusd: int
    input_tokens: int
    output_tokens: int
    actual_cost_microusd: int
    failure_code: str | None
    failure_details: dict[str, Any] | None
    version: int
    progress_percent: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    disclaimer: str = CONCEPTUAL_DISCLAIMER


class FloorPlanGenerationAcceptedResponse(CamelModel):
    run: FloorPlanRunResponse
    job_id: UUID
    status_url: str
    events_url: str


class FloorPlanCompareRequest(CamelModel):
    option_ids: list[UUID] = Field(min_length=2, max_length=5)

    @field_validator("option_ids")
    @classmethod
    def unique_options(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("Comparison option IDs must be unique.")
        return value


class FloorPlanComparisonMetric(CamelModel):
    code: str
    label: str
    values: dict[str, Any]
    best_option_id: UUID | None = None


class FloorPlanCompareResponse(CamelModel):
    options: list[FloorPlanOptionSummaryResponse]
    metrics: list[FloorPlanComparisonMetric]
    disclaimer: str = CONCEPTUAL_DISCLAIMER


class FloorPlanAcceptRequest(CamelModel):
    name: str | None = Field(default=None, max_length=160)
    confirmation: Literal["conceptual_design_reviewed"]

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class FloorPlanRestoreVersionRequest(CamelModel):
    name: str | None = Field(default=None, max_length=160)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        return normalized or None


class FloorPlanRejectRequest(CamelModel):
    reason: str = Field(min_length=4, max_length=1000)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return " ".join(value.split())


class FloorPlanDesignVersionResponse(CamelModel):
    id: UUID
    project_id: UUID
    source_run_id: UUID
    source_option_id: UUID
    geometry_snapshot_id: UUID
    validation_result_id: UUID
    restored_from_design_version_id: UUID | None
    version: int
    name: str
    geometry_hash: str
    source_versions: dict[str, Any]
    engine_versions: dict[str, Any]
    version_metadata: dict[str, Any]
    source_provider: str
    source_model: str
    generation_cost_microusd: int
    generation_time_ms: int | None
    disclaimer: str
    accepted_at: datetime
    created_at: datetime


class FloorPlanRunEventResponse(CamelModel):
    id: UUID
    run_id: UUID
    sequence: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime
