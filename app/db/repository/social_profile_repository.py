from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.social_profile_model import SocialProfile


class SocialProfileRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, profile_id: str) -> SocialProfile | None:
        result = await self.db.execute(
            select(SocialProfile).where(SocialProfile.id == profile_id)
        )
        return result.scalar_one_or_none()

    async def get_by_developer_profile_id(
        self, developer_profile_id: str
    ) -> SocialProfile | None:
        result = await self.db.execute(
            select(SocialProfile).where(
                SocialProfile.developer_profile_id == developer_profile_id
            )
        )
        return result.scalar_one_or_none()

    async def create(self, entity: SocialProfile) -> SocialProfile:
        self.db.add(entity)
        await self.db.flush()
        return entity

    async def update(self, entity: SocialProfile) -> SocialProfile:
        await self.db.flush()
        return entity
