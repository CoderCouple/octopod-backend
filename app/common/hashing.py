import hashlib
import json
from datetime import datetime
from decimal import Decimal
from typing import Any


def _json_serializer(obj: Any) -> Any:
    """Custom JSON serializer for types not handled by the stdlib encoder.

    Supports ``datetime`` (converted to ISO-8601 string) and ``Decimal``
    (converted to its string representation).

    Args:
        obj: The object that the default JSON encoder cannot serialize.

    Returns:
        A JSON-serializable representation of *obj*.

    Raises:
        TypeError: If *obj* is not a ``datetime`` or ``Decimal``.
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def compute_event_hash(
    prev_hash: str,
    entity_type: str,
    entity_id: str,
    action: str,
    after_state: dict | None,
    actor_id: str,
    timestamp: datetime,
) -> str:
    """Compute a SHA-256 hash for an event log entry.

    Builds a canonical JSON payload from the supplied fields, serializes
    it with sorted keys, and produces a hex-encoded SHA-256 digest.
    This hash is stored on the ``EventLog`` record and used to form a
    tamper-evident chain (each entry references the previous entry's hash).

    Args:
        prev_hash: The ``event_hash`` of the preceding event log entry
            (or an empty string / sentinel for the first entry).
        entity_type: The type of entity that was modified (e.g.
            ``"org"``, ``"employee"``).
        entity_id: The prefixed UUID of the modified entity.
        action: The action that was performed (e.g. ``"create"``,
            ``"update"``).
        after_state: A dictionary representing the entity's state after
            the change, or ``None``.
        actor_id: The identifier of the user who triggered the change.
        timestamp: The UTC datetime when the event was recorded.

    Returns:
        A lowercase hex-encoded SHA-256 hash string.
    """
    payload = {
        "prev_hash": prev_hash,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": action,
        "after_state": after_state,
        "actor_id": actor_id,
        "timestamp": timestamp.isoformat(),
    }
    canonical = json.dumps(payload, sort_keys=True, default=_json_serializer)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
