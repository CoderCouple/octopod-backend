"""Service layer for the append-only event log.

Provides business logic for recording entity state changes in a tamper-evident,
hash-chained event log. Each event is linked to the previous event via a
cryptographic hash, enabling integrity verification of the full audit trail.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.common.hashing import compute_event_hash
from app.db.repository.event_log_repository import EventLogRepository
from app.model.event_log_model import EventLog


class EventLogService:
    """Service for managing the append-only, hash-chained event log.

    Provides methods to append new events with cryptographic chaining,
    retrieve events for specific entities, and verify the integrity of the
    entire event chain. Each event stores before and after state snapshots
    and is linked to the previous event via a SHA-256 hash.
    """

    def __init__(self, db: AsyncSession):
        """Initialize EventLogService with a database session.

        Args:
            db: An async SQLAlchemy session used for all database operations.
        """
        self.db = db
        self.repo = EventLogRepository(db)

    async def append_event(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_id: str | None,
        before_state: dict[str, Any] | None = None,
        after_state: dict[str, Any] | None = None,
    ) -> EventLog:
        """Append a new event to the hash-chained event log.

        Retrieves the last event to obtain the previous hash and sequence
        number, computes a new cryptographic hash incorporating the event
        data, and persists the event record.

        Args:
            entity_type: The type of entity this event pertains to (e.g.,
                "org", "employee", "employment").
            entity_id: The UUID string of the entity that changed.
            action: The action performed (e.g., "create", "update", "delete").
            actor_id: The identifier of the user who performed the action,
                or None if performed by the system.
            before_state: Optional dictionary capturing the entity state
                before the change.
            after_state: Optional dictionary capturing the entity state
                after the change.

        Returns:
            The persisted EventLog record with its computed hash and
            sequence number.
        """
        last_event = await self.repo.get_last_event()
        prev_hash = last_event.event_hash if last_event else "0" * 64
        next_seq = (last_event.sequence_no + 1) if last_event else 1
        now = datetime.now(timezone.utc)

        event_hash = compute_event_hash(
            prev_hash=prev_hash,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            after_state=after_state,
            actor_id=actor_id or "system",
            timestamp=now,
        )

        event = EventLog(
            sequence_no=next_seq,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            before_state=before_state,
            after_state=after_state,
            actor_id=actor_id,
            timestamp=now,
            prev_hash=prev_hash,
            event_hash=event_hash,
        )
        return await self.repo.create(event)

    async def get_events_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[EventLog], int]:
        """Retrieve paginated event log entries for a specific entity.

        Args:
            entity_type: The type of entity to filter events by (e.g.,
                "org", "employee").
            entity_id: The UUID string of the entity whose events to
                retrieve.
            offset: The number of records to skip. Defaults to 0.
            limit: The maximum number of records to return. Defaults to 20.

        Returns:
            A tuple of (list of EventLog records, total count of events
            for the entity).
        """
        return await self.repo.get_by_entity(entity_type, entity_id, offset, limit)

    async def verify_chain_integrity(self) -> tuple[bool, str | None]:
        """Verify the integrity of the entire event log hash chain.

        Iterates through all events in sequence order and checks that each
        event's prev_hash matches the event_hash of the preceding event.
        The first event in the chain is expected to reference a zero-hash
        (64 hex zeros).

        Returns:
            A tuple of (is_valid, error_message). If the chain is intact,
            returns (True, None). If a break is detected, returns
            (False, description of where the chain broke).
        """
        events = await self.repo.get_all_ordered()

        prev_hash = "0" * 64
        for event in events:
            if event.prev_hash != prev_hash:
                return (
                    False,
                    f"Chain broken at sequence {event.sequence_no}: prev_hash mismatch",
                )
            prev_hash = event.event_hash

        return True, None
