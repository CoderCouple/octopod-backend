from pydantic import BaseModel, Field


class ConnectGmailRequest(BaseModel):
    """Request to connect a Gmail mailbox via OAuth authorization code."""

    auth_code: str = Field(..., min_length=1)
    display_name: str | None = Field(default=None, max_length=255)


class ConnectOutlookRequest(BaseModel):
    """Request to connect an Outlook mailbox via OAuth authorization code."""

    auth_code: str = Field(..., min_length=1)
    display_name: str | None = Field(default=None, max_length=255)


class ConnectSmtpRequest(BaseModel):
    """Request to connect a generic SMTP mailbox."""

    email_address: str = Field(..., max_length=320)
    display_name: str | None = Field(default=None, max_length=255)
    smtp_host: str = Field(..., max_length=255)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = Field(..., max_length=255)
    smtp_password: str = Field(..., min_length=1)
    smtp_use_tls: bool = Field(default=True)


class ConnectSesRequest(BaseModel):
    """Request to connect an AWS SES mailbox."""

    email_address: str = Field(..., max_length=320)
    display_name: str | None = Field(default=None, max_length=255)


class UpdateMailboxRequest(BaseModel):
    """Request to update a mailbox's settings."""

    display_name: str | None = Field(default=None, max_length=255)
    daily_send_limit: int | None = Field(default=None, ge=1, le=500)
    warmup_enabled: bool | None = None
    warmup_current_limit: int | None = Field(default=None, ge=1, le=100)
