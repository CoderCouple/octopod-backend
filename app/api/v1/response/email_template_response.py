from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EmailTemplateResponse(BaseModel):
    """Response schema for an email template."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    name: str
    category: str | None = None
    subject: str
    body_html: str
    body_text: str | None = None
    variables: list[str] | None = None
    metadata: dict[str, Any] | None = Field(default=None, alias="metadata_")
    is_deleted: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime


class TemplatePreviewResponse(BaseModel):
    """Response for a rendered template preview."""

    subject: str
    body_html: str
    body_text: str | None = None
