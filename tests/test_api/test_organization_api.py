import pytest


@pytest.mark.asyncio
async def test_create_organization(authenticated_client):
    """POST /organization should create a new org."""
    # Auto-provision user first
    await authenticated_client.get("/api/v1/me")
    resp = await authenticated_client.post(
        "/api/v1/organization", json={"name": "Test Org", "slug": "test-org"}
    )
    assert resp.status_code == 201
    result = resp.json()["result"]
    assert result["name"] == "Test Org"
    assert result["slug"] == "test-org"
    assert result["plan"] == "free"


@pytest.mark.asyncio
async def test_list_organizations(authenticated_client):
    """GET /organization should list user's orgs."""
    await authenticated_client.get("/api/v1/me")
    resp = await authenticated_client.get("/api/v1/organization")
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["total"] >= 1  # Personal org from auto-provision


@pytest.mark.asyncio
async def test_get_organization(authenticated_client):
    """GET /organization/{id} should return org details."""
    me_resp = await authenticated_client.get("/api/v1/me")
    org_id = me_resp.json()["result"]["organization_id"]
    resp = await authenticated_client.get(f"/api/v1/organization/{org_id}")
    assert resp.status_code == 200
    assert resp.json()["result"]["id"] == org_id


@pytest.mark.asyncio
async def test_update_organization(authenticated_client):
    """PATCH /organization/{id} should update org."""
    me_resp = await authenticated_client.get("/api/v1/me")
    org_id = me_resp.json()["result"]["organization_id"]
    resp = await authenticated_client.patch(
        f"/api/v1/organization/{org_id}", json={"name": "Updated Org"}
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["name"] == "Updated Org"


@pytest.mark.asyncio
async def test_list_members(authenticated_client):
    """GET /organization/{id}/members should list members."""
    me_resp = await authenticated_client.get("/api/v1/me")
    org_id = me_resp.json()["result"]["organization_id"]
    resp = await authenticated_client.get(f"/api/v1/organization/{org_id}/members")
    assert resp.status_code == 200
    assert resp.json()["result"]["total"] >= 1
