import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.model.developer_profile_model import DeveloperProfile
from app.service.profile_merge_service import ProfileMergeService


@pytest_asyncio.fixture
async def merge_setup(async_session):
    dp = DeveloperProfile(
        github_username="testuser",
        huggingface_username="testuser",
        ingestion_status="completed",
        display_name="GH User",
        bio="GitHub bio",
        avatar_url="https://gh.com/avatar.png",
        company="GH Corp",
        location="GH City",
        website="https://ghuser.dev",
        total_repos=50,
        total_stars=200,
        total_contributions=30,
        total_followers=100,
        total_hf_models=5,
        total_hf_datasets=2,
        total_hf_spaces=3,
        total_hf_downloads=10000,
        total_papers=1,
        languages=["Python", "Rust", "Go"],
        skills=["ML", "FastAPI", "Docker", "Kubernetes"],
        topics=["ml", "backend"],
    )
    async_session.add(dp)
    await async_session.flush()
    return dp


@pytest.mark.asyncio
async def test_merge_creates_cohesive_profile(async_session, merge_setup):
    service = ProfileMergeService(async_session)
    result = await service.merge_profile(merge_setup.id)

    assert result.display_name == "GH User"
    assert result.bio == "GitHub bio"
    assert result.avatar_url == "https://gh.com/avatar.png"
    assert result.total_repos == 50
    assert result.total_stars == 200
    assert result.total_hf_models == 5
    assert result.total_hf_downloads == 10000
    assert "Python" in result.languages
    assert "ML" in result.skills


@pytest.mark.asyncio
async def test_merge_remerge_updates(async_session, merge_setup):
    service = ProfileMergeService(async_session)
    first = await service.merge_profile(merge_setup.id)
    second = await service.merge_profile(merge_setup.id)
    assert first.id == second.id  # same cohesive profile updated


@pytest.mark.asyncio
async def test_merge_partial_data(async_session):
    dp = DeveloperProfile(
        github_username="partialuser",
        ingestion_status="completed",
        display_name="Partial User",
        total_repos=5,
        total_stars=10,
        languages=["Python"],
        topics=[],
    )
    async_session.add(dp)
    await async_session.flush()

    service = ProfileMergeService(async_session)
    result = await service.merge_profile(dp.id)
    assert result.display_name == "Partial User"
    assert result.total_repos == 5
    assert result.headline is None
    assert result.job_history is None or result.job_history == []


@pytest.mark.asyncio
async def test_get_cohesive_profile_not_found(async_session):
    service = ProfileMergeService(async_session)
    with pytest.raises(HTTPException):
        await service.get_cohesive_profile("dp_nonexistent")
