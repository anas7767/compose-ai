from fastapi.testclient import TestClient

from compose_ai_api.main import app
from compose_ai_api.models.base import Base


def test_phase_9_version_management_contract_is_registered() -> None:
    table = Base.metadata.tables["floor_plan_design_versions"]

    assert "restored_from_design_version_id" in table.c
    assert "version_metadata" in table.c
    assert "source_provider" in table.c
    assert "generation_cost_microusd" in table.c
    assert "deleted_at" in table.c

    response = TestClient(app).get(f"/api/v1/projects/{'0' * 32}/floor-plans/design-versions")
    assert response.status_code == 401
