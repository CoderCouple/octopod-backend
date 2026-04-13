from pydantic import BaseModel


class SubmitClaimRequest(BaseModel):
    """Request schema for submitting a new reporting relationship claim.

    Attributes:
        org_id: The prefixed UUID of the organization the relationship
            belongs to (required).
        employee_id: The prefixed UUID of the subordinate employee
            (required).
        manager_id: The prefixed UUID of the manager employee
            (required).
    """

    org_id: str
    employee_id: str
    manager_id: str


class ConfirmClaimRequest(BaseModel):
    """Request schema for a counterparty to confirm or reject a claim.

    Attributes:
        response: The counterparty's response -- expected values are
            ``"confirm"`` or ``"reject"``.
        comment: An optional free-text comment explaining the response.
    """

    response: str  # "confirm" or "reject"
    comment: str | None = None
