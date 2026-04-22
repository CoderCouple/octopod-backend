from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.campaign_step_model import CampaignStep


class CampaignStepRepository:
    """Data-access layer for the CampaignStep entity."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, step_id: str) -> CampaignStep | None:
        result = await self.db.execute(
            select(CampaignStep).where(
                CampaignStep.id == step_id,
                CampaignStep.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def list_by_campaign(self, campaign_id: str) -> list[CampaignStep]:
        result = await self.db.execute(
            select(CampaignStep)
            .where(
                CampaignStep.campaign_id == campaign_id,
                CampaignStep.is_deleted == False,  # noqa: E712
            )
            .order_by(CampaignStep.step_order.asc())
        )
        return list(result.scalars().all())

    async def get_first_step(self, campaign_id: str) -> CampaignStep | None:
        result = await self.db.execute(
            select(CampaignStep)
            .where(
                CampaignStep.campaign_id == campaign_id,
                CampaignStep.is_deleted == False,  # noqa: E712
            )
            .order_by(CampaignStep.step_order.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_next_step(self, campaign_id: str, current_order: int) -> CampaignStep | None:
        result = await self.db.execute(
            select(CampaignStep)
            .where(
                CampaignStep.campaign_id == campaign_id,
                CampaignStep.step_order > current_order,
                CampaignStep.is_deleted == False,  # noqa: E712
            )
            .order_by(CampaignStep.step_order.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_max_order(self, campaign_id: str) -> int:
        result = await self.db.execute(
            select(func.max(CampaignStep.step_order)).where(
                CampaignStep.campaign_id == campaign_id,
                CampaignStep.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar() or 0

    async def create(self, step: CampaignStep) -> CampaignStep:
        self.db.add(step)
        await self.db.flush()
        return step

    async def update(self, step: CampaignStep) -> CampaignStep:
        await self.db.flush()
        return step

    async def soft_delete(self, step: CampaignStep, actor_id: str | None = None) -> CampaignStep:
        step.is_deleted = True
        step.updated_by = actor_id
        step.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return step
