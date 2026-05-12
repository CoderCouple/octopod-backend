import uuid

from sqlalchemy import TIMESTAMP, Boolean, Column, String, func

from app.db.base import Base


def generate_prefixed_uuid() -> str:
    return f"org_{uuid.uuid4()}"


class Organization(Base):
    __tablename__ = "organization"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), nullable=False, unique=True, index=True)
    plan = Column(String(30), nullable=False, default="free")
    logo_url = Column(String(2048), nullable=True)
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_by = Column(String(), nullable=True)
    updated_by = Column(String(), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
