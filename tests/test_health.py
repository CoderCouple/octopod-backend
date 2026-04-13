import pytest
from fastapi.testclient import TestClient


def test_health_check(client: TestClient):
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["service"] == "octopod-backend"


def test_readiness_check(client: TestClient):
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert "timestamp" in data
    assert "checks" in data
    assert data["checks"]["database"] == "ok"
    assert data["checks"]["cache"] == "ok"


def test_root_endpoint(client: TestClient):
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data
    assert "Welcome to Octopod Backend" in data["message"]
    assert data["environment"] == "development"
    assert data["api_docs"] == "/docs"
    assert data["api_prefix"] == "/api/v1"