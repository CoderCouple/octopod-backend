import uuid

from sqlalchemy import TIMESTAMP, Boolean, Column, Integer, String, Text, func

from app.db.base import Base


def generate_prefixed_uuid():
    return f"cst_{uuid.uuid4()}"


class CampaignStep(Base):
    __tablename__ = "campaign_step"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    campaign_id = Column(String(), nullable=False, index=True)
    template_id = Column(String(), nullable=True)
    step_order = Column(Integer(), nullable=False)
    step_type = Column(String(30), nullable=False, default="email")
    delay_days = Column(Integer(), nullable=False, default=0)
    delay_hours = Column(Integer(), nullable=False, default=0)
    subject_override = Column(Text(), nullable=True)
    body_override = Column(Text(), nullable=True)
    condition_field = Column(String(100), nullable=True)
    condition_op = Column(String(20), nullable=True)
    condition_value = Column(String(255), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_by = Column(String(), nullable=True)
    updated_by = Column(String(), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
