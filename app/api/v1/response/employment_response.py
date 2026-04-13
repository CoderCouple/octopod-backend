from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EmploymentResponse(BaseModel):
    """Response schema for an employment record.

    Configured with ``from_attributes=True`` so it can be constructed
    directly from an ``Employment`` SQLAlchemy model instance.

    Attributes:
        id: The prefixed UUID of the employment record.
        employee_id: The prefixed UUID of the associated employee.
        org_id: The prefixed UUID of the associated organization.
        title: The job title, if set.
        department: The department name, if set.
        level: The seniority / grade level, if set.
        location: The work location, if set.
        valid_from: Start datetime of the employment period, if set.
        valid_to: End datetime of the employment period, if set.
        is_current: Whether this is the active employment.
        is_deleted: Soft-delete flag.
        created_by: The actor who created the record.
        updated_by: The actor who last updated the record.
        created_at: When the record was created.
        updated_at: When the record was last updated.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    employee_id: str
    org_id: str
    title: str | None = None
    department: str | None = None
    level: str | None = None
    location: str | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    is_current: bool
    is_deleted: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
