from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

from ortools.sat.python import cp_model
from shapely.geometry import LineString, Point, Polygon, box

from compose_ai_api.domains.floor_plans.geometry import FLOOR_PLAN_SCHEMA_VERSION
from compose_ai_api.domains.floor_plans.schemas import FloorPlanProgramOutput, FloorPlanProgramRoom

GRID_MM = 100
MIN_ENVELOPE_EDGE_MM = 4_500
WALL_THICKNESS_MM = 150
DOOR_WIDTH_MM = 900
WINDOW_WIDTH_MM = 1_200


class FloorPlanSolveError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class SolverResult:
    geometry: dict[str, Any]
    topology_features: dict[str, Any]
    area_summary: dict[str, Any]


@dataclass(frozen=True)
class _Space:
    key: str
    name: str
    room_type: str
    kind: str
    target_area_m2: float
    minimum_width_m: float
    zone: str
    requires_exterior: bool


def solve_floor_plan(
    plot_polygon_mm: Polygon,
    program: FloorPlanProgramOutput,
    *,
    deterministic_seed: int,
    solver_time_limit_seconds: float,
) -> SolverResult:
    envelope = _largest_safe_rectangle(plot_polygon_mm)
    min_x, min_y, max_x, max_y = (int(round(value)) for value in envelope.bounds)
    width = max_x - min_x
    height = max_y - min_y
    preferred_orientation = (
        "vertical" if program.entrance_side in {"north", "south"} else "horizontal"
    )
    orientation = (
        preferred_orientation
        if deterministic_seed % 3 != 1
        else ("horizontal" if preferred_orientation == "vertical" else "vertical")
    )
    if orientation == "horizontal":
        primary_length, cross_length = width, height
        origin_u, origin_v = min_x, min_y
    else:
        primary_length, cross_length = height, width
        origin_u, origin_v = min_y, min_x

    corridor_width = _snap(max(900, round(program.circulation_width_m * 1000)))
    if cross_length - corridor_width < 2_400:
        raise FloorPlanSolveError(
            "FLOOR_PLAN_ENVELOPE_TOO_NARROW",
            "The buildable envelope is too narrow for two room bands and circulation.",
            {"crossLengthMm": cross_length, "corridorWidthMm": corridor_width},
        )
    lower_depth = _snap((cross_length - corridor_width) // 2)
    upper_depth = cross_length - corridor_width - lower_depth
    if min(lower_depth, upper_depth) < 1_200:
        raise FloorPlanSolveError(
            "FLOOR_PLAN_ENVELOPE_TOO_NARROW",
            "The buildable envelope cannot fit usable room depth.",
        )
    corridor_start = lower_depth
    corridor_end = lower_depth + corridor_width

    randomizer = random.Random(deterministic_seed)
    floors: list[dict[str, Any]] = []
    topology_edges: list[list[str]] = []
    topology_rows: list[dict[str, Any]] = []
    actual_entrance_side = _actual_entrance_side(
        orientation, program.entrance_side, deterministic_seed
    )

    for floor_index in range(program.floors):
        floor_rooms = [room for room in program.rooms if room.floor_index == floor_index]
        if not floor_rooms:
            raise FloorPlanSolveError(
                "FLOOR_PLAN_EMPTY_FLOOR",
                "Every requested floor must contain at least one programmed room.",
                {"floorIndex": floor_index},
            )
        floor_random = random.Random(randomizer.randrange(0, 2**63))
        floor_random.shuffle(floor_rooms)
        rows = _assign_rows(floor_rooms)
        lower_spaces = [_program_space(room) for room in rows[0]]
        upper_spaces = [_program_space(room) for room in rows[1]]
        if program.floors > 1:
            lower_spaces.insert(
                0,
                _Space(
                    key="stair-core",
                    name="Stair Core",
                    room_type="stair",
                    kind="stair",
                    target_area_m2=6.0,
                    minimum_width_m=1.8,
                    zone="circulation",
                    requires_exterior=False,
                ),
            )
        if floor_index == 0:
            for parking_index in range(program.parking_spaces):
                upper_spaces.insert(
                    parking_index,
                    _Space(
                        key=f"parking-{parking_index + 1}",
                        name=f"Parking {parking_index + 1}",
                        room_type="parking",
                        kind="parking",
                        target_area_m2=12.5,
                        minimum_width_m=2.4,
                        zone="service",
                        requires_exterior=True,
                    ),
                )
        if not lower_spaces or not upper_spaces:
            populated = lower_spaces or upper_spaces
            midpoint = max(1, len(populated) // 2)
            lower_spaces = populated[:midpoint]
            upper_spaces = populated[midpoint:]
            if not upper_spaces:
                upper_spaces = [lower_spaces.pop()]

        lower_widths = _solve_row_widths(
            lower_spaces,
            primary_length,
            lower_depth,
            deterministic_seed + floor_index * 2,
            solver_time_limit_seconds,
        )
        upper_widths = _solve_row_widths(
            upper_spaces,
            primary_length,
            upper_depth,
            deterministic_seed + floor_index * 2 + 1,
            solver_time_limit_seconds,
        )
        floor, edges, row_feature = _build_floor_geometry(
            floor_index=floor_index,
            orientation=orientation,
            origin_u=origin_u,
            origin_v=origin_v,
            primary_length=primary_length,
            cross_length=cross_length,
            lower_depth=lower_depth,
            corridor_start=corridor_start,
            corridor_end=corridor_end,
            lower_spaces=lower_spaces,
            upper_spaces=upper_spaces,
            lower_widths=lower_widths,
            upper_widths=upper_widths,
            entrance_side=actual_entrance_side,
        )
        floors.append(floor)
        topology_edges.extend(edges)
        topology_rows.append(row_feature)

    room_area = sum(float(room["areaM2"]) for floor in floors for room in floor["rooms"])
    parking_area = sum(float(space["areaM2"]) for floor in floors for space in floor["parking"])
    stair_area = sum(float(space["areaM2"]) for floor in floors for space in floor["stairs"])
    circulation_area = sum(float(floor["circulation"]["areaM2"]) for floor in floors)
    gross_area = (envelope.area * program.floors) / 1_000_000
    area_summary = {
        "grossAreaM2": round(gross_area, 3),
        "roomAreaM2": round(room_area, 3),
        "parkingAreaM2": round(parking_area, 3),
        "stairAreaM2": round(stair_area, 3),
        "circulationAreaM2": round(circulation_area, 3),
        "floorCount": program.floors,
        "efficiencyPercent": round((room_area / gross_area) * 100, 1) if gross_area else 0,
    }
    geometry = {
        "schemaVersion": FLOOR_PLAN_SCHEMA_VERSION,
        "coordinateSpace": "local_cartesian",
        "unit": "millimeter",
        "conceptual": True,
        "plotBoundary": _polygon_points(plot_polygon_mm),
        "buildableEnvelope": _polygon_points(envelope),
        "northIndicatorDegrees": 0,
        "floors": floors,
        "adjacencyGraph": {
            "nodes": sorted(
                {
                    node
                    for edge in topology_edges
                    for node in edge
                    if not node.startswith("corridor-")
                }
            ),
            "edges": topology_edges,
        },
        "areaSummary": area_summary,
    }
    features = {
        "orientation": orientation,
        "entranceSide": actual_entrance_side,
        "rows": topology_rows,
        "adjacencyEdges": sorted("|".join(sorted(edge)) for edge in topology_edges),
    }
    return SolverResult(geometry=geometry, topology_features=features, area_summary=area_summary)


def _largest_safe_rectangle(polygon: Polygon) -> Polygon:
    min_x, min_y, max_x, max_y = polygon.bounds
    snapped_bounds = (
        math.ceil(min_x / GRID_MM) * GRID_MM,
        math.ceil(min_y / GRID_MM) * GRID_MM,
        math.floor(max_x / GRID_MM) * GRID_MM,
        math.floor(max_y / GRID_MM) * GRID_MM,
    )
    full = box(*snapped_bounds)
    if polygon.covers(full) and _rectangle_usable(full):
        return full

    centers = [polygon.representative_point(), polygon.centroid]
    for x_fraction in (0.15, 0.3, 0.5, 0.7, 0.85):
        for y_fraction in (0.15, 0.3, 0.5, 0.7, 0.85):
            point = Point(
                min_x + (max_x - min_x) * x_fraction,
                min_y + (max_y - min_y) * y_fraction,
            )
            if polygon.covers(point):
                centers.append(point)
    best: Polygon | None = None
    for center in centers:
        max_half_width = min(center.x - min_x, max_x - center.x)
        max_half_height = min(center.y - min_y, max_y - center.y)
        for aspect in (0.5, 0.75, 1.0, 1.5, 2.0):
            high = min(max_half_width / math.sqrt(aspect), max_half_height * math.sqrt(aspect))
            low = 0.0
            for _ in range(18):
                scale = (low + high) / 2
                half_width = scale * math.sqrt(aspect)
                half_height = scale / math.sqrt(aspect)
                candidate = box(
                    center.x - half_width,
                    center.y - half_height,
                    center.x + half_width,
                    center.y + half_height,
                )
                if polygon.covers(candidate):
                    low = scale
                else:
                    high = scale
            half_width = low * math.sqrt(aspect)
            half_height = low / math.sqrt(aspect)
            candidate = box(
                math.ceil((center.x - half_width) / GRID_MM) * GRID_MM,
                math.ceil((center.y - half_height) / GRID_MM) * GRID_MM,
                math.floor((center.x + half_width) / GRID_MM) * GRID_MM,
                math.floor((center.y + half_height) / GRID_MM) * GRID_MM,
            )
            if (
                polygon.covers(candidate)
                and _rectangle_usable(candidate)
                and (best is None or candidate.area > best.area)
            ):
                best = candidate
    if best is None:
        raise FloorPlanSolveError(
            "FLOOR_PLAN_BUILDABLE_ENVELOPE_UNAVAILABLE",
            "No usable rectangular conceptual envelope fits within the plot boundary.",
        )
    return best


def _rectangle_usable(value: Polygon) -> bool:
    min_x, min_y, max_x, max_y = value.bounds
    return min(max_x - min_x, max_y - min_y) >= MIN_ENVELOPE_EDGE_MM


def _assign_rows(
    rooms: list[FloorPlanProgramRoom],
) -> tuple[list[FloorPlanProgramRoom], list[FloorPlanProgramRoom]]:
    rows: tuple[list[FloorPlanProgramRoom], list[FloorPlanProgramRoom]] = ([], [])
    totals = [0.0, 0.0]
    for room in rooms:
        target_row = 0 if totals[0] <= totals[1] else 1
        rows[target_row].append(room)
        totals[target_row] += room.target_area_m2
    return rows


def _program_space(room: FloorPlanProgramRoom) -> _Space:
    return _Space(
        key=room.key,
        name=room.name,
        room_type=room.room_type,
        kind="room",
        target_area_m2=room.target_area_m2,
        minimum_width_m=room.minimum_width_m,
        zone=room.zone,
        requires_exterior=room.requires_exterior,
    )


def _solve_row_widths(
    spaces: list[_Space],
    available_mm: int,
    depth_mm: int,
    seed: int,
    time_limit_seconds: float,
) -> list[int]:
    available_units = available_mm // GRID_MM
    minimum_units = [max(9, math.ceil(space.minimum_width_m * 1000 / GRID_MM)) for space in spaces]
    if sum(minimum_units) > available_units:
        raise FloorPlanSolveError(
            "FLOOR_PLAN_PROGRAM_DOES_NOT_FIT",
            "The programmed spaces cannot fit the available conceptual envelope.",
            {"requiredWidthMm": sum(minimum_units) * GRID_MM, "availableWidthMm": available_mm},
        )
    model = cp_model.CpModel()
    widths: list[cp_model.IntVar] = []
    deviations: list[cp_model.IntVar] = []
    for index, (space, minimum) in enumerate(zip(spaces, minimum_units, strict=True)):
        maximum = minimum if space.kind == "stair" else available_units
        width = model.new_int_var(minimum, maximum, f"width_{index}")
        target = max(minimum, round((space.target_area_m2 * 1_000_000) / depth_mm / GRID_MM))
        deviation = model.new_int_var(0, available_units, f"deviation_{index}")
        model.add_abs_equality(deviation, width - min(target, available_units))
        widths.append(width)
        deviations.append(deviation)
    model.add(sum(widths) == available_units)
    model.minimize(sum(deviations))
    solver = cp_model.CpSolver()
    solver.parameters.random_seed = int(seed % 2_147_483_647)
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = max(0.05, min(time_limit_seconds, 5.0))
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise FloorPlanSolveError(
            "FLOOR_PLAN_SOLVER_INFEASIBLE",
            "The deterministic solver could not satisfy the room-width constraints.",
        )
    return [solver.value(width) * GRID_MM for width in widths]


def _build_floor_geometry(
    *,
    floor_index: int,
    orientation: str,
    origin_u: int,
    origin_v: int,
    primary_length: int,
    cross_length: int,
    lower_depth: int,
    corridor_start: int,
    corridor_end: int,
    lower_spaces: list[_Space],
    upper_spaces: list[_Space],
    lower_widths: list[int],
    upper_widths: list[int],
    entrance_side: str,
) -> tuple[dict[str, Any], list[list[str]], dict[str, Any]]:
    corridor_polygon = _rect_points(
        orientation,
        origin_u,
        origin_v,
        0,
        corridor_start,
        primary_length,
        corridor_end,
    )
    entities: list[dict[str, Any]] = []
    row_sequences: list[list[str]] = []
    for row_index, (spaces, widths, v0, v1) in enumerate(
        (
            (lower_spaces, lower_widths, 0, lower_depth),
            (upper_spaces, upper_widths, corridor_end, cross_length),
        )
    ):
        cursor = 0
        sequence: list[str] = []
        for space, width in zip(spaces, widths, strict=True):
            points = _rect_points(
                orientation,
                origin_u,
                origin_v,
                cursor,
                v0,
                cursor + width,
                v1,
            )
            area_m2 = (width * (v1 - v0)) / 1_000_000
            entities.append(
                {
                    "id": f"f{floor_index}-{space.key}",
                    "programKey": space.key,
                    "name": space.name,
                    "type": space.room_type,
                    "kind": space.kind,
                    "zone": space.zone,
                    "floorIndex": floor_index,
                    "polygon": points,
                    "areaM2": round(area_m2, 3),
                    "requiresExterior": space.requires_exterior,
                    "row": row_index,
                    "uStart": cursor,
                    "uEnd": cursor + width,
                    "vDoor": corridor_start if row_index == 0 else corridor_end,
                    "vExterior": 0 if row_index == 0 else cross_length,
                }
            )
            sequence.append(space.key)
            cursor += width
        row_sequences.append(sequence)

    envelope_points = _rect_points(
        orientation, origin_u, origin_v, 0, 0, primary_length, cross_length
    )
    wall_polygons = [envelope_points, corridor_polygon] + [entity["polygon"] for entity in entities]
    walls = _build_walls(wall_polygons, Polygon(envelope_points))
    doors: list[dict[str, Any]] = []
    windows: list[dict[str, Any]] = []
    paths: list[dict[str, Any]] = []
    adjacency: list[list[str]] = []
    corridor_id = f"corridor-{floor_index}"
    entrance_line, entrance_center = _entrance_line(
        orientation,
        origin_u,
        origin_v,
        primary_length,
        corridor_start,
        corridor_end,
        entrance_side,
    )
    doors.append(
        {
            "id": f"f{floor_index}-entrance",
            "kind": "entrance",
            "floorIndex": floor_index,
            "start": entrance_line[0],
            "end": entrance_line[1],
            "wallId": _wall_for_line(walls, entrance_line),
            "connects": ["outside", corridor_id],
        }
    )
    corridor_center = _to_xy(
        orientation,
        origin_u,
        origin_v,
        primary_length // 2,
        (corridor_start + corridor_end) // 2,
    )
    paths.append(
        {
            "id": f"f{floor_index}-path-main",
            "widthMm": corridor_end - corridor_start,
            "points": [entrance_center, corridor_center],
        }
    )
    for entity in entities:
        door_u = (entity["uStart"] + entity["uEnd"]) // 2
        half_door = min(DOOR_WIDTH_MM // 2, max(200, (entity["uEnd"] - entity["uStart"]) // 4))
        door_line = [
            _to_xy(
                orientation,
                origin_u,
                origin_v,
                door_u - half_door,
                entity["vDoor"],
            ),
            _to_xy(
                orientation,
                origin_u,
                origin_v,
                door_u + half_door,
                entity["vDoor"],
            ),
        ]
        doors.append(
            {
                "id": f"{entity['id']}-door",
                "kind": "internal",
                "floorIndex": floor_index,
                "start": door_line[0],
                "end": door_line[1],
                "wallId": _wall_for_line(walls, door_line),
                "connects": [corridor_id, entity["id"]],
            }
        )
        adjacency.append([corridor_id, entity["id"]])
        door_center = _to_xy(
            orientation,
            origin_u,
            origin_v,
            door_u,
            entity["vDoor"],
        )
        paths.append(
            {
                "id": f"{entity['id']}-path",
                "widthMm": corridor_end - corridor_start,
                "points": [corridor_center, door_center],
            }
        )
        if entity["requiresExterior"]:
            half_window = min(
                WINDOW_WIDTH_MM // 2,
                max(200, (entity["uEnd"] - entity["uStart"]) // 4),
            )
            window_line = [
                _to_xy(
                    orientation,
                    origin_u,
                    origin_v,
                    door_u - half_window,
                    entity["vExterior"],
                ),
                _to_xy(
                    orientation,
                    origin_u,
                    origin_v,
                    door_u + half_window,
                    entity["vExterior"],
                ),
            ]
            windows.append(
                {
                    "id": f"{entity['id']}-window",
                    "floorIndex": floor_index,
                    "start": window_line[0],
                    "end": window_line[1],
                    "wallId": _wall_for_line(walls, window_line, exterior_only=True),
                    "roomId": entity["id"],
                }
            )
    for sequence in row_sequences:
        for left, right in zip(sequence, sequence[1:], strict=False):
            adjacency.append([f"f{floor_index}-{left}", f"f{floor_index}-{right}"])

    rooms = [_public_entity(entity) for entity in entities if entity["kind"] == "room"]
    stairs = [_public_entity(entity) for entity in entities if entity["kind"] == "stair"]
    parking = [_public_entity(entity) for entity in entities if entity["kind"] == "parking"]
    floor = {
        "index": floor_index,
        "name": "Ground Floor" if floor_index == 0 else f"Floor {floor_index + 1}",
        "elevationMm": floor_index * 3_200,
        "envelope": envelope_points,
        "rooms": rooms,
        "walls": walls,
        "doors": doors,
        "windows": windows,
        "stairs": stairs,
        "parking": parking,
        "balconies": [],
        "circulation": {
            "id": corridor_id,
            "widthMm": corridor_end - corridor_start,
            "polygon": corridor_polygon,
            "areaM2": round(
                (primary_length * (corridor_end - corridor_start)) / 1_000_000,
                3,
            ),
            "paths": paths,
        },
    }
    return floor, adjacency, {"floorIndex": floor_index, "rows": row_sequences}


def _build_walls(polygons: list[list[list[int]]], envelope: Polygon) -> list[dict[str, Any]]:
    segments: dict[tuple[tuple[int, int], tuple[int, int]], dict[str, Any]] = {}
    for points in polygons:
        for start, end in zip(points, points[1:], strict=False):
            key = _segment_key(start, end)
            line = LineString([start, end])
            exterior = envelope.boundary.buffer(1).covers(line)
            if key not in segments or exterior:
                segments[key] = {
                    "id": "",
                    "start": list(key[0]),
                    "end": list(key[1]),
                    "thicknessMm": WALL_THICKNESS_MM,
                    "exterior": exterior,
                }
    walls = [segments[key] for key in sorted(segments)]
    for index, wall in enumerate(walls, start=1):
        wall["id"] = f"wall-{index}"
    return walls


def _wall_for_line(
    walls: list[dict[str, Any]], line_points: list[list[int]], *, exterior_only: bool = False
) -> str:
    line = LineString(line_points)
    for wall in walls:
        if exterior_only and not wall["exterior"]:
            continue
        wall_line = LineString([wall["start"], wall["end"]])
        if wall_line.buffer(1).covers(line):
            return str(wall["id"])
    raise FloorPlanSolveError(
        "FLOOR_PLAN_OPENING_WALL_MISSING",
        "An opening could not be attached to a generated wall.",
    )


def _entrance_line(
    orientation: str,
    origin_u: int,
    origin_v: int,
    primary_length: int,
    corridor_start: int,
    corridor_end: int,
    entrance_side: str,
) -> tuple[list[list[int]], list[int]]:
    at_end = entrance_side in {"north", "east"}
    u = primary_length if at_end else 0
    center_v = (corridor_start + corridor_end) // 2
    half = min(DOOR_WIDTH_MM // 2, (corridor_end - corridor_start) // 3)
    line = [
        _to_xy(orientation, origin_u, origin_v, u, center_v - half),
        _to_xy(orientation, origin_u, origin_v, u, center_v + half),
    ]
    return line, _to_xy(orientation, origin_u, origin_v, u, center_v)


def _actual_entrance_side(orientation: str, requested: str, seed: int) -> str:
    available = ("west", "east") if orientation == "horizontal" else ("south", "north")
    return requested if requested in available else available[seed % 2]


def _public_entity(entity: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in entity.items()
        if key
        not in {
            "kind",
            "row",
            "uStart",
            "uEnd",
            "vDoor",
            "vExterior",
            "requiresExterior",
        }
    }


def _rect_points(
    orientation: str,
    origin_u: int,
    origin_v: int,
    u0: int,
    v0: int,
    u1: int,
    v1: int,
) -> list[list[int]]:
    return [
        _to_xy(orientation, origin_u, origin_v, u0, v0),
        _to_xy(orientation, origin_u, origin_v, u1, v0),
        _to_xy(orientation, origin_u, origin_v, u1, v1),
        _to_xy(orientation, origin_u, origin_v, u0, v1),
        _to_xy(orientation, origin_u, origin_v, u0, v0),
    ]


def _to_xy(orientation: str, origin_u: int, origin_v: int, u: int, v: int) -> list[int]:
    if orientation == "horizontal":
        return [origin_u + u, origin_v + v]
    return [origin_v + v, origin_u + u]


def _polygon_points(polygon: Polygon) -> list[list[int]]:
    return [[round(x), round(y)] for x, y in polygon.exterior.coords]


def _segment_key(first: list[int], second: list[int]) -> tuple[tuple[int, int], tuple[int, int]]:
    start = (int(first[0]), int(first[1]))
    end = (int(second[0]), int(second[1]))
    return (start, end) if start <= end else (end, start)


def _snap(value: int) -> int:
    return max(GRID_MM, round(value / GRID_MM) * GRID_MM)
