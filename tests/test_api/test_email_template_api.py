import pytest


@pytest.mark.asyncio
async def test_create_template(async_client):
    resp = await async_client.post(
        "/api/v1/email-template",
        json={
            "name": "Welcome",
            "subject": "Hello {{ first_name }}",
            "body_html": "<p>Hi {{ first_name }}, welcome!</p>",
            "variables": ["first_name"],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["result"]["name"] == "Welcome"
    assert body["result"]["id"].startswith("etpl_")


@pytest.mark.asyncio
async def test_list_templates(async_client):
    await async_client.post(
        "/api/v1/email-template",
        json={"name": "T1", "subject": "S1", "body_html": "<p>1</p>"},
    )
    await async_client.post(
        "/api/v1/email-template",
        json={"name": "T2", "subject": "S2", "body_html": "<p>2</p>"},
    )
    resp = await async_client.get("/api/v1/email-template")
    assert resp.status_code == 200
    assert resp.json()["result"]["total"] == 2


@pytest.mark.asyncio
async def test_get_template(async_client):
    create = await async_client.post(
        "/api/v1/email-template",
        json={"name": "Test", "subject": "Sub", "body_html": "<p>Body</p>"},
    )
    tid = create.json()["result"]["id"]
    resp = await async_client.get(f"/api/v1/email-template/{tid}")
    assert resp.status_code == 200
    assert resp.json()["result"]["id"] == tid


@pytest.mark.asyncio
async def test_get_template_not_found(async_client):
    resp = await async_client.get("/api/v1/email-template/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_template(async_client):
    create = await async_client.post(
        "/api/v1/email-template",
        json={"name": "Old", "subject": "Old Sub", "body_html": "<p>Old</p>"},
    )
    tid = create.json()["result"]["id"]
    resp = await async_client.patch(
        f"/api/v1/email-template/{tid}", json={"name": "New"}
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["name"] == "New"


@pytest.mark.asyncio
async def test_delete_template(async_client):
    create = await async_client.post(
        "/api/v1/email-template",
        json={"name": "ToDelete", "subject": "S", "body_html": "<p>B</p>"},
    )
    tid = create.json()["result"]["id"]
    resp = await async_client.delete(f"/api/v1/email-template/{tid}")
    assert resp.status_code == 200
    resp = await async_client.get(f"/api/v1/email-template/{tid}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_preview_template(async_client):
    create = await async_client.post(
        "/api/v1/email-template",
        json={
            "name": "Preview",
            "subject": "Hello {{ first_name }}",
            "body_html": "<p>Hi {{ first_name }}!</p>",
        },
    )
    tid = create.json()["result"]["id"]
    resp = await async_client.post(
        f"/api/v1/email-template/{tid}/preview",
        json={"variables": {"first_name": "Alice"}},
    )
    assert resp.status_code == 200
    result = resp.json()["result"]
    assert result["subject"] == "Hello Alice"
    assert "Alice" in result["body_html"]
