import uuid

from sqlalchemy import JSON, TIMESTAMP, Column, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


def generate_prefixed_uuid():
    return f"pp_{uuid.uuid4()}"


class PlatformProfile(Base):
    __tablename__ = "platform_profile"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    developer_profile_id = Column(String(), nullable=False)
    platform = Column(String(30), nullable=False)
    platform_username = Column(String(255), nullable=True)
    raw_data = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=dict,
    )
    extracted_data = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=dict,
    )
    fetch_status = Column(String(30), nullable=False, default="pending")
    error_message = Column(Text(), nullable=True)
    fetched_at = Column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("developer_profile_id", "platform", name="uq_pp_dev_platform"),
    )
