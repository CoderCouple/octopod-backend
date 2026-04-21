import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.model.developer_profile_model import DeveloperProfile
from app.model.platform_profile_model import PlatformProfile
from app.service.profile_merge_service import ProfileMergeService


@pytest_asyncio.fixture
async def merge_setup(async_session):
    dp = DeveloperProfile(
        github_username="testuser",
        linkedin_url="https://linkedin.com/in/testuser",
        huggingface_username="testuser",
        ingestion_status="completed",
    )
    async_session.add(dp)
    await async_session.flush()

    # GitHub platform profile
    pp_gh = PlatformProfile(
        developer_profile_id=dp.id,
        platform="github",
        platform_username="testuser",
        fetch_status="success",
        extracted_data={
            "display_name": "GH User",
            "bio": "GitHub bio",
            "avatar_url": "https://gh.com/avatar.png",
            "company": "GH Corp",
            "location": "GH City",
            "website": "https://ghuser.dev",
            "total_repos": 50,
            "total_stars": 200,
            "total_contributions": 30,
            "total_followers": 100,
            "languages": ["Python", "Rust", "Go"],
            "topics": ["ml", "backend"],
        },
    )

    # LinkedIn platform profile
    pp_li = PlatformProfile(
        developer_profile_id=dp.id,
        platform="linkedin",
        platform_username="testuser",
        fetch_status="success",
        extracted_data={
            "display_name": "LinkedIn User",
            "headline": "Senior Engineer at BigCo",
            "bio": "LinkedIn summary",
            "location": "LI City",
            "avatar_url": "https://li.com/avatar.png",
            "company": "LI Corp",
            "skills": ["Python", "Machine Learning", "Docker"],
            "job_history": [
                {"company": "BigCo", "title": "Senior Engineer", "start": "2020-01"},
                {"company": "SmallCo", "title": "Junior Dev", "start": "2017-01", "end": "2020-01"},
            ],
            "current_title": "Senior Engineer",
            "current_company": "BigCo",
            "years_of_experience": 7,
        },
    )

    # HuggingFace platform profile
    pp_hf = PlatformProfile(
        developer_profile_id=dp.id,
        platform="huggingface",
        platform_username="testuser",
        fetch_status="success",
        extracted_data={
            "display_name": "HF User",
            "avatar_url": "https://hf.co/avatar.png",
            "total_hf_models": 5,
            "total_hf_datasets": 2,
            "total_hf_spaces": 3,
            "total_hf_downloads": 10000,
            "total_papers": 1,
        },
    )

    async_session.add_all([pp_gh, pp_li, pp_hf])
    await async_session.flush()

    return dp


@pytest.mark.asyncio
async def test_merge_creates_cohesive_profile(async_session, merge_setup):
    service = ProfileMergeService(async_session)
    result = await service.merge_profile(merge_setup.id)

    # LinkedIn wins for display_name
    assert result.display_name == "LinkedIn User"
    # LinkedIn wins for bio
    assert result.bio == "LinkedIn summary"
    # LinkedIn wins for headline
    assert result.headline == "Senior Engineer at BigCo"
    # GitHub wins for avatar_url
    assert result.avatar_url == "https://gh.com/avatar.png"
    # LinkedIn wins for company
    assert result.company == "LI Corp"
    # GitHub metrics
    assert result.total_repos == 50
    assert result.total_stars == 200
    # HuggingFace metrics
    assert result.total_hf_models == 5
    assert result.total_hf_downloads == 10000
    # Skills union
    assert "Python" in result.skills
    assert "Machine Learning" in result.skills
    assert "Docker" in result.skills
    # Languages from GitHub
    assert result.languages == ["Python", "Rust", "Go"]
    # Job history from LinkedIn
    assert len(result.job_history) == 2
    assert result.current_title == "Senior Engineer"


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
    )
    async_session.add(dp)
    await async_session.flush()

    pp = PlatformProfile(
        developer_profile_id=dp.id,
        platform="github",
        platform_username="partialuser",
        fetch_status="success",
        extracted_data={
            "display_name": "Partial User",
            "total_repos": 5,
            "total_stars": 10,
            "languages": ["Python"],
            "topics": [],
        },
    )
    async_session.add(pp)
    await async_session.flush()

    service = ProfileMergeService(async_session)
    result = await service.merge_profile(dp.id)
    assert result.display_name == "Partial User"
    assert result.total_repos == 5
    assert result.headline is None
    assert result.job_history == []


@pytest.mark.asyncio
async def test_get_cohesive_profile_not_found(async_session):
    service = ProfileMergeService(async_session)
    with pytest.raises(HTTPException):
        await service.get_cohesive_profile("dp_nonexistent")
