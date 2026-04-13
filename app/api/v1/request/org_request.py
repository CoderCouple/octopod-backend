from typing import Any

from pydantic import BaseModel, Field


class CreateOrgRequest(BaseModel):
    """Request schema for creating a new organization.

    Attributes:
        name: The display name of the organization (required, 1-255 chars).
        domain: An optional unique domain identifier (e.g. ``"acme.com"``).
        industry: An optional industry classification string.
        logo_url: An optional URL to the organization's logo image.
        metadata: An optional dictionary of arbitrary key-value metadata.
    """

    name: str = Field(..., min_length=1, max_length=255)
    domain: str | None = Field(default=None, max_length=255)
    industry: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=2048)
    metadata: dict[str, Any] | None = None


class UpdateOrgRequest(BaseModel):
    """Request schema for partially updating an existing organization.

    All fields are optional; only provided fields will be updated.

    Attributes:
        name: Updated display name (1-255 chars).
        domain: Updated domain identifier.
        industry: Updated industry classification.
        logo_url: Updated logo URL.
        metadata: Updated arbitrary key-value metadata.
    """

    name: str | None = Field(default=None, min_length=1, max_length=255)
    domain: str | None = Field(default=None, max_length=255)
    industry: str | None = Field(default=None, max_length=255)
    logo_url: str | None = Field(default=None, max_length=2048)
    metadata: dict[str, Any] | None = None
