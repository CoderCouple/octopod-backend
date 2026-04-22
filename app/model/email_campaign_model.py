import uuid

from sqlalchemy import JSON, TIMESTAMP, Boolean, Column, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


def generate_prefixed_uuid():
    return f"ec_{uuid.uuid4()}"


class EmailCampaign(Base):
    __tablename__ = "email_campaign"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    owner_id = Column(String(), nullable=False, index=True)
    mailbox_id = Column(String(), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text(), nullable=True)
    status = Column(String(30), nullable=False, default="draft")
    send_window_start = Column(String(5), nullable=True)
    send_window_end = Column(String(5), nullable=True)
    send_timezone = Column(String(50), default="UTC")
    send_days = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=lambda: [1, 2, 3, 4, 5],
    )
    stop_on_reply = Column(Boolean, default=True)
    stop_on_bounce = Column(Boolean, default=True)
    track_opens = Column(Boolean, default=True)
    track_clicks = Column(Boolean, default=True)
    total_recipients = Column(Integer(), nullable=False, default=0)
    total_sent = Column(Integer(), nullable=False, default=0)
    total_delivered = Column(Integer(), nullable=False, default=0)
    total_opened = Column(Integer(), nullable=False, default=0)
    total_clicked = Column(Integer(), nullable=False, default=0)
    total_replied = Column(Integer(), nullable=False, default=0)
    total_bounced = Column(Integer(), nullable=False, default=0)
    total_unsubscribed = Column(Integer(), nullable=False, default=0)
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
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
