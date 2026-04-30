import pytest

from app.service.reranking import RerankCandidate, Reranker, RerankResult


class MockReranker(Reranker):
    """Scores by word overlap between query and candidate text."""

    async def rerank(
        self, query: str, candidates: list[RerankCandidate], top_k: int = 20
    ) -> list[RerankResult]:
        if not candidates:
            return []

        query_words = set(query.lower().split())
        results = []
        for c in candidates:
            text_words = set(c.text.lower().split())
            overlap = len(query_words & text_words)
            score = overlap / max(len(query_words), 1)
            results.append(
                RerankResult(
                    profile_id=c.profile_id,
                    rerank_score=score,
                    original_score=c.original_score,
                )
            )
        results.sort(key=lambda r: r.rerank_score, reverse=True)
        return results[:top_k]


@pytest.mark.asyncio
async def test_rerank_sorted_output():
    reranker = MockReranker()
    candidates = [
        RerankCandidate("p1", "java spring boot developer", 0.9),
        RerankCandidate("p2", "python machine learning engineer", 0.8),
        RerankCandidate("p3", "python data science machine learning deep learning", 0.7),
    ]
    results = await reranker.rerank("python machine learning deep", candidates)
    # p3 has 4/4 overlap, p2 has 2/4
    assert results[0].profile_id == "p3"
    assert results[0].rerank_score >= results[1].rerank_score
    assert results[-1].rerank_score <= results[0].rerank_score


@pytest.mark.asyncio
async def test_rerank_top_k_limit():
    reranker = MockReranker()
    candidates = [
        RerankCandidate(f"p{i}", f"text {i}", 0.5) for i in range(10)
    ]
    results = await reranker.rerank("text", candidates, top_k=3)
    assert len(results) == 3


@pytest.mark.asyncio
async def test_rerank_empty_input():
    reranker = MockReranker()
    results = await reranker.rerank("anything", [])
    assert results == []


@pytest.mark.asyncio
async def test_rerank_preserves_profile_ids():
    reranker = MockReranker()
    candidates = [
        RerankCandidate("abc-123", "python developer", 0.9),
        RerankCandidate("def-456", "java developer", 0.8),
    ]
    results = await reranker.rerank("developer", candidates)
    result_ids = {r.profile_id for r in results}
    assert result_ids == {"abc-123", "def-456"}


@pytest.mark.asyncio
async def test_rerank_preserves_original_score():
    reranker = MockReranker()
    candidates = [
        RerankCandidate("p1", "python dev", 0.95),
    ]
    results = await reranker.rerank("python", candidates)
    assert results[0].original_score == 0.95
