import uuid

from sqlalchemy import TIMESTAMP, Boolean, Column, String, func

from app.db.base import Base


def generate_prefixed_uuid():
    return f"dp_{uuid.uuid4()}"


class DeveloperProfile(Base):
    __tablename__ = "developer_profile"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    employee_id = Column(String(), nullable=True, unique=True)
    github_username = Column(String(255), nullable=True, unique=True)
    linkedin_url = Column(String(2048), nullable=True, unique=True)
    huggingface_username = Column(String(255), nullable=True, unique=True)
    email_hint = Column(String(320), nullable=True)
    ingestion_status = Column(String(30), nullable=False, default="pending")
    last_ingested_at = Column(TIMESTAMP(timezone=True), nullable=True)

    is_deleted = Column(Boolean, default=False, nullable=False)
    created_by = Column(String(), nullable=True)
    updated_by = Column(String(), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
