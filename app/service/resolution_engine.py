"""Resolution engine for computing claim confidence scores.

Provides functions to look up evidence weights, aggregate evidence into a
composite confidence score, and map confidence scores to human-readable
status labels. The engine uses a weighted-sum model where different types
of evidence contribute different amounts to the overall confidence:

    - SELF_CLAIM:            +0.45  (the initial claim by the submitter)
    - MANAGER_CONFIRMATION:  +0.40  (counterparty confirms the relationship)
    - PEER_CONFIRMATION:     +0.10  (a peer vouches for the relationship)
    - SYSTEM:                +0.80  (automated system verification)
    - REJECTION:             -0.80  (counterparty or moderator rejects)

The final confidence score is clamped to the range [0.0, 1.0].
"""

from decimal import Decimal

from app.common.enum.claim import EvidenceType

_EVIDENCE_WEIGHTS: dict[str, Decimal] = {
    EvidenceType.SELF_CLAIM.value: Decimal("0.45"),
    EvidenceType.MANAGER_CONFIRMATION.value: Decimal("0.40"),
    EvidenceType.PEER_CONFIRMATION.value: Decimal("0.10"),
    EvidenceType.SYSTEM.value: Decimal("0.80"),
    EvidenceType.REJECTION.value: Decimal("-0.80"),
}


def get_evidence_weight(evidence_type: str) -> Decimal:
    """Look up the default weight for a given evidence type.

    Args:
        evidence_type: The evidence type string (e.g., "self_claim",
            "manager_confirmation", "rejection").

    Returns:
        The Decimal weight associated with the evidence type, or
        Decimal("0.0") if the type is not recognized.
    """
    return _EVIDENCE_WEIGHTS.get(evidence_type, Decimal("0.0"))


def compute_confidence(evidence_list: list[dict]) -> Decimal:
    """Compute an aggregate confidence score from a list of evidence entries.

    Sums the weights of all evidence entries. Each entry may provide an
    explicit "weight" value; if absent, the default weight for the entry's
    "evidence_type" is used. The final score is clamped to [0.0, 1.0].

    Args:
        evidence_list: A list of dictionaries, each containing at least an
            "evidence_type" key and optionally a "weight" key (as Decimal
            or string).

    Returns:
        A Decimal confidence score in the range [0.0, 1.0].
    """
    total = Decimal("0.0")
    for ev in evidence_list:
        weight = ev.get("weight") or get_evidence_weight(ev.get("evidence_type", ""))
        if isinstance(weight, str):
            weight = Decimal(weight)
        total += weight
    return max(Decimal("0.0"), min(Decimal("1.0"), total))


def determine_status(confidence: Decimal) -> str:
    """Map a confidence score to a human-readable status label.

    Thresholds:
        - >= 0.90: "confirmed"
        - >= 0.65: "probable"
        - < 0.65:  "weak"

    Args:
        confidence: A Decimal confidence score, typically in [0.0, 1.0].

    Returns:
        A status string: "confirmed", "probable", or "weak".
    """
    if confidence >= Decimal("0.90"):
        return "confirmed"
    elif confidence >= Decimal("0.65"):
        return "probable"
    return "weak"
