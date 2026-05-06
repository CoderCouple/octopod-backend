import uuid

from sqlalchemy import JSON, TIMESTAMP, Column, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


def generate_prefixed_uuid() -> str:
    return f"aip_{uuid.uuid4()}"


class AggregatedIndividualProfile(Base):
    __tablename__ = "aggregated_individual_profile"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    developer_profile_id = Column(String(), nullable=False, unique=True)

    # From developer_profile (GH+HF)
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

    # From social_profile (LN+X)
    headline = Column(Text(), nullable=True)
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

    # Merge metadata
    source_priority = Column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=dict
    )
    aggregated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
