"""Bedrock-backed embedding provider.

Uses Cohere Embed v3 (1024-dim) via AWS Bedrock. Network call per embed,
no model loaded in-process, container can be small.
"""

import asyncio
import json
import logging

import boto3

from app.service.embedding import EmbeddingProvider
from app.settings import settings

logger = logging.getLogger(__name__)

# Cohere Embed v3 outputs 1024 floats regardless of input.
_COHERE_EMBED_DIM = 1024


_client = None


def _get_client():
    """Lazy boto3 Bedrock Runtime client (one per process)."""
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime", region_name=settings.bedrock_region)
        logger.info(
            "Bedrock embedding client initialized (region=%s, model=%s)",
            settings.bedrock_region,
            settings.bedrock_embedding_model,
        )
    return _client


class BedrockCohereEmbeddingProvider(EmbeddingProvider):
    """Cohere Embed v3 via AWS Bedrock."""

    async def embed(self, text: str) -> list[float]:
        body = json.dumps(
            {
                "texts": [text],
                "input_type": "search_document",  # use search_query at query time if needed
                "truncate": "END",
            }
        )

        def _call() -> list[float]:
            client = _get_client()
            resp = client.invoke_model(
                modelId=settings.bedrock_embedding_model,
                body=body,
                contentType="application/json",
                accept="application/json",
            )
            payload = json.loads(resp["body"].read())
            return payload["embeddings"][0]

        return await asyncio.to_thread(_call)

    def dimension(self) -> int:
        return _COHERE_EMBED_DIM
