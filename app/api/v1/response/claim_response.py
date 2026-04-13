from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ClaimEvidenceResponse(BaseModel):
    """Response schema for a single piece of claim evidence.

    Configured with ``from_attributes=True`` so it can be constructed
    directly from a ``ClaimEvidence`` SQLAlchemy model instance.

    Attributes:
        id: The prefixed UUID of the evidence record.
        claim_id: The prefixed UUID of the parent claim.
        actor_id: The actor who provided this evidence.
        evidence_type: The type of evidence (e.g. ``"self_claim"``,
            ``"manager_confirmation"``).
        response: The actor's response (confirm/reject/abstain), if
            applicable.
        weight: The numeric weight assigned to this evidence piece.
        comment: An optional free-text comment.
        created_at: When the evidence was recorded.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    claim_id: str
    actor_id: str
    evidence_type: str
    response: str | None = None
    weight: Decimal | None = None
    comment: str | None = None
    created_at: datetime


class ClaimResponse(BaseModel):
    """Response schema for a reporting claim (summary view).

    Configured with ``from_attributes=True`` so it can be constructed
    directly from a ``ReportingClaim`` SQLAlchemy model instance.

    Attributes:
        id: The prefixed UUID of the claim.
        org_id: The prefixed UUID of the organization.
        employee_id: The prefixed UUID of the subordinate employee.
        manager_id: The prefixed UUID of the manager employee.
        claimant_id: The actor who submitted the claim.
        state: The current claim state (e.g. ``"submitted"``,
            ``"verified"``).
        confidence_score: The computed confidence score, if available.
        submitted_at: When the claim was submitted.
        resolved_at: When the claim reached a terminal state.
        expires_at: The deadline for counterparty response.
        superseded_by: The id of the superseding claim, if any.
        is_deleted: Soft-delete flag.
        created_by: The actor who created the record.
        updated_by: The actor who last updated the record.
        created_at: When the record was created.
        updated_at: When the record was last updated.
    """

    model_config = ConfigDict(from_attributes=True)

    id: str
    org_id: str
    employee_id: str
    manager_id: str
    claimant_id: str
    state: str
    confidence_score: Decimal | None = None
    submitted_at: datetime | None = None
    resolved_at: datetime | None = None
    expires_at: datetime | None = None
    superseded_by: str | None = None
    is_deleted: bool
    created_by: str | None = None
    updated_by: str | None = None
    created_at: datetime
    updated_at: datetime


class ClaimDetailResponse(ClaimResponse):
    """Extended claim response that includes allowed state-machine actions.

    Inherits all fields from ``ClaimResponse`` and adds contextual
    information about what actions the current user can perform on the
    claim.

    Attributes:
        allowed_actions: A list of action names that are valid given
            the claim's current state (e.g. ``["confirm", "reject"]``).
    """

    allowed_actions: list[str] = []
