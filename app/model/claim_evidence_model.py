import uuid

from sqlalchemy import TIMESTAMP, Column, ForeignKey, Numeric, String, func
from sqlalchemy.orm import relationship

from app.db.base import Base


def generate_prefixed_uuid():
    """Generate a UUID4 string prefixed with ``evi_``.

    Returns:
        A string in the form ``"evi_<uuid4>"``, used as the default
        primary key for the ``ClaimEvidence`` model.
    """
    return f"evi_{uuid.uuid4()}"


class ClaimEvidence(Base):
    """SQLAlchemy model for the ``claim_evidence`` table.

    Stores individual pieces of evidence attached to a reporting claim,
    such as self-claims, manager confirmations, peer confirmations, or
    system-generated evidence.

    Table name:
        ``claim_evidence``

    Primary key:
        ``id`` -- prefixed UUID (``evi_<uuid4>``).

    Key columns:
        * ``claim_id`` -- FK to ``reporting_claim.id``.
        * ``actor_id`` -- the user who provided the evidence.
        * ``evidence_type`` -- one of ``EvidenceType`` values (e.g.
          self_claim, manager_confirmation).
        * ``response`` -- the actor's response (confirm, reject,
          abstain), if applicable.
        * ``weight`` -- numeric weight assigned to this evidence piece
          during resolution scoring.
        * ``comment`` -- optional free-text comment.
        * ``created_at`` -- when the evidence was recorded.

    Relationships:
        * ``claim`` -- many-to-one to ``ReportingClaim``.
    """

    __tablename__ = "claim_evidence"

    id = Column(String(), primary_key=True, default=generate_prefixed_uuid, nullable=False)
    claim_id = Column(String(), ForeignKey("reporting_claim.id"), nullable=False)
    actor_id = Column(String(), nullable=False)
    evidence_type = Column(String(30), nullable=False)
    response = Column(String(20), nullable=True)
    weight = Column(Numeric(5, 4), nullable=True)
    comment = Column(String(1000), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now(), nullable=False)

    claim = relationship("ReportingClaim", back_populates="evidence", lazy="selectin")
