from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from compose_ai_api.domains.building_visualization.schemas import (
    SceneBoundingBox,
    SceneCamera,
    SceneCameraPreset,
    SceneGeometry,
    SceneGraphNode,
    SceneLighting,
    SceneManifest,
    SceneMaterial,
    SceneObject,
    SceneTransform,
    SceneValidationIssue,
    SceneValidationResponse,
    SceneValidationSummary,
    SceneVector3,
)
from compose_ai_api.domains.floor_plan_editor.schemas import EditorSnapshot, EditorValidationSummary
from compose_ai_api.domains.floor_plans.schemas import CONCEPTUAL_DISCLAIMER

SCENE_SCHEMA_VERSION = "compose-scene-v1"
SCENE_ENGINE_VERSION = "compose-scene-compiler-v1"
SCENE_GEOMETRY_ENGINE_VERSION = "compose-2d-to-3d-v1"
MATERIAL_SCHEMA_VERSION = "compose-materials-v1"
RENDERER_CONTRACT_VERSION = "compose-renderer-neutral-v1"
SCENE_VALIDATION_ENGINE_VERSION = "compose-scene-validation-v1"
WALL_HEIGHT_MM = 3000
WALL_THICKNESS_MM = 150
SLAB_THICKNESS_MM = 150
ROOF_THICKNESS_MM = 160


@dataclass(frozen=True)
class CompiledScene:
    manifest: SceneManifest
    objects: list[SceneObject]
    materials: list[SceneMaterial]
    validation: SceneValidationResponse
    input_hash: str


def compile_scene_from_checkpoint(
    *,
    project_id: UUID,
    scene_version_id: UUID,
    source_design_version_id: UUID,
    source_editor_document_id: UUID,
    source_editor_checkpoint_id: UUID,
    source_editor_revision: int,
    checkpoint_hash: str,
    snapshot: dict[str, Any],
    validation_summary: dict[str, Any],
    quality_preset: str,
) -> CompiledScene:
    editor_snapshot = EditorSnapshot.model_validate(snapshot)
    editor_summary = EditorValidationSummary.model_validate(validation_summary)
    input_hash = _hash_json(
        {
            "checkpointHash": checkpoint_hash,
            "sourceEditorRevision": source_editor_revision,
            "schema": SCENE_SCHEMA_VERSION,
            "engine": SCENE_ENGINE_VERSION,
            "geometry": SCENE_GEOMETRY_ENGINE_VERSION,
            "quality": quality_preset,
        }
    )
    materials = material_library()
    objects: list[SceneObject] = []
    issues: list[SceneValidationIssue] = []
    if editor_summary.blocking_count or editor_summary.error_count:
        issues.append(
            _issue(
                "SOURCE_CHECKPOINT_INVALID",
                "blocking",
                None,
                None,
                "The source 2D checkpoint has blocking or error validation issues.",
            )
        )

    for floor in editor_snapshot.floors:
        floor_group_id = f"scene-floor-{floor.id}"
        bounds = SceneBoundingBox(
            min=SceneVector3(x=floor.bounds.min_x, y=floor.elevation_mm, z=floor.bounds.min_y),
            max=SceneVector3(
                x=floor.bounds.max_x,
                y=floor.elevation_mm + WALL_HEIGHT_MM,
                z=floor.bounds.max_y,
            ),
        )
        objects.append(
            _scene_object(
                stable_object_id=floor_group_id,
                object_type="floor",
                source_2d_object_id=floor.id,
                source_2d_object_type="floor",
                floor_id=floor.id,
                parent_object_id="building-root",
                name=floor.name,
                material_id="mat-concrete-default",
                geometry=SceneGeometry(kind="placeholder"),
                bounding_box=bounds,
                metadata={"elevationMm": floor.elevation_mm, "floorIndex": floor.index},
            )
        )
        objects.append(_slab_for_floor(floor, floor_group_id))

    for item in editor_snapshot.objects:
        if item.deleted:
            continue
        if item.type == "room":
            objects.append(_room_volume(item))
        elif item.type == "wall":
            objects.append(_wall_mesh(item))
        elif item.type == "opening":
            objects.append(_opening_mesh(item))
        elif item.type == "stair":
            objects.append(_stair_mesh(item))

    roof = _roof_placeholder(editor_snapshot)
    if roof is not None:
        objects.append(roof)
    plot = _plot_boundary(editor_snapshot)
    if plot is not None:
        objects.append(plot)

    issues.extend(validate_scene_objects(objects))
    summary = _summary(issues)
    scene_bounds = _combined_bounds([item.bounding_box for item in objects])
    manifest = SceneManifest(
        scene_version_id=scene_version_id,
        project_id=project_id,
        source_design_version_id=source_design_version_id,
        source_editor_document_id=source_editor_document_id,
        source_editor_checkpoint_id=source_editor_checkpoint_id,
        source_editor_revision=source_editor_revision,
        scene_schema_version=SCENE_SCHEMA_VERSION,
        geometry_engine_version=SCENE_GEOMETRY_ENGINE_VERSION,
        scene_engine_version=SCENE_ENGINE_VERSION,
        material_schema_version=MATERIAL_SCHEMA_VERSION,
        renderer_contract_version=RENDERER_CONTRACT_VERSION,
        unit=editor_snapshot.unit,
        coordinate_space=editor_snapshot.coordinate_space,
        bounding_box=scene_bounds,
        object_count=len(objects),
        triangle_count=sum(item.triangle_count for item in objects),
        camera_presets=_camera_presets(scene_bounds),
        lighting=_lighting("noon"),
        environment_presets=["morning", "noon", "evening", "night"],
        quality_presets=["low", "balanced", "high"],
        section_box={"enabled": False},
        source_versions={
            "checkpointHash": checkpoint_hash,
            "editorSchemaVersion": editor_snapshot.schema_version,
            "source": editor_snapshot.source,
        },
        disclaimer=CONCEPTUAL_DISCLAIMER,
    )
    return CompiledScene(
        manifest=manifest,
        objects=objects,
        materials=materials,
        validation=SceneValidationResponse(
            scene_version_id=scene_version_id,
            validation_engine_version=SCENE_VALIDATION_ENGINE_VERSION,
            geometry_engine_version=SCENE_GEOMETRY_ENGINE_VERSION,
            summary=summary,
            issues=issues,
        ),
        input_hash=input_hash,
    )


def material_library() -> list[SceneMaterial]:
    return [
        _material("mat-paint-white", "Architectural White Paint", "paint", "#f8fafc"),
        _material("mat-brick-warm", "Warm Brick", "brick", "#b86f53"),
        _material("mat-concrete-default", "Soft Concrete", "concrete", "#d7dbe1"),
        _material("mat-marble-light", "Light Marble", "marble", "#f4f1ea"),
        _material("mat-granite-muted", "Muted Granite", "granite", "#8a8f98"),
        _material("mat-wood-oak", "Natural Oak Wood", "wood", "#c4935a"),
        _material(
            "mat-glass-clear",
            "Clear Architectural Glass",
            "glass",
            "#9bd4ff",
            opacity=0.42,
            transparent=True,
        ),
        _material("mat-metal-charcoal", "Charcoal Metal", "metal", "#5d6673", metalness=0.35),
        _material("mat-tiles-stone", "Stone Floor Tiles", "tiles", "#e3e0d8"),
    ]


def validate_scene_objects(objects: list[SceneObject]) -> list[SceneValidationIssue]:
    issues: list[SceneValidationIssue] = []
    stable_ids = [item.stable_object_id for item in objects]
    for stable_id in sorted({item for item in stable_ids if stable_ids.count(item) > 1}):
        issues.append(
            _issue(
                "DUPLICATE_SCENE_OBJECT_ID",
                "blocking",
                stable_id,
                None,
                "Scene object IDs must be stable and unique.",
            )
        )
    for item in objects:
        if item.object_type == "wall":
            height = item.metadata.get("heightMm", 0)
            thickness = item.metadata.get("thicknessMm", 0)
            if height <= 0 or thickness <= 0:
                issues.append(
                    _issue(
                        "INVALID_WALL_VOLUME",
                        "blocking",
                        item.stable_object_id,
                        item.source_2d_object_id,
                        "Wall height and thickness must be positive.",
                    )
                )
        if item.object_type in {"door", "window"} and not item.metadata.get("hostWallId"):
            issues.append(
                _issue(
                    "OPENING_WITHOUT_HOST",
                    "blocking",
                    item.stable_object_id,
                    item.source_2d_object_id,
                    "Openings require a host wall.",
                )
            )
        if item.bounding_box.max.y < item.bounding_box.min.y:
            issues.append(
                _issue(
                    "INVALID_VERTICAL_BOUNDS",
                    "blocking",
                    item.stable_object_id,
                    item.source_2d_object_id,
                    "Scene object vertical bounds are invalid.",
                )
            )
    return issues


def scene_graph(objects: list[SceneObject]) -> list[SceneGraphNode]:
    floors: dict[str, SceneGraphNode] = {}
    root = SceneGraphNode(id="building-root", label="Building", object_type="building")
    groups = {
        "room": "Rooms",
        "wall": "Walls",
        "door": "Doors",
        "window": "Windows",
        "stair": "Stairs",
    }
    for obj in objects:
        if obj.object_type == "floor" and obj.floor_id:
            floors[obj.floor_id] = SceneGraphNode(
                id=obj.stable_object_id,
                label=obj.name,
                object_type="floor",
                source_2d_object_id=obj.source_2d_object_id,
            )
    for floor_node in floors.values():
        floor_node.children = [
            SceneGraphNode(id=f"{floor_node.id}-{kind}", label=label, object_type=kind)
            for kind, label in groups.items()
        ]
    for obj in objects:
        if obj.object_type not in groups or not obj.floor_id or obj.floor_id not in floors:
            continue
        floor_node = floors[obj.floor_id]
        group = next(child for child in floor_node.children if child.object_type == obj.object_type)
        group.children.append(
            SceneGraphNode(
                id=obj.stable_object_id,
                label=obj.name,
                object_type=obj.object_type,
                source_2d_object_id=obj.source_2d_object_id,
            )
        )
    root.children = list(floors.values())
    return [root]


def _scene_object(
    *,
    stable_object_id: str,
    object_type: str,
    source_2d_object_id: str | None,
    source_2d_object_type: str | None,
    floor_id: str | None,
    parent_object_id: str | None,
    name: str,
    material_id: str,
    geometry: SceneGeometry,
    bounding_box: SceneBoundingBox,
    metadata: dict[str, Any] | None = None,
) -> SceneObject:
    return SceneObject(
        id=uuid4(),
        stable_object_id=stable_object_id,
        source_2d_object_id=source_2d_object_id,
        source_2d_object_type=source_2d_object_type,
        object_type=object_type,  # type: ignore[arg-type]
        floor_id=floor_id,
        parent_object_id=parent_object_id,
        name=name,
        geometry_kind=geometry.kind,
        transform=SceneTransform(
            position=SceneVector3(x=0, y=0, z=0),
            rotation=SceneVector3(x=0, y=0, z=0),
        ),
        geometry=geometry,
        bounding_box=bounding_box,
        material_id=material_id,
        triangle_count=max(0, len(geometry.indices) // 3),
        metadata=metadata or {},
    )


def _room_volume(item: Any) -> SceneObject:
    bounds = _point_bounds(item.points, _floor_y(item.floor_id), WALL_HEIGHT_MM)
    return _scene_object(
        stable_object_id=f"room-volume-{item.id}",
        object_type="room",
        source_2d_object_id=item.id,
        source_2d_object_type=item.type,
        floor_id=item.floor_id,
        parent_object_id=f"scene-floor-{item.floor_id}",
        name=item.name or "Room",
        material_id="mat-paint-white",
        geometry=SceneGeometry(
            kind="extrusion",
            source_polygon=[_point_json(point) for point in item.points],
            dimensions={"heightMm": WALL_HEIGHT_MM},
        ),
        bounding_box=bounds,
        metadata={"areaM2": item.metadata.get("areaM2"), "sourceLayerId": item.layer_id},
    )


def _wall_mesh(item: Any) -> SceneObject:
    start, end = item.points[0], item.points[1]
    thickness = float(item.metadata.get("thicknessMm") or WALL_THICKNESS_MM)
    bounds = _segment_bounds(start, end, _floor_y(item.floor_id), WALL_HEIGHT_MM, thickness)
    return _scene_object(
        stable_object_id=f"wall-mesh-{item.id}",
        object_type="wall",
        source_2d_object_id=item.id,
        source_2d_object_type=item.type,
        floor_id=item.floor_id,
        parent_object_id=f"scene-floor-{item.floor_id}",
        name=item.name or "Wall",
        material_id="mat-paint-white",
        geometry=SceneGeometry(
            kind="box",
            vertices=[
                SceneVector3(x=start.x, y=_floor_y(item.floor_id), z=start.y),
                SceneVector3(x=end.x, y=_floor_y(item.floor_id), z=end.y),
            ],
            dimensions={
                "lengthMm": _distance(start.x, start.y, end.x, end.y),
                "heightMm": WALL_HEIGHT_MM,
                "thicknessMm": thickness,
            },
        ),
        bounding_box=bounds,
        metadata={"heightMm": WALL_HEIGHT_MM, "thicknessMm": thickness},
    )


def _opening_mesh(item: Any) -> SceneObject:
    opening_type = item.metadata.get("openingType") or "door"
    sill = 900 if opening_type == "window" else 0
    height = float(item.height or (1200 if opening_type == "window" else 2100))
    bounds = _point_bounds(item.points, _floor_y(item.floor_id) + sill, height)
    return _scene_object(
        stable_object_id=f"{opening_type}-void-{item.id}",
        object_type="window" if opening_type == "window" else "door",
        source_2d_object_id=item.id,
        source_2d_object_type=item.type,
        floor_id=item.floor_id,
        parent_object_id=f"wall-mesh-{item.wall_id}",
        name=item.name or str(opening_type).title(),
        material_id="mat-glass-clear" if opening_type == "window" else "mat-wood-oak",
        geometry=SceneGeometry(
            kind="box",
            source_polygon=[_point_json(point) for point in item.points],
            dimensions={"widthMm": float(item.width or 900), "heightMm": height, "sillMm": sill},
        ),
        bounding_box=bounds,
        metadata={"hostWallId": item.wall_id, "openingType": opening_type},
    )


def _stair_mesh(item: Any) -> SceneObject:
    bounds = _point_bounds(item.points, _floor_y(item.floor_id), WALL_HEIGHT_MM)
    return _scene_object(
        stable_object_id=f"stair-volume-{item.id}",
        object_type="stair",
        source_2d_object_id=item.id,
        source_2d_object_type=item.type,
        floor_id=item.floor_id,
        parent_object_id=f"scene-floor-{item.floor_id}",
        name=item.name or "Stair",
        material_id="mat-concrete-default",
        geometry=SceneGeometry(
            kind="placeholder",
            source_polygon=[_point_json(point) for point in item.points],
            dimensions={"heightMm": WALL_HEIGHT_MM},
        ),
        bounding_box=bounds,
        metadata={"verticalConnection": item.metadata.get("connectsToFloorId")},
    )


def _slab_for_floor(floor: Any, floor_group_id: str) -> SceneObject:
    bounds = SceneBoundingBox(
        min=SceneVector3(
            x=floor.bounds.min_x,
            y=floor.elevation_mm - SLAB_THICKNESS_MM,
            z=floor.bounds.min_y,
        ),
        max=SceneVector3(x=floor.bounds.max_x, y=floor.elevation_mm, z=floor.bounds.max_y),
    )
    return _scene_object(
        stable_object_id=f"slab-{floor.id}",
        object_type="slab",
        source_2d_object_id=floor.id,
        source_2d_object_type="floor",
        floor_id=floor.id,
        parent_object_id=floor_group_id,
        name=f"{floor.name} slab",
        material_id="mat-concrete-default",
        geometry=SceneGeometry(
            kind="box",
            dimensions={
                "widthMm": floor.bounds.max_x - floor.bounds.min_x,
                "depthMm": floor.bounds.max_y - floor.bounds.min_y,
                "heightMm": SLAB_THICKNESS_MM,
            },
        ),
        bounding_box=bounds,
        metadata={"source": "generated_slab"},
    )


def _roof_placeholder(snapshot: EditorSnapshot) -> SceneObject | None:
    if not snapshot.floors:
        return None
    top_floor = max(snapshot.floors, key=lambda floor: floor.elevation_mm)
    y = top_floor.elevation_mm + WALL_HEIGHT_MM
    bounds = SceneBoundingBox(
        min=SceneVector3(x=top_floor.bounds.min_x, y=y, z=top_floor.bounds.min_y),
        max=SceneVector3(
            x=top_floor.bounds.max_x,
            y=y + ROOF_THICKNESS_MM,
            z=top_floor.bounds.max_y,
        ),
    )
    return _scene_object(
        stable_object_id="roof-placeholder",
        object_type="roof",
        source_2d_object_id=top_floor.id,
        source_2d_object_type="floor",
        floor_id=top_floor.id,
        parent_object_id="building-root",
        name="Conceptual roof",
        material_id="mat-metal-charcoal",
        geometry=SceneGeometry(kind="box", dimensions={"heightMm": ROOF_THICKNESS_MM}),
        bounding_box=bounds,
        metadata={"placeholder": True},
    )


def _plot_boundary(snapshot: EditorSnapshot) -> SceneObject | None:
    if not snapshot.floors:
        return None
    bounds = _combined_bounds(
        [
            SceneBoundingBox(
                min=SceneVector3(x=floor.bounds.min_x, y=0, z=floor.bounds.min_y),
                max=SceneVector3(x=floor.bounds.max_x, y=0, z=floor.bounds.max_y),
            )
            for floor in snapshot.floors
        ]
    )
    padding = 2000
    bounds = SceneBoundingBox(
        min=SceneVector3(x=bounds.min.x - padding, y=0, z=bounds.min.z - padding),
        max=SceneVector3(x=bounds.max.x + padding, y=0, z=bounds.max.z + padding),
    )
    return _scene_object(
        stable_object_id="plot-boundary",
        object_type="plot_boundary",
        source_2d_object_id=None,
        source_2d_object_type=None,
        floor_id=None,
        parent_object_id=None,
        name="Plot boundary",
        material_id="mat-tiles-stone",
        geometry=SceneGeometry(kind="plane"),
        bounding_box=bounds,
        metadata={"placeholder": True},
    )


def _camera_presets(bounds: SceneBoundingBox) -> list[SceneCameraPreset]:
    center = _center(bounds)
    span = max(bounds.max.x - bounds.min.x, bounds.max.z - bounds.min.z, 6000)
    height = max(bounds.max.y - bounds.min.y, 3000)
    return [
        SceneCameraPreset(
            id="isometric",
            label="Isometric",
            camera=SceneCamera(
                position=SceneVector3(x=center.x + span, y=height * 1.8, z=center.z + span),
                target=center,
            ),
        ),
        SceneCameraPreset(
            id="top",
            label="Top",
            camera=SceneCamera(
                position=SceneVector3(x=center.x, y=height * 2.4, z=center.z + 1),
                target=center,
            ),
        ),
        SceneCameraPreset(
            id="front",
            label="Front",
            camera=SceneCamera(
                position=SceneVector3(x=center.x, y=height * 0.75, z=bounds.min.z - span),
                target=center,
            ),
        ),
        SceneCameraPreset(
            id="walkthrough",
            label="Walkthrough",
            camera=SceneCamera(
                position=SceneVector3(x=center.x, y=1650, z=bounds.min.z - 1200),
                target=SceneVector3(x=center.x, y=1600, z=center.z),
                fov=60,
            ),
        ),
    ]


def _lighting(preset: str) -> SceneLighting:
    settings = {
        "morning": ("#f8fbff", 1.25, 2.5, SceneVector3(x=-0.65, y=0.85, z=0.35)),
        "noon": ("#ffffff", 1.45, 3.1, SceneVector3(x=-0.25, y=1, z=0.2)),
        "evening": ("#fff7ed", 1.1, 2.0, SceneVector3(x=0.75, y=0.45, z=0.2)),
        "night": ("#eef2ff", 0.7, 0.85, SceneVector3(x=-0.35, y=0.6, z=-0.7)),
    }
    background, ambient, sun, direction = settings.get(preset, settings["noon"])
    return SceneLighting(
        environment_preset=preset,  # type: ignore[arg-type]
        ambient_intensity=ambient,
        sun_intensity=sun,
        sun_direction=direction,
        background=background,
    )


def _material(
    material_id: str,
    name: str,
    category: str,
    color: str,
    *,
    opacity: float = 1,
    transparent: bool = False,
    metalness: float = 0,
) -> SceneMaterial:
    return SceneMaterial(
        material_id=material_id,
        name=name,
        category=category,  # type: ignore[arg-type]
        color=color,
        opacity=opacity,
        transparent=transparent,
        metalness=metalness,
        properties={"libraryFoundation": True},
    )


def _issue(
    code: str,
    severity: str,
    object_id: str | None,
    source_2d_object_id: str | None,
    message: str,
) -> SceneValidationIssue:
    return SceneValidationIssue(
        id=f"{code.lower()}-{object_id or source_2d_object_id or 'scene'}",
        code=code,
        severity=severity,  # type: ignore[arg-type]
        object_id=object_id,
        source_2d_object_id=source_2d_object_id,
        message=message,
        reason=message,
        blocking=severity == "blocking",
    )


def _summary(issues: list[SceneValidationIssue]) -> SceneValidationSummary:
    counts = {
        "blocking": sum(1 for issue in issues if issue.severity == "blocking"),
        "error": sum(1 for issue in issues if issue.severity == "error"),
        "warning": sum(1 for issue in issues if issue.severity == "warning"),
        "info": sum(1 for issue in issues if issue.severity == "info"),
    }
    return SceneValidationSummary(
        status="invalid" if counts["blocking"] or counts["error"] else "valid",
        issue_count=len(issues),
        blocking_count=counts["blocking"],
        error_count=counts["error"],
        warning_count=counts["warning"],
        info_count=counts["info"],
    )


def _point_json(point: Any) -> dict[str, float]:
    return {"x": float(point.x), "y": float(point.y)}


def _point_bounds(points: list[Any], base_y: float, height: float) -> SceneBoundingBox:
    xs = [float(point.x) for point in points] or [0]
    zs = [float(point.y) for point in points] or [0]
    return SceneBoundingBox(
        min=SceneVector3(x=min(xs), y=base_y, z=min(zs)),
        max=SceneVector3(x=max(xs), y=base_y + height, z=max(zs)),
    )


def _segment_bounds(
    start: Any, end: Any, base_y: float, height: float, thickness: float
) -> SceneBoundingBox:
    return SceneBoundingBox(
        min=SceneVector3(
            x=min(start.x, end.x) - thickness / 2,
            y=base_y,
            z=min(start.y, end.y) - thickness / 2,
        ),
        max=SceneVector3(
            x=max(start.x, end.x) + thickness / 2,
            y=base_y + height,
            z=max(start.y, end.y) + thickness / 2,
        ),
    )


def _combined_bounds(bounds: list[SceneBoundingBox]) -> SceneBoundingBox:
    if not bounds:
        return SceneBoundingBox(
            min=SceneVector3(x=0, y=0, z=0),
            max=SceneVector3(x=1000, y=1000, z=1000),
        )
    return SceneBoundingBox(
        min=SceneVector3(
            x=min(bound.min.x for bound in bounds),
            y=min(bound.min.y for bound in bounds),
            z=min(bound.min.z for bound in bounds),
        ),
        max=SceneVector3(
            x=max(bound.max.x for bound in bounds),
            y=max(bound.max.y for bound in bounds),
            z=max(bound.max.z for bound in bounds),
        ),
    )


def _center(bounds: SceneBoundingBox) -> SceneVector3:
    return SceneVector3(
        x=(bounds.min.x + bounds.max.x) / 2,
        y=(bounds.min.y + bounds.max.y) / 2,
        z=(bounds.min.z + bounds.max.z) / 2,
    )


def _floor_y(floor_id: str | None) -> float:
    if not floor_id:
        return 0
    suffix = floor_id.rsplit("-", 1)[-1]
    return float(int(suffix) * WALL_HEIGHT_MM) if suffix.isdigit() else 0


def _distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)


def _hash_json(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
