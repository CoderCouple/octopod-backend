import pytest


async def _create_org_and_employee(client):
    org = await client.post("/api/v1/org", json={"name": "TestOrg"})
    emp = await client.post("/api/v1/employee", json={"canonical_name": "TestEmp"})
    return org.json()["result"]["id"], emp.json()["result"]["id"]


@pytest.mark.asyncio
async def test_create_employment(async_client):
    org_id, emp_id = await _create_org_and_employee(async_client)
    resp = await async_client.post(
        "/api/v1/employment",
        json={
            "employee_id": emp_id,
            "org_id": org_id,
            "title": "Engineer",
            "department": "Eng",
        },
    )
    assert resp.status_code == 201
    data = resp.json()["result"]
    assert data["title"] == "Engineer"
    assert data["is_current"] is True
    assert data["id"].startswith("empl_")


@pytest.mark.asyncio
async def test_end_employment(async_client):
    org_id, emp_id = await _create_org_and_employee(async_client)
    create = await async_client.post(
        "/api/v1/employment",
        json={"employee_id": emp_id, "org_id": org_id, "title": "Eng"},
    )
    eid = create.json()["result"]["id"]
    resp = await async_client.post(f"/api/v1/employment/{eid}/end")
    assert resp.status_code == 200
    assert resp.json()["result"]["is_current"] is False


@pytest.mark.asyncio
async def test_get_employee_employments(async_client):
    org_id, emp_id = await _create_org_and_employee(async_client)
    await async_client.post(
        "/api/v1/employment",
        json={"employee_id": emp_id, "org_id": org_id, "title": "Eng"},
    )
    resp = await async_client.get(f"/api/v1/employee/{emp_id}/employments")
    assert resp.status_code == 200
    assert resp.json()["result"]["total"] == 1
