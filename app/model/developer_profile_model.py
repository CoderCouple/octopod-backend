import uuid

from sqlalchemy import JSON, TIMESTAMP, Boolean, Column, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


def generate_prefixed_uuid() -> str:
    return f"dp_{uuid.uuid4()}"


class DeveloperProfile(Base):
    __tablename__ = "developer_profile"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    github_username = Column(String(255), nullable=True, unique=True)
    huggingface_username = Column(String(255), nullable=True, unique=True)
    email_hint = Column(String(320), nullable=True)
    ingestion_status = Column(String(30), nullable=False, default="pending")
    last_ingested_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Merged GH+HF data (Layer 2: domain merge)
    display_name = Column(String(255), nullable=True)
    bio = Column(Text(), nullable=True)
    avatar_url = Column(String(2048), nullable=True)
    company = Column(String(255), nullable=True)
    location = Column(String(500), nullable=True)
    website = Column(String(2048), nullable=True)
    total_repos = Column(Integer, nullable=True, default=0)
    total_stars = Column(Integer, nullable=True, default=0)
    total_contributions = Column(Integer, nullable=True, default=0)
    total_followers = Column(Integer, nullable=True, default=0)
    total_hf_models = Column(Integer, nullable=True, default=0)
    total_hf_datasets = Column(Integer, nullable=True, default=0)
    total_hf_spaces = Column(Integer, nullable=True, default=0)
    total_hf_downloads = Column(Integer, nullable=True, default=0)
    total_papers = Column(Integer, nullable=True, default=0)
    languages = Column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=list
    )
    skills = Column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=list
    )
    topics = Column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=list
    )
    dev_source_priority = Column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=dict
    )
    dev_merged_at = Column(TIMESTAMP(timezone=True), nullable=True)

    # Audit
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_by = Column(String(), nullable=True)
    updated_by = Column(String(), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
