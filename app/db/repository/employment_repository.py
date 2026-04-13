from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.employment_model import Employment


class EmploymentRepository:
    """Data-access layer for the Employment entity.

    Provides CRUD operations and lookup methods for employment records
    that link an employee to an organization.  All mutating methods
    flush to the session but do **not** commit; the caller is
    responsible for committing the transaction.

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

    async def get_by_id(self, employment_id: str) -> Employment | None:
        """Fetch a single non-deleted employment record by its primary key.

        Args:
            employment_id: The prefixed UUID of the employment
                (e.g. ``empl_...``).

        Returns:
            The matching ``Employment`` instance, or ``None`` if no
            non-deleted record exists with the given id.
        """
        result = await self.db.execute(
            select(Employment).where(
                Employment.id == employment_id,
                Employment.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def list_by_employee(
        self, employee_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[Employment], int]:
        """Return a paginated list of non-deleted employments for a given employee.

        Results are ordered by ``created_at`` descending (newest first).

        Args:
            employee_id: The prefixed UUID of the employee whose
                employment records should be retrieved.
            offset: The number of records to skip (default ``0``).
            limit: The maximum number of records to return (default ``20``).

        Returns:
            A tuple of ``(employments, total)`` where *employments* is the
            list of ``Employment`` instances for the requested page and
            *total* is the count of all matching (non-deleted) records.
        """
        base = select(Employment).where(
            Employment.employee_id == employee_id,
            Employment.is_deleted == False,  # noqa: E712
        )
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base.order_by(Employment.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def create(self, employment: Employment) -> Employment:
        """Persist a new employment record to the session.

        The entity is added and flushed (but not committed) so that
        database-generated defaults (e.g. ``created_at``) are populated
        immediately.

        Args:
            employment: The ``Employment`` instance to insert.

        Returns:
            The same ``Employment`` instance after flushing to the session.
        """
        self.db.add(employment)
        await self.db.flush()
        return employment

    async def update(self, employment: Employment) -> Employment:
        """Flush pending attribute changes on an existing employment record.

        The caller is expected to have mutated the ``Employment`` instance
        directly before calling this method.  Only a flush is performed;
        no commit is issued.

        Args:
            employment: The dirty ``Employment`` instance whose changes
                should be flushed.

        Returns:
            The same ``Employment`` instance after flushing.
        """
        await self.db.flush()
        return employment
