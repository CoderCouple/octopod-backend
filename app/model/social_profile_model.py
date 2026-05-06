import uuid

from sqlalchemy import JSON, TIMESTAMP, Column, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


def generate_prefixed_uuid() -> str:
    return f"sp_{uuid.uuid4()}"


class SocialProfile(Base):
    __tablename__ = "social_profile"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    developer_profile_id = Column(String(), nullable=False, unique=True)
    linkedin_url = Column(String(2048), nullable=True, unique=True)
    x_handle = Column(String(255), nullable=True, unique=True)

    display_name = Column(String(255), nullable=True)
    headline = Column(Text(), nullable=True)
    bio = Column(Text(), nullable=True)
    avatar_url = Column(String(2048), nullable=True)
    location = Column(String(500), nullable=True)
    current_title = Column(String(255), nullable=True)
    current_company = Column(String(255), nullable=True)
    industry = Column(String(255), nullable=True)
    years_of_experience = Column(Integer, nullable=True)
    job_history = Column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=list
    )
    education = Column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=list
    )
    certifications = Column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=list
    )
    connections = Column(Integer, nullable=True)
    skills = Column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=list
    )
    social_source_priority = Column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=dict
    )
    social_merged_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
