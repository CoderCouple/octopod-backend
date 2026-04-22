from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.email_message_model import EmailMessage


class EmailMessageRepository:
    """Data-access layer for the EmailMessage entity."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, message_id: str) -> EmailMessage | None:
        result = await self.db.execute(
            select(EmailMessage).where(EmailMessage.id == message_id)
        )
        return result.scalar_one_or_none()

    async def get_by_tracking_id(self, tracking_id: str) -> EmailMessage | None:
        result = await self.db.execute(
            select(EmailMessage).where(EmailMessage.tracking_id == tracking_id)
        )
        return result.scalar_one_or_none()

    async def get_scheduled_messages(self, batch_size: int = 50) -> list[EmailMessage]:
        """Fetch scheduled messages due for sending.

        Uses FOR UPDATE SKIP LOCKED on PostgreSQL for safe concurrent access.
        Falls back to a plain select on SQLite (for tests).
        """
        query = (
            select(EmailMessage)
            .where(
                EmailMessage.status.in_(["scheduled", "queued"]),
                EmailMessage.scheduled_at <= func.now(),
            )
            .order_by(EmailMessage.scheduled_at.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def cancel_scheduled_for_recipient(self, recipient_id: str) -> int:
        """Cancel all scheduled/queued messages for a recipient."""
        stmt = (
            update(EmailMessage)
            .where(
                EmailMessage.recipient_id == recipient_id,
                EmailMessage.status.in_(["scheduled", "queued"]),
            )
            .values(status="cancelled")
        )
        result = await self.db.execute(stmt)
        await self.db.flush()
        return result.rowcount

    async def list_by_campaign(
        self, campaign_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[EmailMessage], int]:
        base = select(EmailMessage).where(EmailMessage.campaign_id == campaign_id)
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base.order_by(EmailMessage.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_by_thread_id(self, thread_id: str) -> list[EmailMessage]:
        result = await self.db.execute(
            select(EmailMessage).where(EmailMessage.thread_id == thread_id)
        )
        return list(result.scalars().all())

    async def create(self, message: EmailMessage) -> EmailMessage:
        self.db.add(message)
        await self.db.flush()
        return message

    async def update(self, message: EmailMessage) -> EmailMessage:
        await self.db.flush()
        return message
