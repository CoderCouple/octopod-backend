import pytest


@pytest.mark.asyncio
async def test_connect_smtp_mailbox(async_client):
    resp = await async_client.post(
        "/api/v1/mailbox/smtp/connect",
        json={
            "email_address": "test@example.com",
            "display_name": "Test Mailbox",
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "test@example.com",
            "smtp_password": "password123",
            "smtp_use_tls": True,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["result"]["id"].startswith("mbx_")
    assert body["result"]["provider"] == "smtp"
    assert body["result"]["email_address"] == "test@example.com"


@pytest.mark.asyncio
async def test_list_mailboxes(async_client):
    await async_client.post(
        "/api/v1/mailbox/smtp/connect",
        json={
            "email_address": "a@example.com",
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "a@example.com",
            "smtp_password": "pass",
        },
    )
    await async_client.post(
        "/api/v1/mailbox/smtp/connect",
        json={
            "email_address": "b@example.com",
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "b@example.com",
            "smtp_password": "pass",
        },
    )
    resp = await async_client.get("/api/v1/mailbox")
    assert resp.status_code == 200
    assert resp.json()["result"]["total"] == 2


@pytest.mark.asyncio
async def test_get_mailbox(async_client):
    create = await async_client.post(
        "/api/v1/mailbox/smtp/connect",
        json={
            "email_address": "get@example.com",
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "get@example.com",
            "smtp_password": "pass",
        },
    )
    mid = create.json()["result"]["id"]
    resp = await async_client.get(f"/api/v1/mailbox/{mid}")
    assert resp.status_code == 200
    assert resp.json()["result"]["id"] == mid


@pytest.mark.asyncio
async def test_update_mailbox(async_client):
    create = await async_client.post(
        "/api/v1/mailbox/smtp/connect",
        json={
            "email_address": "upd@example.com",
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "upd@example.com",
            "smtp_password": "pass",
        },
    )
    mid = create.json()["result"]["id"]
    resp = await async_client.patch(
        f"/api/v1/mailbox/{mid}", json={"daily_send_limit": 100}
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["daily_send_limit"] == 100


@pytest.mark.asyncio
async def test_disconnect_mailbox(async_client):
    create = await async_client.post(
        "/api/v1/mailbox/smtp/connect",
        json={
            "email_address": "del@example.com",
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "del@example.com",
            "smtp_password": "pass",
        },
    )
    mid = create.json()["result"]["id"]
    resp = await async_client.delete(f"/api/v1/mailbox/{mid}")
    assert resp.status_code == 200
    resp = await async_client.get(f"/api/v1/mailbox/{mid}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_smtp_mailbox(async_client):
    await async_client.post(
        "/api/v1/mailbox/smtp/connect",
        json={
            "email_address": "dup@example.com",
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "dup@example.com",
            "smtp_password": "pass",
        },
    )
    resp = await async_client.post(
        "/api/v1/mailbox/smtp/connect",
        json={
            "email_address": "dup@example.com",
            "smtp_host": "smtp.example.com",
            "smtp_port": 587,
            "smtp_username": "dup@example.com",
            "smtp_password": "pass",
        },
    )
    assert resp.status_code == 409
