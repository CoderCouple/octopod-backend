import uuid
from decimal import Decimal

from sqlalchemy import TIMESTAMP, Boolean, Column, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import relationship

from app.common.enum.relationship import RelationshipStatus, RelationshipType
from app.db.base import Base


def generate_prefixed_uuid():
    """Generate a UUID4 string prefixed with ``rr_``.

    Returns:
        A string in the form ``"rr_<uuid4>"``, used as the default
        primary key for the ``ReportingRelationship`` model.
    """
    return f"rr_{uuid.uuid4()}"


class ReportingRelationship(Base):
    """SQLAlchemy model for the ``reporting_relationship`` table.

    Represents a manager-subordinate reporting line within an
    organization, along with its type, status, and confidence score.

    Table name:
        ``reporting_relationship``

    Primary key:
        ``id`` -- prefixed UUID (``rr_<uuid4>``).

    Key columns:
        * ``org_id`` -- FK to ``organization.id``.
        * ``employee_id`` -- FK to ``employee.id`` (the subordinate).
        * ``manager_employee_id`` -- FK to ``employee.id`` (the manager).
        * ``relationship_type`` -- one of ``RelationshipType`` values
          (solid_line, dotted_line, matrix).
        * ``status`` -- one of ``RelationshipStatus`` values
          (confirmed, probable, weak).
        * ``confidence_score`` -- numeric score (0-1) indicating how
          confident the system is in this relationship.
        * ``valid_from`` / ``valid_to`` -- temporal validity window.
        * ``is_current`` -- whether the relationship is currently active.
        * ``is_deleted`` -- soft-delete flag.
        * ``created_by`` / ``updated_by`` -- actor audit fields.
        * ``created_at`` / ``updated_at`` -- timestamp audit fields.

    Indexes:
        * ``ix_rr_org_employee`` -- composite on ``(org_id, employee_id)``.
        * ``ix_rr_manager`` -- on ``manager_employee_id``.

    Relationships:
        * ``org`` -- many-to-one to ``Organization``.
        * ``employee`` -- many-to-one to ``Employee`` (subordinate).
        * ``manager`` -- many-to-one to ``Employee`` (manager).
    """

    __tablename__ = "reporting_relationship"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    org_id = Column(String(), ForeignKey("organization.id"), nullable=False)
    employee_id = Column(String(), ForeignKey("employee.id"), nullable=False)
    manager_employee_id = Column(String(), ForeignKey("employee.id"), nullable=False)
    relationship_type = Column(
        String(20), nullable=False, default=RelationshipType.SOLID_LINE.value
    )
    status = Column(String(20), nullable=False, default=RelationshipStatus.WEAK.value)
    confidence_score = Column(Numeric(5, 4), nullable=False, default=Decimal("0.0"))
    valid_from = Column(TIMESTAMP(timezone=True), nullable=True)
    valid_to = Column(TIMESTAMP(timezone=True), nullable=True)
    is_current = Column(Boolean, default=True, nullable=False)

    is_deleted = Column(Boolean, default=False, nullable=False)
    created_by = Column(String(), nullable=True)
    updated_by = Column(String(), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_rr_org_employee", "org_id", "employee_id"),
        Index("ix_rr_manager", "manager_employee_id"),
    )

    org = relationship("Organization", back_populates="reporting_relationships", lazy="selectin")
    employee = relationship("Employee", foreign_keys=[employee_id], lazy="selectin")
    manager = relationship("Employee", foreign_keys=[manager_employee_id], lazy="selectin")
