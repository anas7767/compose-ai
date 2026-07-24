from __future__ import annotations

import hashlib
import json
from typing import Any


def topology_signature(features: dict[str, Any]) -> str:
    payload = json.dumps(features, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def topology_diversity(candidate: dict[str, Any], existing: list[dict[str, Any]]) -> float:
    if not existing:
        return 1.0
    return min(_pairwise_diversity(candidate, item) for item in existing)


def _pairwise_diversity(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_edges = set(left.get("adjacencyEdges", []))
    right_edges = set(right.get("adjacencyEdges", []))
    union = left_edges | right_edges
    edge_distance = 1.0 if not union else 1 - (len(left_edges & right_edges) / len(union))
    orientation_distance = 1.0 if left.get("orientation") != right.get("orientation") else 0.0
    entrance_distance = 1.0 if left.get("entranceSide") != right.get("entranceSide") else 0.0
    row_distance = _row_order_distance(left.get("rows", []), right.get("rows", []))
    return round(
        min(
            1.0,
            edge_distance * 0.45
            + orientation_distance * 0.25
            + entrance_distance * 0.1
            + row_distance * 0.2,
        ),
        3,
    )


def _row_order_distance(left_rows: list[Any], right_rows: list[Any]) -> float:
    left = _flatten_rows(left_rows)
    right = _flatten_rows(right_rows)
    common = [value for value in left if value in set(right)]
    if len(common) < 2:
        return 1.0 if left != right else 0.0
    right_positions = {value: index for index, value in enumerate(right)}
    discordant = 0
    pairs = 0
    for index, first in enumerate(common):
        for second in common[index + 1 :]:
            pairs += 1
            if right_positions[first] > right_positions[second]:
                discordant += 1
    return discordant / pairs if pairs else 0.0


def _flatten_rows(value: list[Any]) -> list[str]:
    flattened: list[str] = []
    for floor in value:
        if not isinstance(floor, dict):
            continue
        for row in floor.get("rows", []):
            flattened.extend(str(item) for item in row)
    return flattened
