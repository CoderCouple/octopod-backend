import pytest


async def _setup_entities(client):
    org = await client.post("/api/v1/org", json={"name": "ClaimOrg"})
    emp = await client.post("/api/v1/employee", json={"canonical_name": "Employee1"})
    mgr = await client.post("/api/v1/employee", json={"canonical_name": "Manager1"})
    return (
        org.json()["result"]["id"],
        emp.json()["result"]["id"],
        mgr.json()["result"]["id"],
    )


@pytest.mark.asyncio
async def test_submit_claim(async_client):
    org_id, emp_id, mgr_id = await _setup_entities(async_client)
    resp = await async_client.post(
        "/api/v1/claim",
        json={"org_id": org_id, "employee_id": emp_id, "manager_id": mgr_id},
        headers={"x-actor-id": "actor1"},
    )
    assert resp.status_code == 201
    data = resp.json()["result"]
    assert data["state"] == "pending_counterparty"
    assert data["id"].startswith("claim_")
    assert data["claimant_id"] == "actor1"


@pytest.mark.asyncio
async def test_duplicate_claim_rejected(async_client):
    org_id, emp_id, mgr_id = await _setup_entities(async_client)
    await async_client.post(
        "/api/v1/claim",
        json={"org_id": org_id, "employee_id": emp_id, "manager_id": mgr_id},
    )
    resp = await async_client.post(
        "/api/v1/claim",
        json={"org_id": org_id, "employee_id": emp_id, "manager_id": mgr_id},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_claim_detail(async_client):
    org_id, emp_id, mgr_id = await _setup_entities(async_client)
    create = await async_client.post(
        "/api/v1/claim",
        json={"org_id": org_id, "employee_id": emp_id, "manager_id": mgr_id},
    )
    claim_id = create.json()["result"]["id"]
    resp = await async_client.get(f"/api/v1/claim/{claim_id}")
    assert resp.status_code == 200
    data = resp.json()["result"]
    assert "allowed_actions" in data
    assert "confirm" in data["allowed_actions"]


@pytest.mark.asyncio
async def test_list_claims(async_client):
    org_id, emp_id, mgr_id = await _setup_entities(async_client)
    await async_client.post(
        "/api/v1/claim",
        json={"org_id": org_id, "employee_id": emp_id, "manager_id": mgr_id},
    )
    resp = await async_client.get("/api/v1/claim")
    assert resp.status_code == 200
    assert resp.json()["result"]["total"] >= 1


@pytest.mark.asyncio
async def test_confirm_claim_creates_relationship(async_client):
    org_id, emp_id, mgr_id = await _setup_entities(async_client)
    create = await async_client.post(
        "/api/v1/claim",
        json={"org_id": org_id, "employee_id": emp_id, "manager_id": mgr_id},
        headers={"x-actor-id": "claimant1"},
    )
    claim_id = create.json()["result"]["id"]

    resp = await async_client.post(
        f"/api/v1/claim/{claim_id}/confirm",
        json={"response": "confirm", "comment": "Looks correct"},
        headers={"x-actor-id": "manager_actor"},
    )
    assert resp.status_code == 200
    data = resp.json()["result"]
    assert data["state"] == "verified"

    # Check relationship was created
    rr_resp = await async_client.get(
        f"/api/v1/relationship?org_id={org_id}&employee_id={emp_id}"
    )
    assert rr_resp.status_code == 200
    rrs = rr_resp.json()["result"]["items"]
    assert len(rrs) >= 1
    assert rrs[0]["manager_employee_id"] == mgr_id


@pytest.mark.asyncio
async def test_reject_claim(async_client):
    org_id, emp_id, mgr_id = await _setup_entities(async_client)
    create = await async_client.post(
        "/api/v1/claim",
        json={"org_id": org_id, "employee_id": emp_id, "manager_id": mgr_id},
    )
    claim_id = create.json()["result"]["id"]

    resp = await async_client.post(
        f"/api/v1/claim/{claim_id}/confirm",
        json={"response": "reject", "comment": "Not accurate"},
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["state"] == "rejected"


@pytest.mark.asyncio
async def test_claim_with_invalid_entities(async_client):
    resp = await async_client.post(
        "/api/v1/claim",
        json={
            "org_id": "fake_org",
            "employee_id": "fake_emp",
            "manager_id": "fake_mgr",
        },
    )
    assert resp.status_code == 404
