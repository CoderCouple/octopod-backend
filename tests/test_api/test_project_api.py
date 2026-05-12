import pytest


@pytest.mark.asyncio
async def test_create_project(authenticated_client):
    """POST /project should create a new project."""
    await authenticated_client.get("/api/v1/me")
    resp = await authenticated_client.post(
        "/api/v1/project",
        json={"name": "New Project", "slug": "new-project", "description": "A test project"},
    )
    assert resp.status_code == 201
    result = resp.json()["result"]
    assert result["name"] == "New Project"
    assert result["slug"] == "new-project"


@pytest.mark.asyncio
async def test_list_projects(authenticated_client):
    """GET /project should list projects in active org."""
    await authenticated_client.get("/api/v1/me")
    resp = await authenticated_client.get("/api/v1/project")
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["total"] >= 1  # Default project from auto-provision


@pytest.mark.asyncio
async def test_get_project(authenticated_client):
    """GET /project/{id} should return project details."""
    me_resp = await authenticated_client.get("/api/v1/me")
    project_id = me_resp.json()["result"]["project_id"]
    resp = await authenticated_client.get(f"/api/v1/project/{project_id}")
    assert resp.status_code == 200
    assert resp.json()["result"]["id"] == project_id


@pytest.mark.asyncio
async def test_update_project(authenticated_client):
    """PATCH /project/{id} should update project."""
    me_resp = await authenticated_client.get("/api/v1/me")
    project_id = me_resp.json()["result"]["project_id"]
    resp = await authenticated_client.patch(
        f"/api/v1/project/{project_id}", json={"name": "Updated Project"}
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["name"] == "Updated Project"


@pytest.mark.asyncio
async def test_delete_project(authenticated_client):
    """DELETE /project/{id} should soft-delete project."""
    # Create a new project first
    await authenticated_client.get("/api/v1/me")
    create_resp = await authenticated_client.post(
        "/api/v1/project",
        json={"name": "To Delete", "slug": "to-delete"},
    )
    project_id = create_resp.json()["result"]["id"]
    resp = await authenticated_client.delete(f"/api/v1/project/{project_id}")
    assert resp.status_code == 200
    assert resp.json()["success"] is True
