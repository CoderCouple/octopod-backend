from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.model.event_log_model import EventLog


class EventLogRepository:
    """Data-access layer for the EventLog entity.

    Provides read and create operations for the append-only,
    hash-chained event log.  All mutating methods flush to the session
    but do **not** commit; the caller is responsible for committing the
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

    async def get_last_event(self) -> EventLog | None:
        """Retrieve the most recent event log entry by sequence number.

        Used to obtain the ``prev_hash`` when appending a new entry to
        the hash chain.

        Returns:
            The ``EventLog`` with the highest ``sequence_no``, or
            ``None`` if the log is empty.
        """
        result = await self.db.execute(
            select(EventLog).order_by(EventLog.sequence_no.desc()).limit(1)
        )
        return result.scalar_one_or_none()

    async def get_all_ordered(self) -> list[EventLog]:
        """Retrieve every event log entry ordered by ascending sequence number.

        Returns:
            A list of all ``EventLog`` instances in chronological
            (sequence) order.
        """
        result = await self.db.execute(
            select(EventLog).order_by(EventLog.sequence_no.asc())
        )
        return list(result.scalars().all())

    async def get_by_entity(
        self,
        entity_type: str,
        entity_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[EventLog], int]:
        """Return a paginated list of event log entries for a specific entity.

        Results are ordered by ``sequence_no`` ascending (oldest first).

        Args:
            entity_type: The type of entity (e.g. ``"org"``,
                ``"employee"``).
            entity_id: The prefixed UUID of the entity.
            offset: The number of records to skip (default ``0``).
            limit: The maximum number of records to return (default ``20``).

        Returns:
            A tuple of ``(events, total)`` where *events* is the list of
            ``EventLog`` instances for the requested page and *total* is
            the count of all matching records.
        """
        base_query = select(EventLog).where(
            EventLog.entity_type == entity_type,
            EventLog.entity_id == entity_id,
        )
        count_result = await self.db.execute(
            select(func.count()).select_from(base_query.subquery())
        )
        total = count_result.scalar() or 0

        result = await self.db.execute(
            base_query.order_by(EventLog.sequence_no.asc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def create(self, event: EventLog) -> EventLog:
        """Append a new entry to the event log.

        The entity is added and flushed (but not committed) so that
        the database-assigned defaults are populated immediately.

        Args:
            event: The ``EventLog`` instance to insert.

        Returns:
            The same ``EventLog`` instance after flushing to the session.
        """
        self.db.add(event)
        await self.db.flush()
        return event
