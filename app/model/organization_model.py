import uuid

from sqlalchemy import JSON, TIMESTAMP, Boolean, Column, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


def generate_prefixed_uuid():
    """Generate a UUID4 string prefixed with ``org_``.

    Returns:
        A string in the form ``"org_<uuid4>"``, used as the default
        primary key for the ``Organization`` model.
    """
    return f"org_{uuid.uuid4()}"


class Organization(Base):
    """SQLAlchemy model for the ``organization`` table.

    Represents a company or organizational entity within the system.

    Table name:
        ``organization``

    Primary key:
        ``id`` -- prefixed UUID (``org_<uuid4>``).

    Key columns:
        * ``name`` -- display name of the organization (indexed).
        * ``domain`` -- unique domain identifier (e.g. ``"acme.com"``).
        * ``industry`` -- optional industry classification.
        * ``logo_url`` -- optional URL to the organization logo.
        * ``metadata_`` -- arbitrary JSON metadata (mapped from the
          ``metadata`` database column).
        * ``is_deleted`` -- soft-delete flag.
        * ``created_by`` / ``updated_by`` -- actor audit fields.
        * ``created_at`` / ``updated_at`` -- timestamp audit fields.

    Relationships:
        * ``employments`` -- one-to-many to ``Employment``.
        * ``reporting_relationships`` -- one-to-many to
          ``ReportingRelationship``.
    """

    __tablename__ = "organization"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    name = Column(String(255), nullable=False, index=True)
    domain = Column(String(255), nullable=True, unique=True)
    industry = Column(String(255), nullable=True)
    logo_url = Column(String(2048), nullable=True)
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

    employments = relationship("Employment", back_populates="org", lazy="selectin")
    reporting_relationships = relationship(
        "ReportingRelationship", back_populates="org", lazy="selectin"
    )
