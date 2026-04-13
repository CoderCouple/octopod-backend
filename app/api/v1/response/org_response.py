from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OrgResponse(BaseModel):
    """Response schema for an organization entity.

    Configured with ``from_attributes=True`` so it can be constructed
    directly from an ``Organization`` SQLAlchemy model instance.

    Attributes:
        id: The prefixed UUID of the organization.
        name: The display name.
        domain: The unique domain identifier, if set.
        industry: The industry classification, if set.
        logo_url: The logo image URL, if set.
        metadata: Arbitrary key-value metadata (aliased from
            ``metadata_`` on the ORM model).
        is_deleted: Soft-delete flag.
        created_by: The actor who created the record.
        updated_by: The actor who last updated the record.
        created_at: When the record was created.
        updated_at: When the record was last updated.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    domain: str | None = None
    industry: str | None = None
    logo_url: str | None = None
    metadata: dict[str, Any] | None = Field(default=None, alias="metadata_")
    is_deleted: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
