import pytest


@pytest.mark.asyncio
async def test_create_developer_profile(async_client):
    resp = await async_client.post(
        "/api/v1/developer-profile",
        json={"github_username": "octocat", "auto_ingest": False},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert body["result"]["id"].startswith("dp_")
    assert body["result"]["github_username"] == "octocat"
    assert body["result"]["ingestion_status"] == "pending"


@pytest.mark.asyncio
async def test_create_profile_requires_identifier(async_client):
    resp = await async_client.post(
        "/api/v1/developer-profile",
        json={"auto_ingest": False},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_duplicate_github_username(async_client):
    await async_client.post(
        "/api/v1/developer-profile",
        json={"github_username": "dup_user", "auto_ingest": False},
    )
    resp = await async_client.post(
        "/api/v1/developer-profile",
        json={"github_username": "dup_user", "auto_ingest": False},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_developer_profiles(async_client):
    await async_client.post(
        "/api/v1/developer-profile",
        json={"github_username": "user1", "auto_ingest": False},
    )
    await async_client.post(
        "/api/v1/developer-profile",
        json={"github_username": "user2", "auto_ingest": False},
    )
    resp = await async_client.get("/api/v1/developer-profile")
    assert resp.status_code == 200
    assert resp.json()["result"]["total"] == 2


@pytest.mark.asyncio
async def test_get_developer_profile(async_client):
    create = await async_client.post(
        "/api/v1/developer-profile",
        json={"github_username": "getme", "auto_ingest": False},
    )
    pid = create.json()["result"]["id"]
    resp = await async_client.get(f"/api/v1/developer-profile/{pid}")
    assert resp.status_code == 200
    assert resp.json()["result"]["github_username"] == "getme"


@pytest.mark.asyncio
async def test_get_nonexistent_profile(async_client):
    resp = await async_client.get("/api/v1/developer-profile/dp_nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_developer_profile(async_client):
    create = await async_client.post(
        "/api/v1/developer-profile",
        json={"github_username": "olduser", "auto_ingest": False},
    )
    pid = create.json()["result"]["id"]
    resp = await async_client.patch(
        f"/api/v1/developer-profile/{pid}",
        json={"huggingface_username": "newuser"},
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["huggingface_username"] == "newuser"
    assert resp.json()["result"]["github_username"] == "olduser"


@pytest.mark.asyncio
async def test_create_with_linkedin(async_client):
    resp = await async_client.post(
        "/api/v1/developer-profile",
        json={"linkedin_url": "https://linkedin.com/in/test", "auto_ingest": False},
    )
    assert resp.status_code == 201
    assert resp.json()["result"]["linkedin_url"] == "https://linkedin.com/in/test"


@pytest.mark.asyncio
async def test_create_with_huggingface(async_client):
    resp = await async_client.post(
        "/api/v1/developer-profile",
        json={"huggingface_username": "hfuser", "auto_ingest": False},
    )
    assert resp.status_code == 201
    assert resp.json()["result"]["huggingface_username"] == "hfuser"
