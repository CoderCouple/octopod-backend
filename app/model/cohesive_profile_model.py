import uuid

from sqlalchemy import JSON, TIMESTAMP, Column, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR

from app.db.base import Base


def generate_prefixed_uuid():
    return f"cp_{uuid.uuid4()}"


class CohesiveProfile(Base):
    __tablename__ = "cohesive_profile"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    developer_profile_id = Column(String(), nullable=False, unique=True)

    display_name = Column(String(255), nullable=True)
    bio = Column(Text(), nullable=True)
    headline = Column(Text(), nullable=True)
    location = Column(String(500), nullable=True)
    avatar_url = Column(String(2048), nullable=True)
    company = Column(String(255), nullable=True)
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
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=list,
    )
    skills = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=list,
    )
    topics = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=list,
    )

    years_of_experience = Column(Integer, nullable=True)
    current_title = Column(String(255), nullable=True)
    current_company = Column(String(255), nullable=True)
    job_history = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=list,
    )

    embedding_text = Column(Text(), nullable=True)
    search_tsv = Column(
        Text().with_variant(TSVECTOR, "postgresql"),
        nullable=True,
    )
    embedding_vector_id = Column(String(255), nullable=True)
    source_priority = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=dict,
    )
    merged_at = Column(TIMESTAMP(timezone=True), nullable=True)
