import uuid

from sqlalchemy import TIMESTAMP, Column, String, func

from app.db.base import Base


def generate_prefixed_uuid() -> str:
    return f"usr_{uuid.uuid4()}"


class User(Base):
    __tablename__ = "user"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    cognito_sub = Column(String(), nullable=False, unique=True, index=True)
    email = Column(String(320), nullable=True, index=True)
    display_name = Column(String(255), nullable=True)
    avatar_url = Column(String(2048), nullable=True)
    default_org_id = Column(String(), nullable=True)
    default_project_id = Column(String(), nullable=True)
    last_login_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
