"""Tests for discovery ranking logic — no network."""
from app.ingest.gh.discover import UserCandidate
from app.ingest.gh.discover import _rank_and_score as gh_rank
from app.ingest.hf.discover import AuthorCandidate, _aggregate_by_author, _author_of
from app.ingest.hf.discover import _rank_and_score as hf_rank


def test_gh_rank_pure_followers():
    users = {
        "a": UserCandidate("a", followers=100, total_stars=1),
        "b": UserCandidate("b", followers=50, total_stars=1000),
        "c": UserCandidate("c", followers=10, total_stars=500),
    }
    ranked = gh_rank(users, alpha=1.0)
    assert [u.login for u in ranked] == ["a", "b", "c"]


def test_gh_rank_pure_stars():
    users = {
        "a": UserCandidate("a", followers=100, total_stars=1),
        "b": UserCandidate("b", followers=50, total_stars=1000),
        "c": UserCandidate("c", followers=10, total_stars=500),
    }
    ranked = gh_rank(users, alpha=0.0)
    assert [u.login for u in ranked] == ["b", "c", "a"]


def test_gh_rank_balanced_prefers_both():
    users = {
        "all_rounder": UserCandidate("all_rounder", followers=80, total_stars=800),
        "follower_only": UserCandidate("follower_only", followers=100, total_stars=1),
        "star_only": UserCandidate("star_only", followers=1, total_stars=1000),
    }
    ranked = gh_rank(users, alpha=0.5)
    assert ranked[0].login == "all_rounder"


def test_gh_rank_empty():
    assert gh_rank({}, alpha=0.5) == []


def test_hf_author_of():
    assert _author_of("openai/whisper") == "openai"
    assert _author_of("no-slash") is None
    assert _author_of("") is None


def test_hf_aggregate_sums_across_models():
    models = [
        {"id": "openai/whisper-large", "downloads": 1000, "likes": 500},
        {"id": "openai/whisper-small", "downloads": 500, "likes": 200},
        {"id": "meta/llama", "downloads": 2000, "likes": 900},
        {"id": "no-author", "downloads": 1, "likes": 1},
    ]
    authors = _aggregate_by_author(models)
    assert set(authors) == {"openai", "meta"}
    assert authors["openai"].total_downloads == 1500
    assert authors["openai"].total_likes == 700
    assert authors["openai"].num_models == 2
    assert authors["meta"].num_models == 1


def test_hf_rank_balanced():
    authors = {
        "both": AuthorCandidate("both", total_downloads=800, total_likes=800),
        "downloads_only": AuthorCandidate(
            "downloads_only", total_downloads=1000, total_likes=1
        ),
        "likes_only": AuthorCandidate("likes_only", total_downloads=1, total_likes=1000),
    }
    ranked = hf_rank(authors, alpha=0.5)
    assert ranked[0].username == "both"


def test_hf_rank_missing_counts_default_to_zero():
    models = [
        {"id": "x/a", "downloads": None, "likes": None},
        {"id": "x/b", "downloads": 10, "likes": 5},
    ]
    authors = _aggregate_by_author(models)
    assert authors["x"].total_downloads == 10
    assert authors["x"].total_likes == 5
    assert authors["x"].num_models == 2
