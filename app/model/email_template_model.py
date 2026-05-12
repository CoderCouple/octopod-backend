import uuid

from sqlalchemy import JSON, TIMESTAMP, Boolean, Column, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


def generate_prefixed_uuid() -> str:
    return f"etpl_{uuid.uuid4()}"


class EmailTemplate(Base):
    __tablename__ = "email_template"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    owner_id = Column(String(), nullable=False, index=True)
    project_id = Column(String(), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=True)
    subject = Column(Text(), nullable=False)
    body_html = Column(Text(), nullable=False)
    body_text = Column(Text(), nullable=True)
    variables = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=list,
    )
    metadata_ = Column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=dict,
    )
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_by = Column(String(), nullable=True)
    updated_by = Column(String(), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
