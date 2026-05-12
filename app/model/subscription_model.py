import uuid

from sqlalchemy import TIMESTAMP, Column, Integer, String, func

from app.db.base import Base


def generate_prefixed_uuid() -> str:
    return f"sub_{uuid.uuid4()}"


class Subscription(Base):
    __tablename__ = "subscription"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    org_id = Column(String(), nullable=False, unique=True, index=True)
    stripe_customer_id = Column(String(255), nullable=False, index=True)
    stripe_subscription_id = Column(String(255), nullable=True, unique=True, index=True)
    plan = Column(String(30), nullable=False, default="free")
    status = Column(String(30), nullable=False, default="active")
    seat_count = Column(Integer, nullable=False, default=1)
    current_period_start = Column(TIMESTAMP(timezone=True), nullable=True)
    current_period_end = Column(TIMESTAMP(timezone=True), nullable=True)
    cancel_at_period_end = Column(String(5), nullable=False, default="false")
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
