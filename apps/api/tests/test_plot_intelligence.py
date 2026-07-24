from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from compose_ai_api.domains.plot_intelligence.analysis import (
    ANALYSIS_ENGINE_VERSION,
    BoundaryState,
    PlotState,
    RoadState,
    analyze_plot,
)
from compose_ai_api.domains.plot_intelligence.geometry import (
    GEOMETRY_ENGINE_VERSION,
    PlotGeometryError,
    normalize_geojson,
)
from compose_ai_api.domains.plot_intelligence.models import CoordinateSpace
from compose_ai_api.domains.plot_intelligence.schemas import PlotBoundaryInput
from compose_ai_api.domains.projects.models import UnitSystem
from compose_ai_api.main import app
from compose_ai_api.models.base import Base


def _polygon(points: list[list[float]]) -> dict[str, object]:
    return {"type": "Polygon", "coordinates": [points]}


def _state(
    *,
    boundary: BoundaryState | None = None,
    roads: tuple[RoadState, ...] = (),
    parking_spaces: int = 0,
) -> PlotState:
    return PlotState(
        project_id=uuid4(),
        profile_revision=3,
        plot_length_m=Decimal("10"),
        plot_width_m=Decimal("10"),
        plot_area_m2=Decimal("100"),
        plot_shape="rectangle",
        open_sides=1,
        corner_plot=False,
        orientation_degrees=Decimal("90"),
        north_rotation_degrees=Decimal("0"),
        north_reference="true",
        latitude=None,
        longitude=None,
        has_address=False,
        roads=roads,
        boundary=boundary,
        target_parking_spaces=parking_spaces,
    )


def test_plot_tables_and_routes_are_registered() -> None:
    expected_tables = {
        "project_plot_road_sides",
        "plot_boundary_versions",
        "plot_analysis_snapshots",
        "plot_boundary_restore_actions",
    }

    assert expected_tables.issubset(Base.metadata.tables)
    response = TestClient(app).get(f"/api/v1/projects/{uuid4()}/plot")
    assert response.status_code == 401


def test_local_geometry_is_normalized_to_canonical_meters() -> None:
    geometry = normalize_geojson(
        _polygon([[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]),
        CoordinateSpace.LOCAL_CARTESIAN,
        UnitSystem.METRIC,
    )

    assert geometry.area_m2 == Decimal("100.0")
    assert geometry.perimeter_m == Decimal("40.0")
    assert geometry.vertex_count == 4
    assert geometry.geometry_engine_version == GEOMETRY_ENGINE_VERSION


def test_imperial_local_geometry_converts_before_measurement() -> None:
    geometry = normalize_geojson(
        _polygon([[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]),
        CoordinateSpace.LOCAL_CARTESIAN,
        UnitSystem.IMPERIAL,
    )

    assert geometry.area_m2 == Decimal("9.29")
    assert geometry.perimeter_m == Decimal("12.192")


def test_self_intersecting_geometry_is_rejected() -> None:
    with pytest.raises(PlotGeometryError) as error:
        normalize_geojson(
            _polygon([[0, 0], [10, 10], [10, 0], [0, 10], [0, 0]]),
            CoordinateSpace.LOCAL_CARTESIAN,
            UnitSystem.METRIC,
        )

    assert error.value.code == "PLOT_GEOMETRY_INVALID"


def test_analysis_records_geometry_engine_independently_from_analysis_engine() -> None:
    boundary = BoundaryState(
        id=uuid4(),
        version=7,
        area_m2=Decimal("100"),
        perimeter_m=Decimal("40"),
        vertex_count=4,
        edge_lengths_m=(Decimal("10"),) * 4,
        warnings=(),
    )
    roads = (
        RoadState(
            id=uuid4(),
            direction="north",
            is_primary=True,
            boundary_edge_index=0,
            road_width_m=Decimal("6"),
            access_allowed=True,
        ),
    )

    analysis = analyze_plot(_state(boundary=boundary, roads=roads, parking_spaces=1))

    assert analysis.analysis_engine_version == ANALYSIS_ENGINE_VERSION
    assert analysis.geometry_engine_version == GEOMETRY_ENGINE_VERSION
    assert analysis.analysis_engine_version != analysis.geometry_engine_version
    assert analysis.parking_status == "likely"
    assert analysis.coverage_status == "awaiting_building_footprint"
    assert analysis.regulation_status == "not_configured"


def test_analysis_detects_a_road_edge_outside_the_boundary() -> None:
    boundary = BoundaryState(
        id=uuid4(),
        version=1,
        area_m2=Decimal("100"),
        perimeter_m=Decimal("40"),
        vertex_count=4,
        edge_lengths_m=(Decimal("10"),) * 4,
        warnings=(),
    )
    roads = (
        RoadState(
            id=uuid4(),
            direction="north",
            is_primary=True,
            boundary_edge_index=5,
            road_width_m=None,
            access_allowed=True,
        ),
    )

    analysis = analyze_plot(_state(boundary=boundary, roads=roads, parking_spaces=1))

    assert any(issue["code"] == "PLOT_ROAD_EDGE_INVALID" for issue in analysis.issues)
    assert analysis.feasibility_status == "invalid"


def test_boundary_input_does_not_accept_internal_immutable_sources() -> None:
    with pytest.raises(ValidationError):
        PlotBoundaryInput(
            coordinate_space="local_cartesian",
            geojson=_polygon([[0, 0], [1, 0], [1, 1], [0, 0]]),
            source="restore",
        )
