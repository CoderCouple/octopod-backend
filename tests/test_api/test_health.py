import pytest


@pytest.mark.asyncio
async def test_health_check(async_client):
    resp = await async_client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["service"] == "octopod-backend"


@pytest.mark.asyncio
async def test_readiness_check(async_client):
    resp = await async_client.get("/api/v1/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_root_endpoint(async_client):
    resp = await async_client.get("/")
    assert resp.status_code == 200
    assert "Welcome to Octopod Backend" in resp.json()["message"]
