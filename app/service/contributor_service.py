"""Service layer for contributor reputation scoring.

Provides business logic for tracking and computing contributor reputation
scores based on their claim-related activities. The scoring model awards
points for positive contributions (submitting claims, verifying claims,
providing confirmations) and penalizes rejections. Scores determine a
contributor's visibility level, which controls how much of the org graph
they can see.

Scoring weights:
    - Claims submitted:      +1 point each
    - Claims verified:       +3 points each
    - Confirmations given:   +2 points each
    - Rejections given:      -0.5 points each

Visibility level thresholds:
    - Level 0: raw_score < 1
    - Level 1: raw_score >= 1
    - Level 2: raw_score >= 5
    - Level 3: raw_score >= 10
"""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repository.contributor_repository import ContributorRepository
from app.model.contributor_score_model import ContributorScore


class ContributorService:
    """Service for managing contributor reputation scores and visibility levels.

    Tracks contributor activity counts, computes weighted reputation scores,
    and derives visibility levels that control access to organizational graph
    data. Each increment operation updates the raw score and visibility level
    automatically.
    """

    def __init__(self, db: AsyncSession):
        """Initialize ContributorService with a database session.

        Args:
            db: An async SQLAlchemy session used for all database operations.
        """
        self.db = db
        self.repo = ContributorRepository(db)

    async def get_or_create_score(self, actor_id: str) -> ContributorScore:
        """Retrieve an existing contributor score or create a new one.

        If no score record exists for the given actor, a new one is created
        with default zero values.

        Args:
            actor_id: The unique identifier of the contributor.

        Returns:
            The ContributorScore record for the given actor.
        """
        score = await self.repo.get_by_actor_id(actor_id)
        if not score:
            score = ContributorScore(actor_id=actor_id)
            score = await self.repo.create(score)
        return score

    async def increment_claims_submitted(self, actor_id: str) -> ContributorScore:
        """Increment the total claims submitted count for a contributor.

        Adds one to the contributor's total_claims_submitted counter and
        triggers a recalculation of the raw score and visibility level.

        Args:
            actor_id: The unique identifier of the contributor.

        Returns:
            The updated ContributorScore record.
        """
        score = await self.get_or_create_score(actor_id)
        score.total_claims_submitted += 1
        await self._recalculate(score)
        return await self.repo.update(score)

    async def increment_claims_verified(self, actor_id: str) -> ContributorScore:
        """Increment the total claims verified count for a contributor.

        Adds one to the contributor's total_claims_verified counter and
        triggers a recalculation of the raw score and visibility level.

        Args:
            actor_id: The unique identifier of the contributor.

        Returns:
            The updated ContributorScore record.
        """
        score = await self.get_or_create_score(actor_id)
        score.total_claims_verified += 1
        await self._recalculate(score)
        return await self.repo.update(score)

    async def increment_confirmations(self, actor_id: str) -> ContributorScore:
        """Increment the total confirmations given count for a contributor.

        Adds one to the contributor's total_confirmations_given counter and
        triggers a recalculation of the raw score and visibility level.

        Args:
            actor_id: The unique identifier of the contributor.

        Returns:
            The updated ContributorScore record.
        """
        score = await self.get_or_create_score(actor_id)
        score.total_confirmations_given += 1
        await self._recalculate(score)
        return await self.repo.update(score)

    async def increment_rejections(self, actor_id: str) -> ContributorScore:
        """Increment the total rejections given count for a contributor.

        Adds one to the contributor's total_rejections_given counter and
        triggers a recalculation of the raw score and visibility level.
        Rejections carry a negative weight in the scoring model.

        Args:
            actor_id: The unique identifier of the contributor.

        Returns:
            The updated ContributorScore record.
        """
        score = await self.get_or_create_score(actor_id)
        score.total_rejections_given += 1
        await self._recalculate(score)
        return await self.repo.update(score)

    async def get_visibility_level(self, actor_id: str) -> int:
        """Get the current visibility level for a contributor.

        Returns the contributor's visibility level (0-3) which determines
        how much of the organizational graph they are allowed to see.
        Returns 0 (minimum visibility) if no score record exists.

        Args:
            actor_id: The unique identifier of the contributor.

        Returns:
            An integer visibility level from 0 (least access) to 3
            (full access).
        """
        score = await self.repo.get_by_actor_id(actor_id)
        if not score:
            return 0
        return score.visibility_level

    async def _recalculate(self, score: ContributorScore) -> None:
        """Recalculate the raw score and visibility level for a contributor.

        Computes the weighted sum of all activity counts and updates the
        visibility level based on threshold breakpoints. This method is
        called internally after every increment operation.

        Args:
            score: The ContributorScore record to recalculate. Modified
                in place with updated raw_score, visibility_level, and
                updated_at fields.

        Returns:
            None. The score object is modified in place.
        """
        raw = (
            Decimal(score.total_claims_submitted) * Decimal("1")
            + Decimal(score.total_claims_verified) * Decimal("3")
            + Decimal(score.total_confirmations_given) * Decimal("2")
            - Decimal(score.total_rejections_given) * Decimal("0.5")
        )
        score.raw_score = raw
        if raw >= Decimal("10"):
            score.visibility_level = 3
        elif raw >= Decimal("5"):
            score.visibility_level = 2
        elif raw >= Decimal("1"):
            score.visibility_level = 1
        else:
            score.visibility_level = 0
        score.updated_at = datetime.now(timezone.utc)
