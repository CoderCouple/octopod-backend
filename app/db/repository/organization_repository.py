from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.org_membership_model import OrgMembership
from app.model.organization_model import Organization


class OrganizationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, org_id: str) -> Organization | None:
        result = await self.db.execute(
            select(Organization).where(
                Organization.id == org_id,
                Organization.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Organization | None:
        result = await self.db.execute(
            select(Organization).where(
                Organization.slug == slug,
                Organization.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def list_by_user(
        self, user_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[Organization], int]:
        base = (
            select(Organization)
            .join(OrgMembership, OrgMembership.org_id == Organization.id)
            .where(
                OrgMembership.user_id == user_id,
                OrgMembership.status == "active",
                Organization.is_deleted == False,  # noqa: E712
            )
        )
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base.order_by(Organization.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def create(self, org: Organization) -> Organization:
        self.db.add(org)
        await self.db.flush()
        return org

    async def update(self, org: Organization) -> Organization:
        await self.db.flush()
        return org

    async def soft_delete(self, org: Organization, actor_id: str | None = None) -> Organization:
        org.is_deleted = True
        org.updated_by = actor_id
        org.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return org
