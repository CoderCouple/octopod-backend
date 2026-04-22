import uuid

from sqlalchemy import JSON, TIMESTAMP, Boolean, Column, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


def generate_prefixed_uuid():
    return f"cr_{uuid.uuid4()}"


class CampaignRecipient(Base):
    __tablename__ = "campaign_recipient"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    campaign_id = Column(String(), nullable=False, index=True)
    developer_profile_id = Column(String(), nullable=True)
    email = Column(String(320), nullable=False)
    first_name = Column(String(255), nullable=True)
    last_name = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    title = Column(String(255), nullable=True)
    status = Column(String(30), nullable=False, default="active")
    current_step_order = Column(Integer(), nullable=False, default=0)
    next_send_at = Column(TIMESTAMP(timezone=True), nullable=True)
    email_source = Column(String(30), nullable=True)
    merge_variables = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=dict,
    )
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
