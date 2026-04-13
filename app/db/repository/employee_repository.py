from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.employee_model import Employee


class EmployeeRepository:
    """Data-access layer for the Employee entity.

    Provides CRUD operations and lookup methods for employees.
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

    async def get_by_id(self, employee_id: str) -> Employee | None:
        """Fetch a single non-deleted employee by its primary key.

        Args:
            employee_id: The prefixed UUID of the employee (e.g. ``emp_...``).

        Returns:
            The matching ``Employee`` instance, or ``None`` if no
            non-deleted record exists with the given id.
        """
        result = await self.db.execute(
            select(Employee).where(
                Employee.id == employee_id,
                Employee.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str, exclude_id: str | None = None) -> Employee | None:
        """Look up a non-deleted employee by their primary email address.

        Primarily used for duplicate-detection when creating or updating
        an employee.

        Args:
            email: The email address to search for.
            exclude_id: An optional employee id to exclude from the
                search.  Useful during updates to ensure no *other*
                employee owns the email.

        Returns:
            The matching ``Employee`` instance, or ``None`` if not found.
        """
        query = select(Employee).where(
            Employee.primary_email == email,
            Employee.is_deleted == False,  # noqa: E712
        )
        if exclude_id:
            query = query.where(Employee.id != exclude_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def list_all(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[Employee], int]:
        """Return a paginated list of non-deleted employees.

        Results are ordered by ``created_at`` descending (newest first).

        Args:
            offset: The number of records to skip (default ``0``).
            limit: The maximum number of records to return (default ``20``).

        Returns:
            A tuple of ``(employees, total)`` where *employees* is the
            list of ``Employee`` instances for the requested page and
            *total* is the count of all matching (non-deleted) records.
        """
        base = select(Employee).where(
            Employee.is_deleted == False  # noqa: E712
        )
        count_result = await self.db.execute(
            select(func.count()).select_from(base.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base.order_by(Employee.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def create(self, employee: Employee) -> Employee:
        """Persist a new employee to the session.

        The entity is added and flushed (but not committed) so that
        database-generated defaults (e.g. ``created_at``) are populated
        immediately.

        Args:
            employee: The ``Employee`` instance to insert.

        Returns:
            The same ``Employee`` instance after flushing to the session.
        """
        self.db.add(employee)
        await self.db.flush()
        return employee

    async def update(self, employee: Employee) -> Employee:
        """Flush pending attribute changes on an existing employee.

        The caller is expected to have mutated the ``Employee`` instance
        directly before calling this method.  Only a flush is performed;
        no commit is issued.

        Args:
            employee: The dirty ``Employee`` instance whose changes should
                be flushed.

        Returns:
            The same ``Employee`` instance after flushing.
        """
        await self.db.flush()
        return employee
