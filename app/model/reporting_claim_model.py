import uuid
from decimal import Decimal

from sqlalchemy import TIMESTAMP, Boolean, Column, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import relationship

from app.common.enum.claim import ClaimState
from app.db.base import Base


def generate_prefixed_uuid():
    """Generate a UUID4 string prefixed with ``claim_``.

    Returns:
        A string in the form ``"claim_<uuid4>"``, used as the default
        primary key for the ``ReportingClaim`` model.
    """
    return f"claim_{uuid.uuid4()}"


class ReportingClaim(Base):
    """SQLAlchemy model for the ``reporting_claim`` table.

    Represents a user-submitted claim asserting that a specific
    employee-manager reporting relationship exists within an
    organization.  Claims progress through a state machine (see
    ``ClaimState``) and accumulate evidence before being resolved.

    Table name:
        ``reporting_claim``

    Primary key:
        ``id`` -- prefixed UUID (``claim_<uuid4>``).

    Key columns:
        * ``org_id`` -- FK to ``organization.id``.
        * ``employee_id`` -- FK to ``employee.id`` (the subordinate).
        * ``manager_id`` -- FK to ``employee.id`` (the manager).
        * ``claimant_id`` -- id of the actor who submitted the claim.
        * ``state`` -- current claim state (default ``ClaimState.DRAFT``).
        * ``confidence_score`` -- numeric score (0-1) computed during
          resolution.
        * ``submitted_at`` -- when the claim was submitted.
        * ``resolved_at`` -- when the claim reached a terminal state.
        * ``expires_at`` -- deadline for counterparty response.
        * ``superseded_by`` -- FK to a newer ``reporting_claim.id``
          that supersedes this claim.
        * ``is_deleted`` -- soft-delete flag.
        * ``created_by`` / ``updated_by`` -- actor audit fields.
        * ``created_at`` / ``updated_at`` -- timestamp audit fields.

    Indexes:
        * ``ix_claim_employee_manager`` -- composite on
          ``(employee_id, manager_id)``.
        * ``ix_claim_state`` -- on ``state``.
        * ``ix_claim_claimant`` -- on ``claimant_id``.

    Relationships:
        * ``org`` -- many-to-one to ``Organization``.
        * ``employee`` -- many-to-one to ``Employee`` (subordinate).
        * ``manager`` -- many-to-one to ``Employee`` (manager).
        * ``superseded_by_claim`` -- self-referential to the superseding
          ``ReportingClaim``.
        * ``evidence`` -- one-to-many to ``ClaimEvidence``.
    """

    __tablename__ = "reporting_claim"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    org_id = Column(String(), ForeignKey("organization.id"), nullable=False)
    employee_id = Column(String(), ForeignKey("employee.id"), nullable=False)
    manager_id = Column(String(), ForeignKey("employee.id"), nullable=False)
    claimant_id = Column(String(), nullable=False)
    state = Column(String(30), nullable=False, default=ClaimState.DRAFT.value)
    confidence_score = Column(Numeric(5, 4), nullable=True, default=Decimal("0.0"))
    submitted_at = Column(TIMESTAMP(timezone=True), nullable=True)
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)
    expires_at = Column(TIMESTAMP(timezone=True), nullable=True)
    superseded_by = Column(String(), ForeignKey("reporting_claim.id"), nullable=True)

    is_deleted = Column(Boolean, default=False, nullable=False)
    created_by = Column(String(), nullable=True)
    updated_by = Column(String(), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_claim_employee_manager", "employee_id", "manager_id"),
        Index("ix_claim_state", "state"),
        Index("ix_claim_claimant", "claimant_id"),
    )

    org = relationship("Organization", lazy="selectin")
    employee = relationship("Employee", foreign_keys=[employee_id], lazy="selectin")
    manager = relationship("Employee", foreign_keys=[manager_id], lazy="selectin")
    superseded_by_claim = relationship(
        "ReportingClaim", remote_side=[id], lazy="selectin"
    )
    evidence = relationship("ClaimEvidence", back_populates="claim", lazy="selectin")
