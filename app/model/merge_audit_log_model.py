import uuid

from sqlalchemy import JSON, TIMESTAMP, Column, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


def generate_prefixed_uuid():
    return f"mal_{uuid.uuid4()}"


class MergeAuditLog(Base):
    __tablename__ = "merge_audit_log"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    developer_profile_id = Column(String(), nullable=False)
    merge_level = Column(String(30), nullable=False)
    target_table = Column(String(60), nullable=False)
    merge_run_id = Column(String(), nullable=False)
    field_name = Column(String(100), nullable=False)
    winning_source = Column(String(30), nullable=False)
    winning_value = Column(Text(), nullable=True)
    previous_value = Column(Text(), nullable=True)
    overridden_values = Column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    action = Column(String(20), nullable=False)
    merged_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
