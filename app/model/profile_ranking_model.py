import uuid

from sqlalchemy import JSON, TIMESTAMP, Column, Numeric, String, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


def generate_prefixed_uuid():
    return f"pr_{uuid.uuid4()}"


class ProfileRanking(Base):
    __tablename__ = "profile_ranking"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    cohesive_profile_id = Column(String(), nullable=False, unique=True)

    github_activity_score = Column(Numeric(5, 4), nullable=True, default=0)
    technical_influence_score = Column(Numeric(5, 4), nullable=True, default=0)
    hiring_fit_score = Column(Numeric(5, 4), nullable=True, default=0)
    experience_score = Column(Numeric(5, 4), nullable=True, default=0)
    skills_breadth_score = Column(Numeric(5, 4), nullable=True, default=0)
    recency_score = Column(Numeric(5, 4), nullable=True, default=0)
    oss_contribution_score = Column(Numeric(5, 4), nullable=True, default=0)
    hf_impact_score = Column(Numeric(5, 4), nullable=True, default=0)
    composite_score = Column(Numeric(5, 4), nullable=True, default=0)

    weight_config = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=dict,
    )
    computed_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=True)
