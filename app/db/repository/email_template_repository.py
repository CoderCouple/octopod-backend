from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.email_template_model import EmailTemplate


class EmailTemplateRepository:
    """Data-access layer for the EmailTemplate entity."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, template_id: str) -> EmailTemplate | None:
        result = await self.db.execute(
            select(EmailTemplate).where(
                EmailTemplate.id == template_id,
                EmailTemplate.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def list_by_owner(
        self, owner_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[EmailTemplate], int]:
        base = select(EmailTemplate).where(
            EmailTemplate.owner_id == owner_id,
            EmailTemplate.is_deleted == False,  # noqa: E712
        )
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base.order_by(EmailTemplate.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_by_project(
        self, project_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[EmailTemplate], int]:
        base = select(EmailTemplate).where(
            EmailTemplate.project_id == project_id,
            EmailTemplate.is_deleted == False,  # noqa: E712
        )
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base.order_by(EmailTemplate.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def get_by_category(
        self, owner_id: str, category: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[EmailTemplate], int]:
        base = select(EmailTemplate).where(
            EmailTemplate.owner_id == owner_id,
            EmailTemplate.category == category,
            EmailTemplate.is_deleted == False,  # noqa: E712
        )
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base.order_by(EmailTemplate.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def create(self, template: EmailTemplate) -> EmailTemplate:
        self.db.add(template)
        await self.db.flush()
        return template

    async def update(self, template: EmailTemplate) -> EmailTemplate:
        await self.db.flush()
        return template

    async def soft_delete(
        self, template: EmailTemplate, actor_id: str | None = None
    ) -> EmailTemplate:
        template.is_deleted = True
        template.updated_by = actor_id
        template.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return template
