import logging
import math
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.request.developer_profile_request import RankingWeights, RankProfilesRequest
from app.api.v1.response.developer_profile_response import (
    CohesiveProfileResponse,
    ProfileRankingResponse,
    SearchResultResponse,
)
from app.common.exceptions import EntityNotFoundError
from app.db.repository.cohesive_profile_repository import CohesiveProfileRepository
from app.db.repository.developer_profile_repository import DeveloperProfileRepository
from app.db.repository.profile_ranking_repository import ProfileRankingRepository
from app.model.cohesive_profile_model import CohesiveProfile
from app.model.profile_ranking_model import ProfileRanking

logger = logging.getLogger(__name__)

DEFAULT_WEIGHTS = RankingWeights()


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _log_score(value: int | float, scale: float = 100.0) -> float:
    if value <= 0:
        return 0.0
    return _clamp(math.log10(1 + value) / math.log10(1 + scale))


class ProfileRankingService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.dp_repo = DeveloperProfileRepository(db)
        self.cp_repo = CohesiveProfileRepository(db)
        self.pr_repo = ProfileRankingRepository(db)

    async def get_ranking(self, developer_profile_id: str) -> ProfileRankingResponse:
        cp = await self.cp_repo.get_by_developer_profile_id(developer_profile_id)
        if not cp:
            raise EntityNotFoundError("CohesiveProfile", developer_profile_id)

        ranking = await self.pr_repo.get_by_cohesive_profile_id(cp.id)
        if not ranking:
            ranking = await self._compute_and_store(cp)

        return ProfileRankingResponse.model_validate(ranking)

    async def rank_profiles(
        self, request: RankProfilesRequest
    ) -> tuple[list[SearchResultResponse], int]:
        weights = request.weights or DEFAULT_WEIGHTS

        if request.profile_ids:
            cohesive_profiles = await self.cp_repo.list_by_developer_profile_ids(
                request.profile_ids
            )
        else:
            cohesive_profiles, _ = await self.cp_repo.list_all(offset=0, limit=1000)

        results: list[SearchResultResponse] = []
        for cp in cohesive_profiles:
            ranking = await self.pr_repo.get_by_cohesive_profile_id(cp.id)
            if not ranking:
                ranking = await self._compute_and_store(cp, weights)

            composite = self._compute_composite(ranking, weights)
            results.append(
                SearchResultResponse(
                    profile=CohesiveProfileResponse.model_validate(cp),
                    score=float(composite),
                    ranking=ProfileRankingResponse.model_validate(ranking),
                )
            )

        results.sort(key=lambda r: r.score, reverse=True)
        total = len(results)
        results = results[request.offset : request.offset + request.limit]
        return results, total

    async def _compute_and_store(
        self, cp: CohesiveProfile, weights: RankingWeights | None = None
    ) -> ProfileRanking:
        weights = weights or DEFAULT_WEIGHTS
        scores = self._compute_scores(cp)

        ranking = await self.pr_repo.get_by_cohesive_profile_id(cp.id)
        if not ranking:
            ranking = ProfileRanking(cohesive_profile_id=cp.id)

        ranking.github_activity_score = Decimal(str(round(scores["github_activity"], 4)))
        ranking.technical_influence_score = Decimal(str(round(scores["technical_influence"], 4)))
        ranking.hiring_fit_score = Decimal(str(round(scores["hiring_fit"], 4)))
        ranking.experience_score = Decimal(str(round(scores["experience"], 4)))
        ranking.skills_breadth_score = Decimal(str(round(scores["skills_breadth"], 4)))
        ranking.recency_score = Decimal(str(round(scores["recency"], 4)))
        ranking.oss_contribution_score = Decimal(str(round(scores["oss_contribution"], 4)))
        ranking.hf_impact_score = Decimal(str(round(scores["hf_impact"], 4)))

        composite = self._compute_composite(ranking, weights)
        ranking.composite_score = Decimal(str(round(composite, 4)))
        ranking.weight_config = weights.model_dump()
        ranking.computed_at = datetime.now(timezone.utc)

        if not ranking.id or ranking.id.startswith("pr_"):
            existing = await self.pr_repo.get_by_cohesive_profile_id(cp.id)
            if existing:
                for attr in [
                    "github_activity_score", "technical_influence_score",
                    "hiring_fit_score", "experience_score", "skills_breadth_score",
                    "recency_score", "oss_contribution_score", "hf_impact_score",
                    "composite_score", "weight_config", "computed_at",
                ]:
                    setattr(existing, attr, getattr(ranking, attr))
                ranking = await self.pr_repo.update(existing)
            else:
                ranking = await self.pr_repo.create(ranking)

        return ranking

    def _compute_scores(self, cp: CohesiveProfile) -> dict[str, float]:
        return {
            "github_activity": self._github_activity_score(cp),
            "technical_influence": self._technical_influence_score(cp),
            "hiring_fit": self._hiring_fit_score(cp),
            "experience": self._experience_score(cp),
            "skills_breadth": self._skills_breadth_score(cp),
            "recency": self._recency_score(cp),
            "oss_contribution": self._oss_contribution_score(cp),
            "hf_impact": self._hf_impact_score(cp),
        }

    @staticmethod
    def _github_activity_score(cp: CohesiveProfile) -> float:
        contributions = cp.total_contributions or 0
        repos = cp.total_repos or 0
        return _clamp(
            0.6 * _log_score(contributions, 500) + 0.4 * _log_score(repos, 200)
        )

    @staticmethod
    def _technical_influence_score(cp: CohesiveProfile) -> float:
        stars = cp.total_stars or 0
        followers = cp.total_followers or 0
        downloads = cp.total_hf_downloads or 0
        papers = cp.total_papers or 0
        return _clamp(
            0.35 * _log_score(stars, 1000)
            + 0.25 * _log_score(followers, 500)
            + 0.25 * _log_score(downloads, 100000)
            + 0.15 * _log_score(papers, 20)
        )

    @staticmethod
    def _hiring_fit_score(cp: CohesiveProfile) -> float:
        skills_count = len(cp.skills or [])
        has_title = 1.0 if cp.current_title else 0.0
        has_company = 1.0 if cp.current_company else 0.0
        return _clamp(
            0.4 * _log_score(skills_count, 30)
            + 0.3 * has_title
            + 0.3 * has_company
        )

    @staticmethod
    def _experience_score(cp: CohesiveProfile) -> float:
        years = cp.years_of_experience or 0
        return _clamp(min(years, 15) / 15.0)

    @staticmethod
    def _skills_breadth_score(cp: CohesiveProfile) -> float:
        skills = len(cp.skills or [])
        langs = len(cp.languages or [])
        return _clamp(
            0.5 * min(skills, 20) / 20.0 + 0.5 * min(langs, 10) / 10.0
        )

    @staticmethod
    def _recency_score(cp: CohesiveProfile) -> float:
        if not cp.merged_at:
            return 0.5
        merged = cp.merged_at
        now = datetime.now(timezone.utc)
        # Handle naive datetimes (e.g. from SQLite in tests)
        if merged.tzinfo is None:
            merged = merged.replace(tzinfo=timezone.utc)
        days = (now - merged).days
        if days <= 7:
            return 1.0
        elif days <= 30:
            return 0.8
        elif days <= 90:
            return 0.6
        elif days <= 180:
            return 0.4
        elif days <= 365:
            return 0.2
        return 0.1

    @staticmethod
    def _oss_contribution_score(cp: CohesiveProfile) -> float:
        contributions = cp.total_contributions or 0
        repos = cp.total_repos or 0
        topics = len(cp.topics or [])
        return _clamp(
            0.4 * _log_score(contributions, 500)
            + 0.4 * _log_score(repos, 100)
            + 0.2 * _log_score(topics, 30)
        )

    @staticmethod
    def _hf_impact_score(cp: CohesiveProfile) -> float:
        models = cp.total_hf_models or 0
        datasets = cp.total_hf_datasets or 0
        downloads = cp.total_hf_downloads or 0
        spaces = cp.total_hf_spaces or 0
        return _clamp(
            0.3 * _log_score(models, 50)
            + 0.2 * _log_score(datasets, 30)
            + 0.3 * _log_score(downloads, 100000)
            + 0.2 * _log_score(spaces, 20)
        )

    @staticmethod
    def _compute_composite(ranking: ProfileRanking, weights: RankingWeights) -> float:
        return _clamp(
            weights.github_activity * float(ranking.github_activity_score or 0)
            + weights.technical_influence * float(ranking.technical_influence_score or 0)
            + weights.hiring_fit * float(ranking.hiring_fit_score or 0)
            + weights.experience * float(ranking.experience_score or 0)
            + weights.skills_breadth * float(ranking.skills_breadth_score or 0)
            + weights.recency * float(ranking.recency_score or 0)
            + weights.oss_contribution * float(ranking.oss_contribution_score or 0)
            + weights.hf_impact * float(ranking.hf_impact_score or 0)
        )
