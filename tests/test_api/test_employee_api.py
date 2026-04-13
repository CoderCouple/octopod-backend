import pytest


@pytest.mark.asyncio
async def test_create_employee(async_client):
    resp = await async_client.post(
        "/api/v1/employee",
        json={"canonical_name": "John Doe", "primary_email": "john@test.com"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["result"]["canonical_name"] == "John Doe"
    assert body["result"]["id"].startswith("emp_")


@pytest.mark.asyncio
async def test_list_employees(async_client):
    await async_client.post("/api/v1/employee", json={"canonical_name": "A"})
    await async_client.post("/api/v1/employee", json={"canonical_name": "B"})
    resp = await async_client.get("/api/v1/employee")
    assert resp.status_code == 200
    assert resp.json()["result"]["total"] == 2


@pytest.mark.asyncio
async def test_update_employee(async_client):
    create = await async_client.post(
        "/api/v1/employee", json={"canonical_name": "Old"}
    )
    emp_id = create.json()["result"]["id"]
    resp = await async_client.patch(
        f"/api/v1/employee/{emp_id}", json={"canonical_name": "New"}
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["canonical_name"] == "New"
