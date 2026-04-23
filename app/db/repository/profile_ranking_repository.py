from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.profile_ranking_model import ProfileRanking


class ProfileRankingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, ranking_id: str) -> ProfileRanking | None:
        result = await self.db.execute(
            select(ProfileRanking).where(ProfileRanking.id == ranking_id)
        )
        return result.scalar_one_or_none()

    async def get_by_cohesive_individual_profile_id(
        self, cohesive_individual_profile_id: str
    ) -> ProfileRanking | None:
        result = await self.db.execute(
            select(ProfileRanking).where(
                ProfileRanking.cohesive_individual_profile_id == cohesive_individual_profile_id,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_cohesive_individual_profile_ids(
        self, cohesive_individual_profile_ids: list[str]
    ) -> list[ProfileRanking]:
        if not cohesive_individual_profile_ids:
            return []
        result = await self.db.execute(
            select(ProfileRanking).where(
                ProfileRanking.cohesive_individual_profile_id.in_(cohesive_individual_profile_ids)
            )
        )
        return list(result.scalars().all())

    async def create(self, entity: ProfileRanking) -> ProfileRanking:
        self.db.add(entity)
        await self.db.flush()
        return entity

    async def update(self, entity: ProfileRanking) -> ProfileRanking:
        await self.db.flush()
        return entity
