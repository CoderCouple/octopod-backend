from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.developer_profile_model import DeveloperProfile


class DeveloperProfileRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, profile_id: str) -> DeveloperProfile | None:
        result = await self.db.execute(
            select(DeveloperProfile).where(
                DeveloperProfile.id == profile_id,
                DeveloperProfile.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_github_username(
        self, username: str, exclude_id: str | None = None
    ) -> DeveloperProfile | None:
        query = select(DeveloperProfile).where(
            DeveloperProfile.github_username == username,
            DeveloperProfile.is_deleted == False,  # noqa: E712
        )
        if exclude_id:
            query = query.where(DeveloperProfile.id != exclude_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_huggingface_username(
        self, username: str, exclude_id: str | None = None
    ) -> DeveloperProfile | None:
        query = select(DeveloperProfile).where(
            DeveloperProfile.huggingface_username == username,
            DeveloperProfile.is_deleted == False,  # noqa: E712
        )
        if exclude_id:
            query = query.where(DeveloperProfile.id != exclude_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_all(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[DeveloperProfile], int]:
        base = select(DeveloperProfile).where(
            DeveloperProfile.is_deleted == False  # noqa: E712
        )
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base.order_by(DeveloperProfile.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def create(self, entity: DeveloperProfile) -> DeveloperProfile:
        self.db.add(entity)
        await self.db.flush()
        return entity

    async def update(self, entity: DeveloperProfile) -> DeveloperProfile:
        await self.db.flush()
        return entity
