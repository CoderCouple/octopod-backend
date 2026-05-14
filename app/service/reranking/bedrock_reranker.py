"""Bedrock-backed reranker.

Uses Cohere Rerank v3.5 via AWS Bedrock. ~0.3s per call vs ~50s for
the local cross-encoder on CPU. No model loaded in-process.
"""

import asyncio
import json
import logging

import boto3

from app.service.reranking import RerankCandidate, Reranker, RerankResult
from app.settings import settings

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=settings.bedrock_region)
        logger.info(
            "Bedrock reranker client initialized (region=%s, model=%s)",
            settings.bedrock_region,
            settings.bedrock_rerank_model,
        )
    return _client


class BedrockCohereReranker(Reranker):
    """Cohere Rerank 3.5 via AWS Bedrock."""

    async def rerank(
        self, query: str, candidates: list[RerankCandidate], top_k: int = 20
    ) -> list[RerankResult]:
        if not candidates:
            return []

        # Cohere Rerank API: query + list of documents.
        # Returns indices into the original list, with relevance_score [0, 1].
        body = json.dumps(
            {
                "query": query,
                "documents": [c.text for c in candidates],
                "top_n": min(top_k, len(candidates)),
                "api_version": 2,
            }
        )

        def _call() -> list[dict]:
            client = _get_client()
            resp = client.invoke_model(
                modelId=settings.bedrock_rerank_model,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            payload = json.loads(resp["body"].read())
            return payload.get("results", [])

        ranked = await asyncio.to_thread(_call)

        results: list[RerankResult] = []
        for r in ranked:
            idx = r["index"]
            cand = candidates[idx]
            results.append(
                RerankResult(
                    profile_id=cand.profile_id,
                    rerank_score=float(r["relevance_score"]),
                    original_score=cand.original_score,
                )
            )
        return results
