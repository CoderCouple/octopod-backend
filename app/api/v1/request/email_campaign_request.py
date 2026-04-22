from typing import Any

from pydantic import BaseModel, Field


class CreateCampaignRequest(BaseModel):
    """Request to create a new email campaign."""

    name: str = Field(..., min_length=1, max_length=255)
    mailbox_id: str = Field(..., min_length=1)
    description: str | None = Field(default=None, max_length=2000)
    send_window_start: str | None = Field(default=None, description="HH:MM format")
    send_window_end: str | None = Field(default=None, description="HH:MM format")
    send_timezone: str = Field(default="UTC", max_length=50)
    send_days: list[int] | None = Field(default=None, description="ISO weekdays 1-7")
    stop_on_reply: bool = True
    stop_on_bounce: bool = True
    track_opens: bool = True
    track_clicks: bool = True
    metadata: dict[str, Any] | None = None


class UpdateCampaignRequest(BaseModel):
    """Request to update a campaign."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    mailbox_id: str | None = Field(default=None, min_length=1)
    send_window_start: str | None = None
    send_window_end: str | None = None
    send_timezone: str | None = Field(default=None, max_length=50)
    send_days: list[int] | None = None
    stop_on_reply: bool | None = None
    stop_on_bounce: bool | None = None
    track_opens: bool | None = None
    track_clicks: bool | None = None
    metadata: dict[str, Any] | None = None


class CreateStepRequest(BaseModel):
    """Request to add a step to a campaign."""

    template_id: str | None = None
    step_type: str = Field(default="email", max_length=30)
    delay_days: int = Field(default=0, ge=0)
    delay_hours: int = Field(default=0, ge=0)
    subject_override: str | None = None
    body_override: str | None = None
    condition_field: str | None = Field(default=None, max_length=100)
    condition_op: str | None = Field(default=None, max_length=20)
    condition_value: str | None = Field(default=None, max_length=255)


class UpdateStepRequest(BaseModel):
    """Request to update a campaign step."""

    template_id: str | None = None
    step_type: str | None = Field(default=None, max_length=30)
    delay_days: int | None = Field(default=None, ge=0)
    delay_hours: int | None = Field(default=None, ge=0)
    step_order: int | None = Field(default=None, ge=1)
    subject_override: str | None = None
    body_override: str | None = None
    condition_field: str | None = Field(default=None, max_length=100)
    condition_op: str | None = Field(default=None, max_length=20)
    condition_value: str | None = Field(default=None, max_length=255)


class AddRecipientRequest(BaseModel):
    """Request to manually add a recipient to a campaign."""

    email: str = Field(..., max_length=320)
    first_name: str | None = Field(default=None, max_length=255)
    last_name: str | None = Field(default=None, max_length=255)
    company: str | None = Field(default=None, max_length=255)
    title: str | None = Field(default=None, max_length=255)
    merge_variables: dict[str, str] | None = None


class AddRecipientsFromSearchRequest(BaseModel):
    """Request to add recipients from developer profile IDs."""

    profile_ids: list[str] = Field(..., min_length=1)
