from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.subscription_model import Subscription


class SubscriptionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_org_id(self, org_id: str) -> Subscription | None:
        result = await self.db.execute(
            select(Subscription).where(Subscription.org_id == org_id)
        )
        return result.scalar_one_or_none()

    async def get_by_stripe_customer_id(self, customer_id: str) -> Subscription | None:
        result = await self.db.execute(
            select(Subscription).where(Subscription.stripe_customer_id == customer_id)
        )
        return result.scalar_one_or_none()

    async def get_by_stripe_subscription_id(self, subscription_id: str) -> Subscription | None:
        result = await self.db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
        )
        return result.scalar_one_or_none()

    async def create(self, subscription: Subscription) -> Subscription:
        self.db.add(subscription)
        await self.db.flush()
        return subscription

    async def update(self, subscription: Subscription) -> Subscription:
        await self.db.flush()
        return subscription
