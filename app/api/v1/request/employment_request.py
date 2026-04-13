from datetime import datetime

from pydantic import BaseModel, Field


class CreateEmploymentRequest(BaseModel):
    """Request schema for creating a new employment record.

    Attributes:
        employee_id: The prefixed UUID of the employee (required).
        org_id: The prefixed UUID of the organization (required).
        title: Optional job title (max 255 chars).
        department: Optional department name (max 255 chars).
        level: Optional seniority / grade level (max 100 chars).
        location: Optional work location (max 255 chars).
        valid_from: Optional start datetime of the employment period.
        valid_to: Optional end datetime of the employment period.
        is_current: Whether this is the active employment.  Defaults
            to ``True``.
    """

    employee_id: str
    org_id: str
    title: str | None = Field(default=None, max_length=255)
    department: str | None = Field(default=None, max_length=255)
    level: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=255)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    is_current: bool = True


class UpdateEmploymentRequest(BaseModel):
    """Request schema for partially updating an existing employment record.

    All fields are optional; only provided fields will be updated.

    Attributes:
        title: Updated job title (max 255 chars).
        department: Updated department name (max 255 chars).
        level: Updated seniority / grade level (max 100 chars).
        location: Updated work location (max 255 chars).
        valid_from: Updated start datetime of the employment period.
        valid_to: Updated end datetime of the employment period.
    """

    title: str | None = Field(default=None, max_length=255)
    department: str | None = Field(default=None, max_length=255)
    level: str | None = Field(default=None, max_length=100)
    location: str | None = Field(default=None, max_length=255)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
