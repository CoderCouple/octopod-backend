import uuid

from sqlalchemy import JSON, TIMESTAMP, Boolean, Column, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


def generate_prefixed_uuid() -> str:
    return f"mbx_{uuid.uuid4()}"


class Mailbox(Base):
    __tablename__ = "mailbox"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    owner_id = Column(String(), nullable=False, index=True)
    provider = Column(String(30), nullable=False)
    email_address = Column(String(320), nullable=False)
    display_name = Column(String(255), nullable=True)
    status = Column(String(30), nullable=False, default="connected")
    access_token = Column(Text(), nullable=True)
    refresh_token = Column(Text(), nullable=True)
    token_expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    smtp_host = Column(String(255), nullable=True)
    smtp_port = Column(Integer(), nullable=True)
    smtp_username = Column(String(255), nullable=True)
    smtp_password = Column(Text(), nullable=True)
    smtp_use_tls = Column(Boolean, default=True)
    daily_send_limit = Column(Integer(), nullable=False, default=35)
    sends_today = Column(Integer(), nullable=False, default=0)
    sends_today_reset_at = Column(TIMESTAMP(timezone=True), nullable=True)
    warmup_enabled = Column(Boolean, default=False)
    warmup_current_limit = Column(Integer(), default=5)
    error_message = Column(Text(), nullable=True)
    last_error_at = Column(TIMESTAMP(timezone=True), nullable=True)
    metadata_ = Column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=dict,
    )
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_by = Column(String(), nullable=True)
    updated_by = Column(String(), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
