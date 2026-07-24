from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from shapely.geometry import LineString, Polygon

from compose_ai_api.domains.floor_plans.geometry import FLOOR_PLAN_VALIDATION_VERSION

TOLERANCE_MM = 2
MIN_CIRCULATION_WIDTH_MM = 900


@dataclass(frozen=True)
class ValidationOutcome:
    valid: bool
    summary: dict[str, Any]
    checks: list[dict[str, Any]]
    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    engine_version: str = FLOOR_PLAN_VALIDATION_VERSION


def validate_floor_plan(geometry: dict[str, Any], plot_polygon_mm: Polygon) -> ValidationOutcome:
    checks: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    floors = geometry.get("floors", [])
    _check(bool(floors), "FLOORS_PRESENT", "At least one floor is present.", checks, errors)
    stair_footprints: list[list[list[int]]] = []
    total_entity_area = 0.0
    exterior_window_rooms: set[str] = set()
    required_window_rooms: set[str] = set()

    for floor in floors:
        floor_index = int(floor.get("index", -1))
        spaces = [*floor.get("rooms", []), *floor.get("stairs", []), *floor.get("parking", [])]
        polygons: list[tuple[dict[str, Any], Polygon]] = []
        for space in spaces:
            points = space.get("polygon", [])
            closed = len(points) >= 4 and points[0] == points[-1]
            _check(
                closed,
                "ROOM_POLYGON_CLOSED",
                "Space polygons must be explicitly closed.",
                checks,
                errors,
                {"floorIndex": floor_index, "spaceId": space.get("id")},
            )
            polygon = Polygon(points) if closed else Polygon()
            valid_polygon = (
                closed and polygon.is_valid and not polygon.is_empty and polygon.area > 0
            )
            _check(
                valid_polygon,
                "ROOM_POLYGON_VALID",
                "Space polygons must be valid and enclose positive area.",
                checks,
                errors,
                {"floorIndex": floor_index, "spaceId": space.get("id")},
            )
            if not valid_polygon:
                continue
            polygons.append((space, polygon))
            contained = plot_polygon_mm.buffer(TOLERANCE_MM).covers(polygon)
            _check(
                contained,
                "PLOT_CONTAINMENT",
                "Every generated space must remain inside the plot boundary.",
                checks,
                errors,
                {"floorIndex": floor_index, "spaceId": space.get("id")},
            )
            reported_area = float(space.get("areaM2", 0))
            calculated_area = polygon.area / 1_000_000
            area_consistent = abs(reported_area - calculated_area) <= max(
                0.01, calculated_area * 0.002
            )
            _check(
                area_consistent,
                "SPACE_AREA_CONSISTENT",
                "Reported space areas must match geometry.",
                checks,
                errors,
                {
                    "floorIndex": floor_index,
                    "spaceId": space.get("id"),
                    "reportedM2": reported_area,
                    "calculatedM2": round(calculated_area, 3),
                },
            )
            total_entity_area += calculated_area
            if space.get("type") == "stair":
                stair_footprints.append(points)

        for index, (left_space, left_polygon) in enumerate(polygons):
            for right_space, right_polygon in polygons[index + 1 :]:
                overlap_area = left_polygon.intersection(right_polygon).area
                _check(
                    overlap_area <= TOLERANCE_MM**2,
                    "SPACE_OVERLAP",
                    "Generated spaces cannot overlap.",
                    checks,
                    errors,
                    {
                        "floorIndex": floor_index,
                        "leftSpaceId": left_space.get("id"),
                        "rightSpaceId": right_space.get("id"),
                        "overlapMm2": round(overlap_area),
                    },
                )

        walls_by_id = {wall.get("id"): wall for wall in floor.get("walls", [])}
        for door in floor.get("doors", []):
            wall = walls_by_id.get(door.get("wallId"))
            attached = wall is not None and _line_covers(wall, door)
            _check(
                attached,
                "DOOR_CONNECTED_TO_WALL",
                "Every door must be placed on a generated wall.",
                checks,
                errors,
                {"floorIndex": floor_index, "doorId": door.get("id")},
            )
        for window in floor.get("windows", []):
            wall = walls_by_id.get(window.get("wallId"))
            exterior = (
                wall is not None and bool(wall.get("exterior")) and _line_covers(wall, window)
            )
            _check(
                exterior,
                "WINDOW_ON_EXTERIOR_WALL",
                "Every window must be placed on a valid exterior wall.",
                checks,
                errors,
                {"floorIndex": floor_index, "windowId": window.get("id")},
            )
            if exterior and window.get("roomId"):
                exterior_window_rooms.add(str(window["roomId"]))
        for room in floor.get("rooms", []):
            if room.get("type") not in {"bathroom", "storage", "utility"}:
                required_window_rooms.add(str(room.get("id")))

        circulation = floor.get("circulation", {})
        width = int(circulation.get("widthMm", 0))
        _check(
            width >= MIN_CIRCULATION_WIDTH_MM,
            "CIRCULATION_WIDTH",
            "Conceptual circulation must meet the configured minimum width.",
            checks,
            errors,
            {"floorIndex": floor_index, "widthMm": width, "minimumMm": MIN_CIRCULATION_WIDTH_MM},
        )
        connected_ids = {
            str(connection)
            for door in floor.get("doors", [])
            for connection in door.get("connects", [])
        }
        for space in spaces:
            _check(
                str(space.get("id")) in connected_ids,
                "SPACE_CIRCULATION_CONNECTED",
                "Every generated space must connect to the circulation network.",
                checks,
                errors,
                {"floorIndex": floor_index, "spaceId": space.get("id")},
            )

    if len(floors) > 1:
        continuity = len(stair_footprints) == len(floors) and all(
            footprint == stair_footprints[0] for footprint in stair_footprints[1:]
        )
        _check(
            continuity,
            "STAIR_CONTINUITY",
            "Multi-floor plans require an identical stair footprint on every floor.",
            checks,
            errors,
            {"floorCount": len(floors), "stairCount": len(stair_footprints)},
        )

    missing_daylight = sorted(required_window_rooms - exterior_window_rooms)
    if missing_daylight:
        warnings.append(
            {
                "code": "NATURAL_LIGHT_REVIEW_REQUIRED",
                "message": "Some habitable spaces do not have a conceptual exterior window.",
                "details": {"roomIds": missing_daylight},
            }
        )
    summary_area = (
        float(geometry.get("areaSummary", {}).get("roomAreaM2", 0))
        + float(geometry.get("areaSummary", {}).get("parkingAreaM2", 0))
        + float(geometry.get("areaSummary", {}).get("stairAreaM2", 0))
    )
    _check(
        abs(summary_area - total_entity_area) <= max(0.05, total_entity_area * 0.002),
        "TOTAL_AREA_CONSISTENT",
        "Area summary totals must match generated space geometry.",
        checks,
        errors,
        {"summaryM2": summary_area, "calculatedM2": round(total_entity_area, 3)},
    )
    passed = sum(1 for check in checks if check["status"] == "passed")
    failed = len(checks) - passed
    return ValidationOutcome(
        valid=not errors,
        summary={"checkCount": len(checks), "passed": passed, "failed": failed},
        checks=checks,
        errors=errors,
        warnings=warnings,
    )


def _line_covers(wall: dict[str, Any], opening: dict[str, Any]) -> bool:
    wall_line = LineString([wall.get("start"), wall.get("end")])
    opening_line = LineString([opening.get("start"), opening.get("end")])
    return wall_line.buffer(TOLERANCE_MM).covers(opening_line)


def _check(
    condition: bool,
    code: str,
    message: str,
    checks: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    details: dict[str, Any] | None = None,
) -> None:
    item = {
        "code": code,
        "status": "passed" if condition else "failed",
        "message": message,
        "details": details or {},
    }
    checks.append(item)
    if not condition:
        errors.append({"code": code, "message": message, "details": details or {}})
