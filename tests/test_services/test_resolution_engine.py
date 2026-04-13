from decimal import Decimal

from app.service.resolution_engine import (
    compute_confidence,
    determine_status,
    get_evidence_weight,
)


def test_evidence_weights():
    assert get_evidence_weight("self_claim") == Decimal("0.45")
    assert get_evidence_weight("manager_confirmation") == Decimal("0.40")
    assert get_evidence_weight("rejection") == Decimal("-0.80")
    assert get_evidence_weight("unknown") == Decimal("0.0")


def test_compute_confidence_self_claim_only():
    evidence = [{"evidence_type": "self_claim"}]
    result = compute_confidence(evidence)
    assert result == Decimal("0.45")


def test_compute_confidence_self_plus_manager():
    evidence = [
        {"evidence_type": "self_claim"},
        {"evidence_type": "manager_confirmation"},
    ]
    result = compute_confidence(evidence)
    assert result == Decimal("0.85")


def test_compute_confidence_clamped_at_zero():
    evidence = [{"evidence_type": "rejection"}]
    result = compute_confidence(evidence)
    assert result == Decimal("0.0")


def test_compute_confidence_clamped_at_one():
    evidence = [
        {"evidence_type": "system"},
        {"evidence_type": "manager_confirmation"},
    ]
    result = compute_confidence(evidence)
    assert result == Decimal("1.0")


def test_compute_confidence_with_explicit_weight():
    evidence = [{"evidence_type": "self_claim", "weight": Decimal("0.30")}]
    result = compute_confidence(evidence)
    assert result == Decimal("0.30")


def test_determine_status_confirmed():
    assert determine_status(Decimal("0.95")) == "confirmed"
    assert determine_status(Decimal("0.90")) == "confirmed"


def test_determine_status_probable():
    assert determine_status(Decimal("0.85")) == "probable"
    assert determine_status(Decimal("0.65")) == "probable"


def test_determine_status_weak():
    assert determine_status(Decimal("0.50")) == "weak"
    assert determine_status(Decimal("0.0")) == "weak"
