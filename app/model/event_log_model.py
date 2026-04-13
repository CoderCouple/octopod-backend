import uuid

from sqlalchemy import JSON, TIMESTAMP, Column, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.base import Base


def generate_prefixed_uuid():
    """Generate a UUID4 string prefixed with ``evt_``.

    Returns:
        A string in the form ``"evt_<uuid4>"``, used as the default
        primary key for the ``EventLog`` model.
    """
    return f"evt_{uuid.uuid4()}"


class EventLog(Base):
    """SQLAlchemy model for the ``event_log`` table.

    Append-only, hash-chained audit log that records every state
    change in the system.  Each entry captures the before/after state
    of an entity, the acting user, and a SHA-256 hash linking it to
    the previous entry to form a tamper-evident chain.

    Table name:
        ``event_log``

    Primary key:
        ``id`` -- prefixed UUID (``evt_<uuid4>``).

    Key columns:
        * ``sequence_no`` -- monotonically increasing sequence number
          (indexed).
        * ``entity_type`` -- the type of entity that changed (e.g.
          ``"org"``, ``"employee"``).
        * ``entity_id`` -- the id of the entity that changed.
        * ``action`` -- the action performed (e.g. ``"create"``,
          ``"update"``).
        * ``before_state`` -- JSON snapshot of the entity before the
          change.
        * ``after_state`` -- JSON snapshot of the entity after the
          change.
        * ``actor_id`` -- the user who triggered the change (indexed).
        * ``timestamp`` -- when the event was recorded.
        * ``prev_hash`` -- the ``event_hash`` of the preceding log
          entry.
        * ``event_hash`` -- SHA-256 hash of this entry's payload for
          chain integrity.

    Indexes:
        * ``ix_event_log_entity`` -- composite on
          ``(entity_type, entity_id)``.
    """

    __tablename__ = "event_log"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    sequence_no = Column(Integer, nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(), nullable=False)
    action = Column(String(50), nullable=False)
    before_state = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    after_state = Column(JSON().with_variant(JSONB, "postgresql"), nullable=True)
    actor_id = Column(String(), nullable=True, index=True)
    timestamp = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    prev_hash = Column(Text, nullable=True)
    event_hash = Column(Text, nullable=False)

    __table_args__ = (
        Index("ix_event_log_entity", "entity_type", "entity_id"),
    )
