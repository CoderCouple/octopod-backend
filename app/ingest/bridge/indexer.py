"""DualIndexer: indexes profiles to both Qdrant and OpenSearch."""
from __future__ import annotations

import logging
import uuid
from typing import Any

log = logging.getLogger(__name__)


class DualIndexer:
    """Indexes cohesive profiles to Qdrant (vector ANN) and optionally OpenSearch (keyword)."""

    def __init__(
        self,
        qdrant_client: Any = None,
        opensearch_client: Any = None,
        embedding_provider: Any = None,
    ):
        self._qdrant = qdrant_client
        self._opensearch = opensearch_client
        self._embedder = embedding_provider

    async def index_profile(self, profile_data: dict[str, Any]) -> dict[str, str]:
        """Index a single profile to both search engines.

        Returns dict with vector_id and opensearch status.
        """
        results: dict[str, str] = {}

        # Qdrant vector index
        if self._qdrant and self._embedder:
            try:
                embedding_text = profile_data.get("embedding_text", "")
                if embedding_text:
                    vector = await self._embedder.embed(embedding_text)
                    point_id = profile_data.get("embedding_vector_id") or str(uuid.uuid4())

                    from qdrant_client.models import PointStruct

                    from app.db.qdrant_client import COLLECTION_NAME

                    payload = _build_qdrant_payload(profile_data)
                    self._qdrant.upsert(
                        collection_name=COLLECTION_NAME,
                        points=[PointStruct(id=point_id, vector=vector, payload=payload)],
                    )
                    results["vector_id"] = point_id
            except Exception:
                log.exception("Failed to index to Qdrant")

        # OpenSearch keyword index
        if self._opensearch:
            try:
                from app.settings import settings

                doc = _build_opensearch_doc(profile_data)
                doc_id = profile_data.get("cohesive_individual_profile_id") or profile_data.get("id")
                self._opensearch.index(
                    index=settings.opensearch_index,
                    id=doc_id,
                    body=doc,
                )
                results["opensearch"] = "indexed"
            except Exception:
                log.exception("Failed to index to OpenSearch")

        return results

    async def batch_index(
        self, profiles: list[dict[str, Any]]
    ) -> dict[str, int]:
        """Batch index multiple profiles. Returns counts."""
        stats = {"qdrant": 0, "opensearch": 0, "errors": 0}
        for p in profiles:
            try:
                result = await self.index_profile(p)
                if "vector_id" in result:
                    stats["qdrant"] += 1
                if "opensearch" in result:
                    stats["opensearch"] += 1
            except Exception:
                stats["errors"] += 1
        return stats


def _build_qdrant_payload(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "cohesive_individual_profile_id": data.get("id"),
        "developer_profile_id": data.get("developer_profile_id"),
        "languages": data.get("languages", []),
        "skills": data.get("skills", []),
        "total_stars": data.get("total_stars", 0),
        "years_of_experience": data.get("years_of_experience", 0),
        "location": (data.get("location") or "").lower(),
        "company": (data.get("company") or "").lower(),
        "topics": data.get("topics", []),
        "total_contributions": data.get("total_contributions", 0),
        "total_followers": data.get("total_followers", 0),
        "total_hf_downloads": data.get("total_hf_downloads", 0),
        "embedding_text": data.get("embedding_text", ""),
    }


def _build_opensearch_doc(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "cohesive_individual_profile_id": data.get("id"),
        "developer_profile_id": data.get("developer_profile_id"),
        "display_name": data.get("display_name"),
        "headline": data.get("headline"),
        "bio": data.get("bio"),
        "location": data.get("location"),
        "company": data.get("company"),
        "languages": data.get("languages", []),
        "skills": data.get("skills", []),
        "topics": data.get("topics", []),
        "total_stars": data.get("total_stars", 0),
        "total_contributions": data.get("total_contributions", 0),
        "total_followers": data.get("total_followers", 0),
        "total_hf_downloads": data.get("total_hf_downloads", 0),
        "years_of_experience": data.get("years_of_experience"),
        "job_history": data.get("job_history", []),
        "embedding_text": data.get("embedding_text"),
        "merged_at": data.get("merged_at"),
    }
