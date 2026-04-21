"""Shared error types for ingestion engines.

PermanentError = don't retry (404, suspended, deleted).
TransientError = worth retrying (5xx, timeout, rate limit).
"""


class PermanentError(Exception):
    """User/resource-specific failure that should not be retried (404, suspended, etc.)."""


class TransientError(Exception):
    """Temporary failure; worth retrying."""
