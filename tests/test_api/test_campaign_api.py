import pytest


async def _create_mailbox(client):
    """Helper to create an SMTP mailbox for campaign tests."""
    resp = await client.post(
        "/api/v1/mailbox/smtp/connect",
        json={
            "email_address": "campaign@example.com",
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "campaign@example.com",
            "smtp_password": "pass",
        },
    )
    return resp.json()["result"]["id"]


@pytest.mark.asyncio
async def test_create_campaign(authenticated_client):
    mbx_id = await _create_mailbox(authenticated_client)
    resp = await authenticated_client.post(
        "/api/v1/email-campaign",
        json={"name": "Test Campaign", "mailbox_id": mbx_id},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["result"]["id"].startswith("ec_")
    assert body["result"]["status"] == "draft"


@pytest.mark.asyncio
async def test_list_campaigns(authenticated_client):
    mbx_id = await _create_mailbox(authenticated_client)
    await authenticated_client.post(
        "/api/v1/email-campaign", json={"name": "C1", "mailbox_id": mbx_id}
    )
    await authenticated_client.post(
        "/api/v1/email-campaign", json={"name": "C2", "mailbox_id": mbx_id}
    )
    resp = await authenticated_client.get("/api/v1/email-campaign")
    assert resp.status_code == 200
    assert resp.json()["result"]["total"] == 2


@pytest.mark.asyncio
async def test_campaign_crud(authenticated_client):
    mbx_id = await _create_mailbox(authenticated_client)
    # Create
    create = await authenticated_client.post(
        "/api/v1/email-campaign", json={"name": "CRUD Test", "mailbox_id": mbx_id}
    )
    cid = create.json()["result"]["id"]

    # Get
    resp = await authenticated_client.get(f"/api/v1/email-campaign/{cid}")
    assert resp.status_code == 200

    # Update
    resp = await authenticated_client.patch(
        f"/api/v1/email-campaign/{cid}", json={"name": "Updated"}
    )
    assert resp.json()["result"]["name"] == "Updated"

    # Delete
    resp = await authenticated_client.delete(f"/api/v1/email-campaign/{cid}")
    assert resp.status_code == 200
    resp = await authenticated_client.get(f"/api/v1/email-campaign/{cid}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_step(authenticated_client):
    mbx_id = await _create_mailbox(authenticated_client)
    create = await authenticated_client.post(
        "/api/v1/email-campaign", json={"name": "Step Test", "mailbox_id": mbx_id}
    )
    cid = create.json()["result"]["id"]

    resp = await authenticated_client.post(
        f"/api/v1/email-campaign/{cid}/steps",
        json={"step_type": "email", "delay_days": 0, "subject_override": "Hello"},
    )
    assert resp.status_code == 201
    assert resp.json()["result"]["id"].startswith("cst_")
    assert resp.json()["result"]["step_order"] == 1


@pytest.mark.asyncio
async def test_list_steps(authenticated_client):
    mbx_id = await _create_mailbox(authenticated_client)
    create = await authenticated_client.post(
        "/api/v1/email-campaign", json={"name": "Steps", "mailbox_id": mbx_id}
    )
    cid = create.json()["result"]["id"]

    await authenticated_client.post(
        f"/api/v1/email-campaign/{cid}/steps",
        json={"step_type": "email", "delay_days": 0},
    )
    await authenticated_client.post(
        f"/api/v1/email-campaign/{cid}/steps",
        json={"step_type": "email", "delay_days": 3},
    )

    resp = await authenticated_client.get(f"/api/v1/email-campaign/{cid}/steps")
    assert resp.status_code == 200
    steps = resp.json()["result"]
    assert len(steps) == 2
    assert steps[0]["step_order"] == 1
    assert steps[1]["step_order"] == 2


@pytest.mark.asyncio
async def test_add_recipient(authenticated_client):
    mbx_id = await _create_mailbox(authenticated_client)
    create = await authenticated_client.post(
        "/api/v1/email-campaign", json={"name": "Recip Test", "mailbox_id": mbx_id}
    )
    cid = create.json()["result"]["id"]

    resp = await authenticated_client.post(
        f"/api/v1/email-campaign/{cid}/recipients",
        json={"email": "dev@example.com", "first_name": "Alice"},
    )
    assert resp.status_code == 201
    assert resp.json()["result"]["id"].startswith("cr_")
    assert resp.json()["result"]["email"] == "dev@example.com"


@pytest.mark.asyncio
async def test_list_recipients(authenticated_client):
    mbx_id = await _create_mailbox(authenticated_client)
    create = await authenticated_client.post(
        "/api/v1/email-campaign", json={"name": "Recips", "mailbox_id": mbx_id}
    )
    cid = create.json()["result"]["id"]

    await authenticated_client.post(
        f"/api/v1/email-campaign/{cid}/recipients",
        json={"email": "a@example.com"},
    )
    await authenticated_client.post(
        f"/api/v1/email-campaign/{cid}/recipients",
        json={"email": "b@example.com"},
    )

    resp = await authenticated_client.get(f"/api/v1/email-campaign/{cid}/recipients")
    assert resp.status_code == 200
    assert resp.json()["result"]["total"] == 2


@pytest.mark.asyncio
async def test_campaign_analytics(authenticated_client):
    mbx_id = await _create_mailbox(authenticated_client)
    create = await authenticated_client.post(
        "/api/v1/email-campaign", json={"name": "Analytics", "mailbox_id": mbx_id}
    )
    cid = create.json()["result"]["id"]

    resp = await authenticated_client.get(f"/api/v1/email-campaign/{cid}/analytics")
    assert resp.status_code == 200
    analytics = resp.json()["result"]
    assert analytics["campaign_id"] == cid
    assert analytics["total_recipients"] == 0


@pytest.mark.asyncio
async def test_campaign_state_machine(authenticated_client):
    mbx_id = await _create_mailbox(authenticated_client)
    create = await authenticated_client.post(
        "/api/v1/email-campaign", json={"name": "SM Test", "mailbox_id": mbx_id}
    )
    cid = create.json()["result"]["id"]

    # Cannot pause from draft
    resp = await authenticated_client.post(f"/api/v1/email-campaign/{cid}/pause")
    assert resp.status_code == 409

    # Start from draft
    resp = await authenticated_client.post(f"/api/v1/email-campaign/{cid}/start")
    assert resp.status_code == 200
    assert resp.json()["result"]["status"] == "active"

    # Pause from active
    resp = await authenticated_client.post(f"/api/v1/email-campaign/{cid}/pause")
    assert resp.status_code == 200
    assert resp.json()["result"]["status"] == "paused"

    # Resume from paused
    resp = await authenticated_client.post(f"/api/v1/email-campaign/{cid}/resume")
    assert resp.status_code == 200
    assert resp.json()["result"]["status"] == "active"

    # Cancel from active
    resp = await authenticated_client.post(f"/api/v1/email-campaign/{cid}/cancel")
    assert resp.status_code == 200
    assert resp.json()["result"]["status"] == "cancelled"

    # Cannot start from cancelled
    resp = await authenticated_client.post(f"/api/v1/email-campaign/{cid}/start")
    assert resp.status_code == 409
