from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.aggregated_individual_profile_model import AggregatedIndividualProfile


class AggregatedIndividualProfileRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, profile_id: str) -> AggregatedIndividualProfile | None:
        result = await self.db.execute(
            select(AggregatedIndividualProfile).where(
                AggregatedIndividualProfile.id == profile_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_developer_profile_id(
        self, developer_profile_id: str
    ) -> AggregatedIndividualProfile | None:
        result = await self.db.execute(
            select(AggregatedIndividualProfile).where(
                AggregatedIndividualProfile.developer_profile_id == developer_profile_id
            )
        )
        return result.scalar_one_or_none()

    async def list_all(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[AggregatedIndividualProfile], int]:
        base = select(AggregatedIndividualProfile)
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0
        result = await self.db.execute(base.offset(offset).limit(limit))
        return list(result.scalars().all()), total

    async def create(self, entity: AggregatedIndividualProfile) -> AggregatedIndividualProfile:
        self.db.add(entity)
        await self.db.flush()
        return entity

    async def update(self, entity: AggregatedIndividualProfile) -> AggregatedIndividualProfile:
        await self.db.flush()
        return entity
