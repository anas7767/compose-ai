from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import pyproj
import shapely
from pyproj import Geod
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient
from shapely.validation import explain_validity

from compose_ai_api.domains.plot_intelligence.models import CoordinateSpace
from compose_ai_api.domains.plot_intelligence.units import METERS_PER_FOOT
from compose_ai_api.domains.projects.models import UnitSystem

MAX_BOUNDARY_VERTICES = 500
MAX_BOUNDARY_BYTES = 256 * 1024
GEOMETRY_ENGINE_VERSION = f"shapely/{shapely.__version__};pyproj/{pyproj.__version__}"
WGS84_GEOD = Geod(ellps="WGS84")


class PlotGeometryError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass(frozen=True)
class NormalizedGeometry:
    geojson: dict[str, Any]
    checksum: str
    coordinate_space: CoordinateSpace
    vertex_count: int
    area_m2: Decimal
    perimeter_m: Decimal
    bounding_box: dict[str, float]
    centroid: dict[str, float]
    edge_lengths_m: tuple[Decimal, ...]
    warnings: tuple[dict[str, Any], ...]
    geometry_engine_version: str = GEOMETRY_ENGINE_VERSION


def normalize_geojson(
    value: dict[str, Any],
    coordinate_space: CoordinateSpace,
    unit_system: UnitSystem,
) -> NormalizedGeometry:
    if len(json.dumps(value, separators=(",", ":")).encode("utf-8")) > MAX_BOUNDARY_BYTES:
        raise PlotGeometryError(
            "PLOT_BOUNDARY_TOO_COMPLEX",
            "Boundary payload exceeds the 256 KB Phase 5A limit.",
            {"maxBytes": MAX_BOUNDARY_BYTES},
        )

    geometry = _extract_polygon_geometry(value)
    coordinates = geometry.get("coordinates")
    if not isinstance(coordinates, list) or len(coordinates) != 1:
        raise PlotGeometryError(
            "PLOT_GEOMETRY_UNSUPPORTED",
            "Phase 5A supports one exterior polygon ring without holes.",
        )
    raw_ring = coordinates[0]
    if not isinstance(raw_ring, list):
        raise PlotGeometryError("PLOT_GEOMETRY_INVALID", "Polygon coordinates must be an array.")

    ring = _normalize_ring(raw_ring, coordinate_space, unit_system)
    if len(ring) - 1 > MAX_BOUNDARY_VERTICES:
        raise PlotGeometryError(
            "PLOT_BOUNDARY_TOO_COMPLEX",
            "Boundary contains more than 500 vertices.",
            {"maxVertices": MAX_BOUNDARY_VERTICES, "vertexCount": len(ring) - 1},
        )

    polygon = Polygon(ring)
    if not polygon.is_valid:
        raise PlotGeometryError(
            "PLOT_GEOMETRY_INVALID",
            "Polygon topology is invalid.",
            {"reason": explain_validity(polygon)},
        )
    if polygon.is_empty or polygon.area <= 0:
        raise PlotGeometryError("PLOT_GEOMETRY_INVALID", "Polygon must enclose a positive area.")

    if coordinate_space == CoordinateSpace.WGS84 and polygon.bounds[2] - polygon.bounds[0] > 180:
        raise PlotGeometryError(
            "PLOT_GEOMETRY_UNSUPPORTED",
            "Boundaries crossing the antimeridian are not supported in Phase 5A.",
        )

    polygon = orient(polygon, sign=1.0)
    precision = 7 if coordinate_space == CoordinateSpace.WGS84 else 4
    normalized_ring = [
        [round(float(x), precision), round(float(y), precision)] for x, y in polygon.exterior.coords
    ]
    normalized_polygon = Polygon(normalized_ring)
    if not normalized_polygon.is_valid or normalized_polygon.area <= 0:
        raise PlotGeometryError(
            "PLOT_GEOMETRY_PRECISION_LOSS",
            "Boundary becomes invalid at the supported coordinate precision.",
        )

    area_m2, perimeter_m, edge_lengths = _measure_polygon(normalized_polygon, coordinate_space)
    warnings = _geometry_warnings(normalized_polygon, coordinate_space, area_m2, edge_lengths)
    normalized_geojson = {"type": "Polygon", "coordinates": [normalized_ring]}
    checksum = hashlib.sha256(
        json.dumps(normalized_geojson, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    min_x, min_y, max_x, max_y = normalized_polygon.bounds
    centroid = normalized_polygon.centroid
    return NormalizedGeometry(
        geojson=normalized_geojson,
        checksum=checksum,
        coordinate_space=coordinate_space,
        vertex_count=len(normalized_ring) - 1,
        area_m2=_decimal(area_m2),
        perimeter_m=_decimal(perimeter_m),
        bounding_box={
            "minX": round(min_x, precision),
            "minY": round(min_y, precision),
            "maxX": round(max_x, precision),
            "maxY": round(max_y, precision),
        },
        centroid={"x": round(centroid.x, precision), "y": round(centroid.y, precision)},
        edge_lengths_m=tuple(_decimal(length) for length in edge_lengths),
        warnings=tuple(warnings),
    )


def geojson_from_canonical(
    value: dict[str, Any] | None,
    coordinate_space: CoordinateSpace | str,
    unit_system: UnitSystem | str,
) -> dict[str, Any] | None:
    if value is None or str(coordinate_space) == CoordinateSpace.WGS84.value:
        return value
    factor = float(METERS_PER_FOOT) if str(unit_system) == UnitSystem.IMPERIAL.value else 1.0
    ring = value["coordinates"][0]
    return {
        "type": "Polygon",
        "coordinates": [
            [[round(point[0] / factor, 4), round(point[1] / factor, 4)] for point in ring]
        ],
    }


def tombstone_checksum(previous_id: str | None, version: int) -> str:
    return hashlib.sha256(f"tombstone:{previous_id or 'none'}:{version}".encode()).hexdigest()


def _extract_polygon_geometry(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PlotGeometryError("PLOT_GEOMETRY_INVALID", "GeoJSON must be an object.")
    value_type = value.get("type")
    if value_type == "Feature":
        feature_geometry = value.get("geometry")
        if not isinstance(feature_geometry, dict):
            raise PlotGeometryError("PLOT_GEOMETRY_INVALID", "Feature geometry is required.")
        value = feature_geometry
        value_type = value.get("type")
    if value_type != "Polygon":
        raise PlotGeometryError(
            "PLOT_GEOMETRY_UNSUPPORTED",
            "Only GeoJSON Polygon geometry is supported in Phase 5A.",
            {"receivedType": value_type},
        )
    return value


def _normalize_ring(
    raw_ring: list[Any],
    coordinate_space: CoordinateSpace,
    unit_system: UnitSystem,
) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    factor = float(METERS_PER_FOOT) if unit_system == UnitSystem.IMPERIAL else 1.0
    for index, raw_point in enumerate(raw_ring):
        if not isinstance(raw_point, (list, tuple)) or len(raw_point) != 2:
            raise PlotGeometryError(
                "PLOT_GEOMETRY_INVALID",
                "Every polygon coordinate must contain exactly two numbers.",
                {"vertexIndex": index},
            )
        if any(isinstance(item, bool) or not isinstance(item, (int, float)) for item in raw_point):
            raise PlotGeometryError(
                "PLOT_GEOMETRY_INVALID",
                "Polygon coordinates must be finite numbers.",
                {"vertexIndex": index},
            )
        x, y = float(raw_point[0]), float(raw_point[1])
        if not math.isfinite(x) or not math.isfinite(y):
            raise PlotGeometryError(
                "PLOT_GEOMETRY_INVALID",
                "Polygon coordinates must be finite numbers.",
                {"vertexIndex": index},
            )
        if coordinate_space == CoordinateSpace.WGS84:
            if not -180 <= x <= 180 or not -90 <= y <= 90:
                raise PlotGeometryError(
                    "PLOT_GEOMETRY_INVALID",
                    "WGS84 coordinates must use valid longitude and latitude values.",
                    {"vertexIndex": index},
                )
        else:
            x *= factor
            y *= factor
            if abs(x) > 1_000_000 or abs(y) > 1_000_000:
                raise PlotGeometryError(
                    "PLOT_GEOMETRY_INVALID",
                    "Local coordinates exceed the supported one-million-metre range.",
                    {"vertexIndex": index},
                )
        point = (x, y)
        if not points or point != points[-1]:
            points.append(point)
    if points and points[0] != points[-1]:
        points.append(points[0])
    if len(points) < 4 or len(set(points[:-1])) < 3:
        raise PlotGeometryError(
            "PLOT_GEOMETRY_INVALID",
            "A polygon requires at least three distinct vertices.",
        )
    return points


def _measure_polygon(
    polygon: Polygon, coordinate_space: CoordinateSpace
) -> tuple[float, float, list[float]]:
    coordinates = list(polygon.exterior.coords)
    if coordinate_space == CoordinateSpace.LOCAL_CARTESIAN:
        edge_lengths = [
            math.dist(coordinates[index], coordinates[index + 1])
            for index in range(len(coordinates) - 1)
        ]
        return polygon.area, polygon.length, edge_lengths
    area, perimeter = WGS84_GEOD.geometry_area_perimeter(polygon)
    edge_lengths = []
    for index in range(len(coordinates) - 1):
        first = coordinates[index]
        second = coordinates[index + 1]
        _, _, distance = WGS84_GEOD.inv(first[0], first[1], second[0], second[1])
        edge_lengths.append(abs(distance))
    return abs(area), abs(perimeter), edge_lengths


def _geometry_warnings(
    polygon: Polygon,
    coordinate_space: CoordinateSpace,
    area_m2: float,
    edge_lengths: list[float],
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []
    if area_m2 < 10:
        warnings.append(
            {
                "code": "PLOT_AREA_UNUSUALLY_SMALL",
                "severity": "warning",
                "field": "boundary",
                "message": "Plot area is unusually small and should be reviewed.",
            }
        )
    if area_m2 > 10_000_000:
        warnings.append(
            {
                "code": "PLOT_AREA_UNUSUALLY_LARGE",
                "severity": "warning",
                "field": "boundary",
                "message": "Plot area is unusually large and should be reviewed.",
            }
        )
    if edge_lengths and min(edge_lengths) < 0.1:
        warnings.append(
            {
                "code": "PLOT_EDGE_UNUSUALLY_SHORT",
                "severity": "warning",
                "field": "boundary",
                "message": "Boundary contains an edge shorter than 0.1 metres.",
                "details": {"minimumEdgeM": round(min(edge_lengths), 3)},
            }
        )
    if coordinate_space == CoordinateSpace.LOCAL_CARTESIAN:
        rectangle = polygon.minimum_rotated_rectangle
        rectangle_coordinates = list(rectangle.exterior.coords)
        lengths = [
            math.dist(rectangle_coordinates[index], rectangle_coordinates[index + 1])
            for index in range(4)
        ]
        if lengths and max(lengths) > 0 and min(lengths) / max(lengths) < 0.03:
            warnings.append(
                {
                    "code": "PLOT_GEOMETRY_EXTREMELY_NARROW",
                    "severity": "warning",
                    "field": "boundary",
                    "message": "Plot geometry is extremely narrow and needs professional review.",
                }
            )
    return warnings


def _decimal(value: float) -> Decimal:
    return Decimal(str(round(value, 3)))
