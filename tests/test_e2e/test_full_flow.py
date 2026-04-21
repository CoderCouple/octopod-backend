"""End-to-end test: Create → Ingest (mocked) → Merge → Rank → Search."""

import math
import struct
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.service.embedding import EmbeddingProvider


class MockEmbeddingProvider(EmbeddingProvider):
    async def embed(self, text: str) -> list[float]:
        import hashlib

        h = hashlib.sha256(text.encode()).digest()
        extended = h * (384 * 4 // len(h) + 1)
        raw = extended[: 384 * 4]
        values = list(struct.unpack(f"{384}f", raw))
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    def dimension(self) -> int:
        return 384


class MockQdrantClient:
    def __init__(self):
        self._points: dict[str, dict] = {}
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

    def search(self, collection_name, query_vector, query_filter=None, limit=10, score_threshold=None):
        points = self._points.get(collection_name, {})
        results = []
        for pid, data in points.items():
            score = self._cosine_sim(query_vector, data["vector"])
            if score_threshold is not None and score < score_threshold:
                continue
            results.append(
                type("ScoredPoint", (), {"id": pid, "score": score, "payload": data["payload"]})()
            )
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    @staticmethod
    def _cosine_sim(a, b):
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
        norm_b = math.sqrt(sum(x * x for x in b)) or 1.0
        return dot / (norm_a * norm_b)


MOCK_GITHUB_RAW = {
    "user": {
        "login": "torvalds",
        "name": "Linus Torvalds",
        "bio": "Creator of Linux and Git",
        "avatar_url": "https://avatars.githubusercontent.com/u/1024025",
        "company": "Linux Foundation",
        "location": "Portland, OR",
        "blog": "https://torvalds.dev",
        "public_repos": 7,
        "followers": 200000,
    },
    "repos": [
        {
            "fork": False,
            "stargazers_count": 170000,
            "language": "C",
            "topics": ["linux", "kernel", "operating-system"],
        },
        {
            "fork": False,
            "stargazers_count": 50000,
            "language": "C",
            "topics": ["git", "vcs"],
        },
        {
            "fork": True,
            "stargazers_count": 5000,
            "language": "Python",
            "topics": [],
        },
    ],
}


async def mock_fetch_github(self, username):
    from app.service.clients.github_client import GitHubClient

    extracted = GitHubClient.extract(MOCK_GITHUB_RAW)
    return MOCK_GITHUB_RAW, extracted


@pytest.mark.asyncio
async def test_full_e2e_flow(async_client):
    """Test the complete flow: create → ingest → merge → rank."""

    # ── Step 1: Create developer profile ──
    resp = await async_client.post(
        "/api/v1/developer-profile",
        json={"github_username": "torvalds", "auto_ingest": False},
    )
    assert resp.status_code == 201, resp.json()
    body = resp.json()
    assert body["success"] is True
    profile_id = body["result"]["id"]
    assert profile_id.startswith("dp_")
    assert body["result"]["github_username"] == "torvalds"
    assert body["result"]["ingestion_status"] == "pending"
    print(f"\n✅ Created profile: {profile_id}")

    # ── Step 2: List profiles ──
    resp = await async_client.get("/api/v1/developer-profile")
    assert resp.status_code == 200
    assert resp.json()["result"]["total"] >= 1
    print("✅ Listed profiles")

    # ── Step 3: Get profile by ID ──
    resp = await async_client.get(f"/api/v1/developer-profile/{profile_id}")
    assert resp.status_code == 200
    assert resp.json()["result"]["id"] == profile_id
    print("✅ Got profile by ID")

    # ── Step 4: Update profile ──
    resp = await async_client.patch(
        f"/api/v1/developer-profile/{profile_id}",
        json={"email_hint": "torvalds@linux-foundation.org"},
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["email_hint"] == "torvalds@linux-foundation.org"
    print("✅ Updated profile")

    # ── Step 5: Trigger ingestion (mocked GitHub) ──
    with patch(
        "app.service.platform_ingestion_service.PlatformIngestionService._fetch_github",
        mock_fetch_github,
    ):
        resp = await async_client.post(
            f"/api/v1/developer-profile/{profile_id}/ingest"
        )
    assert resp.status_code == 202, resp.json()
    status_body = resp.json()["result"]
    assert status_body["ingestion_status"] == "completed"
    assert len(status_body["platforms"]) == 1
    assert status_body["platforms"][0]["fetch_status"] == "success"
    assert status_body["platforms"][0]["platform"] == "github"
    print("✅ Ingestion completed (mocked GitHub)")

    # ── Step 6: Check ingestion status ──
    resp = await async_client.get(
        f"/api/v1/developer-profile/{profile_id}/status"
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["ingestion_status"] == "completed"
    print("✅ Checked ingestion status")

    # ── Step 7: Merge profile ──
    resp = await async_client.post(
        f"/api/v1/developer-profile/{profile_id}/merge"
    )
    assert resp.status_code == 200, resp.json()
    cohesive = resp.json()["result"]
    assert cohesive["display_name"] == "Linus Torvalds"
    assert cohesive["bio"] == "Creator of Linux and Git"
    assert cohesive["total_stars"] == 220000
    assert cohesive["total_repos"] == 7
    assert "C" in cohesive["languages"]
    assert "linux" in cohesive["topics"]
    assert cohesive["merged_at"] is not None
    print(f"✅ Merged profile: {cohesive['display_name']}")
    print(f"   Stars: {cohesive['total_stars']}, Repos: {cohesive['total_repos']}")
    print(f"   Languages: {cohesive['languages']}")
    print(f"   Topics: {cohesive['topics']}")

    # ── Step 8: Get cohesive profile ──
    resp = await async_client.get(
        f"/api/v1/developer-profile/{profile_id}/cohesive"
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["display_name"] == "Linus Torvalds"
    print("✅ Got cohesive profile")

    # ── Step 9: Get ranking ──
    resp = await async_client.get(
        f"/api/v1/developer-profile/{profile_id}/ranking"
    )
    assert resp.status_code == 200, resp.json()
    ranking = resp.json()["result"]
    assert float(ranking["composite_score"]) > 0
    assert float(ranking["github_activity_score"]) > 0
    assert float(ranking["technical_influence_score"]) > 0
    assert float(ranking["oss_contribution_score"]) > 0
    print(f"✅ Got ranking scores:")
    print(f"   Composite: {ranking['composite_score']}")
    print(f"   GitHub Activity: {ranking['github_activity_score']}")
    print(f"   Technical Influence: {ranking['technical_influence_score']}")
    print(f"   OSS Contribution: {ranking['oss_contribution_score']}")
    print(f"   Skills Breadth: {ranking['skills_breadth_score']}")
    print(f"   Recency: {ranking['recency_score']}")

    # ── Step 10: Re-merge (idempotent) ──
    resp = await async_client.post(
        f"/api/v1/developer-profile/{profile_id}/merge"
    )
    assert resp.status_code == 200
    assert resp.json()["result"]["id"] == cohesive["id"]  # same cohesive profile
    print("✅ Re-merge is idempotent")

    # ── Step 11: Rank profiles ──
    resp = await async_client.post(
        "/api/v1/developer-profile/rank",
        json={"limit": 10},
    )
    assert resp.status_code == 200
    rank_result = resp.json()["result"]
    assert rank_result["total"] >= 1
    assert len(rank_result["items"]) >= 1
    assert rank_result["items"][0]["score"] > 0
    print(f"✅ Ranked {rank_result['total']} profiles")

    print("\n🎉 All 11 steps passed! Full E2E flow verified.")
