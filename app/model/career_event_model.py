import uuid

from sqlalchemy import JSON, TIMESTAMP, Column, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


def generate_prefixed_uuid():
    """Generate a UUID4 string prefixed with ``ce_``.

    Returns:
        A string in the form ``"ce_<uuid4>"``, used as the default
        primary key for the ``CareerEvent`` model.
    """
    return f"ce_{uuid.uuid4()}"


class CareerEvent(Base):
    """SQLAlchemy model for the ``career_event`` table.

    Records a discrete career milestone for an employee, such as
    joining, leaving, promotion, or transfer.

    Table name:
        ``career_event``

    Primary key:
        ``id`` -- prefixed UUID (``ce_<uuid4>``).

    Key columns:
        * ``employee_id`` -- FK to ``employee.id`` (indexed).
        * ``org_id`` -- FK to ``organization.id`` (optional).
        * ``employment_id`` -- FK to ``employment.id`` (optional).
        * ``event_type`` -- one of ``CareerEventType`` values (e.g.
          join, leave, promotion).
        * ``effective_at`` -- when the event took effect.
        * ``recorded_at`` -- when the event was recorded in the system.
        * ``payload`` -- arbitrary JSON data associated with the event.

    Relationships:
        * ``employee`` -- many-to-one to ``Employee``.
        * ``org`` -- many-to-one to ``Organization``.
        * ``employment`` -- many-to-one to ``Employment``.
    """

    __tablename__ = "career_event"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    employee_id = Column(String(), ForeignKey("employee.id"), nullable=False, index=True)
    org_id = Column(String(), ForeignKey("organization.id"), nullable=True)
    employment_id = Column(String(), ForeignKey("employment.id"), nullable=True)
    event_type = Column(String(30), nullable=False)
    effective_at = Column(TIMESTAMP(timezone=True), nullable=False)
    recorded_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    payload = Column(
        JSON().with_variant(JSONB, "postgresql"),
        nullable=True,
        default=dict,
    )

    employee = relationship("Employee", lazy="selectin")
    org = relationship("Organization", lazy="selectin")
    employment = relationship("Employment", back_populates="career_events", lazy="selectin")
