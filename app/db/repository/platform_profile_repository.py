from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.platform_profile_model import PlatformProfile


class PlatformProfileRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, profile_id: str) -> PlatformProfile | None:
        result = await self.db.execute(
            select(PlatformProfile).where(PlatformProfile.id == profile_id)
        )
        return result.scalar_one_or_none()

    async def get_by_dev_and_platform(
        self, developer_profile_id: str, platform: str
    ) -> PlatformProfile | None:
        result = await self.db.execute(
            select(PlatformProfile).where(
                PlatformProfile.developer_profile_id == developer_profile_id,
                PlatformProfile.platform == platform,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_developer(self, developer_profile_id: str) -> list[PlatformProfile]:
        result = await self.db.execute(
            select(PlatformProfile).where(
                PlatformProfile.developer_profile_id == developer_profile_id,
            )
        )
        return list(result.scalars().all())

    async def create(self, entity: PlatformProfile) -> PlatformProfile:
        self.db.add(entity)
        await self.db.flush()
        return entity

    async def update(self, entity: PlatformProfile) -> PlatformProfile:
        await self.db.flush()
        return entity
