from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.org_membership_model import OrgMembership


class OrgMembershipRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, membership_id: str) -> OrgMembership | None:
        result = await self.db.execute(
            select(OrgMembership).where(OrgMembership.id == membership_id)
        )
        return result.scalar_one_or_none()

    async def get(self, org_id: str, user_id: str) -> OrgMembership | None:
        result = await self.db.execute(
            select(OrgMembership).where(
                OrgMembership.org_id == org_id,
                OrgMembership.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_org_and_email(self, org_id: str, email: str) -> OrgMembership | None:
        result = await self.db.execute(
            select(OrgMembership).where(
                OrgMembership.org_id == org_id,
                OrgMembership.invited_email == email,
                OrgMembership.status == "invited",
            )
        )
        return result.scalar_one_or_none()

    async def list_by_org(
        self, org_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[OrgMembership], int]:
        base = select(OrgMembership).where(OrgMembership.org_id == org_id)
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base.order_by(OrgMembership.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_by_user(self, user_id: str) -> list[OrgMembership]:
        result = await self.db.execute(
            select(OrgMembership).where(
                OrgMembership.user_id == user_id,
                OrgMembership.status == "active",
            )
        )
        return list(result.scalars().all())

    async def create(self, membership: OrgMembership) -> OrgMembership:
        self.db.add(membership)
        await self.db.flush()
        return membership

    async def update(self, membership: OrgMembership) -> OrgMembership:
        await self.db.flush()
        return membership

    async def delete(self, membership: OrgMembership) -> None:
        await self.db.delete(membership)
        await self.db.flush()
