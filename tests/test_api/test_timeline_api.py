import pytest


@pytest.mark.asyncio
async def test_employee_timeline(async_client):
    org = await async_client.post("/api/v1/org", json={"name": "TimelineOrg"})
    org_id = org.json()["result"]["id"]
    emp = await async_client.post(
        "/api/v1/employee", json={"canonical_name": "TimelineEmp"}
    )
    emp_id = emp.json()["result"]["id"]

    # Create employment (generates a JOIN career event)
    await async_client.post(
        "/api/v1/employment",
        json={"employee_id": emp_id, "org_id": org_id, "title": "Engineer"},
    )

    resp = await async_client.get(f"/api/v1/timeline/employee/{emp_id}")
    assert resp.status_code == 200
    data = resp.json()["result"]
    assert data["total"] >= 1
    assert data["items"][0]["event_type"] == "join"


@pytest.mark.asyncio
async def test_employee_timeline_with_leave(async_client):
    org = await async_client.post("/api/v1/org", json={"name": "LeaveOrg"})
    org_id = org.json()["result"]["id"]
    emp = await async_client.post(
        "/api/v1/employee", json={"canonical_name": "LeaveEmp"}
    )
    emp_id = emp.json()["result"]["id"]

    create = await async_client.post(
        "/api/v1/employment",
        json={"employee_id": emp_id, "org_id": org_id, "title": "Dev"},
    )
    empl_id = create.json()["result"]["id"]
    await async_client.post(f"/api/v1/employment/{empl_id}/end")

    resp = await async_client.get(f"/api/v1/timeline/employee/{emp_id}")
    assert resp.status_code == 200
    data = resp.json()["result"]
    assert data["total"] == 2  # join + leave


@pytest.mark.asyncio
async def test_employee_reporting_history(async_client):
    org = await async_client.post("/api/v1/org", json={"name": "HistOrg"})
    org_id = org.json()["result"]["id"]
    emp = await async_client.post(
        "/api/v1/employee", json={"canonical_name": "HistEmp"}
    )
    mgr = await async_client.post(
        "/api/v1/employee", json={"canonical_name": "HistMgr"}
    )
    emp_id = emp.json()["result"]["id"]
    mgr_id = mgr.json()["result"]["id"]

    # Submit and confirm claim to create a reporting relationship
    c = await async_client.post(
        "/api/v1/claim",
        json={"org_id": org_id, "employee_id": emp_id, "manager_id": mgr_id},
    )
    await async_client.post(
        f"/api/v1/claim/{c.json()['result']['id']}/confirm",
        json={"response": "confirm"},
    )

    resp = await async_client.get(
        f"/api/v1/timeline/employee/{emp_id}/reporting-history"
    )
    assert resp.status_code == 200
    data = resp.json()["result"]
    assert data["total"] >= 1
    assert data["items"][0]["manager_employee_id"] == mgr_id
