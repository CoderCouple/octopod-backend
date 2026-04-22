from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MailboxResponse(BaseModel):
    """Response schema for a mailbox entity.

    Sensitive fields (tokens, passwords) are excluded.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    owner_id: str
    provider: str
    email_address: str
    display_name: str | None = None
    status: str
    daily_send_limit: int
    sends_today: int
    warmup_enabled: bool | None = None
    warmup_current_limit: int | None = None
    error_message: str | None = None
    last_error_at: datetime | None = None
    metadata: dict[str, Any] | None = Field(default=None, alias="metadata_")
    is_deleted: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime
