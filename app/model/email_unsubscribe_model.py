import uuid

from sqlalchemy import TIMESTAMP, Column, String, Text, func

from app.db.base import Base


def generate_prefixed_uuid():
    return f"unsub_{uuid.uuid4()}"


class EmailUnsubscribe(Base):
    __tablename__ = "email_unsubscribe"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    email = Column(String(320), nullable=False, unique=True)
    reason = Column(Text(), nullable=True)
    source = Column(String(100), nullable=True)
    message_id = Column(String(), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
