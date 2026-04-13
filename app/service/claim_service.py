"""Service layer for reporting claim lifecycle management.

Provides business logic for submitting, reviewing, confirming, rejecting,
and expiring reporting-relationship claims. Claims progress through a
state machine and accumulate evidence that feeds into a confidence-scoring
resolution engine. Verified claims are promoted to canonical reporting
relationships.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.request.claim_request import ConfirmClaimRequest, SubmitClaimRequest
from app.api.v1.response.claim_response import ClaimDetailResponse, ClaimResponse
from app.common.enum.claim import ClaimState, EvidenceResponse, EvidenceType
from app.common.enum.system import EntityType
from app.common.exceptions import (
    DuplicateEntityError,
    EntityNotFoundError,
    InvalidStateTransitionError,
)
from app.db.repository.claim_evidence_repository import ClaimEvidenceRepository
from app.db.repository.claim_repository import ClaimRepository
from app.db.repository.employee_repository import EmployeeRepository
from app.db.repository.org_repository import OrgRepository
from app.db.repository.reporting_relationship_repository import (
    ReportingRelationshipRepository,
)
from app.model.claim_evidence_model import ClaimEvidence
from app.model.reporting_claim_model import ReportingClaim
from app.model.reporting_relationship_model import ReportingRelationship
from app.service.contributor_service import ContributorService
from app.service.event_log_service import EventLogService
from app.service.graph_service import GraphService
from app.service.resolution_engine import compute_confidence, determine_status
from app.service.state_machine import get_allowed_actions, transition

# Number of days after which an unresolved claim automatically expires.
CLAIM_EXPIRY_DAYS = 14


class ClaimService:
    """Service for managing reporting-relationship claims.

    Orchestrates the full claim lifecycle: submission with duplicate detection,
    state-machine transitions, evidence collection, confidence scoring via
    the resolution engine, counterparty confirmation or rejection, automatic
    expiry of stale claims, and promotion of verified claims to canonical
    reporting relationships. All state changes are logged to the event log
    and contributor scores are updated accordingly.
    """

    def __init__(self, db: AsyncSession):
        """Initialize ClaimService with a database session.

        Args:
            db: An async SQLAlchemy session used for all database operations.
        """
        self.db = db
        self.repo = ClaimRepository(db)
        self.evidence_repo = ClaimEvidenceRepository(db)
        self.employee_repo = EmployeeRepository(db)
        self.org_repo = OrgRepository(db)
        self.rr_repo = ReportingRelationshipRepository(db)
        self.event_log = EventLogService(db)
        self.contributor = ContributorService(db)
        self.graph = GraphService(db)

    async def submit_claim(
        self, data: SubmitClaimRequest, actor_id: str | None = None
    ) -> ClaimResponse:
        """Submit a new reporting-relationship claim.

        Validates that the referenced organization, employee, and manager all
        exist and that no active claim already exists for the same triple.
        Creates the claim in DRAFT state, attaches initial self-claim
        evidence, and auto-transitions through SUBMITTED -> VALIDATION ->
        PENDING_COUNTERPARTY. Also increments the submitter's contributor
        score.

        Args:
            data: The request payload containing org_id, employee_id, and
                manager_id identifying the claimed reporting relationship.
            actor_id: Optional identifier of the user submitting the claim,
                used for audit tracking and contributor scoring.

        Returns:
            A ClaimResponse representing the newly submitted claim.

        Raises:
            EntityNotFoundError: If the referenced organization, employee, or
                manager does not exist.
            DuplicateEntityError: If an active claim already exists for the
                same employee-manager-org combination.
        """
        if not await self.org_repo.get_by_id(data.org_id):
            raise EntityNotFoundError("Organization", data.org_id)
        if not await self.employee_repo.get_by_id(data.employee_id):
            raise EntityNotFoundError("Employee", data.employee_id)
        if not await self.employee_repo.get_by_id(data.manager_id):
            raise EntityNotFoundError("Employee (manager)", data.manager_id)

        existing = await self.repo.find_active_claim(
            data.employee_id, data.manager_id, data.org_id
        )
        if existing:
            raise DuplicateEntityError(
                "ReportingClaim",
                "employee_id+manager_id+org_id",
                f"{data.employee_id}+{data.manager_id}+{data.org_id}",
            )

        now = datetime.now(timezone.utc)
        claimant = actor_id or "anonymous"

        claim = ReportingClaim(
            org_id=data.org_id,
            employee_id=data.employee_id,
            manager_id=data.manager_id,
            claimant_id=claimant,
            state=ClaimState.DRAFT.value,
            confidence_score=Decimal("0.0"),
            submitted_at=now,
            expires_at=now + timedelta(days=CLAIM_EXPIRY_DAYS),
            created_by=actor_id,
            updated_by=actor_id,
        )
        claim = await self.repo.create(claim)

        evidence = ClaimEvidence(
            claim_id=claim.id,
            actor_id=claimant,
            evidence_type=EvidenceType.SELF_CLAIM.value,
            response=EvidenceResponse.CONFIRM.value,
            weight=Decimal("0.45"),
        )
        await self.evidence_repo.create(evidence)

        # Auto-transition: DRAFT -> SUBMITTED -> VALIDATION -> PENDING_COUNTERPARTY
        claim.state = transition(ClaimState(claim.state), "submit").value
        claim.state = transition(ClaimState(claim.state), "validate").value
        claim.state = transition(ClaimState(claim.state), "request_counterparty").value
        claim.confidence_score = Decimal("0.45")
        await self.repo.update(claim)

        await self.event_log.append_event(
            entity_type=EntityType.REPORTING_CLAIM,
            entity_id=claim.id,
            action="submit",
            actor_id=actor_id,
            after_state={
                "employee_id": claim.employee_id,
                "manager_id": claim.manager_id,
                "org_id": claim.org_id,
                "state": claim.state,
            },
        )

        # Contributor scoring
        if actor_id:
            await self.contributor.increment_claims_submitted(actor_id)

        return ClaimResponse.model_validate(claim)

    async def get_claim(self, claim_id: str) -> ClaimDetailResponse:
        """Retrieve a single claim with its allowed actions.

        Fetches the claim by ID and enriches the response with the list of
        actions permitted by the state machine in the claim's current state.

        Args:
            claim_id: The UUID string of the claim to retrieve.

        Returns:
            A ClaimDetailResponse containing the claim data and a list of
            allowed state-machine actions.

        Raises:
            EntityNotFoundError: If no claim exists with the given ID.
        """
        claim = await self.repo.get_by_id(claim_id)
        if not claim:
            raise EntityNotFoundError("ReportingClaim", claim_id)
        detail = ClaimDetailResponse.model_validate(claim)
        detail.allowed_actions = get_allowed_actions(ClaimState(claim.state))
        return detail

    async def list_claims(
        self,
        org_id: str | None = None,
        employee_id: str | None = None,
        claimant_id: str | None = None,
        state: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ClaimResponse], int]:
        """List claims with optional filtering and pagination.

        Args:
            org_id: Optional organization ID to filter claims by.
            employee_id: Optional employee ID to filter claims by.
            claimant_id: Optional claimant ID to filter claims by.
            state: Optional claim state string to filter by (e.g.,
                "pending_counterparty", "verified").
            offset: The number of records to skip. Defaults to 0.
            limit: The maximum number of records to return. Defaults to 20.

        Returns:
            A tuple of (list of ClaimResponse objects, total count of
            matching claims).
        """
        claims, total = await self.repo.list_filtered(
            org_id=org_id,
            employee_id=employee_id,
            claimant_id=claimant_id,
            state=state,
            offset=offset,
            limit=limit,
        )
        return [ClaimResponse.model_validate(c) for c in claims], total

    async def get_pending_confirmations(
        self, actor_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[ClaimResponse], int]:
        """List claims awaiting confirmation from a specific counterparty.

        Returns claims in the PENDING_COUNTERPARTY state where the given
        actor is the manager (counterparty) who needs to confirm or reject.

        Args:
            actor_id: The identifier of the counterparty whose pending
                confirmations to retrieve.
            offset: The number of records to skip. Defaults to 0.
            limit: The maximum number of records to return. Defaults to 20.

        Returns:
            A tuple of (list of ClaimResponse objects, total count of
            pending confirmations for this actor).
        """
        claims, total = await self.repo.list_pending_for_counterparty(
            actor_id, offset, limit
        )
        return [ClaimResponse.model_validate(c) for c in claims], total

    async def confirm_claim(
        self, claim_id: str, data: ConfirmClaimRequest, actor_id: str | None = None
    ) -> ClaimResponse:
        """Process a counterparty confirmation or rejection of a claim.

        Handles both confirm and reject responses. For confirmations, adds
        manager-confirmation evidence, computes the new confidence score,
        transitions the claim to VERIFIED, promotes it to a canonical
        reporting relationship, and updates contributor scores. For rejections,
        adds rejection evidence, recomputes confidence, and transitions the
        claim to REJECTED.

        Args:
            claim_id: The UUID string of the claim to confirm or reject.
            data: The request payload containing the response type ("confirm"
                or "reject") and an optional comment.
            actor_id: Optional identifier of the user performing the
                confirmation, used for audit tracking and contributor scoring.

        Returns:
            A ClaimResponse representing the updated claim after the
            confirmation or rejection.

        Raises:
            EntityNotFoundError: If no claim exists with the given ID.
            InvalidStateTransitionError: If the claim is not in the
                PENDING_COUNTERPARTY state or the response type is invalid.
        """
        claim = await self.repo.get_by_id(claim_id)
        if not claim:
            raise EntityNotFoundError("ReportingClaim", claim_id)

        current_state = ClaimState(claim.state)
        if current_state != ClaimState.PENDING_COUNTERPARTY:
            raise InvalidStateTransitionError(claim.state, data.response)

        now = datetime.now(timezone.utc)

        if data.response == EvidenceResponse.CONFIRM.value:
            evidence = ClaimEvidence(
                claim_id=claim.id,
                actor_id=actor_id or "anonymous",
                evidence_type=EvidenceType.MANAGER_CONFIRMATION.value,
                response=EvidenceResponse.CONFIRM.value,
                weight=Decimal("0.40"),
                comment=data.comment,
            )
            await self.evidence_repo.create(evidence)

            # Compute confidence using resolution engine
            all_evidence = await self.evidence_repo.list_by_claim(claim.id)
            evidence_dicts = [
                {"evidence_type": e.evidence_type, "weight": e.weight}
                for e in all_evidence
            ]
            confidence = compute_confidence(evidence_dicts)

            claim.state = transition(current_state, "confirm").value
            claim.confidence_score = confidence
            claim.resolved_at = now
            claim.updated_by = actor_id
            claim.updated_at = now
            await self.repo.update(claim)

            await self._promote_to_canonical(claim, actor_id)

            # Contributor scoring
            if actor_id:
                await self.contributor.increment_confirmations(actor_id)
            if claim.claimant_id and claim.claimant_id != "anonymous":
                await self.contributor.increment_claims_verified(claim.claimant_id)

        elif data.response == EvidenceResponse.REJECT.value:
            evidence = ClaimEvidence(
                claim_id=claim.id,
                actor_id=actor_id or "anonymous",
                evidence_type=EvidenceType.REJECTION.value,
                response=EvidenceResponse.REJECT.value,
                weight=Decimal("-0.80"),
                comment=data.comment,
            )
            await self.evidence_repo.create(evidence)

            all_evidence = await self.evidence_repo.list_by_claim(claim.id)
            evidence_dicts = [
                {"evidence_type": e.evidence_type, "weight": e.weight}
                for e in all_evidence
            ]
            confidence = compute_confidence(evidence_dicts)

            claim.state = transition(current_state, "reject").value
            claim.confidence_score = confidence
            claim.resolved_at = now
            claim.updated_by = actor_id
            claim.updated_at = now
            await self.repo.update(claim)

            # Contributor scoring
            if actor_id:
                await self.contributor.increment_rejections(actor_id)
        else:
            raise InvalidStateTransitionError(claim.state, data.response)

        await self.event_log.append_event(
            entity_type=EntityType.REPORTING_CLAIM,
            entity_id=claim.id,
            action=data.response,
            actor_id=actor_id,
            after_state={"state": claim.state, "confidence_score": str(claim.confidence_score)},
        )
        return ClaimResponse.model_validate(claim)

    async def expire_stale_claims(self) -> int:
        """Expire all claims that have passed their expiry deadline.

        Finds all claims whose expires_at timestamp is in the past and
        transitions them to the EXPIRED state via the state machine.

        Returns:
            The number of claims that were expired.
        """
        now = datetime.now(timezone.utc)
        claims = await self.repo.list_expired_claims(now)
        count = 0
        for claim in claims:
            claim.state = transition(ClaimState(claim.state), "expire").value
            claim.resolved_at = now
            claim.updated_at = now
            await self.repo.update(claim)
            count += 1
        return count

    async def _promote_to_canonical(
        self, claim: ReportingClaim, actor_id: str | None
    ) -> None:
        """Promote a verified claim to a canonical reporting relationship.

        Determines the relationship status from the claim's confidence score,
        checks for cycles in the org graph, and either updates an existing
        relationship or creates a new one. If the employee already has a
        confirmed solid-line manager, the new relationship is created as
        dotted-line instead.

        Args:
            claim: The verified ReportingClaim to promote.
            actor_id: Optional identifier of the user who triggered the
                promotion, used for audit tracking.

        Returns:
            None. The reporting relationship is created or updated as a
            side effect.
        """
        now = datetime.now(timezone.utc)
        status = determine_status(claim.confidence_score)

        # Cycle detection
        would_cycle = await self.graph.would_create_cycle(
            claim.org_id, claim.employee_id, claim.manager_id
        )
        if would_cycle:
            # Don't promote if it would create a cycle
            return

        # Check for existing active relationship
        existing_rrs, _ = await self.rr_repo.list_filtered(
            org_id=claim.org_id,
            employee_id=claim.employee_id,
            is_current=True,
        )
        for rr in existing_rrs:
            if rr.manager_employee_id == claim.manager_id:
                rr.confidence_score = claim.confidence_score
                rr.status = status
                rr.updated_by = actor_id
                rr.updated_at = now
                await self.rr_repo.update(rr)
                return

        # Validate single solid-line manager
        conflict = await self.graph.validate_single_solid_manager(
            claim.employee_id, claim.org_id, claim.manager_id
        )
        relationship_type = "dotted_line" if conflict else "solid_line"

        rr = ReportingRelationship(
            org_id=claim.org_id,
            employee_id=claim.employee_id,
            manager_employee_id=claim.manager_id,
            relationship_type=relationship_type,
            status=status,
            confidence_score=claim.confidence_score,
            valid_from=now,
            is_current=True,
            created_by=actor_id,
            updated_by=actor_id,
        )
        await self.rr_repo.create(rr)

        await self.event_log.append_event(
            entity_type=EntityType.REPORTING_RELATIONSHIP,
            entity_id=rr.id,
            action="create_from_claim",
            actor_id=actor_id,
            after_state={
                "employee_id": rr.employee_id,
                "manager_employee_id": rr.manager_employee_id,
                "org_id": rr.org_id,
                "claim_id": claim.id,
                "relationship_type": relationship_type,
                "status": status,
            },
        )
