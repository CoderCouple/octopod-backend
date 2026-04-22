from typing import Any

from pydantic import BaseModel, Field


class CreateEmailTemplateRequest(BaseModel):
    """Request to create a new email template."""

    name: str = Field(..., min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    subject: str = Field(..., min_length=1)
    body_html: str = Field(..., min_length=1)
    body_text: str | None = None
    variables: list[str] | None = None
    metadata: dict[str, Any] | None = None


class UpdateEmailTemplateRequest(BaseModel):
    """Request to update an email template."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, max_length=100)
    subject: str | None = Field(default=None, min_length=1)
    body_html: str | None = Field(default=None, min_length=1)
    body_text: str | None = None
    variables: list[str] | None = None
    metadata: dict[str, Any] | None = None


class PreviewTemplateRequest(BaseModel):
    """Request to preview a rendered template with sample variables."""

    variables: dict[str, str] = Field(default_factory=dict)
