from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from compose_ai_api.domains.plot_intelligence.geometry import GEOMETRY_ENGINE_VERSION

ANALYSIS_ENGINE_VERSION = "plot-intelligence/1"


@dataclass(frozen=True)
class RoadState:
    id: UUID | None
    direction: str
    is_primary: bool
    boundary_edge_index: int | None
    road_width_m: Decimal | None
    access_allowed: bool


@dataclass(frozen=True)
class BoundaryState:
    id: UUID | None
    version: int | None
    area_m2: Decimal
    perimeter_m: Decimal
    vertex_count: int
    edge_lengths_m: tuple[Decimal, ...]
    warnings: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class PlotState:
    project_id: UUID
    profile_revision: int
    plot_length_m: Decimal | None
    plot_width_m: Decimal | None
    plot_area_m2: Decimal | None
    plot_shape: str | None
    open_sides: int
    corner_plot: bool
    orientation_degrees: Decimal | None
    north_rotation_degrees: Decimal | None
    north_reference: str | None
    latitude: Decimal | None
    longitude: Decimal | None
    has_address: bool
    roads: tuple[RoadState, ...]
    boundary: BoundaryState | None
    target_parking_spaces: int


@dataclass(frozen=True)
class AnalysisResult:
    analysis_engine_version: str
    geometry_engine_version: str
    input_checksum: str
    plot_completeness: int
    plot_health_score: int
    plot_health_status: str
    feasibility_status: str
    pre_regulation_buildable_area_m2: Decimal | None
    parking_status: str
    parking_confidence: str
    parking_details: dict[str, Any]
    coverage_status: str
    coverage_details: dict[str, Any]
    regulation_status: str
    regulation_context: dict[str, Any]
    issues: tuple[dict[str, Any], ...]
    validation_summary: dict[str, Any]
    site_summary: dict[str, Any]


def analyze_plot(state: PlotState) -> AnalysisResult:
    issues = _validate_state(state)
    area_m2, area_source = _resolve_area(state)
    completeness = _completeness(state)
    parking_status, parking_confidence, parking_details = _parking_feasibility(state, area_m2)
    health_score, health_status = _health(state, issues)
    error_count = sum(issue["severity"] == "error" for issue in issues)
    warning_count = sum(issue["severity"] == "warning" for issue in issues)

    if error_count:
        feasibility = "invalid"
    elif area_m2 is None:
        feasibility = "insufficient_data"
    elif parking_status == "constrained":
        feasibility = "constrained"
    elif completeness < 60 or warning_count:
        feasibility = "professional_review_required"
    else:
        feasibility = "preliminarily_feasible"

    summary = {
        "errorCount": error_count,
        "warningCount": warning_count,
        "infoCount": sum(issue["severity"] == "info" for issue in issues),
        "highestSeverity": "error" if error_count else "warning" if warning_count else "none",
    }
    site_summary = {
        "areaM2": _json_decimal(area_m2),
        "areaSource": area_source,
        "perimeterM": _json_decimal(state.boundary.perimeter_m if state.boundary else None),
        "shape": state.plot_shape,
        "roadSideCount": len(state.roads),
        "openSides": state.open_sides,
        "orientationDegrees": _json_decimal(state.orientation_degrees),
        "parkingStatus": parking_status,
    }
    input_checksum = hashlib.sha256(
        json.dumps(_state_payload(state), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return AnalysisResult(
        analysis_engine_version=ANALYSIS_ENGINE_VERSION,
        geometry_engine_version=GEOMETRY_ENGINE_VERSION,
        input_checksum=input_checksum,
        plot_completeness=completeness,
        plot_health_score=health_score,
        plot_health_status=health_status,
        feasibility_status=feasibility,
        pre_regulation_buildable_area_m2=area_m2,
        parking_status=parking_status,
        parking_confidence=parking_confidence,
        parking_details=parking_details,
        coverage_status="awaiting_building_footprint",
        coverage_details={
            "plotAreaM2": _json_decimal(area_m2),
            "proposedFootprintAreaM2": None,
            "coveragePercent": None,
        },
        regulation_status="not_configured",
        regulation_context={
            "farFsi": None,
            "maximumCoveragePercent": None,
            "setbacks": None,
            "jurisdictionSource": None,
        },
        issues=tuple(issues),
        validation_summary=summary,
        site_summary=site_summary,
    )


def _validate_state(state: PlotState) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    dimension_area = _dimension_area(state)
    if state.plot_shape == "square" and state.plot_length_m and state.plot_width_m:
        difference = _relative_difference(state.plot_length_m, state.plot_width_m)
        if difference > Decimal("0.01"):
            issues.append(
                _issue(
                    "PLOT_SQUARE_DIMENSION_CONFLICT",
                    "error",
                    "plotWidth",
                    "Square plot dimensions must be within one percent of each other.",
                )
            )
    if dimension_area is not None and state.plot_area_m2 is not None:
        difference = _relative_difference(dimension_area, state.plot_area_m2)
        if difference > Decimal("0.03"):
            issues.append(
                _issue(
                    "PLOT_DIMENSION_CONFLICT",
                    "error",
                    "plotArea",
                    "Declared area differs from calculated dimensions by more than three percent.",
                    {"differencePercent": float(round(difference * 100, 2))},
                )
            )
        elif difference > Decimal("0.01"):
            issues.append(
                _issue(
                    "PLOT_DIMENSION_WARNING",
                    "warning",
                    "plotArea",
                    "Declared area differs from calculated dimensions by more than one percent.",
                    {"differencePercent": float(round(difference * 100, 2))},
                )
            )
    if state.boundary and state.plot_area_m2 is not None:
        difference = _relative_difference(state.boundary.area_m2, state.plot_area_m2)
        if difference > Decimal("0.05"):
            issues.append(
                _issue(
                    "PLOT_BOUNDARY_AREA_CONFLICT",
                    "error",
                    "boundary",
                    "Boundary area differs from declared area by more than five percent.",
                    {"differencePercent": float(round(difference * 100, 2))},
                )
            )
        elif difference > Decimal("0.02"):
            issues.append(
                _issue(
                    "PLOT_BOUNDARY_AREA_WARNING",
                    "warning",
                    "boundary",
                    "Boundary area differs from declared area by more than two percent.",
                    {"differencePercent": float(round(difference * 100, 2))},
                )
            )
    if state.plot_shape in {"l_shaped", "trapezoid", "irregular", "other"} and not state.boundary:
        issues.append(
            _issue(
                "PLOT_BOUNDARY_REQUIRED_FOR_VERIFICATION",
                "warning",
                "boundary",
                "This plot shape needs a boundary polygon for verified geometry.",
            )
        )

    if len(state.roads) > state.open_sides:
        issues.append(
            _issue(
                "PLOT_ROADS_EXCEED_OPEN_SIDES",
                "error",
                "openSides",
                "Road-side count cannot exceed open-side count.",
            )
        )
    if state.corner_plot and (state.open_sides < 2 or len(state.roads) < 2):
        issues.append(
            _issue(
                "PLOT_CORNER_PROFILE_INVALID",
                "error",
                "cornerPlot",
                "Corner plots require at least two open sides and two road sides.",
            )
        )
    directions = [road.direction for road in state.roads]
    if len(directions) != len(set(directions)):
        issues.append(
            _issue(
                "PLOT_ROAD_DIRECTION_DUPLICATE",
                "error",
                "roadSides",
                "Road sides must use distinct directions.",
            )
        )
    primary_count = sum(road.is_primary for road in state.roads)
    if state.roads and primary_count != 1:
        issues.append(
            _issue(
                "PLOT_PRIMARY_ROAD_INVALID",
                "error",
                "roadSides",
                "Exactly one road side must be primary.",
            )
        )
    edge_indexes = [
        road.boundary_edge_index for road in state.roads if road.boundary_edge_index is not None
    ]
    if len(edge_indexes) != len(set(edge_indexes)):
        issues.append(
            _issue(
                "PLOT_ROAD_EDGE_DUPLICATE",
                "error",
                "roadSides",
                "A boundary edge cannot be assigned to more than one road side.",
            )
        )
    if state.boundary and any(index >= state.boundary.vertex_count for index in edge_indexes):
        issues.append(
            _issue(
                "PLOT_ROAD_EDGE_INVALID",
                "error",
                "roadSides",
                "A road references an edge outside the current boundary.",
            )
        )
    if state.orientation_degrees is not None and state.north_reference is None:
        issues.append(
            _issue(
                "PLOT_NORTH_REFERENCE_REQUIRED",
                "warning",
                "northReference",
                "Select a north reference for the supplied orientation.",
            )
        )
    if state.boundary:
        issues.extend(state.boundary.warnings)
    if _has_no_plot_data(state):
        issues.append(
            _issue(
                "PLOT_PROFILE_INCOMPLETE",
                "info",
                "plotProfile",
                "Add plot dimensions or a boundary to begin site analysis.",
            )
        )
    return issues


def _resolve_area(state: PlotState) -> tuple[Decimal | None, str]:
    if state.boundary:
        return state.boundary.area_m2, "boundary"
    dimension_area = _dimension_area(state)
    if dimension_area is not None:
        return dimension_area, "dimensions"
    if state.plot_area_m2 is not None:
        return state.plot_area_m2, "declared"
    return None, "unknown"


def _dimension_area(state: PlotState) -> Decimal | None:
    if (
        state.plot_shape in {"rectangle", "square"}
        and state.plot_length_m is not None
        and state.plot_width_m is not None
    ):
        return state.plot_length_m * state.plot_width_m
    return None


def _completeness(state: PlotState) -> int:
    score = 0
    area, _ = _resolve_area(state)
    if area is not None:
        score += 15
    if state.plot_length_m is not None and state.plot_width_m is not None:
        score += 10
    if state.plot_shape is not None:
        score += 10
    if state.boundary or (
        state.plot_shape in {"rectangle", "square"}
        and state.plot_length_m is not None
        and state.plot_width_m is not None
    ):
        score += 15
    if state.open_sides >= 0:
        score += 5
    if state.open_sides == 0 or state.roads:
        score += 10
    if not state.corner_plot or len(state.roads) >= 2:
        score += 5
    if state.orientation_degrees is not None:
        score += 7
    if state.north_reference is not None:
        score += 4
    if state.north_rotation_degrees is not None:
        score += 4
    if state.latitude is not None and state.longitude is not None:
        score += 10
    if state.has_address:
        score += 5
    return min(score, 100)


def _health(state: PlotState, issues: list[dict[str, Any]]) -> tuple[int, str]:
    if _has_no_plot_data(state):
        return 0, "insufficient_data"
    error_count = sum(issue["severity"] == "error" for issue in issues)
    warning_count = sum(issue["severity"] == "warning" for issue in issues)
    area, _ = _resolve_area(state)
    geometry_score = 40 if state.boundary or _dimension_area(state) else 20 if area else 0
    dimension_score = 20
    if any(
        issue["code"] in {"PLOT_DIMENSION_CONFLICT", "PLOT_SQUARE_DIMENSION_CONFLICT"}
        for issue in issues
    ):
        dimension_score = 0
    elif any(
        issue["code"] in {"PLOT_DIMENSION_WARNING", "PLOT_BOUNDARY_AREA_WARNING"}
        for issue in issues
    ):
        dimension_score = 10
    access_score = (
        20
        if not any("ROAD" in issue["code"] or "CORNER" in issue["code"] for issue in issues)
        else 0
    )
    orientation_score = (
        10
        if state.orientation_degrees is not None and state.north_reference
        else 5
        if state.orientation_degrees is not None
        else 0
    )
    warning_score = max(0, 10 - warning_count * 2)
    score = max(
        0,
        min(
            100, geometry_score + dimension_score + access_score + orientation_score + warning_score
        ),
    )
    if error_count:
        score = min(score, 49)
        return score, "invalid"
    if score >= 90:
        return score, "excellent"
    if score >= 75:
        return score, "good"
    return score, "needs_review"


def _parking_feasibility(
    state: PlotState, area_m2: Decimal | None
) -> tuple[str, str, dict[str, Any]]:
    target = state.target_parking_spaces
    if target <= 0:
        return "not_required", "high", {"targetSpaces": 0, "reason": "No parking requested."}
    accessible_roads = [road for road in state.roads if road.access_allowed]
    if area_m2 is None or not accessible_roads:
        return (
            "indeterminate",
            "low",
            {
                "targetSpaces": target,
                "reason": "Validated area and an accessible road side are required.",
            },
        )
    required_area = Decimal(target) * Decimal("16.875")
    frontage_m: Decimal | None = None
    if state.boundary:
        primary = next((road for road in accessible_roads if road.is_primary), accessible_roads[0])
        if primary.boundary_edge_index is not None and 0 <= primary.boundary_edge_index < len(
            state.boundary.edge_lengths_m
        ):
            frontage_m = state.boundary.edge_lengths_m[primary.boundary_edge_index]
    if frontage_m is None and state.plot_length_m and state.plot_width_m:
        frontage_m = min(state.plot_length_m, state.plot_width_m)
    details = {
        "targetSpaces": target,
        "heuristicRequiredAreaM2": _json_decimal(required_area),
        "availableAreaM2": _json_decimal(area_m2),
        "estimatedFrontageM": _json_decimal(frontage_m),
        "regulatory": False,
    }
    if area_m2 < required_area * Decimal("0.8") or (
        frontage_m is not None and frontage_m < Decimal("2.3")
    ):
        details["reason"] = "Available geometry is below the preliminary physical allowance."
        return "constrained", "medium", details
    if area_m2 >= required_area and frontage_m is not None and frontage_m >= Decimal("2.5"):
        details["reason"] = "Area and frontage satisfy the preliminary physical allowance."
        return "likely", "medium", details
    details["reason"] = "More detailed access geometry is needed."
    return "indeterminate", "low", details


def _has_no_plot_data(state: PlotState) -> bool:
    return not any(
        (
            state.plot_length_m,
            state.plot_width_m,
            state.plot_area_m2,
            state.plot_shape,
            state.boundary,
        )
    )


def _relative_difference(first: Decimal, second: Decimal) -> Decimal:
    largest = max(abs(first), abs(second))
    return Decimal(0) if largest == 0 else abs(first - second) / largest


def _issue(
    code: str,
    severity: str,
    field: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "code": code,
        "severity": severity,
        "field": field,
        "message": message,
    }
    if details:
        value["details"] = details
    return value


def _state_payload(state: PlotState) -> dict[str, Any]:
    return {
        "analysisEngineVersion": ANALYSIS_ENGINE_VERSION,
        "geometryEngineVersion": GEOMETRY_ENGINE_VERSION,
        "projectId": str(state.project_id),
        "profileRevision": state.profile_revision,
        "plotLengthM": _json_decimal(state.plot_length_m),
        "plotWidthM": _json_decimal(state.plot_width_m),
        "plotAreaM2": _json_decimal(state.plot_area_m2),
        "plotShape": state.plot_shape,
        "openSides": state.open_sides,
        "cornerPlot": state.corner_plot,
        "orientationDegrees": _json_decimal(state.orientation_degrees),
        "northRotationDegrees": _json_decimal(state.north_rotation_degrees),
        "northReference": state.north_reference,
        "roads": [
            {
                "direction": road.direction,
                "primary": road.is_primary,
                "edge": road.boundary_edge_index,
                "widthM": _json_decimal(road.road_width_m),
                "access": road.access_allowed,
            }
            for road in state.roads
        ],
        "boundaryId": str(state.boundary.id) if state.boundary and state.boundary.id else None,
        "boundaryVersion": state.boundary.version if state.boundary else None,
        "boundaryAreaM2": _json_decimal(state.boundary.area_m2 if state.boundary else None),
        "targetParkingSpaces": state.target_parking_spaces,
    }


def _json_decimal(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None
