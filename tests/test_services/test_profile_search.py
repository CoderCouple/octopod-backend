import math
import struct
from datetime import datetime, timezone

import pytest
import pytest_asyncio

from app.api.v1.request.developer_profile_request import SemanticSearchRequest
from app.model.cohesive_profile_model import CohesiveProfile
from app.model.developer_profile_model import DeveloperProfile
from app.service.embedding import EmbeddingProvider
from app.service.profile_search_service import ProfileSearchService
from app.service.reranking import Reranker, RerankCandidate, RerankResult


class MockEmbeddingProvider(EmbeddingProvider):
    """Deterministic embedding: hash text to 384-dim vector."""

    async def embed(self, text: str) -> list[float]:
        import hashlib

        h = hashlib.sha256(text.encode()).digest()
        # Generate 384 floats from hash bytes (repeat hash as needed)
        extended = h * (384 * 4 // len(h) + 1)
        raw = extended[: 384 * 4]
        values = list(struct.unpack(f"{384}f", raw))
        # Normalize
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    def dimension(self) -> int:
        return 384


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


class MockQdrantClient:
    """In-memory mock Qdrant that stores points and does cosine similarity."""

    def __init__(self):
        self._points: dict[str, dict] = {}  # collection -> {point_id: {vector, payload}}
        self._collections: dict[str, bool] = {}

    def get_collections(self):
        class Collections:
            def __init__(self, names):
                self.collections = [type("C", (), {"name": n})() for n in names]

        return Collections(self._collections.keys())

    def create_collection(self, collection_name, vectors_config=None):
        self._collections[collection_name] = True
        self._points[collection_name] = {}

    def upsert(self, collection_name, points):
        if collection_name not in self._points:
            self._points[collection_name] = {}
        for p in points:
            self._points[collection_name][p.id] = {
                "vector": p.vector,
                "payload": p.payload,
            }

    def query_points(
        self, collection_name, query=None, query_filter=None, limit=10,
        score_threshold=None, **kwargs,
    ):
        points = self._points.get(collection_name, {})
        results = []
        for pid, data in points.items():
            score = self._cosine_sim(query, data["vector"])
            if score_threshold is not None and score < score_threshold:
                continue
            results.append(
                type("ScoredPoint", (), {
                    "id": pid,
                    "score": score,
                    "payload": data["payload"],
                })()
            )
        results.sort(key=lambda x: x.score, reverse=True)
        return type("QueryResponse", (), {"points": results[:limit]})()

    @staticmethod
    def _cosine_sim(a, b):
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
        norm_b = math.sqrt(sum(x * x for x in b)) or 1.0
        return dot / (norm_a * norm_b)


@pytest_asyncio.fixture
async def search_setup(async_session):
    mock_qdrant = MockQdrantClient()
    mock_qdrant.create_collection("developer_profiles")
    mock_embedder = MockEmbeddingProvider()
    mock_reranker = MockReranker()

    profiles = []
    for i, (name, text) in enumerate([
        ("ML Engineer", "Machine learning expert with Python and TensorFlow"),
        ("Backend Dev", "FastAPI and PostgreSQL backend developer"),
        ("Data Scientist", "Data analysis statistics and Python pandas"),
    ]):
        dp = DeveloperProfile(
            github_username=f"searchuser{i}",
            ingestion_status="completed",
        )
        async_session.add(dp)
        await async_session.flush()

        cp = CohesiveProfile(
            developer_profile_id=dp.id,
            display_name=name,
            embedding_text=text,
            languages=["Python"],
            skills=[name.split()[0]],
            total_stars=i * 50,
            merged_at=datetime.now(timezone.utc),
        )
        async_session.add(cp)
        await async_session.flush()
        profiles.append((dp, cp))

    # Index all profiles in mock qdrant
    service = ProfileSearchService(
        async_session,
        embedding_provider=mock_embedder,
        qdrant_client=mock_qdrant,
        reranker=mock_reranker,
    )
    for _dp, cp in profiles:
        point_id = await service.upsert_profile(cp)
        cp.embedding_vector_id = point_id
    await async_session.flush()

    return profiles, mock_qdrant, mock_embedder, mock_reranker


@pytest.mark.asyncio
async def test_search_returns_results(async_session, search_setup):
    profiles, mock_qdrant, mock_embedder, mock_reranker = search_setup

    service = ProfileSearchService(
        async_session,
        embedding_provider=mock_embedder,
        qdrant_client=mock_qdrant,
        reranker=mock_reranker,
    )
    request = SemanticSearchRequest(query="machine learning Python", limit=10)
    results = await service.search(request)

    assert len(results) > 0
    assert all(isinstance(r, type(results[0])) for r in results)


@pytest.mark.asyncio
async def test_search_limit(async_session, search_setup):
    profiles, mock_qdrant, mock_embedder, mock_reranker = search_setup

    service = ProfileSearchService(
        async_session,
        embedding_provider=mock_embedder,
        qdrant_client=mock_qdrant,
        reranker=mock_reranker,
    )
    request = SemanticSearchRequest(query="developer", limit=2)
    results = await service.search(request)

    assert len(results) <= 2


@pytest.mark.asyncio
async def test_upsert_profile(async_session, search_setup):
    profiles, mock_qdrant, mock_embedder, mock_reranker = search_setup

    # Verify points were inserted
    points = mock_qdrant._points.get("developer_profiles", {})
    assert len(points) == 3


@pytest.mark.asyncio
async def test_search_same_query_returns_same_order(async_session, search_setup):
    profiles, mock_qdrant, mock_embedder, mock_reranker = search_setup
    service = ProfileSearchService(
        async_session,
        embedding_provider=mock_embedder,
        qdrant_client=mock_qdrant,
        reranker=mock_reranker,
    )
    request = SemanticSearchRequest(query="backend developer", limit=10)
    results1 = await service.search(request)
    results2 = await service.search(request)

    assert len(results1) == len(results2)
    for r1, r2 in zip(results1, results2, strict=True):
        assert r1.profile.id == r2.profile.id


@pytest.mark.asyncio
async def test_search_with_reranking(async_session, search_setup):
    profiles, mock_qdrant, mock_embedder, mock_reranker = search_setup
    service = ProfileSearchService(
        async_session,
        embedding_provider=mock_embedder,
        qdrant_client=mock_qdrant,
        reranker=mock_reranker,
    )
    request = SemanticSearchRequest(query="machine learning Python", limit=10, rerank=True)
    results = await service.search(request)

    assert len(results) > 0
    # Reranker uses word overlap — "ML Engineer" profile has "machine learning" and "Python"
    # so it should score highly
    profile_names = [r.profile.display_name for r in results]
    assert "ML Engineer" in profile_names


@pytest.mark.asyncio
async def test_search_without_reranking(async_session, search_setup):
    profiles, mock_qdrant, mock_embedder, mock_reranker = search_setup
    service = ProfileSearchService(
        async_session,
        embedding_provider=mock_embedder,
        qdrant_client=mock_qdrant,
        reranker=mock_reranker,
    )
    request = SemanticSearchRequest(query="developer", limit=10, rerank=False)
    results = await service.search(request)

    # Should still return results, just without reranking pass
    assert len(results) > 0
