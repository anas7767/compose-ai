from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

import ortools
import pyproj
import shapely
from pyproj import CRS, Transformer
from shapely.geometry import Polygon

from compose_ai_api.domains.plot_intelligence.models import CoordinateSpace, PlotBoundaryVersion

FLOOR_PLAN_ENGINE_VERSION = "compose-floor-plan/1.0.0"
FLOOR_PLAN_SCHEMA_VERSION = "floor-plan-geometry.v1"
FLOOR_PLAN_PROMPT_VERSION = "floor-plan-program.v1"
FLOOR_PLAN_VALIDATION_VERSION = "floor-plan-validation.v1"
FLOOR_PLAN_SOLVER_VERSION = f"ortools/{ortools.__version__};cp-sat.v1"
FLOOR_PLAN_GEOMETRY_ENGINE_VERSION = (
    f"shapely/{shapely.__version__};pyproj/{pyproj.__version__};canonical-mm.v1"
)


@dataclass(frozen=True)
class CanonicalPlot:
    polygon_mm: Polygon
    transform: dict[str, Any]


def canonicalize_boundary(boundary: PlotBoundaryVersion) -> CanonicalPlot:
    geojson = boundary.normalized_geojson
    if not geojson or geojson.get("type") != "Polygon":
        raise ValueError("An active polygon boundary is required.")
    ring = geojson.get("coordinates", [[]])[0]
    if len(ring) < 4:
        raise ValueError("The active boundary has insufficient vertices.")

    coordinate_space = CoordinateSpace(str(boundary.coordinate_space))
    source_points = [(float(point[0]), float(point[1])) for point in ring]
    transform: dict[str, Any] = {
        "sourceCoordinateSpace": coordinate_space.value,
        "sourceBoundaryVersionId": str(boundary.id),
    }
    if coordinate_space == CoordinateSpace.WGS84:
        centroid_lon = sum(point[0] for point in source_points[:-1]) / (len(source_points) - 1)
        centroid_lat = sum(point[1] for point in source_points[:-1]) / (len(source_points) - 1)
        zone = int((centroid_lon + 180) // 6) + 1
        epsg = (32600 if centroid_lat >= 0 else 32700) + zone
        transformer = Transformer.from_crs(CRS.from_epsg(4326), CRS.from_epsg(epsg), always_xy=True)
        metric_points = [transformer.transform(x, y) for x, y in source_points]
        transform.update(
            {
                "projectedCrs": f"EPSG:{epsg}",
                "projectionOrigin": {"longitude": centroid_lon, "latitude": centroid_lat},
            }
        )
    else:
        metric_points = source_points

    min_x = min(point[0] for point in metric_points)
    min_y = min(point[1] for point in metric_points)
    points_mm = [
        (round((point[0] - min_x) * 1000), round((point[1] - min_y) * 1000))
        for point in metric_points
    ]
    polygon = Polygon(points_mm)
    if not polygon.is_valid or polygon.is_empty or polygon.area <= 0:
        raise ValueError("The active boundary cannot be normalized for floor-plan generation.")
    transform["metricOffset"] = {"x": min_x, "y": min_y}
    transform["canonicalUnit"] = "millimeter"
    return CanonicalPlot(polygon_mm=polygon, transform=transform)


def geometry_hash(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stable_seed(*parts: object) -> int:
    payload = ":".join(str(part) for part in parts)
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") & 0x7FFF_FFFF_FFFF_FFFF
