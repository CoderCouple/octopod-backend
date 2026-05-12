import uuid

from sqlalchemy import TIMESTAMP, Column, String, Text, func

from app.db.base import Base


def generate_prefixed_uuid() -> str:
    return f"be_{uuid.uuid4()}"


class BillingEvent(Base):
    __tablename__ = "billing_event"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    stripe_event_id = Column(String(255), nullable=False, unique=True, index=True)
    event_type = Column(String(100), nullable=False)
    org_id = Column(String(), nullable=True, index=True)
    payload = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
