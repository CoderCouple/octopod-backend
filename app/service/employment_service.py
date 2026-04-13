"""Service layer for employment record management.

Provides business logic for creating, reading, updating, listing, and
ending employment relationships between employees and organizations.
Each employment mutation also creates corresponding career events and
is recorded in the event log for audit purposes.
"""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.request.employment_request import (
    CreateEmploymentRequest,
    UpdateEmploymentRequest,
)
from app.api.v1.response.employment_response import EmploymentResponse
from app.common.enum.career import CareerEventType
from app.common.enum.system import EntityType
from app.common.exceptions import EntityNotFoundError
from app.db.repository.career_event_repository import CareerEventRepository
from app.db.repository.employee_repository import EmployeeRepository
from app.db.repository.employment_repository import EmploymentRepository
from app.db.repository.org_repository import OrgRepository
from app.model.career_event_model import CareerEvent
from app.model.employment_model import Employment
from app.service.event_log_service import EventLogService


class EmploymentService:
    """Service for managing employment records.

    Handles the full lifecycle of employment relationships between employees
    and organizations, including creation, retrieval, listing, updates, and
    termination. Creating and ending employments automatically generates
    career events (JOIN and LEAVE respectively). All state changes are
    persisted to the append-only event log.
    """

    def __init__(self, db: AsyncSession):
        """Initialize EmploymentService with a database session.

        Args:
            db: An async SQLAlchemy session used for all database operations.
        """
        self.db = db
        self.repo = EmploymentRepository(db)
        self.employee_repo = EmployeeRepository(db)
        self.org_repo = OrgRepository(db)
        self.career_event_repo = CareerEventRepository(db)
        self.event_log = EventLogService(db)

    async def create_employment(
        self, data: CreateEmploymentRequest, actor_id: str | None = None
    ) -> EmploymentResponse:
        """Create a new employment record linking an employee to an organization.

        Validates that both the employee and organization exist, then persists
        the employment record, creates a JOIN career event, and logs a
        creation event.

        Args:
            data: The request payload containing employment fields such as
                employee_id, org_id, title, department, level, location,
                valid_from, valid_to, and is_current.
            actor_id: Optional identifier of the user performing the action,
                used for audit tracking.

        Returns:
            An EmploymentResponse representing the newly created employment.

        Raises:
            EntityNotFoundError: If the referenced employee or organization
                does not exist.
        """
        if not await self.employee_repo.get_by_id(data.employee_id):
            raise EntityNotFoundError("Employee", data.employee_id)
        if not await self.org_repo.get_by_id(data.org_id):
            raise EntityNotFoundError("Organization", data.org_id)

        employment = Employment(
            employee_id=data.employee_id,
            org_id=data.org_id,
            title=data.title,
            department=data.department,
            level=data.level,
            location=data.location,
            valid_from=data.valid_from,
            valid_to=data.valid_to,
            is_current=data.is_current,
            created_by=actor_id,
            updated_by=actor_id,
        )
        employment = await self.repo.create(employment)

        career_event = CareerEvent(
            employee_id=data.employee_id,
            org_id=data.org_id,
            employment_id=employment.id,
            event_type=CareerEventType.JOIN,
            effective_at=data.valid_from or datetime.now(timezone.utc),
            payload={"title": data.title, "department": data.department},
        )
        await self.career_event_repo.create(career_event)

        await self.event_log.append_event(
            entity_type=EntityType.EMPLOYMENT,
            entity_id=employment.id,
            action="create",
            actor_id=actor_id,
            after_state={
                "employee_id": employment.employee_id,
                "org_id": employment.org_id,
                "title": employment.title,
            },
        )
        return EmploymentResponse.model_validate(employment)

    async def get_employment(self, employment_id: str) -> EmploymentResponse:
        """Retrieve a single employment record by its unique identifier.

        Args:
            employment_id: The UUID string of the employment record to retrieve.

        Returns:
            An EmploymentResponse representing the found employment.

        Raises:
            EntityNotFoundError: If no employment record exists with the
                given ID.
        """
        employment = await self.repo.get_by_id(employment_id)
        if not employment:
            raise EntityNotFoundError("Employment", employment_id)
        return EmploymentResponse.model_validate(employment)

    async def list_employments_for_employee(
        self, employee_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[EmploymentResponse], int]:
        """List all employment records for a specific employee with pagination.

        Args:
            employee_id: The UUID string of the employee whose employment
                records to retrieve.
            offset: The number of records to skip. Defaults to 0.
            limit: The maximum number of records to return. Defaults to 20.

        Returns:
            A tuple of (list of EmploymentResponse objects, total count of
            employment records for the employee).
        """
        employments, total = await self.repo.list_by_employee(
            employee_id, offset, limit
        )
        return [EmploymentResponse.model_validate(e) for e in employments], total

    async def update_employment(
        self,
        employment_id: str,
        data: UpdateEmploymentRequest,
        actor_id: str | None = None,
    ) -> EmploymentResponse:
        """Update an existing employment record.

        Applies partial updates from the request payload and logs both the
        before and after states to the event log.

        Args:
            employment_id: The UUID string of the employment record to update.
            data: The request payload containing the fields to update. Only
                fields explicitly set in the request will be modified.
            actor_id: Optional identifier of the user performing the action,
                used for audit tracking.

        Returns:
            An EmploymentResponse representing the updated employment.

        Raises:
            EntityNotFoundError: If no employment record exists with the
                given ID.
        """
        employment = await self.repo.get_by_id(employment_id)
        if not employment:
            raise EntityNotFoundError("Employment", employment_id)

        before = {"title": employment.title, "department": employment.department}

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(employment, key, value)
        employment.updated_by = actor_id
        employment.updated_at = datetime.now(timezone.utc)

        employment = await self.repo.update(employment)

        await self.event_log.append_event(
            entity_type=EntityType.EMPLOYMENT,
            entity_id=employment.id,
            action="update",
            actor_id=actor_id,
            before_state=before,
            after_state={
                "title": employment.title,
                "department": employment.department,
            },
        )
        return EmploymentResponse.model_validate(employment)

    async def end_employment(
        self, employment_id: str, actor_id: str | None = None
    ) -> EmploymentResponse:
        """Terminate an active employment record.

        Sets the valid_to date to the current UTC time, marks the employment
        as no longer current, creates a LEAVE career event, and logs the
        termination to the event log.

        Args:
            employment_id: The UUID string of the employment record to end.
            actor_id: Optional identifier of the user performing the action,
                used for audit tracking.

        Returns:
            An EmploymentResponse representing the terminated employment.

        Raises:
            EntityNotFoundError: If no employment record exists with the
                given ID.
        """
        employment = await self.repo.get_by_id(employment_id)
        if not employment:
            raise EntityNotFoundError("Employment", employment_id)

        now = datetime.now(timezone.utc)
        employment.valid_to = now
        employment.is_current = False
        employment.updated_by = actor_id
        employment.updated_at = now

        employment = await self.repo.update(employment)

        career_event = CareerEvent(
            employee_id=employment.employee_id,
            org_id=employment.org_id,
            employment_id=employment.id,
            event_type=CareerEventType.LEAVE,
            effective_at=now,
            payload={
                "title": employment.title,
                "department": employment.department,
            },
        )
        await self.career_event_repo.create(career_event)

        await self.event_log.append_event(
            entity_type=EntityType.EMPLOYMENT,
            entity_id=employment.id,
            action="end",
            actor_id=actor_id,
            after_state={"valid_to": now.isoformat(), "is_current": False},
        )
        return EmploymentResponse.model_validate(employment)
