"""API tests for the /v1/health endpoint."""

from fastapi.testclient import TestClient


def test_health_endpoint(client: TestClient):
    response = client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "model_version" in data
    assert "data_version" in data
    assert "app_version" in data
