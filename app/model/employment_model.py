import uuid

from sqlalchemy import TIMESTAMP, Boolean, Column, ForeignKey, Index, String, func
from sqlalchemy.orm import relationship

from app.db.base import Base


def generate_prefixed_uuid():
    """Generate a UUID4 string prefixed with ``empl_``.

    Returns:
        A string in the form ``"empl_<uuid4>"``, used as the default
        primary key for the ``Employment`` model.
    """
    return f"empl_{uuid.uuid4()}"


class Employment(Base):
    """SQLAlchemy model for the ``employment`` table.

    Represents a specific employment position held by an employee
    within an organization, including title, department, and tenure.

    Table name:
        ``employment``

    Primary key:
        ``id`` -- prefixed UUID (``empl_<uuid4>``).

    Key columns:
        * ``employee_id`` -- FK to ``employee.id``.
        * ``org_id`` -- FK to ``organization.id``.
        * ``title`` -- job title.
        * ``department`` -- department name.
        * ``level`` -- seniority or grade level.
        * ``location`` -- work location.
        * ``valid_from`` / ``valid_to`` -- temporal validity window.
        * ``is_current`` -- whether this is the active employment.
        * ``is_deleted`` -- soft-delete flag.
        * ``created_by`` / ``updated_by`` -- actor audit fields.
        * ``created_at`` / ``updated_at`` -- timestamp audit fields.

    Indexes:
        * ``ix_employment_employee_org`` -- composite index on
          ``(employee_id, org_id)``.

    Relationships:
        * ``employee`` -- many-to-one to ``Employee``.
        * ``org`` -- many-to-one to ``Organization``.
        * ``career_events`` -- one-to-many to ``CareerEvent``.
    """

    __tablename__ = "employment"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    employee_id = Column(String(), ForeignKey("employee.id"), nullable=False)
    org_id = Column(String(), ForeignKey("organization.id"), nullable=False)
    title = Column(String(255), nullable=True)
    department = Column(String(255), nullable=True)
    level = Column(String(100), nullable=True)
    location = Column(String(255), nullable=True)
    valid_from = Column(TIMESTAMP(timezone=True), nullable=True)
    valid_to = Column(TIMESTAMP(timezone=True), nullable=True)
    is_current = Column(Boolean, default=True, nullable=False)

    is_deleted = Column(Boolean, default=False, nullable=False)
    created_by = Column(String(), nullable=True)
    updated_by = Column(String(), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)

    __table_args__ = (Index("ix_employment_employee_org", "employee_id", "org_id"),)

    employee = relationship("Employee", back_populates="employments", lazy="selectin")
    org = relationship("Organization", back_populates="employments", lazy="selectin")
    career_events = relationship("CareerEvent", back_populates="employment", lazy="selectin")
