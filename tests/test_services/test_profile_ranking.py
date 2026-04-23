from datetime import datetime, timezone

import pytest
import pytest_asyncio

from app.api.v1.request.developer_profile_request import RankingWeights
from app.model.cohesive_individual_profile_model import CohesiveIndividualProfile
from app.model.developer_profile_model import DeveloperProfile
from app.service.profile_ranking_service import (
    ProfileRankingService,
    _clamp,
    _log_score,
)


class TestScoreHelpers:
    def test_clamp_within_range(self):
        assert _clamp(0.5) == 0.5

    def test_clamp_below_zero(self):
        assert _clamp(-0.5) == 0.0

    def test_clamp_above_one(self):
        assert _clamp(1.5) == 1.0

    def test_log_score_zero(self):
        assert _log_score(0) == 0.0

    def test_log_score_positive(self):
        score = _log_score(50, 100)
        assert 0.0 < score < 1.0

    def test_log_score_at_scale(self):
        score = _log_score(100, 100)
        assert score == pytest.approx(1.0, abs=0.01)


@pytest_asyncio.fixture
async def ranking_setup(async_session):
    dp = DeveloperProfile(
        github_username="ranker",
        ingestion_status="completed",
    )
    async_session.add(dp)
    await async_session.flush()

    cp = CohesiveIndividualProfile(
        developer_profile_id=dp.id,
        display_name="Ranker User",
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
        years_of_experience=7,
        current_title="Senior Engineer",
        current_company="BigCo",
        job_history=[{"company": "BigCo", "title": "Senior Engineer"}],
        merged_at=datetime.now(timezone.utc),
    )
    async_session.add(cp)
    await async_session.flush()

    return dp, cp


@pytest.mark.asyncio
async def test_compute_ranking(async_session, ranking_setup):
    dp, cp = ranking_setup
    service = ProfileRankingService(async_session)
    result = await service.get_ranking(dp.id)

    assert result.cohesive_individual_profile_id == cp.id
    assert 0.0 <= float(result.github_activity_score) <= 1.0
    assert 0.0 <= float(result.technical_influence_score) <= 1.0
    assert 0.0 <= float(result.experience_score) <= 1.0
    assert 0.0 <= float(result.composite_score) <= 1.0
    assert float(result.composite_score) > 0


@pytest.mark.asyncio
async def test_ranking_scores_nonzero(async_session, ranking_setup):
    dp, cp = ranking_setup
    service = ProfileRankingService(async_session)
    result = await service.get_ranking(dp.id)

    # With real data, most scores should be > 0
    assert float(result.github_activity_score) > 0
    assert float(result.experience_score) > 0
    assert float(result.skills_breadth_score) > 0
    assert float(result.hf_impact_score) > 0


@pytest.mark.asyncio
async def test_ranking_zero_profile(async_session):
    dp = DeveloperProfile(
        github_username="zeroprofile",
        ingestion_status="completed",
    )
    async_session.add(dp)
    await async_session.flush()

    cp = CohesiveIndividualProfile(
        developer_profile_id=dp.id,
        display_name="Zero User",
        merged_at=datetime.now(timezone.utc),
    )
    async_session.add(cp)
    await async_session.flush()

    service = ProfileRankingService(async_session)
    result = await service.get_ranking(dp.id)

    assert float(result.github_activity_score) == 0.0
    assert float(result.hf_impact_score) == 0.0


class TestRankingWeightsValidation:
    def test_default_weights_valid(self):
        w = RankingWeights()
        total = (
            w.github_activity + w.technical_influence + w.hiring_fit
            + w.experience + w.skills_breadth + w.recency
            + w.oss_contribution + w.hf_impact
        )
        assert abs(total - 1.0) < 0.05

    def test_invalid_weights_rejected(self):
        with pytest.raises(ValueError):
            RankingWeights(github_activity=0.9, technical_influence=0.9)
