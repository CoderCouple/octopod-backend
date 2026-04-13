"""Service layer for employee CRUD operations.

Provides business logic for creating, reading, updating, and listing
employee records. All mutating operations are recorded in the event log
for audit purposes.
"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.request.employee_request import (
    CreateEmployeeRequest,
    UpdateEmployeeRequest,
)
from app.api.v1.response.employee_response import EmployeeResponse
from app.common.enum.system import EntityType
from app.common.exceptions import DuplicateEntityError, EntityNotFoundError
from app.db.repository.employee_repository import EmployeeRepository
from app.model.employee_model import Employee
from app.service.event_log_service import EventLogService


class EmployeeService:
    """Service for managing employee entities.

    Handles the full lifecycle of employees including creation with
    email uniqueness validation, retrieval, listing with pagination,
    and updates. All state changes are persisted to the append-only
    event log.
    """

    def __init__(self, db: AsyncSession):
        """Initialize EmployeeService with a database session.

        Args:
            db: An async SQLAlchemy session used for all database operations.
        """
        self.db = db
        self.repo = EmployeeRepository(db)
        self.event_log = EventLogService(db)

    async def create_employee(
        self, data: CreateEmployeeRequest, actor_id: str | None = None
    ) -> EmployeeResponse:
        """Create a new employee record.

        Validates that the primary email (if provided) is not already in use
        by another employee, then persists the new record and logs a creation
        event.

        Args:
            data: The request payload containing employee fields such as
                canonical_name, primary_email, and profile_data.
            actor_id: Optional identifier of the user performing the action,
                used for audit tracking.

        Returns:
            An EmployeeResponse representing the newly created employee.

        Raises:
            DuplicateEntityError: If an employee with the same primary_email
                already exists.
        """
        if data.primary_email:
            existing = await self.repo.get_by_email(data.primary_email)
            if existing:
                raise DuplicateEntityError(
                    "Employee", "primary_email", data.primary_email
                )

        employee = Employee(
            canonical_name=data.canonical_name,
            primary_email=data.primary_email,
            profile_data=data.profile_data or {},
            created_by=actor_id,
            updated_by=actor_id,
        )
        employee = await self.repo.create(employee)

        await self.event_log.append_event(
            entity_type=EntityType.EMPLOYEE,
            entity_id=employee.id,
            action="create",
            actor_id=actor_id,
            after_state={
                "canonical_name": employee.canonical_name,
                "primary_email": employee.primary_email,
            },
        )
        return EmployeeResponse.model_validate(employee)

    async def get_employee(self, employee_id: str) -> EmployeeResponse:
        """Retrieve a single employee by their unique identifier.

        Args:
            employee_id: The UUID string of the employee to retrieve.

        Returns:
            An EmployeeResponse representing the found employee.

        Raises:
            EntityNotFoundError: If no employee exists with the given ID.
        """
        employee = await self.repo.get_by_id(employee_id)
        if not employee:
            raise EntityNotFoundError("Employee", employee_id)
        return EmployeeResponse.model_validate(employee)

    async def list_employees(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[EmployeeResponse], int]:
        """List employees with pagination.

        Args:
            offset: The number of records to skip. Defaults to 0.
            limit: The maximum number of records to return. Defaults to 20.

        Returns:
            A tuple of (list of EmployeeResponse objects, total count of
            employees).
        """
        employees, total = await self.repo.list_all(offset, limit)
        return [EmployeeResponse.model_validate(e) for e in employees], total

    async def update_employee(
        self,
        employee_id: str,
        data: UpdateEmployeeRequest,
        actor_id: str | None = None,
    ) -> EmployeeResponse:
        """Update an existing employee record.

        Applies partial updates from the request payload. If the primary email
        is being changed, validates that the new email is not already in use.
        Logs both the before and after states to the event log.

        Args:
            employee_id: The UUID string of the employee to update.
            data: The request payload containing the fields to update. Only
                fields explicitly set in the request will be modified.
            actor_id: Optional identifier of the user performing the action,
                used for audit tracking.

        Returns:
            An EmployeeResponse representing the updated employee.

        Raises:
            EntityNotFoundError: If no employee exists with the given ID.
            DuplicateEntityError: If the new primary_email conflicts with an
                existing employee.
        """
        employee = await self.repo.get_by_id(employee_id)
        if not employee:
            raise EntityNotFoundError("Employee", employee_id)

        before = {
            "canonical_name": employee.canonical_name,
            "primary_email": employee.primary_email,
        }

        if (
            data.primary_email is not None
            and data.primary_email != employee.primary_email
        ):
            existing = await self.repo.get_by_email(
                data.primary_email, exclude_id=employee_id
            )
            if existing:
                raise DuplicateEntityError(
                    "Employee", "primary_email", data.primary_email
                )

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(employee, key, value)
        employee.updated_by = actor_id
        employee.updated_at = datetime.now(timezone.utc)

        employee = await self.repo.update(employee)

        await self.event_log.append_event(
            entity_type=EntityType.EMPLOYEE,
            entity_id=employee.id,
            action="update",
            actor_id=actor_id,
            before_state=before,
            after_state={
                "canonical_name": employee.canonical_name,
                "primary_email": employee.primary_email,
            },
        )
        return EmployeeResponse.model_validate(employee)
