"""Claim API controller.

Exposes endpoints for the claim lifecycle: submitting new claims, listing
and filtering claims, retrieving claim details, viewing pending
confirmations, and confirming or rejecting claims.  Claims represent
assertions about reporting relationships that require verification.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tags import Tags
from app.api.v1.request.claim_request import ConfirmClaimRequest, SubmitClaimRequest
from app.api.v1.response.base_response import BaseResponse, success_response
from app.api.v1.response.claim_response import ClaimDetailResponse, ClaimResponse
from app.common.auth.auth import get_actor_id
from app.common.pagination import PaginatedResponse
from app.db.session import get_db
from app.service.claim_service import ClaimService

router = APIRouter(tags=[Tags.Claim])


def get_claim_service(db: AsyncSession = Depends(get_db)) -> ClaimService:
    """Construct a ``ClaimService`` instance with a database session.

    Used as a FastAPI dependency to inject the service into route handlers.

    Args:
        db: Async SQLAlchemy session provided by ``get_db``.

    Returns:
        ClaimService: A new service instance bound to the given session.
    """
    return ClaimService(db)


@router.post("/claim", response_model=BaseResponse[ClaimResponse], status_code=201)
async def submit_claim(
    body: SubmitClaimRequest,
    actor_id: str | None = Depends(get_actor_id),
    service: ClaimService = Depends(get_claim_service),
):
    """Submit a new reporting-relationship claim.

    A claim asserts that a particular reporting relationship exists and
    enters a pending state until it is confirmed or rejected by the
    relevant party.

    HTTP Method:
        POST /api/v1/claim

    Args:
        body: Request payload containing claim details (e.g. employee_id,
            manager_employee_id, org_id, relationship type).
        actor_id: Authenticated user ID extracted from the request.
            Used for audit attribution and identifying the claimant.
        service: Injected ``ClaimService`` instance.

    Returns:
        BaseResponse[ClaimResponse]: The newly submitted claim wrapped in
        a standard response envelope.

    Side Effects:
        Logs a claim-submitted event to the event log.

    Status Codes:
        201 Created: Claim successfully submitted.
        422 Unprocessable Entity: Validation error in request body.
    """
    claim = await service.submit_claim(body, actor_id)
    return success_response(claim, "Claim submitted", 201)


@router.get("/claim", response_model=BaseResponse[PaginatedResponse[ClaimResponse]])
async def list_claims(
    org_id: str | None = Query(default=None),
    employee_id: str | None = Query(default=None),
    claimant_id: str | None = Query(default=None),
    state: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    service: ClaimService = Depends(get_claim_service),
):
    """List claims with optional filters and pagination.

    Supports filtering by organization, employee, claimant, and claim
    state.  All filter parameters are optional; when omitted the full
    (paginated) set of claims is returned.

    HTTP Method:
        GET /api/v1/claim

    Args:
        org_id: Filter by organization ID (optional).
        employee_id: Filter by the subject employee ID (optional).
        claimant_id: Filter by the user who submitted the claim (optional).
        state: Filter by claim state, e.g. ``"pending"``, ``"confirmed"``,
            ``"rejected"`` (optional).
        offset: Zero-based index of the first record to return.
        limit: Maximum number of records to return (1--100, default 20).
        service: Injected ``ClaimService`` instance.

    Returns:
        BaseResponse[PaginatedResponse[ClaimResponse]]: A paginated list
        of claims including ``items``, ``total``, ``offset``, and ``limit``
        fields.

    Status Codes:
        200 OK: Claims fetched successfully.
    """
    claims, total = await service.list_claims(
        org_id=org_id,
        employee_id=employee_id,
        claimant_id=claimant_id,
        state=state,
        offset=offset,
        limit=limit,
    )
    page = PaginatedResponse(items=claims, total=total, offset=offset, limit=limit)
    return success_response(page, "Claims fetched")


@router.get(
    "/claim/pending",
    response_model=BaseResponse[PaginatedResponse[ClaimResponse]],
)
async def get_pending_confirmations(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    actor_id: str | None = Depends(get_actor_id),
    service: ClaimService = Depends(get_claim_service),
):
    """List claims awaiting confirmation by the current actor.

    Returns only those claims in a pending state where the authenticated
    user is the expected confirmer.  Falls back to ``"anonymous"`` when no
    actor ID is available.

    HTTP Method:
        GET /api/v1/claim/pending

    Args:
        offset: Zero-based index of the first record to return.
        limit: Maximum number of records to return (1--100, default 20).
        actor_id: Authenticated user ID extracted from the request.
            Determines which pending claims to surface.
        service: Injected ``ClaimService`` instance.

    Returns:
        BaseResponse[PaginatedResponse[ClaimResponse]]: A paginated list
        of pending claims requiring the actor's confirmation.

    Status Codes:
        200 OK: Pending confirmations fetched successfully.
    """
    claims, total = await service.get_pending_confirmations(
        actor_id or "anonymous", offset, limit
    )
    page = PaginatedResponse(items=claims, total=total, offset=offset, limit=limit)
    return success_response(page, "Pending confirmations fetched")


@router.get("/claim/{claim_id}", response_model=BaseResponse[ClaimDetailResponse])
async def get_claim(
    claim_id: str,
    service: ClaimService = Depends(get_claim_service),
):
    """Retrieve detailed information for a single claim.

    Returns a richer response model (``ClaimDetailResponse``) that
    includes confirmation history and related entity details.

    HTTP Method:
        GET /api/v1/claim/{claim_id}

    Args:
        claim_id: Unique identifier of the claim.
        service: Injected ``ClaimService`` instance.

    Returns:
        BaseResponse[ClaimDetailResponse]: The requested claim with full
        details, wrapped in a standard response envelope.

    Status Codes:
        200 OK: Claim fetched successfully.
        404 Not Found: No claim exists with the given ID.
    """
    claim = await service.get_claim(claim_id)
    return success_response(claim, "Claim fetched")


@router.post(
    "/claim/{claim_id}/confirm",
    response_model=BaseResponse[ClaimResponse],
)
async def confirm_claim(
    claim_id: str,
    body: ConfirmClaimRequest,
    actor_id: str | None = Depends(get_actor_id),
    service: ClaimService = Depends(get_claim_service),
):
    """Confirm or reject a pending claim.

    Advances the claim through its lifecycle by recording a confirmation
    decision (approve or reject) from the authenticated actor.

    HTTP Method:
        POST /api/v1/claim/{claim_id}/confirm

    Args:
        claim_id: Unique identifier of the claim to confirm.
        body: Request payload containing the confirmation decision
            (e.g. approved/rejected and optional notes).
        actor_id: Authenticated user ID extracted from the request.
            Used for audit attribution.
        service: Injected ``ClaimService`` instance.

    Returns:
        BaseResponse[ClaimResponse]: The updated claim wrapped in a
        standard response envelope.

    Side Effects:
        Logs a claim-confirmed event to the event log.  If approved, may
        create or update reporting relationships.

    Status Codes:
        200 OK: Claim confirmation recorded successfully.
        404 Not Found: No claim exists with the given ID.
        422 Unprocessable Entity: Validation error in request body.
    """
    claim = await service.confirm_claim(claim_id, body, actor_id)
    return success_response(claim, "Claim updated")
