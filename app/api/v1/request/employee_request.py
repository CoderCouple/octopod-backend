from typing import Any

from pydantic import BaseModel, Field


class CreateEmployeeRequest(BaseModel):
    """Request schema for creating a new employee.

    Attributes:
        canonical_name: The display name of the employee (required,
            1-255 chars).
        primary_email: An optional unique email address (max 320 chars).
        profile_data: An optional dictionary of arbitrary profile
            metadata.
    """

    canonical_name: str = Field(..., min_length=1, max_length=255)
    primary_email: str | None = Field(default=None, max_length=320)
    profile_data: dict[str, Any] | None = None


class UpdateEmployeeRequest(BaseModel):
    """Request schema for partially updating an existing employee.

    All fields are optional; only provided fields will be updated.

    Attributes:
        canonical_name: Updated display name (1-255 chars).
        primary_email: Updated email address (max 320 chars).
        profile_data: Updated arbitrary profile metadata.
    """

    canonical_name: str | None = Field(default=None, min_length=1, max_length=255)
    primary_email: str | None = Field(default=None, max_length=320)
    profile_data: dict[str, Any] | None = None
