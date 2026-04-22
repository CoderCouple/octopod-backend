from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.email_event_model import EmailEvent


class EmailEventRepository:
    """Data-access layer for the EmailEvent entity."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, event_id: str) -> EmailEvent | None:
        result = await self.db.execute(
            select(EmailEvent).where(EmailEvent.id == event_id)
        )
        return result.scalar_one_or_none()

    async def list_by_message(
        self, message_id: str, offset: int = 0, limit: int = 50
    ) -> tuple[list[EmailEvent], int]:
        base = select(EmailEvent).where(EmailEvent.message_id == message_id)
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base.order_by(EmailEvent.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def create(self, event: EmailEvent) -> EmailEvent:
        self.db.add(event)
        await self.db.flush()
        return event
