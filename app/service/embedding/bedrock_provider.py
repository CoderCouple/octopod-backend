"""Bedrock-backed embedding providers.

Supports both Cohere Embed v3 and Amazon Titan Embed v2. Both produce
1024-dim vectors (compatible with the same Qdrant collection).

Cohere requires AWS Marketplace subscription (extra IAM step).
Titan is Amazon-native — no marketplace dance, cheaper ($0.02 vs
$0.10 per 1M tokens), and already enabled in any AWS account.
"""

import asyncio
import json
import logging

import boto3

from app.service.embedding import EmbeddingProvider
from app.settings import settings

logger = logging.getLogger(__name__)

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
    """Cohere Embed v3 via AWS Bedrock (1024-dim).

    NOTE: Requires AWS Marketplace subscription on first invocation
    (account-wide, one-time). If your IAM principal lacks
    aws-marketplace:Subscribe, use BedrockTitanEmbeddingProvider instead.
    """

    async def embed(self, text: str) -> list[float]:
        body = json.dumps(
            {
                "texts": [text],
                "input_type": "search_document",
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
        return 1024


class BedrockTitanEmbeddingProvider(EmbeddingProvider):
    """Amazon Titan Embed v2 via AWS Bedrock.

    Configurable output dim (256, 512, or 1024) via
    settings.embedding_dimension. Defaults to 1024 to match the
    developer_profiles_v2 Qdrant collection.
    """

    async def embed(self, text: str) -> list[float]:
        dim = settings.embedding_dimension if settings.embedding_dimension in (256, 512, 1024) else 1024
        body = json.dumps(
            {
                "inputText": text,
                "dimensions": dim,
                "normalize": True,
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
            return payload["embedding"]

        return await asyncio.to_thread(_call)

    def dimension(self) -> int:
        return settings.embedding_dimension if settings.embedding_dimension in (256, 512, 1024) else 1024
