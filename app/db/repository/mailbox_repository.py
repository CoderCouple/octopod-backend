from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.mailbox_model import Mailbox


class MailboxRepository:
    """Data-access layer for the Mailbox entity."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, mailbox_id: str) -> Mailbox | None:
        result = await self.db.execute(
            select(Mailbox).where(
                Mailbox.id == mailbox_id,
                Mailbox.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email_address: str) -> Mailbox | None:
        result = await self.db.execute(
            select(Mailbox).where(
                Mailbox.email_address == email_address,
                Mailbox.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def list_by_owner(
        self, owner_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[Mailbox], int]:
        base = select(Mailbox).where(
            Mailbox.owner_id == owner_id,
            Mailbox.is_deleted == False,  # noqa: E712
        )
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base.order_by(Mailbox.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def create(self, mailbox: Mailbox) -> Mailbox:
        self.db.add(mailbox)
        await self.db.flush()
        return mailbox

    async def update(self, mailbox: Mailbox) -> Mailbox:
        await self.db.flush()
        return mailbox

    async def soft_delete(self, mailbox: Mailbox, actor_id: str | None = None) -> Mailbox:
        mailbox.is_deleted = True
        mailbox.updated_by = actor_id
        mailbox.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return mailbox
