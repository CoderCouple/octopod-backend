import pytest

from app.service.contributor_service import ContributorService


@pytest.mark.asyncio
async def test_get_or_create_score(async_session):
    svc = ContributorService(async_session)
    score = await svc.get_or_create_score("actor_test")
    assert score.actor_id == "actor_test"
    assert score.total_claims_submitted == 0
    assert score.visibility_level == 0


@pytest.mark.asyncio
async def test_increment_claims_submitted(async_session):
    svc = ContributorService(async_session)
    score = await svc.increment_claims_submitted("actor1")
    assert score.total_claims_submitted == 1
    assert score.visibility_level == 1  # raw_score = 1


@pytest.mark.asyncio
async def test_visibility_level_calculation(async_session):
    svc = ContributorService(async_session)
    # Submit 3 claims (raw = 3), verify 1 (raw += 3 = 6) -> level 2
    for _ in range(3):
        await svc.increment_claims_submitted("actor_vis")
    score = await svc.increment_claims_verified("actor_vis")
    assert score.visibility_level == 2  # raw = 6

    # Give 2 confirmations (raw += 4 = 10) -> level 3
    await svc.increment_confirmations("actor_vis")
    score = await svc.increment_confirmations("actor_vis")
    assert score.visibility_level == 3  # raw = 10


@pytest.mark.asyncio
async def test_get_visibility_level_unknown_actor(async_session):
    svc = ContributorService(async_session)
    level = await svc.get_visibility_level("unknown_actor")
    assert level == 0
