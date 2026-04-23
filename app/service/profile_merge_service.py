import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.response.developer_profile_response import CohesiveProfileResponse
from app.common.exceptions import EntityNotFoundError
from app.db.repository.cohesive_individual_profile_repository import (
    CohesiveIndividualProfileRepository,
)
from app.db.repository.developer_profile_repository import DeveloperProfileRepository
from app.ingest.bridge.merge import (
    build_embedding_text,
    merge_aggregated_fields,
    merge_cohesive_fields,
)
from app.model.cohesive_individual_profile_model import CohesiveIndividualProfile

logger = logging.getLogger(__name__)


class ProfileMergeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.dp_repo = DeveloperProfileRepository(db)
        self.cip_repo = CohesiveIndividualProfileRepository(db)

    async def get_cohesive_profile(
        self, developer_profile_id: str
    ) -> CohesiveProfileResponse:
        cp = await self.cip_repo.get_by_developer_profile_id(developer_profile_id)
        if not cp:
            raise EntityNotFoundError("CohesiveIndividualProfile", developer_profile_id)
        return CohesiveProfileResponse.model_validate(cp)

    async def merge_profile(self, developer_profile_id: str) -> CohesiveProfileResponse:
        profile = await self.dp_repo.get_by_id(developer_profile_id)
        if not profile:
            raise EntityNotFoundError("DeveloperProfile", developer_profile_id)

        # Build dev data from the developer_profile itself (already merged by bridge)
        dev_data = {
            "display_name": profile.display_name,
            "bio": profile.bio,
            "avatar_url": profile.avatar_url,
            "company": profile.company,
            "location": profile.location,
            "website": profile.website,
            "total_repos": profile.total_repos or 0,
            "total_stars": profile.total_stars or 0,
            "total_contributions": profile.total_contributions or 0,
            "total_followers": profile.total_followers or 0,
            "total_hf_models": profile.total_hf_models or 0,
            "total_hf_datasets": profile.total_hf_datasets or 0,
            "total_hf_spaces": profile.total_hf_spaces or 0,
            "total_hf_downloads": profile.total_hf_downloads or 0,
            "total_papers": profile.total_papers or 0,
            "languages": profile.languages or [],
            "skills": profile.skills or [],
            "topics": profile.topics or [],
        }

        # Aggregate (no social data in ORM path for now)
        agg_merged, _ = merge_aggregated_fields(dev_data, {})
        coh_merged, _ = merge_cohesive_fields(agg_merged)

        cp = await self.cip_repo.get_by_developer_profile_id(developer_profile_id)
        if not cp:
            cp = CohesiveIndividualProfile(developer_profile_id=developer_profile_id)
            for key, value in coh_merged.items():
                if hasattr(cp, key):
                    setattr(cp, key, value)
            cp.merged_at = datetime.now(timezone.utc)
            cp.embedding_text = build_embedding_text(coh_merged)
            cp = await self.cip_repo.create(cp)
        else:
            for key, value in coh_merged.items():
                if hasattr(cp, key):
                    setattr(cp, key, value)
            cp.merged_at = datetime.now(timezone.utc)
            cp.embedding_text = build_embedding_text(coh_merged)
            cp = await self.cip_repo.update(cp)

        return CohesiveProfileResponse.model_validate(cp)
