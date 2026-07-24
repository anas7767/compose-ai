from fastapi.testclient import TestClient

from compose_ai_api.main import app


def test_live_health_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "compose-ai-api"}


def test_root_endpoint_points_to_docs() -> None:
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["docs"] == "/api/v1/docs"
