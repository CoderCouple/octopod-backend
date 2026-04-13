from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class EmployeeResponse(BaseModel):
    """Response schema for an employee entity.

    Configured with ``from_attributes=True`` so it can be constructed
    directly from an ``Employee`` SQLAlchemy model instance.

    Attributes:
        id: The prefixed UUID of the employee.
        canonical_name: The display name.
        primary_email: The unique email address, if set.
        profile_data: Arbitrary profile metadata, if set.
        is_deleted: Soft-delete flag.
        created_by: The actor who created the record.
        updated_by: The actor who last updated the record.
        created_at: When the record was created.
        updated_at: When the record was last updated.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    canonical_name: str
    primary_email: str | None = None
    profile_data: dict[str, Any] | None = None
    is_deleted: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
