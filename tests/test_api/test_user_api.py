import pytest


@pytest.mark.asyncio
async def test_get_me(authenticated_client):
    """GET /me should auto-provision and return user context."""
    resp = await authenticated_client.get("/api/v1/me")
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    result = data["result"]
    assert result["user"]["cognito_sub"] == "test-user-00000000-0000-0000-0000-000000000001"
    assert result["user"]["email"] == "test@example.com"
    assert result["organization_id"] is not None
    assert result["project_id"] is not None
    assert result["role"] == "owner"


@pytest.mark.asyncio
async def test_update_me(authenticated_client):
    """PATCH /me should update display name."""
    # First call to auto-provision
    await authenticated_client.get("/api/v1/me")
    resp = await authenticated_client.patch(
        "/api/v1/me", json={"display_name": "New Name"}
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["display_name"] == "New Name"


@pytest.mark.asyncio
async def test_switch_context(authenticated_client):
    """PUT /me/context should update default org/project."""
    # First call to auto-provision and get IDs
    me_resp = await authenticated_client.get("/api/v1/me")
    org_id = me_resp.json()["result"]["organization_id"]
    project_id = me_resp.json()["result"]["project_id"]

    resp = await authenticated_client.put(
        "/api/v1/me/context",
        json={"organization_id": org_id, "project_id": project_id},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
