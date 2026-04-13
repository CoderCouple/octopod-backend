from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.contributor_score_model import ContributorScore


class ContributorRepository:
    """Data-access layer for the ContributorScore entity.

    Provides CRUD operations for contributor score records that track
    each actor's cumulative claim-related activity and reputation.
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

    async def get_by_actor_id(self, actor_id: str) -> ContributorScore | None:
        """Fetch a contributor score record by the actor's unique identifier.

        Args:
            actor_id: The unique identifier of the actor (user).

        Returns:
            The matching ``ContributorScore`` instance, or ``None`` if
            no record exists for the given actor.
        """
        result = await self.db.execute(
            select(ContributorScore).where(ContributorScore.actor_id == actor_id)
        )
        return result.scalar_one_or_none()

    async def create(self, score: ContributorScore) -> ContributorScore:
        """Persist a new contributor score record to the session.

        The entity is added and flushed (but not committed) so that
        database-generated defaults are populated immediately.

        Args:
            score: The ``ContributorScore`` instance to insert.

        Returns:
            The same ``ContributorScore`` instance after flushing to the
            session.
        """
        self.db.add(score)
        await self.db.flush()
        return score

    async def update(self, score: ContributorScore) -> ContributorScore:
        """Flush pending attribute changes on an existing contributor score.

        The caller is expected to have mutated the ``ContributorScore``
        instance directly before calling this method.  Only a flush is
        performed; no commit is issued.

        Args:
            score: The dirty ``ContributorScore`` instance whose changes
                should be flushed.

        Returns:
            The same ``ContributorScore`` instance after flushing.
        """
        await self.db.flush()
        return score
