from sqlalchemy.ext.asyncio import AsyncSession

from app.model.career_event_model import CareerEvent


class CareerEventRepository:
    """Data-access layer for the CareerEvent entity.

    Provides a create-only interface for recording career events such
    as promotions, transfers, and manager changes.  All mutating methods
    flush to the session but do **not** commit; the caller is
    responsible for committing the transaction.

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

    async def create(self, career_event: CareerEvent) -> CareerEvent:
        """Persist a new career event to the session.

        The entity is added and flushed (but not committed) so that
        database-generated defaults (e.g. ``recorded_at``) are
        populated immediately.

        Args:
            career_event: The ``CareerEvent`` instance to insert.

        Returns:
            The same ``CareerEvent`` instance after flushing to the
            session.
        """
        self.db.add(career_event)
        await self.db.flush()
        return career_event
