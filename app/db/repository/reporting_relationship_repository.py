from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.reporting_relationship_model import ReportingRelationship


class ReportingRelationshipRepository:
    """Data-access layer for the ReportingRelationship entity.

    Provides CRUD operations and filtered queries for manager-employee
    reporting relationships.  All mutating methods flush to the session
    but do **not** commit; the caller is responsible for committing the
    transaction.

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

    async def get_by_id(self, relationship_id: str) -> ReportingRelationship | None:
        """Fetch a single non-deleted reporting relationship by its primary key.

        Args:
            relationship_id: The prefixed UUID of the relationship
                (e.g. ``rr_...``).

        Returns:
            The matching ``ReportingRelationship`` instance, or ``None``
            if no non-deleted record exists with the given id.
        """
        result = await self.db.execute(
            select(ReportingRelationship).where(
                ReportingRelationship.id == relationship_id,
                ReportingRelationship.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def list_filtered(
        self,
        org_id: str | None = None,
        employee_id: str | None = None,
        manager_employee_id: str | None = None,
        is_current: bool | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ReportingRelationship], int]:
        """Return a paginated, optionally filtered list of non-deleted reporting relationships.

        All filter parameters are optional; when omitted the corresponding
        predicate is not applied.  Results are ordered by ``created_at``
        descending (newest first).

        Args:
            org_id: Filter by organization id.
            employee_id: Filter by the subordinate employee id.
            manager_employee_id: Filter by the manager employee id.
            is_current: Filter by whether the relationship is currently
                active.
            offset: The number of records to skip (default ``0``).
            limit: The maximum number of records to return (default ``20``).

        Returns:
            A tuple of ``(relationships, total)`` where *relationships* is
            the list of ``ReportingRelationship`` instances for the
            requested page and *total* is the count of all matching
            (non-deleted) records.
        """
        query = select(ReportingRelationship).where(
            ReportingRelationship.is_deleted == False  # noqa: E712
        )
        if org_id:
            query = query.where(ReportingRelationship.org_id == org_id)
        if employee_id:
            query = query.where(ReportingRelationship.employee_id == employee_id)
        if manager_employee_id:
            query = query.where(
                ReportingRelationship.manager_employee_id == manager_employee_id
            )
        if is_current is not None:
            query = query.where(ReportingRelationship.is_current == is_current)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            query.order_by(ReportingRelationship.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def create(self, rr: ReportingRelationship) -> ReportingRelationship:
        """Persist a new reporting relationship to the session.

        The entity is added and flushed (but not committed) so that
        database-generated defaults are populated immediately.

        Args:
            rr: The ``ReportingRelationship`` instance to insert.

        Returns:
            The same ``ReportingRelationship`` instance after flushing.
        """
        self.db.add(rr)
        await self.db.flush()
        return rr

    async def update(self, rr: ReportingRelationship) -> ReportingRelationship:
        """Flush pending attribute changes on an existing reporting relationship.

        The caller is expected to have mutated the
        ``ReportingRelationship`` instance directly before calling this
        method.  Only a flush is performed; no commit is issued.

        Args:
            rr: The dirty ``ReportingRelationship`` instance whose
                changes should be flushed.

        Returns:
            The same ``ReportingRelationship`` instance after flushing.
        """
        await self.db.flush()
        return rr
