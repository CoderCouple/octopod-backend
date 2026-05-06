import uuid

from sqlalchemy import JSON, TIMESTAMP, Column, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


def generate_prefixed_uuid() -> str:
    return f"em_{uuid.uuid4()}"


class EmailMessage(Base):
    __tablename__ = "email_message"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    campaign_id = Column(String(), nullable=False, index=True)
    step_id = Column(String(), nullable=False)
    recipient_id = Column(String(), nullable=False, index=True)
    mailbox_id = Column(String(), nullable=False)
    tracking_id = Column(String(), nullable=False, unique=True)
    from_email = Column(String(320), nullable=False)
    from_name = Column(String(255), nullable=True)
    to_email = Column(String(320), nullable=False)
    subject = Column(Text(), nullable=False)
    body_html = Column(Text(), nullable=False)
    body_text = Column(Text(), nullable=True)
    status = Column(String(30), nullable=False, default="scheduled")
    scheduled_at = Column(TIMESTAMP(timezone=True), nullable=False)
    sent_at = Column(TIMESTAMP(timezone=True), nullable=True)
    delivered_at = Column(TIMESTAMP(timezone=True), nullable=True)
    opened_at = Column(TIMESTAMP(timezone=True), nullable=True)
    clicked_at = Column(TIMESTAMP(timezone=True), nullable=True)
    replied_at = Column(TIMESTAMP(timezone=True), nullable=True)
    bounced_at = Column(TIMESTAMP(timezone=True), nullable=True)
    failed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    provider = Column(String(30), nullable=True)
    provider_message_id = Column(Text(), nullable=True)
    message_id_header = Column(Text(), nullable=True)
    thread_id = Column(Text(), nullable=True)
    in_reply_to = Column(Text(), nullable=True)
    link_map = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=dict,
    )
    open_count = Column(Integer(), nullable=False, default=0)
    click_count = Column(Integer(), nullable=False, default=0)
    retry_count = Column(Integer(), nullable=False, default=0)
    max_retries = Column(Integer(), nullable=False, default=3)
    next_retry_at = Column(TIMESTAMP(timezone=True), nullable=True)
    error_message = Column(Text(), nullable=True)
    metadata_ = Column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=dict,
    )
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
