from types import SimpleNamespace
from uuid import uuid4

from compose_ai_api.domains.floor_plan_editor.schemas import EditorSnapshot
from compose_ai_api.domains.floor_plan_editor.service import (
    _editor_snapshot_from_floor_plan,
    validate_snapshot,
)


def _snapshot(objects):
    return EditorSnapshot.model_validate(
        {
            "schemaVersion": "compose-editor-v1",
            "unit": "mm",
            "coordinateSpace": "local_mm",
            "floors": [
                {
                    "id": "floor-0",
                    "index": 0,
                    "name": "Ground Floor",
                    "elevationMm": 0,
                    "bounds": {"minX": 0, "minY": 0, "maxX": 10000, "maxY": 10000},
                }
            ],
            "objects": objects,
            "layers": [
                {
                    "id": "rooms",
                    "label": "Rooms",
                    "visible": True,
                    "locked": False,
                    "objectCount": 1,
                },
                {
                    "id": "walls",
                    "label": "Walls",
                    "visible": True,
                    "locked": False,
                    "objectCount": 1,
                },
                {
                    "id": "openings",
                    "label": "Openings",
                    "visible": True,
                    "locked": False,
                    "objectCount": 0,
                },
            ],
            "snapSettings": {
                "enabled": True,
                "grid": True,
                "corner": True,
                "wallIntersection": True,
                "parallel": True,
                "perpendicular": True,
                "center": True,
                "equalSpacingGuides": True,
            },
            "measurementOverlay": None,
            "source": {},
        }
    )


def test_editor_validation_accepts_basic_room_and_wall():
    result = validate_snapshot(
        _snapshot(
            [
                {
                    "id": "room-1",
                    "type": "room",
                    "floorId": "floor-0",
                    "layerId": "rooms",
                    "name": "Living",
                    "points": [
                        {"x": 0, "y": 0},
                        {"x": 4000, "y": 0},
                        {"x": 4000, "y": 3000},
                        {"x": 0, "y": 3000},
                    ],
                    "wallId": None,
                    "position": None,
                    "width": None,
                    "height": None,
                    "metadata": {"areaM2": 12},
                    "revisionCreated": 0,
                    "revisionUpdated": 0,
                    "deleted": False,
                },
                {
                    "id": "wall-1",
                    "type": "wall",
                    "floorId": "floor-0",
                    "layerId": "walls",
                    "name": "Wall",
                    "points": [{"x": 0, "y": 0}, {"x": 4000, "y": 0}],
                    "wallId": None,
                    "position": None,
                    "width": None,
                    "height": None,
                    "metadata": {"thicknessMm": 150},
                    "revisionCreated": 0,
                    "revisionUpdated": 0,
                    "deleted": False,
                },
            ]
        )
    )

    assert result.summary.status == "valid"
    assert result.summary.blocking_count == 0


def test_editor_validation_blocks_opening_without_wall():
    result = validate_snapshot(
        _snapshot(
            [
                {
                    "id": "door-1",
                    "type": "opening",
                    "floorId": "floor-0",
                    "layerId": "openings",
                    "name": "Door",
                    "points": [{"x": 0, "y": 0}, {"x": 900, "y": 0}],
                    "wallId": "missing-wall",
                    "position": None,
                    "width": 900,
                    "height": 2100,
                    "metadata": {"openingType": "door"},
                    "revisionCreated": 0,
                    "revisionUpdated": 0,
                    "deleted": False,
                }
            ]
        )
    )

    assert result.summary.status == "invalid"
    assert result.summary.blocking_count == 1
    assert result.issues[0].code == "INVALID_OPENING_WALL"


def test_floor_plan_import_namespaces_repeated_object_ids_per_floor():
    geometry = {
        "buildableEnvelope": [[0, 0], [5000, 0], [5000, 4000], [0, 4000]],
        "floors": [
            {
                "index": 0,
                "name": "Ground Floor",
                "rooms": [
                    {
                        "id": "living",
                        "name": "Living",
                        "polygon": [[0, 0], [4000, 0], [4000, 3000], [0, 3000]],
                    }
                ],
                "walls": [{"id": "wall-1", "start": [0, 0], "end": [4000, 0], "thicknessMm": 150}],
                "doors": [
                    {
                        "id": "door-1",
                        "wallId": "wall-1",
                        "start": [1500, 0],
                        "end": [2400, 0],
                        "widthMm": 900,
                    }
                ],
            },
            {
                "index": 1,
                "name": "First Floor",
                "rooms": [
                    {
                        "id": "living",
                        "name": "Family",
                        "polygon": [[0, 0], [4000, 0], [4000, 3000], [0, 3000]],
                    }
                ],
                "walls": [{"id": "wall-1", "start": [0, 0], "end": [4000, 0], "thicknessMm": 150}],
                "doors": [
                    {
                        "id": "door-1",
                        "wallId": "wall-1",
                        "start": [1500, 0],
                        "end": [2400, 0],
                        "widthMm": 900,
                    }
                ],
            },
        ],
    }
    snapshot = _editor_snapshot_from_floor_plan(
        geometry,
        SimpleNamespace(id=uuid4()),
        SimpleNamespace(id=uuid4(), coordinate_space="local_mm", geometry_hash="hash"),
    )
    object_ids = [item["id"] for item in snapshot["objects"]]
    openings = [item for item in snapshot["objects"] if item["type"] == "opening"]

    assert len(object_ids) == len(set(object_ids))
    assert {item["wallId"] for item in openings} == {"floor-0-wall-1", "floor-1-wall-1"}
    assert validate_snapshot(EditorSnapshot.model_validate(snapshot)).summary.blocking_count == 0
