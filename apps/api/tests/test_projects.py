from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from compose_ai_api.domains.projects.models import (
    Project,
    ProjectRoomRequirement,
    ProjectSite,
    ProjectType,
)
from compose_ai_api.domains.projects.schemas import (
    ProjectCreateRequest,
    ProjectRoomRequirementInput,
    ProjectSitePatch,
    ProjectUpdateRequest,
)
from compose_ai_api.domains.projects.service import (
    _apply_room_requirements,
    _validate_project_completion,
    _validate_site,
    decode_cursor,
    encode_cursor,
)
from compose_ai_api.main import app
from compose_ai_api.models.base import Base


def test_project_routes_require_authentication() -> None:
    response = TestClient(app).get("/api/v1/projects")

    assert response.status_code == 401


def test_project_tables_are_registered() -> None:
    expected_tables = {
        "projects",
        "project_clients",
        "project_sites",
        "project_requirements",
        "project_room_requirements",
        "tags",
        "project_tag_assignments",
        "audit_logs",
        "idempotency_records",
    }

    assert expected_tables.issubset(Base.metadata.tables)


def test_project_name_and_tags_are_normalized() -> None:
    create_request = ProjectCreateRequest(name="  Lake   House  ")
    update_request = ProjectUpdateRequest(tags=["Concept", " concept ", "Residential"])

    assert create_request.name == "Lake House"
    assert update_request.tags == ["Concept", "Residential"]


def test_site_coordinates_must_be_supplied_together() -> None:
    with pytest.raises(ValidationError):
        ProjectSitePatch(latitude=Decimal("12.971599"))


def test_corner_plot_requires_valid_road_profile() -> None:
    site = ProjectSite(
        corner_plot=True,
        open_sides=1,
        road_direction_primary="north",
    )

    with pytest.raises(HTTPException) as error:
        _validate_site(site)

    assert error.value.status_code == 422
    assert error.value.detail["code"] == "PROJECT_SITE_INVALID"


def test_project_completion_requires_type_and_country() -> None:
    project = Project(
        id=uuid4(),
        organization_id=uuid4(),
        name="Courtyard House",
        country=None,
        project_type=None,
    )

    with pytest.raises(HTTPException) as error:
        _validate_project_completion(project)

    assert error.value.detail["code"] == "PROJECT_COMPLETION_INVALID"
    assert error.value.detail["details"]["missingFields"] == ["projectType", "country"]


def test_project_cursor_round_trip() -> None:
    project = Project(
        id=uuid4(),
        organization_id=uuid4(),
        name="Courtyard House",
        project_type=ProjectType.RESIDENTIAL_HOUSE,
    )
    project.updated_at = datetime.now(UTC)

    cursor_time, cursor_id = decode_cursor(encode_cursor(project))

    assert cursor_time == project.updated_at
    assert cursor_id == project.id


def test_room_update_preserves_existing_model_identity() -> None:
    room_id = uuid4()
    existing_room = ProjectRoomRequirement(
        id=room_id,
        name="Study",
        quantity=1,
        sort_order=0,
    )
    project = Project(
        id=uuid4(),
        organization_id=uuid4(),
        name="Courtyard House",
        room_requirements=[existing_room],
    )
    request = ProjectUpdateRequest(
        room_requirements=[
            ProjectRoomRequirementInput(
                id=room_id,
                name="Home office",
                quantity=2,
                sort_order=0,
            )
        ]
    )

    _apply_room_requirements(project, request)

    assert project.room_requirements == [existing_room]
    assert existing_room.name == "Home office"
    assert existing_room.quantity == 2


def test_room_update_rejects_foreign_room_identifier() -> None:
    project = Project(
        id=uuid4(),
        organization_id=uuid4(),
        name="Courtyard House",
        room_requirements=[],
    )
    request = ProjectUpdateRequest(
        room_requirements=[
            ProjectRoomRequirementInput(
                id=uuid4(),
                name="Study",
                quantity=1,
                sort_order=0,
            )
        ]
    )

    with pytest.raises(HTTPException) as error:
        _apply_room_requirements(project, request)

    assert error.value.status_code == 422
    assert error.value.detail["code"] == "PROJECT_ROOM_INVALID"
