"""Finite state machine for reporting-claim lifecycle transitions.

Defines the valid state transitions for reporting claims and provides
functions to perform transitions and query allowed actions. The claim
lifecycle follows this general flow:

    DRAFT -> SUBMITTED -> VALIDATION -> PENDING_COUNTERPARTY
        -> VERIFIED (on confirm)
        -> REJECTED (on reject)
        -> EXPIRED  (on timeout)
        -> DISPUTED (on dispute) -> PENDING_MODERATION
            -> VERIFIED (on approve)
            -> REJECTED (on reject)

Any claim in a non-terminal state may also be SUPERSEDED by a newer claim.
"""

from app.common.enum.claim import ClaimState
from app.common.exceptions import InvalidStateTransitionError

_TRANSITIONS: dict[tuple[ClaimState, str], ClaimState] = {
    (ClaimState.DRAFT, "submit"): ClaimState.SUBMITTED,
    (ClaimState.SUBMITTED, "validate"): ClaimState.VALIDATION,
    (ClaimState.VALIDATION, "request_counterparty"): ClaimState.PENDING_COUNTERPARTY,
    (ClaimState.VALIDATION, "request_moderation"): ClaimState.PENDING_MODERATION,
    (ClaimState.PENDING_COUNTERPARTY, "confirm"): ClaimState.VERIFIED,
    (ClaimState.PENDING_COUNTERPARTY, "reject"): ClaimState.REJECTED,
    (ClaimState.PENDING_COUNTERPARTY, "expire"): ClaimState.EXPIRED,
    (ClaimState.PENDING_COUNTERPARTY, "dispute"): ClaimState.DISPUTED,
    (ClaimState.DISPUTED, "moderate"): ClaimState.PENDING_MODERATION,
    (ClaimState.PENDING_MODERATION, "approve"): ClaimState.VERIFIED,
    (ClaimState.PENDING_MODERATION, "reject"): ClaimState.REJECTED,
}

_SUPERSEDE_ACTION = "supersede"


def transition(current_state: ClaimState, action: str) -> ClaimState:
    """Perform a state transition on a claim.

    Looks up the (current_state, action) pair in the transition table and
    returns the resulting state. The special "supersede" action is always
    valid and transitions any state to SUPERSEDED.

    Args:
        current_state: The current ClaimState of the claim.
        action: The action to perform (e.g., "submit", "validate",
            "confirm", "reject", "expire", "dispute", "moderate",
            "approve", "supersede").

    Returns:
        The new ClaimState after the transition.

    Raises:
        InvalidStateTransitionError: If the (current_state, action) pair
            is not a valid transition.
    """
    if action == _SUPERSEDE_ACTION:
        return ClaimState.SUPERSEDED

    key = (current_state, action)
    new_state = _TRANSITIONS.get(key)
    if new_state is None:
        raise InvalidStateTransitionError(current_state.value, action)
    return new_state


def get_allowed_actions(state: ClaimState) -> list[str]:
    """Get the list of actions available from a given claim state.

    Looks up all transitions originating from the given state and returns
    the corresponding action names. The "supersede" action is always
    included as it is universally available.

    Args:
        state: The current ClaimState to query.

    Returns:
        A list of action name strings that are valid from the given state.
    """
    actions = [action for (s, action) in _TRANSITIONS if s == state]
    actions.append(_SUPERSEDE_ACTION)
    return actions
