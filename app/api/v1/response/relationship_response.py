from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ReportingRelationshipResponse(BaseModel):
    """Response schema for a reporting relationship record.

    Configured with ``from_attributes=True`` so it can be constructed
    directly from a ``ReportingRelationship`` SQLAlchemy model instance.

    Attributes:
        id: The prefixed UUID of the reporting relationship.
        org_id: The prefixed UUID of the organization.
        employee_id: The prefixed UUID of the subordinate employee.
        manager_employee_id: The prefixed UUID of the manager employee.
        relationship_type: The type of relationship (e.g.
            ``"solid_line"``, ``"dotted_line"``).
        status: The verification status (e.g. ``"confirmed"``,
            ``"weak"``).
        confidence_score: Numeric confidence score (0-1).
        valid_from: Start datetime of the relationship period, if set.
        valid_to: End datetime of the relationship period, if set.
        is_current: Whether the relationship is currently active.
        is_deleted: Soft-delete flag.
        created_by: The actor who created the record.
        updated_by: The actor who last updated the record.
        created_at: When the record was created.
        updated_at: When the record was last updated.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    employee_id: str
    manager_employee_id: str
    relationship_type: str
    status: str
    confidence_score: Decimal
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    is_current: bool
    is_deleted: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
