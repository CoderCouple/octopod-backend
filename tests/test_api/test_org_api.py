import pytest


@pytest.mark.asyncio
async def test_create_org(async_client):
    resp = await async_client.post(
        "/api/v1/org", json={"name": "Acme", "domain": "acme.com"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["result"]["name"] == "Acme"
    assert body["result"]["id"].startswith("org_")


@pytest.mark.asyncio
async def test_list_orgs(async_client):
    await async_client.post("/api/v1/org", json={"name": "Org1"})
    await async_client.post("/api/v1/org", json={"name": "Org2"})
    resp = await async_client.get("/api/v1/org")
    assert resp.status_code == 200
    assert resp.json()["result"]["total"] == 2


@pytest.mark.asyncio
async def test_get_org(async_client):
    create = await async_client.post("/api/v1/org", json={"name": "Acme"})
    org_id = create.json()["result"]["id"]
    resp = await async_client.get(f"/api/v1/org/{org_id}")
    assert resp.status_code == 200
    assert resp.json()["result"]["id"] == org_id


@pytest.mark.asyncio
async def test_get_org_not_found(async_client):
    resp = await async_client.get("/api/v1/org/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_org(async_client):
    create = await async_client.post("/api/v1/org", json={"name": "Old"})
    org_id = create.json()["result"]["id"]
    resp = await async_client.patch(f"/api/v1/org/{org_id}", json={"name": "New"})
    assert resp.status_code == 200
    assert resp.json()["result"]["name"] == "New"


@pytest.mark.asyncio
async def test_delete_org(async_client):
    create = await async_client.post("/api/v1/org", json={"name": "ToDelete"})
    org_id = create.json()["result"]["id"]
    resp = await async_client.delete(f"/api/v1/org/{org_id}")
    assert resp.status_code == 200
    resp = await async_client.get(f"/api/v1/org/{org_id}")
    assert resp.status_code == 404
