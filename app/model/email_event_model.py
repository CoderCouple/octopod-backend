import uuid

from sqlalchemy import JSON, TIMESTAMP, Column, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


def generate_prefixed_uuid():
    return f"ee_{uuid.uuid4()}"


class EmailEvent(Base):
    __tablename__ = "email_event"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    message_id = Column(String(), nullable=False, index=True)
    event_type = Column(String(30), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text(), nullable=True)
    link_url = Column(Text(), nullable=True)
    raw_payload = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=dict,
    )
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
