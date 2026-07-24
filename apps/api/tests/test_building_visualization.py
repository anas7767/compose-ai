from __future__ import annotations

from uuid import uuid4

from compose_ai_api.domains.building_visualization.compiler import (
    compile_scene_from_checkpoint,
    material_library,
    scene_graph,
)


def _snapshot() -> dict[str, object]:
    return {
        "schemaVersion": "compose-editor-v1",
        "unit": "mm",
        "coordinateSpace": "local_mm",
        "floors": [
            {
                "id": "floor-0",
                "index": 0,
                "name": "Ground Floor",
                "elevationMm": 0,
                "bounds": {"minX": 0, "minY": 0, "maxX": 8000, "maxY": 6000},
            }
        ],
        "objects": [
            {
                "id": "room-living",
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
                "id": "wall-front",
                "type": "wall",
                "floorId": "floor-0",
                "layerId": "walls",
                "name": "Front wall",
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
            {
                "id": "door-main",
                "type": "opening",
                "floorId": "floor-0",
                "layerId": "openings",
                "name": "Main door",
                "points": [{"x": 1200, "y": 0}, {"x": 2100, "y": 0}],
                "wallId": "wall-front",
                "position": None,
                "width": 900,
                "height": 2100,
                "metadata": {"openingType": "door"},
                "revisionCreated": 0,
                "revisionUpdated": 0,
                "deleted": False,
            },
        ],
        "layers": [],
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


def _validation_summary() -> dict[str, object]:
    return {
        "status": "valid",
        "issueCount": 0,
        "blockingCount": 0,
        "errorCount": 0,
        "warningCount": 0,
        "infoCount": 0,
    }


def test_material_library_contains_phase_8_categories() -> None:
    categories = {material.category for material in material_library()}

    assert categories == {
        "paint",
        "brick",
        "concrete",
        "marble",
        "granite",
        "wood",
        "glass",
        "metal",
        "tiles",
    }


def test_compiler_preserves_source_object_links_and_scene_graph() -> None:
    compiled = compile_scene_from_checkpoint(
        project_id=uuid4(),
        scene_version_id=uuid4(),
        source_design_version_id=uuid4(),
        source_editor_document_id=uuid4(),
        source_editor_checkpoint_id=uuid4(),
        source_editor_revision=3,
        checkpoint_hash="hash",
        snapshot=_snapshot(),
        validation_summary=_validation_summary(),
        quality_preset="balanced",
    )

    linked_ids = {item.source_2d_object_id for item in compiled.objects}
    graph = scene_graph(compiled.objects)

    assert "room-living" in linked_ids
    assert "wall-front" in linked_ids
    assert "door-main" in linked_ids
    assert graph[0].label == "Building"
    assert compiled.manifest.renderer_contract_version == "compose-renderer-neutral-v1"
    assert compiled.validation.summary.status == "valid"


def test_invalid_source_checkpoint_blocks_compilation() -> None:
    invalid_summary = _validation_summary()
    invalid_summary["blockingCount"] = 1

    compiled = compile_scene_from_checkpoint(
        project_id=uuid4(),
        scene_version_id=uuid4(),
        source_design_version_id=uuid4(),
        source_editor_document_id=uuid4(),
        source_editor_checkpoint_id=uuid4(),
        source_editor_revision=3,
        checkpoint_hash="hash",
        snapshot=_snapshot(),
        validation_summary=invalid_summary,
        quality_preset="balanced",
    )

    assert compiled.validation.summary.status == "invalid"
    assert compiled.validation.summary.blocking_count == 1
    assert compiled.validation.issues[0].code == "SOURCE_CHECKPOINT_INVALID"
