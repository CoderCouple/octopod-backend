import uuid

from sqlalchemy import TIMESTAMP, Boolean, Column, String, Text, UniqueConstraint, func

from app.db.base import Base


def generate_prefixed_uuid() -> str:
    return f"prj_{uuid.uuid4()}"


class Project(Base):
    __tablename__ = "project"
    __table_args__ = (
        UniqueConstraint("org_id", "slug", name="uq_project_org_slug"),
    )

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    org_id = Column(String(), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False)
    description = Column(Text(), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_by = Column(String(), nullable=True)
    updated_by = Column(String(), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
