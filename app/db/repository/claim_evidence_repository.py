from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.claim_evidence_model import ClaimEvidence


class ClaimEvidenceRepository:
    """Data-access layer for the ClaimEvidence entity.

    Provides read and create operations for evidence items attached to
    reporting claims (e.g. self-claims, manager confirmations, peer
    confirmations).  All mutating methods flush to the session but do
    **not** commit; the caller is responsible for committing the
    transaction.

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

    async def list_by_claim(self, claim_id: str) -> list[ClaimEvidence]:
        """Return all evidence items for a given claim.

        Results are ordered by ``created_at`` ascending (oldest first).

        Args:
            claim_id: The prefixed UUID of the claim whose evidence
                should be retrieved.

        Returns:
            A list of ``ClaimEvidence`` instances in chronological order.
        """
        result = await self.db.execute(
            select(ClaimEvidence)
            .where(ClaimEvidence.claim_id == claim_id)
            .order_by(ClaimEvidence.created_at.asc())
        )
        return list(result.scalars().all())

    async def create(self, evidence: ClaimEvidence) -> ClaimEvidence:
        """Persist a new evidence item to the session.

        The entity is added and flushed (but not committed) so that
        database-generated defaults (e.g. ``created_at``) are populated
        immediately.

        Args:
            evidence: The ``ClaimEvidence`` instance to insert.

        Returns:
            The same ``ClaimEvidence`` instance after flushing to the
            session.
        """
        self.db.add(evidence)
        await self.db.flush()
        return evidence
