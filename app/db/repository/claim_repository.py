from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enum.claim import ClaimState
from app.model.reporting_claim_model import ReportingClaim


class ClaimRepository:
    """Data-access layer for the ReportingClaim entity.

    Provides CRUD operations and filtered queries for reporting claims
    -- assertions that a specific employee-manager relationship exists.
    All mutating methods flush to the session but do **not** commit;
    the caller is responsible for committing the transaction.

    Args:
        db: An async SQLAlchemy session used for all database operations.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the repository with an async database session.

        Args:
            db: The SQLAlchemy ``AsyncSession`` bound to the current
                request or unit of work.
        """
        self.db = db

    async def get_by_id(self, claim_id: str) -> ReportingClaim | None:
        """Fetch a single non-deleted reporting claim by its primary key.

        Args:
            claim_id: The prefixed UUID of the claim (e.g. ``claim_...``).

        Returns:
            The matching ``ReportingClaim`` instance, or ``None`` if no
            non-deleted record exists with the given id.
        """
        result = await self.db.execute(
            select(ReportingClaim).where(
                ReportingClaim.id == claim_id,
                ReportingClaim.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def find_active_claim(
        self, employee_id: str, manager_id: str, org_id: str
    ) -> ReportingClaim | None:
        """Find an existing claim that is still in an active (non-terminal) state.

        Active states are: DRAFT, SUBMITTED, VALIDATION,
        PENDING_COUNTERPARTY, PENDING_MODERATION, and DISPUTED.
        This is used to prevent duplicate claims for the same
        employee-manager-org triple.

        Args:
            employee_id: The subordinate employee id.
            manager_id: The manager employee id.
            org_id: The organization id.

        Returns:
            The active ``ReportingClaim`` instance, or ``None`` if no
            active claim exists for the given triple.
        """
        active_states = [
            ClaimState.DRAFT,
            ClaimState.SUBMITTED,
            ClaimState.VALIDATION,
            ClaimState.PENDING_COUNTERPARTY,
            ClaimState.PENDING_MODERATION,
            ClaimState.DISPUTED,
        ]
        result = await self.db.execute(
            select(ReportingClaim).where(
                ReportingClaim.employee_id == employee_id,
                ReportingClaim.manager_id == manager_id,
                ReportingClaim.org_id == org_id,
                ReportingClaim.state.in_([s.value for s in active_states]),
                ReportingClaim.is_deleted == False,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def list_filtered(
        self,
        org_id: str | None = None,
        employee_id: str | None = None,
        claimant_id: str | None = None,
        state: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[ReportingClaim], int]:
        """Return a paginated, optionally filtered list of non-deleted claims.

        All filter parameters are optional; when omitted the corresponding
        predicate is not applied.  Results are ordered by ``created_at``
        descending (newest first).

        Args:
            org_id: Filter by organization id.
            employee_id: Filter by the subordinate employee id.
            claimant_id: Filter by the actor who submitted the claim.
            state: Filter by the claim state value (e.g. ``"submitted"``).
            offset: The number of records to skip (default ``0``).
            limit: The maximum number of records to return (default ``20``).

        Returns:
            A tuple of ``(claims, total)`` where *claims* is the list of
            ``ReportingClaim`` instances for the requested page and
            *total* is the count of all matching (non-deleted) records.
        """
        query = select(ReportingClaim).where(
            ReportingClaim.is_deleted == False  # noqa: E712
        )
        if org_id:
            query = query.where(ReportingClaim.org_id == org_id)
        if employee_id:
            query = query.where(ReportingClaim.employee_id == employee_id)
        if claimant_id:
            query = query.where(ReportingClaim.claimant_id == claimant_id)
        if state:
            query = query.where(ReportingClaim.state == state)

        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            query.order_by(ReportingClaim.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_pending_for_counterparty(
        self, counterparty_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[ReportingClaim], int]:
        """Return claims awaiting confirmation by a specific counterparty.

        A counterparty is either the employee or the manager named in
        the claim who has not yet responded.  Only claims in the
        ``PENDING_COUNTERPARTY`` state are returned, ordered by
        ``created_at`` descending.

        Args:
            counterparty_id: The employee id of the counterparty who
                must confirm or reject the claim.
            offset: The number of records to skip (default ``0``).
            limit: The maximum number of records to return (default ``20``).

        Returns:
            A tuple of ``(claims, total)`` where *claims* is the list of
            ``ReportingClaim`` instances for the requested page and
            *total* is the count of all matching records.
        """
        query = select(ReportingClaim).where(
            ReportingClaim.state == ClaimState.PENDING_COUNTERPARTY.value,
            ReportingClaim.is_deleted == False,  # noqa: E712
            (ReportingClaim.employee_id == counterparty_id)
            | (ReportingClaim.manager_id == counterparty_id),
        )
        count_result = await self.db.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            query.order_by(ReportingClaim.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def list_expired_claims(self, now) -> list[ReportingClaim]:
        """Return all non-deleted claims that have passed their expiry time.

        Only claims in the ``PENDING_COUNTERPARTY`` state with an
        ``expires_at`` timestamp at or before *now* are returned.

        Args:
            now: The current UTC datetime used as the expiry threshold.

        Returns:
            A list of expired ``ReportingClaim`` instances.
        """
        result = await self.db.execute(
            select(ReportingClaim).where(
                ReportingClaim.state == ClaimState.PENDING_COUNTERPARTY.value,
                ReportingClaim.expires_at <= now,
                ReportingClaim.is_deleted == False,  # noqa: E712
            )
        )
        return list(result.scalars().all())

    async def create(self, claim: ReportingClaim) -> ReportingClaim:
        """Persist a new reporting claim to the session.

        The entity is added and flushed (but not committed) so that
        database-generated defaults (e.g. ``created_at``) are populated
        immediately.

        Args:
            claim: The ``ReportingClaim`` instance to insert.

        Returns:
            The same ``ReportingClaim`` instance after flushing to the
            session.
        """
        self.db.add(claim)
        await self.db.flush()
        return claim

    async def update(self, claim: ReportingClaim) -> ReportingClaim:
        """Flush pending attribute changes on an existing reporting claim.

        The caller is expected to have mutated the ``ReportingClaim``
        instance directly before calling this method.  Only a flush is
        performed; no commit is issued.

        Args:
            claim: The dirty ``ReportingClaim`` instance whose changes
                should be flushed.

        Returns:
            The same ``ReportingClaim`` instance after flushing.
        """
        await self.db.flush()
        return claim
