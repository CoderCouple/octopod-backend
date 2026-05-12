from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.email_campaign_model import EmailCampaign


class EmailCampaignRepository:
    """Data-access layer for the EmailCampaign entity."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, campaign_id: str) -> EmailCampaign | None:
        result = await self.db.execute(
            select(EmailCampaign).where(
                EmailCampaign.id == campaign_id,
                EmailCampaign.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def list_by_owner(
        self, owner_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[EmailCampaign], int]:
        base = select(EmailCampaign).where(
            EmailCampaign.owner_id == owner_id,
            EmailCampaign.is_deleted == False,  # noqa: E712
        )
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base.order_by(EmailCampaign.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_by_project(
        self, project_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[EmailCampaign], int]:
        base = select(EmailCampaign).where(
            EmailCampaign.project_id == project_id,
            EmailCampaign.is_deleted == False,  # noqa: E712
        )
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base.order_by(EmailCampaign.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_by_status(
        self, status: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[EmailCampaign], int]:
        base = select(EmailCampaign).where(
            EmailCampaign.status == status,
            EmailCampaign.is_deleted == False,  # noqa: E712
        )
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base.order_by(EmailCampaign.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def increment_stat(self, campaign_id: str, field: str, amount: int = 1) -> None:
        """Atomically increment a denormalized stat counter."""
        col = getattr(EmailCampaign, field, None)
        if col is None:
            return
        await self.db.execute(
            EmailCampaign.__table__.update()
            .where(EmailCampaign.id == campaign_id)
            .values({field: col + amount})
        )
        await self.db.flush()

    async def create(self, campaign: EmailCampaign) -> EmailCampaign:
        self.db.add(campaign)
        await self.db.flush()
        return campaign

    async def update(self, campaign: EmailCampaign) -> EmailCampaign:
        await self.db.flush()
        return campaign

    async def soft_delete(
        self, campaign: EmailCampaign, actor_id: str | None = None
    ) -> EmailCampaign:
        campaign.is_deleted = True
        campaign.updated_by = actor_id
        campaign.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return campaign
