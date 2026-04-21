"""Unit tests for GH client helpers and error classification — no network."""
import pytest

from app.ingest.common.errors import PermanentError, TransientError
from app.ingest.gh.storage import _parse_ts


def test_parse_ts_valid():
    ts = _parse_ts("2024-01-15T12:34:56Z")
    assert ts is not None
    assert ts.year == 2024 and ts.month == 1 and ts.day == 15


def test_parse_ts_none():
    assert _parse_ts(None) is None
    assert _parse_ts("") is None


def test_permanent_error_is_exception():
    with pytest.raises(PermanentError):
        raise PermanentError("404: not found")


def test_transient_error_is_exception():
    with pytest.raises(TransientError):
        raise TransientError("502: bad gateway")


def test_errors_are_not_related():
    assert not issubclass(PermanentError, TransientError)
    assert not issubclass(TransientError, PermanentError)
