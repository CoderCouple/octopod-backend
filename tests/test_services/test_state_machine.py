import pytest

from app.common.enum.claim import ClaimState
from app.common.exceptions import InvalidStateTransitionError
from app.service.state_machine import get_allowed_actions, transition


def test_draft_to_submitted():
    assert transition(ClaimState.DRAFT, "submit") == ClaimState.SUBMITTED


def test_submitted_to_validation():
    assert transition(ClaimState.SUBMITTED, "validate") == ClaimState.VALIDATION


def test_validation_to_pending_counterparty():
    result = transition(ClaimState.VALIDATION, "request_counterparty")
    assert result == ClaimState.PENDING_COUNTERPARTY


def test_pending_counterparty_confirm():
    result = transition(ClaimState.PENDING_COUNTERPARTY, "confirm")
    assert result == ClaimState.VERIFIED


def test_pending_counterparty_reject():
    result = transition(ClaimState.PENDING_COUNTERPARTY, "reject")
    assert result == ClaimState.REJECTED


def test_pending_counterparty_expire():
    result = transition(ClaimState.PENDING_COUNTERPARTY, "expire")
    assert result == ClaimState.EXPIRED


def test_pending_counterparty_dispute():
    result = transition(ClaimState.PENDING_COUNTERPARTY, "dispute")
    assert result == ClaimState.DISPUTED


def test_disputed_to_moderation():
    result = transition(ClaimState.DISPUTED, "moderate")
    assert result == ClaimState.PENDING_MODERATION


def test_moderation_approve():
    result = transition(ClaimState.PENDING_MODERATION, "approve")
    assert result == ClaimState.VERIFIED


def test_supersede_from_any_state():
    for state in ClaimState:
        assert transition(state, "supersede") == ClaimState.SUPERSEDED


def test_invalid_transition():
    with pytest.raises(InvalidStateTransitionError):
        transition(ClaimState.VERIFIED, "submit")


def test_get_allowed_actions():
    actions = get_allowed_actions(ClaimState.PENDING_COUNTERPARTY)
    assert "confirm" in actions
    assert "reject" in actions
    assert "expire" in actions
    assert "dispute" in actions
    assert "supersede" in actions
