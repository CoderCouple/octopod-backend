"""OpenSearch client singleton and index management."""
from __future__ import annotations

import logging
from typing import Any

from app.settings import settings

log = logging.getLogger(__name__)

_client = None

INDEX_MAPPING = {
    "mappings": {
        "properties": {
            "cohesive_individual_profile_id": {"type": "keyword"},
            "developer_profile_id": {"type": "keyword"},
            "display_name": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "headline": {"type": "text"},
            "bio": {"type": "text"},
            "location": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "company": {
                "type": "text",
                "fields": {"keyword": {"type": "keyword"}},
            },
            "languages": {"type": "keyword"},
            "skills": {"type": "keyword"},
            "topics": {"type": "keyword"},
            "total_stars": {"type": "integer"},
            "total_contributions": {"type": "integer"},
            "total_followers": {"type": "integer"},
            "total_hf_downloads": {"type": "long"},
            "years_of_experience": {"type": "integer"},
            "job_history": {
                "type": "nested",
                "properties": {
                    "company": {"type": "text"},
                    "title": {"type": "text"},
                },
            },
            "embedding_text": {"type": "text"},
            "merged_at": {"type": "date"},
        }
    },
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
    },
}


def get_opensearch_client() -> Any:
    """Get or create the OpenSearch client singleton."""
    global _client
    if _client is not None:
        return _client

    if not settings.opensearch_enabled:
        return None

    from opensearchpy import OpenSearch

    _client = OpenSearch(
        hosts=[{"host": settings.opensearch_host, "port": settings.opensearch_port}],
        use_ssl=settings.opensearch_use_ssl,
        verify_certs=False,
        ssl_show_warn=False,
    )
    return _client


async def ensure_index() -> None:
    """Create the OpenSearch index if it doesn't exist."""
    client = get_opensearch_client()
    if client is None:
        return

    index_name = settings.opensearch_index
    try:
        if not client.indices.exists(index=index_name):
            client.indices.create(index=index_name, body=INDEX_MAPPING)
            log.info("Created OpenSearch index: %s", index_name)
        else:
            log.info("OpenSearch index already exists: %s", index_name)
    except Exception:
        log.warning("Failed to create OpenSearch index (OpenSearch may be unavailable)")


def search_profiles(
    query: str,
    limit: int = 20,
    filters: dict | None = None,
) -> list[tuple[str, float]]:
    """Keyword search in OpenSearch. Returns (profile_id, score) pairs."""
    client = get_opensearch_client()
    if client is None:
        return []

    must_clauses: list[dict[str, Any]] = [
        {
            "multi_match": {
                "query": query,
                "fields": [
                    "display_name^3",
                    "headline^2",
                    "bio",
                    "skills^2",
                    "languages",
                    "topics",
                    "embedding_text",
                    "company",
                    "location",
                ],
                "type": "best_fields",
                "fuzziness": "AUTO",
            }
        }
    ]

    filter_clauses: list[dict[str, Any]] = []
    if filters:
        if filters.get("languages"):
            filter_clauses.append({"terms": {"languages": filters["languages"]}})
        if filters.get("skills"):
            filter_clauses.append({"terms": {"skills": filters["skills"]}})
        if filters.get("min_stars") is not None:
            filter_clauses.append(
                {"range": {"total_stars": {"gte": filters["min_stars"]}}}
            )
        if filters.get("min_experience_years") is not None:
            filter_clauses.append(
                {"range": {"years_of_experience": {"gte": filters["min_experience_years"]}}}
            )
        if filters.get("location"):
            filter_clauses.append(
                {"match": {"location.keyword": filters["location"]}}
            )
        if filters.get("company"):
            filter_clauses.append(
                {"match": {"company.keyword": filters["company"]}}
            )

    bool_query: dict[str, Any] = {"must": must_clauses}
    if filter_clauses:
        bool_query["filter"] = filter_clauses

    body: dict[str, Any] = {
        "size": limit,
        "query": {"bool": bool_query},
    }

    try:
        resp = client.search(index=settings.opensearch_index, body=body)
        results = []
        for hit in resp.get("hits", {}).get("hits", []):
            cip_id = hit["_source"].get("cohesive_individual_profile_id")
            if cip_id:
                results.append((cip_id, hit["_score"]))
        return results
    except Exception:
        log.exception("OpenSearch search failed")
        return []
