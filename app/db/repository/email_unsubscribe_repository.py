from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.email_unsubscribe_model import EmailUnsubscribe


class EmailUnsubscribeRepository:
    """Data-access layer for the EmailUnsubscribe entity."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> EmailUnsubscribe | None:
        result = await self.db.execute(
            select(EmailUnsubscribe).where(EmailUnsubscribe.email == email)
        )
        return result.scalar_one_or_none()

    async def is_unsubscribed(self, email: str) -> bool:
        unsub = await self.get_by_email(email)
        return unsub is not None

    async def create(self, unsub: EmailUnsubscribe) -> EmailUnsubscribe:
        self.db.add(unsub)
        await self.db.flush()
        return unsub
