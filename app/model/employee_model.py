import uuid

from sqlalchemy import JSON, TIMESTAMP, Boolean, Column, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


def generate_prefixed_uuid():
    """Generate a UUID4 string prefixed with ``emp_``.

    Returns:
        A string in the form ``"emp_<uuid4>"``, used as the default
        primary key for the ``Employee`` model.
    """
    return f"emp_{uuid.uuid4()}"


class Employee(Base):
    """SQLAlchemy model for the ``employee`` table.

    Represents an individual person who may hold one or more employment
    positions across different organizations.

    Table name:
        ``employee``

    Primary key:
        ``id`` -- prefixed UUID (``emp_<uuid4>``).

    Key columns:
        * ``canonical_name`` -- the display name of the employee (indexed).
        * ``primary_email`` -- unique email address.
        * ``profile_data`` -- arbitrary JSON profile metadata.
        * ``is_deleted`` -- soft-delete flag.
        * ``created_by`` / ``updated_by`` -- actor audit fields.
        * ``created_at`` / ``updated_at`` -- timestamp audit fields.

    Relationships:
        * ``employments`` -- one-to-many to ``Employment``.
    """

    __tablename__ = "employee"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    canonical_name = Column(String(255), nullable=False, index=True)
    primary_email = Column(String(320), nullable=True, unique=True)
    profile_data = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=dict,
    )

    is_deleted = Column(Boolean, default=False, nullable=False)
    created_by = Column(String(), nullable=True)
    updated_by = Column(String(), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)

    employments = relationship("Employment", back_populates="employee", lazy="selectin")
