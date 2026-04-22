from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CampaignStepResponse(BaseModel):
    """Response schema for a campaign step."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    campaign_id: str
    template_id: str | None = None
    step_order: int
    step_type: str
    delay_days: int
    delay_hours: int
    subject_override: str | None = None
    body_override: str | None = None
    condition_field: str | None = None
    condition_op: str | None = None
    condition_value: str | None = None
    created_at: datetime
    updated_at: datetime


class CampaignRecipientResponse(BaseModel):
    """Response schema for a campaign recipient."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    campaign_id: str
    developer_profile_id: str | None = None
    email: str
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    title: str | None = None
    status: str
    current_step_order: int
    next_send_at: datetime | None = None
    email_source: str | None = None
    merge_variables: dict[str, str] | None = None
    metadata: dict[str, Any] | None = Field(default=None, alias="metadata_")
    created_at: datetime
    updated_at: datetime


class EmailCampaignResponse(BaseModel):
    """Response schema for an email campaign."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    mailbox_id: str
    name: str
    description: str | None = None
    status: str
    send_window_start: str | None = None
    send_window_end: str | None = None
    send_timezone: str | None = None
    send_days: list[int] | None = None
    stop_on_reply: bool
    stop_on_bounce: bool
    track_opens: bool
    track_clicks: bool
    total_recipients: int
    total_sent: int
    total_delivered: int
    total_opened: int
    total_clicked: int
    total_replied: int
    total_bounced: int
    total_unsubscribed: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    metadata: dict[str, Any] | None = Field(default=None, alias="metadata_")
    is_deleted: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime


class EmailMessageResponse(BaseModel):
    """Response schema for an individual email message."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    campaign_id: str
    step_id: str
    recipient_id: str
    tracking_id: str
    from_email: str
    to_email: str
    subject: str
    status: str
    scheduled_at: datetime
    sent_at: datetime | None = None
    delivered_at: datetime | None = None
    opened_at: datetime | None = None
    clicked_at: datetime | None = None
    replied_at: datetime | None = None
    bounced_at: datetime | None = None
    open_count: int
    click_count: int
    error_message: str | None = None
    created_at: datetime


class CampaignAnalyticsResponse(BaseModel):
    """Aggregated campaign analytics."""

    campaign_id: str
    total_recipients: int
    total_sent: int
    total_delivered: int
    total_opened: int
    total_clicked: int
    total_replied: int
    total_bounced: int
    total_unsubscribed: int
    open_rate: float
    click_rate: float
    reply_rate: float
    bounce_rate: float


class StepAnalyticsResponse(BaseModel):
    """Per-step analytics."""

    step_id: str
    step_order: int
    total_sent: int
    total_opened: int
    total_clicked: int
    total_replied: int
    open_rate: float
    click_rate: float
    reply_rate: float
