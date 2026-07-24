from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from compose_ai_api.domains.ai_architect.models import (
    AIBriefStatus,
    AIMessageMode,
    AIMessageRole,
    AIMessageStatus,
    AIProposalStatus,
    AIProposalTarget,
    AIRunStatus,
    AIRunType,
    AIThreadStatus,
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


class StrictAIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceReference(StrictAIModel):
    source_type: Literal[
        "user_input",
        "project",
        "requirements",
        "room_requirement",
        "site",
        "plot_analysis",
        "conversation",
        "approved_brief",
    ]
    source_id: str | None = None
    field_path: str | None = None
    excerpt: str | None = Field(default=None, max_length=300)


class BriefGoal(StrictAIModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=800)
    confidence: float = Field(ge=0, le=1)
    source_references: list[SourceReference] = Field(min_length=1, max_length=8)


class BriefPriority(StrictAIModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=800)
    rank: int = Field(ge=1, le=20)
    category: str = Field(min_length=1, max_length=80)
    confirmed: bool
    confidence: float = Field(ge=0, le=1)
    source_references: list[SourceReference] = Field(min_length=1, max_length=8)


class BriefConstraint(StrictAIModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=800)
    category: str = Field(min_length=1, max_length=80)
    constraint_type: Literal["hard", "preferred", "informational", "unresolved"]
    confidence: float = Field(ge=0, le=1)
    source_references: list[SourceReference] = Field(min_length=1, max_length=8)


class NormalizedArea(StrictAIModel):
    original_value: float | None = Field(default=None, ge=0)
    original_unit: str | None = Field(default=None, max_length=24)
    normalized_value: float | None = Field(default=None, ge=0)
    normalized_unit: Literal["square_meter", "square_foot"] | None = None


class NormalizedRoom(StrictAIModel):
    original_name: str = Field(min_length=1, max_length=80)
    canonical_name: str = Field(min_length=1, max_length=80)
    canonical_type: str = Field(min_length=1, max_length=80)
    quantity: int = Field(ge=1, le=20)
    preferred_floors: list[int] = Field(default_factory=list, max_length=20)
    minimum_area: NormalizedArea | None = None
    notes: str | None = Field(default=None, max_length=1000)
    confidence: float = Field(ge=0, le=1)
    warnings: list[str] = Field(default_factory=list, max_length=10)
    source_references: list[SourceReference] = Field(min_length=1, max_length=8)


class NormalizedBudget(StrictAIModel):
    minimum: float | None = Field(default=None, ge=0)
    maximum: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    confidence: float = Field(ge=0, le=1)
    source_references: list[SourceReference] = Field(default_factory=list, max_length=8)


class NormalizedRequirements(StrictAIModel):
    bedrooms: int | None = Field(default=None, ge=0, le=50)
    bathrooms: float | None = Field(default=None, ge=0, le=50)
    floors: int | None = Field(default=None, ge=1, le=100)
    parking_spaces: int | None = Field(default=None, ge=0, le=100)
    budget: NormalizedBudget | None = None
    construction_quality: Literal["economy", "standard", "premium", "luxury"] | None = None
    preferred_style: str | None = Field(default=None, max_length=80)
    vastu_preference: Literal["not_required", "preferred", "strict"] | None = None
    rooms: list[NormalizedRoom] = Field(default_factory=list, max_length=50)
    site_constraints: list[str] = Field(default_factory=list, max_length=30)


class MissingInformation(StrictAIModel):
    topic: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=1, max_length=800)
    blocking: bool
    priority: Literal["high", "medium", "low"]
    expected_answer: str = Field(min_length=1, max_length=300)
    target_path: str | None = Field(default=None, max_length=255)


class BriefConflict(StrictAIModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=1000)
    severity: Literal["blocking", "warning", "informational"]
    suggested_resolution: str = Field(min_length=1, max_length=800)
    affected_paths: list[str] = Field(default_factory=list, max_length=10)
    source_references: list[SourceReference] = Field(min_length=2, max_length=10)


class ClarificationQuestion(StrictAIModel):
    question: str = Field(min_length=1, max_length=500)
    reason: str = Field(min_length=1, max_length=500)
    priority: int = Field(ge=1, le=20)
    target_path: str | None = Field(default=None, max_length=255)


class RecommendedNextStep(StrictAIModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(min_length=1, max_length=800)
    priority: int = Field(ge=1, le=20)


class BriefWarning(StrictAIModel):
    code: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=800)
    target_path: str | None = Field(default=None, max_length=255)


class BriefAssumption(StrictAIModel):
    statement: str = Field(min_length=1, max_length=800)
    reason: str = Field(min_length=1, max_length=500)
    confidence: float = Field(ge=0, le=1)


class AIProposalOutput(StrictAIModel):
    target_type: AIProposalTarget
    target_path: str = Field(min_length=1, max_length=255)
    proposed_value: Any
    explanation: str = Field(min_length=8, max_length=1000)
    confidence: float = Field(ge=0, le=1)
    source_references: list[SourceReference] = Field(min_length=1, max_length=10)
    warnings: list[BriefWarning] = Field(default_factory=list, max_length=10)


class ArchitectBriefOutput(StrictAIModel):
    summary: str = Field(min_length=1, max_length=3000)
    goals: list[BriefGoal] = Field(default_factory=list, max_length=20)
    priorities: list[BriefPriority] = Field(default_factory=list, max_length=20)
    constraints: list[BriefConstraint] = Field(default_factory=list, max_length=30)
    normalized_requirements: NormalizedRequirements
    missing_information: list[MissingInformation] = Field(default_factory=list, max_length=30)
    conflicts: list[BriefConflict] = Field(default_factory=list, max_length=20)
    clarification_questions: list[ClarificationQuestion] = Field(default_factory=list, max_length=8)
    recommended_next_steps: list[RecommendedNextStep] = Field(default_factory=list, max_length=12)
    warnings: list[BriefWarning] = Field(default_factory=list, max_length=20)
    assumptions: list[BriefAssumption] = Field(default_factory=list, max_length=20)
    aggregate_confidence: float = Field(ge=0, le=1)
    proposals: list[AIProposalOutput] = Field(default_factory=list, max_length=80)


class AIThreadCreateRequest(CamelModel):
    title: str = Field(default="New conversation", min_length=1, max_length=160)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Conversation title is required.")
        return normalized


class AIThreadUpdateRequest(CamelModel):
    title: str = Field(min_length=1, max_length=160)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Conversation title is required.")
        return normalized


class AIThreadResponse(CamelModel):
    id: UUID
    project_id: UUID
    title: str
    status: AIThreadStatus
    version: int
    message_count: int
    last_message_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AIMessageCreateRequest(CamelModel):
    content: str = Field(min_length=1, max_length=12_000)
    mode: AIMessageMode = AIMessageMode.ADVICE
    client_message_id: str = Field(min_length=8, max_length=80)

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Message content is required.")
        return normalized


class AIMessageResponse(CamelModel):
    id: UUID
    thread_id: UUID
    run_id: UUID | None
    role: AIMessageRole
    mode: AIMessageMode
    sequence_number: int
    content: str
    status: AIMessageStatus
    created_at: datetime


class AIRunResponse(CamelModel):
    id: UUID
    project_id: UUID
    thread_id: UUID | None
    run_type: AIRunType
    status: AIRunStatus
    provider: str
    model_alias: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_microusd: int
    input_tokens: int
    output_tokens: int
    actual_cost_microusd: int
    cache_hit: bool
    failure_code: str | None
    failure_details: dict[str, Any] | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class AIMessageAcceptedResponse(CamelModel):
    message: AIMessageResponse
    run: AIRunResponse
    stream_url: str


class AIBriefGenerateRequest(CamelModel):
    raw_requirements: str = Field(min_length=10, max_length=30_000)
    thread_id: UUID | None = None

    @field_validator("raw_requirements")
    @classmethod
    def normalize_requirements(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 10:
            raise ValueError("Provide at least ten characters of project requirements.")
        return normalized


class AIBriefAcceptedResponse(CamelModel):
    run: AIRunResponse
    job_id: UUID
    status_url: str


class AIRunRetryResponse(CamelModel):
    run: AIRunResponse
    job_id: UUID | None
    stream_url: str | None


class AIProposalResponse(CamelModel):
    id: UUID
    brief_version_id: UUID
    target_type: AIProposalTarget
    target_path: str
    existing_value: Any | None
    proposed_value: Any
    explanation: str
    confidence: Decimal
    source_references: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    status: AIProposalStatus
    expected_project_version: int
    reviewed_at: datetime | None
    applied_at: datetime | None


class AIBriefResponse(CamelModel):
    id: UUID
    project_id: UUID
    version: int
    source_run_id: UUID
    status: AIBriefStatus
    original_input: str
    summary: str
    goals: list[dict[str, Any]]
    priorities: list[dict[str, Any]]
    constraints: list[dict[str, Any]]
    normalized_requirements: dict[str, Any]
    missing_information: list[dict[str, Any]]
    conflicts: list[dict[str, Any]]
    clarification_questions: list[dict[str, Any]]
    recommended_next_steps: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    assumptions: list[dict[str, Any]]
    aggregate_confidence: Decimal
    based_on_project_version: int
    approved_at: datetime | None
    applied_at: datetime | None
    created_at: datetime
    proposals: list[AIProposalResponse]


class AIProposalApplyRequest(CamelModel):
    proposal_ids: list[UUID] = Field(min_length=1, max_length=80)


class AIProposalApplyResponse(CamelModel):
    project_id: UUID
    project_version: int
    applied_proposal_ids: list[UUID]
    brief_status: AIBriefStatus


class AIMemoryResponse(CamelModel):
    id: UUID
    version: int
    project_version: int
    context_summary: str
    included_sources: list[dict[str, Any]]
    redaction_summary: dict[str, Any]
    token_estimate: int
    context_hash: str
    schema_version: str
    created_at: datetime


class AIUsageResponse(CamelModel):
    period_start: date
    period_end: date
    input_tokens: int
    output_tokens: int
    cost_microusd: int
    run_count: int
    cache_hit_count: int
    daily_cost_limit_microusd: int
    monthly_cost_limit_microusd: int


class AISuggestedPromptResponse(CamelModel):
    id: str
    label: str
    prompt: str
    mode: AIMessageMode


class AIRunEventResponse(CamelModel):
    id: UUID
    run_id: UUID
    sequence: int
    event_type: str
    payload: dict[str, Any]
    created_at: datetime
