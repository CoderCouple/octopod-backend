import pytest


@pytest.mark.asyncio
async def test_create_developer_profile(authenticated_client):
    resp = await authenticated_client.post(
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
async def test_create_profile_requires_identifier(authenticated_client):
    resp = await authenticated_client.post(
        "/api/v1/developer-profile",
        json={"auto_ingest": False},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_duplicate_github_username(authenticated_client):
    await authenticated_client.post(
        "/api/v1/developer-profile",
        json={"github_username": "dup_user", "auto_ingest": False},
    )
    resp = await authenticated_client.post(
        "/api/v1/developer-profile",
        json={"github_username": "dup_user", "auto_ingest": False},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_developer_profiles(authenticated_client):
    await authenticated_client.post(
        "/api/v1/developer-profile",
        json={"github_username": "user1", "auto_ingest": False},
    )
    await authenticated_client.post(
        "/api/v1/developer-profile",
        json={"github_username": "user2", "auto_ingest": False},
    )
    resp = await authenticated_client.get("/api/v1/developer-profile")
    assert resp.status_code == 200
    assert resp.json()["result"]["total"] == 2


@pytest.mark.asyncio
async def test_get_developer_profile(authenticated_client):
    create = await authenticated_client.post(
        "/api/v1/developer-profile",
        json={"github_username": "getme", "auto_ingest": False},
    )
    pid = create.json()["result"]["id"]
    resp = await authenticated_client.get(f"/api/v1/developer-profile/{pid}")
    assert resp.status_code == 200
    assert resp.json()["result"]["github_username"] == "getme"


@pytest.mark.asyncio
async def test_get_nonexistent_profile(authenticated_client):
    resp = await authenticated_client.get("/api/v1/developer-profile/dp_nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_developer_profile(authenticated_client):
    create = await authenticated_client.post(
        "/api/v1/developer-profile",
        json={"github_username": "olduser", "auto_ingest": False},
    )
    pid = create.json()["result"]["id"]
    resp = await authenticated_client.patch(
        f"/api/v1/developer-profile/{pid}",
        json={"huggingface_username": "newuser"},
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["huggingface_username"] == "newuser"
    assert resp.json()["result"]["github_username"] == "olduser"


@pytest.mark.asyncio
async def test_create_with_github_and_huggingface(authenticated_client):
    resp = await authenticated_client.post(
        "/api/v1/developer-profile",
        json={
            "github_username": "combo_user",
            "huggingface_username": "combo_hf",
            "auto_ingest": False,
        },
    )
    assert resp.status_code == 201
    assert resp.json()["result"]["github_username"] == "combo_user"
    assert resp.json()["result"]["huggingface_username"] == "combo_hf"


@pytest.mark.asyncio
async def test_create_with_huggingface(authenticated_client):
    resp = await authenticated_client.post(
        "/api/v1/developer-profile",
        json={"huggingface_username": "hfuser", "auto_ingest": False},
    )
    assert resp.status_code == 201
    assert resp.json()["result"]["huggingface_username"] == "hfuser"
