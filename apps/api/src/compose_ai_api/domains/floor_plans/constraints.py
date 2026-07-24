from __future__ import annotations

from typing import Any

from compose_ai_api.domains.floor_plans.schemas import (
    ConstraintTraceItem,
    FloorPlanGenerationRequest,
    FloorPlanProgramOutput,
)
from compose_ai_api.domains.floor_plans.validation import ValidationOutcome


def build_constraint_trace(
    request: FloorPlanGenerationRequest,
    program: FloorPlanProgramOutput,
    geometry: dict[str, Any],
    topology_features: dict[str, Any],
    validation: ValidationOutcome,
) -> list[ConstraintTraceItem]:
    rooms = [room for floor in geometry["floors"] for room in floor["rooms"]]
    parking = [space for floor in geometry["floors"] for space in floor["parking"]]
    windows = [window for floor in geometry["floors"] for window in floor["windows"]]
    bedroom_count = sum(1 for room in rooms if room["type"] == "bedroom")
    bathroom_count = sum(1 for room in rooms if room["type"] == "bathroom")
    required_daylight = {
        room["id"] for room in rooms if room["type"] not in {"bathroom", "storage", "utility"}
    }
    daylight_rooms = {window["roomId"] for window in windows}
    entrance_matches = topology_features.get("entranceSide") == program.entrance_side
    trace = [
        _quantified("FLOOR_COUNT", "program", program.floors, len(geometry["floors"])),
        _quantified(
            "BEDROOM_COUNT",
            "program",
            sum(1 for room in program.rooms if room.room_type == "bedroom"),
            bedroom_count,
        ),
        _quantified(
            "BATHROOM_COUNT",
            "program",
            sum(1 for room in program.rooms if room.room_type == "bathroom"),
            bathroom_count,
        ),
        _quantified("PARKING_COUNT", "site", program.parking_spaces, len(parking)),
        ConstraintTraceItem(
            code="DETERMINISTIC_GEOMETRY_VALIDATION",
            category="geometry",
            status="satisfied" if validation.valid else "violated",
            severity="blocking",
            target="all deterministic checks pass",
            actual=validation.summary,
            reason_code="VALIDATION_PASSED" if validation.valid else "VALIDATION_FAILED",
            reason=(
                "All deterministic geometry checks passed."
                if validation.valid
                else (
                    "One or more deterministic geometry checks failed; "
                    "the option cannot be accepted."
                )
            ),
        ),
        ConstraintTraceItem(
            code="ROAD_AWARE_ENTRANCE",
            category="site",
            status="satisfied" if entrance_matches else "partially_satisfied",
            severity="warning",
            target=program.entrance_side,
            actual=topology_features.get("entranceSide"),
            reason_code="ENTRANCE_MATCHED" if entrance_matches else "ENVELOPE_AXIS_LIMITATION",
            reason=(
                "The conceptual entrance aligns with the preferred road-facing side."
                if entrance_matches
                else (
                    "The safe rectangular envelope moved the entrance to the nearest "
                    "reachable corridor edge."
                )
            ),
        ),
        ConstraintTraceItem(
            code="NATURAL_LIGHT_ACCESS",
            category="environment",
            status="satisfied" if required_daylight <= daylight_rooms else "partially_satisfied",
            severity="warning",
            target=len(required_daylight),
            actual=len(required_daylight & daylight_rooms),
            reason_code=(
                "EXTERIOR_WINDOWS_PROVIDED"
                if required_daylight <= daylight_rooms
                else "DAYLIGHT_REVIEW_REQUIRED"
            ),
            reason=(
                "Every conceptual habitable room has an exterior window."
                if required_daylight <= daylight_rooms
                else "Some conceptual habitable rooms need professional daylight review."
            ),
        ),
        ConstraintTraceItem(
            code="BUDGET_MODE",
            category="budget",
            status="partially_satisfied",
            severity="informational",
            target=request.budget_mode,
            actual="spatial heuristic only",
            reason_code="COST_ENGINE_NOT_IN_SCOPE",
            reason=(
                "The layout uses the selected spatial budget heuristic; "
                "cost validation is not part of Phase 6."
            ),
        ),
    ]
    if request.vastu_preference != "not_required":
        trace.append(
            ConstraintTraceItem(
                code="VASTU_PREFERENCE",
                category="user_preference",
                status="partially_satisfied",
                severity="informational",
                target=request.vastu_preference,
                actual="preserved for review",
                reason_code="VASTU_ENGINE_NOT_IN_SCOPE",
                reason=(
                    "The user-supplied preference is preserved, but no Vastu compliance claim or "
                    "engine evaluation is performed."
                ),
            )
        )
    for item in request.user_constraints:
        trace.append(
            ConstraintTraceItem(
                code=item.code,
                category=item.category,
                status="partially_satisfied",
                severity="warning" if item.priority == "hard" else "informational",
                target=item.value,
                actual="manual review required",
                reason_code="CUSTOM_CONSTRAINT_REQUIRES_REVIEW",
                reason=(
                    "The custom constraint was preserved in the run, but deterministic "
                    "verification "
                    "is not available for this constraint code."
                ),
            )
        )
    return trace


def confidence_from_trace(trace: list[ConstraintTraceItem], validation: ValidationOutcome) -> float:
    if not validation.valid:
        return 0.0
    weights = {"satisfied": 1.0, "partially_satisfied": 0.62, "violated": 0.0}
    score = sum(weights[item.status] for item in trace) / max(1, len(trace))
    return round(min(0.97, max(0.1, score)), 3)


def _quantified(code: str, category: str, target: int, actual: int) -> ConstraintTraceItem:
    matches = target == actual
    return ConstraintTraceItem(
        code=code,
        category=category,
        status="satisfied" if matches else "violated",
        severity="blocking",
        target=target,
        actual=actual,
        reason_code="COUNT_MATCHED" if matches else "COUNT_MISMATCH",
        reason="The generated count matches the approved program."
        if matches
        else "The generated count does not match the approved program.",
    )
