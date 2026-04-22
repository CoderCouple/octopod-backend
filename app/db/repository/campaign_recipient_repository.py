from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.campaign_recipient_model import CampaignRecipient


class CampaignRecipientRepository:
    """Data-access layer for the CampaignRecipient entity."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, recipient_id: str) -> CampaignRecipient | None:
        result = await self.db.execute(
            select(CampaignRecipient).where(
                CampaignRecipient.id == recipient_id,
                CampaignRecipient.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def list_by_campaign(
        self, campaign_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[CampaignRecipient], int]:
        base = select(CampaignRecipient).where(
            CampaignRecipient.campaign_id == campaign_id,
            CampaignRecipient.is_deleted == False,  # noqa: E712
        )
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base.order_by(CampaignRecipient.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_due_recipients(self, limit: int = 100) -> list[CampaignRecipient]:
        """Fetch recipients whose next_send_at is in the past and status is active."""
        result = await self.db.execute(
            select(CampaignRecipient)
            .where(
                CampaignRecipient.status == "active",
                CampaignRecipient.next_send_at <= func.now(),
                CampaignRecipient.is_deleted == False,  # noqa: E712
            )
            .order_by(CampaignRecipient.next_send_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_email_and_campaign(
        self, email: str, campaign_id: str
    ) -> CampaignRecipient | None:
        result = await self.db.execute(
            select(CampaignRecipient).where(
                CampaignRecipient.email == email,
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def count_by_campaign(self, campaign_id: str) -> int:
        result = await self.db.execute(
            select(func.count()).where(
                CampaignRecipient.campaign_id == campaign_id,
                CampaignRecipient.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar() or 0

    async def create(self, recipient: CampaignRecipient) -> CampaignRecipient:
        self.db.add(recipient)
        await self.db.flush()
        return recipient

    async def update(self, recipient: CampaignRecipient) -> CampaignRecipient:
        await self.db.flush()
        return recipient

    async def soft_delete(
        self, recipient: CampaignRecipient, actor_id: str | None = None
    ) -> CampaignRecipient:
        recipient.is_deleted = True
        recipient.updated_by = actor_id
        recipient.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return recipient
