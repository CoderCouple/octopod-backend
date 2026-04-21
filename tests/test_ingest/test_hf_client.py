"""Unit tests for HF client parsing helpers — no network or DB."""
from app.ingest.hf.client import _parse_next_link
from app.ingest.hf.storage import _coerce_list, _extract_languages, _parse_ts, _split_id


def test_parse_next_link_present():
    h = '<https://huggingface.co/api/models?cursor=abc>; rel="next"'
    assert _parse_next_link(h) == "https://huggingface.co/api/models?cursor=abc"


def test_parse_next_link_with_other_rels():
    h = (
        '<https://huggingface.co/api/models?cursor=prev>; rel="prev", '
        '<https://huggingface.co/api/models?cursor=next>; rel="next"'
    )
    assert _parse_next_link(h) == "https://huggingface.co/api/models?cursor=next"


def test_parse_next_link_missing():
    assert _parse_next_link(None) is None
    assert _parse_next_link("") is None
    assert _parse_next_link('<https://x>; rel="prev"') is None


def test_split_id():
    assert _split_id("openai/whisper-large") == ("openai", "whisper-large")
    assert _split_id("bert-base-uncased") == ("", "bert-base-uncased")
    assert _split_id("org/sub/name") == ("org", "sub/name")


def test_extract_languages():
    tags = ["language:en", "pytorch", "language:zh", "transformers", "license:apache-2.0"]
    assert sorted(_extract_languages(tags)) == ["en", "zh"]
    assert _extract_languages([]) == []
    assert _extract_languages(None) == []  # type: ignore[arg-type]


def test_coerce_list():
    assert _coerce_list(None) == []
    assert _coerce_list("single") == ["single"]
    assert _coerce_list(["a", "b"]) == ["a", "b"]
    assert _coerce_list([1, 2]) == ["1", "2"]
    assert _coerce_list({"unexpected": "dict"}) == []


def test_parse_ts():
    assert _parse_ts(None) is None
    assert _parse_ts("") is None
    ts = _parse_ts("2024-03-15T10:30:00.000Z")
    assert ts is not None and ts.year == 2024 and ts.month == 3
    assert _parse_ts("not-a-date") is None
