from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.billing_event_model import BillingEvent


class BillingEventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def exists_by_stripe_event_id(self, stripe_event_id: str) -> bool:
        result = await self.db.execute(
            select(BillingEvent.id).where(BillingEvent.stripe_event_id == stripe_event_id)
        )
        return result.scalar_one_or_none() is not None

    async def create(self, event: BillingEvent) -> BillingEvent:
        self.db.add(event)
        await self.db.flush()
        return event
