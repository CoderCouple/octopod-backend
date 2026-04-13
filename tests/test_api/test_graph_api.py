import pytest


async def _setup_org_with_relationships(client):
    """Create org, employees, and confirmed claims to produce relationships."""
    org = await client.post("/api/v1/org", json={"name": "GraphOrg"})
    org_id = org.json()["result"]["id"]

    alice = await client.post("/api/v1/employee", json={"canonical_name": "Alice"})
    bob = await client.post("/api/v1/employee", json={"canonical_name": "Bob"})
    carol = await client.post("/api/v1/employee", json={"canonical_name": "Carol"})

    alice_id = alice.json()["result"]["id"]
    bob_id = bob.json()["result"]["id"]
    carol_id = carol.json()["result"]["id"]

    # Bob reports to Alice
    c1 = await client.post(
        "/api/v1/claim",
        json={"org_id": org_id, "employee_id": bob_id, "manager_id": alice_id},
    )
    await client.post(
        f"/api/v1/claim/{c1.json()['result']['id']}/confirm",
        json={"response": "confirm"},
    )

    # Carol reports to Alice
    c2 = await client.post(
        "/api/v1/claim",
        json={"org_id": org_id, "employee_id": carol_id, "manager_id": alice_id},
    )
    await client.post(
        f"/api/v1/claim/{c2.json()['result']['id']}/confirm",
        json={"response": "confirm"},
    )

    return org_id, alice_id, bob_id, carol_id


@pytest.mark.asyncio
async def test_get_org_graph(async_client):
    org_id, alice_id, bob_id, carol_id = await _setup_org_with_relationships(
        async_client
    )
    resp = await async_client.get(f"/api/v1/graph/org/{org_id}")
    assert resp.status_code == 200
    graph = resp.json()["result"]
    assert graph["node_count"] >= 3
    assert graph["edge_count"] >= 2


@pytest.mark.asyncio
async def test_detect_no_cycles(async_client):
    org_id, *_ = await _setup_org_with_relationships(async_client)
    resp = await async_client.get(f"/api/v1/graph/org/{org_id}/cycles")
    assert resp.status_code == 200
    data = resp.json()["result"]
    assert data["has_cycles"] is False


@pytest.mark.asyncio
async def test_graph_empty_org(async_client):
    org = await async_client.post("/api/v1/org", json={"name": "EmptyOrg"})
    org_id = org.json()["result"]["id"]
    resp = await async_client.get(f"/api/v1/graph/org/{org_id}")
    assert resp.status_code == 200
    graph = resp.json()["result"]
    assert graph["node_count"] == 0
    assert graph["edge_count"] == 0
