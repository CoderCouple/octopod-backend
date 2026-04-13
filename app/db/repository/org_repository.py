from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.organization_model import Organization


class OrgRepository:
    """Data-access layer for the Organization entity.

    Provides CRUD operations and lookup methods for organizations.
    All mutating methods flush to the session but do **not** commit;
    the caller (typically a service or the request-scoped session
    middleware) is responsible for committing the transaction.

    Args:
        db: An async SQLAlchemy session used for all database operations.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the repository with an async database session.

        Args:
            db: The SQLAlchemy ``AsyncSession`` bound to the current
                request or unit of work.
        """
        self.db = db

    async def get_by_id(self, org_id: str) -> Organization | None:
        """Fetch a single non-deleted organization by its primary key.

        Args:
            org_id: The prefixed UUID of the organization (e.g. ``org_...``).

        Returns:
            The matching ``Organization`` instance, or ``None`` if no
            non-deleted record exists with the given id.
        """
        result = await self.db.execute(
            select(Organization).where(
                Organization.id == org_id,
                Organization.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_domain(self, domain: str, exclude_id: str | None = None) -> Organization | None:
        """Look up a non-deleted organization by its unique domain.

        This is primarily used for duplicate-detection when creating or
        updating an organization.

        Args:
            domain: The domain string to search for (e.g. ``"acme.com"``).
            exclude_id: An optional organization id to exclude from the
                search.  Useful when updating an organization and the
                caller needs to ensure no *other* org owns the domain.

        Returns:
            The matching ``Organization`` instance, or ``None`` if not found.
        """
        query = select(Organization).where(
            Organization.domain == domain,
            Organization.is_deleted == False,  # noqa: E712
        )
        if exclude_id:
            query = query.where(Organization.id != exclude_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_all(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[Organization], int]:
        """Return a paginated list of non-deleted organizations.

        Results are ordered by ``created_at`` descending (newest first).

        Args:
            offset: The number of records to skip (default ``0``).
            limit: The maximum number of records to return (default ``20``).

        Returns:
            A tuple of ``(organizations, total)`` where *organizations* is
            the list of ``Organization`` instances for the requested page and
            *total* is the count of all matching (non-deleted) records.
        """
        base = select(Organization).where(
            Organization.is_deleted == False  # noqa: E712
        )
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base.order_by(Organization.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def create(self, org: Organization) -> Organization:
        """Persist a new organization to the session.

        The entity is added and flushed (but not committed) so that
        database-generated defaults (e.g. ``created_at``) are populated
        immediately.

        Args:
            org: The ``Organization`` instance to insert.

        Returns:
            The same ``Organization`` instance after flushing to the session.
        """
        self.db.add(org)
        await self.db.flush()
        return org

    async def update(self, org: Organization) -> Organization:
        """Flush pending attribute changes on an existing organization.

        The caller is expected to have mutated the ``Organization`` instance
        directly before calling this method.  Only a flush is performed;
        no commit is issued.

        Args:
            org: The dirty ``Organization`` instance whose changes should
                be flushed.

        Returns:
            The same ``Organization`` instance after flushing.
        """
        await self.db.flush()
        return org

    async def soft_delete(self, org: Organization, actor_id: str | None = None) -> Organization:
        """Mark an organization as deleted (soft-delete).

        Sets ``is_deleted`` to ``True``, records who performed the
        deletion, and updates the ``updated_at`` timestamp.  The row
        is **not** physically removed from the database.

        Args:
            org: The ``Organization`` instance to soft-delete.
            actor_id: Optional identifier of the user performing the
                deletion, written to ``updated_by``.

        Returns:
            The soft-deleted ``Organization`` instance after flushing.
        """
        org.is_deleted = True
        org.updated_by = actor_id
        org.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return org
