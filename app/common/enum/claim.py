from enum import Enum


class ClaimState(str, Enum):
    """State machine states for a reporting relationship claim.

    Values:
        DRAFT: The claim has been created but not yet submitted.
        SUBMITTED: The claim has been submitted for processing.
        VALIDATION: The claim is undergoing automated validation.
        PENDING_COUNTERPARTY: Awaiting confirmation or rejection from
            the counterparty (employee or manager).
        PENDING_MODERATION: The claim requires manual moderation.
        VERIFIED: The claim has been verified and accepted.
        REJECTED: The claim has been rejected.
        EXPIRED: The claim expired before the counterparty responded.
        DISPUTED: The claim is under dispute.
        SUPERSEDED: The claim has been replaced by a newer claim.
    """

    DRAFT = "draft"
    SUBMITTED = "submitted"
    VALIDATION = "validation"
    PENDING_COUNTERPARTY = "pending_counterparty"
    PENDING_MODERATION = "pending_moderation"
    VERIFIED = "verified"
    REJECTED = "rejected"
    EXPIRED = "expired"
    DISPUTED = "disputed"
    SUPERSEDED = "superseded"


class EvidenceType(str, Enum):
    """Type of evidence attached to a reporting claim.

    Values:
        SELF_CLAIM: Evidence provided by the claimant themselves.
        MANAGER_CONFIRMATION: Confirmation from the named manager.
        PEER_CONFIRMATION: Confirmation from a peer or colleague.
        SYSTEM: Automatically generated system evidence.
        REJECTION: Evidence representing a rejection response.
    """

    SELF_CLAIM = "self_claim"
    MANAGER_CONFIRMATION = "manager_confirmation"
    PEER_CONFIRMATION = "peer_confirmation"
    SYSTEM = "system"
    REJECTION = "rejection"


class EvidenceResponse(str, Enum):
    """Possible responses an actor can give when providing evidence.

    Values:
        CONFIRM: The actor confirms the claimed relationship.
        REJECT: The actor rejects the claimed relationship.
        ABSTAIN: The actor declines to provide an opinion.
    """

    CONFIRM = "confirm"
    REJECT = "reject"
    ABSTAIN = "abstain"
