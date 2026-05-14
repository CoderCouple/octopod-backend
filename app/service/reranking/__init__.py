from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class RerankCandidate:
    profile_id: str
    text: str
    original_score: float


@dataclass
class RerankResult:
    profile_id: str
    rerank_score: float
    original_score: float


class Reranker(ABC):
    @abstractmethod
    async def rerank(
        self, query: str, candidates: list[RerankCandidate], top_k: int = 20
    ) -> list[RerankResult]:
        ...


def get_reranker() -> Reranker:
    """Factory: dispatch to the configured reranker backend.

    Driven by ``settings.reranker_provider``:
      * ``local`` -> CrossEncoderReranker (default, sentence-transformers, slow on CPU)
      * ``bedrock_cohere`` -> Cohere Rerank 3.5 via AWS Bedrock (sub-second)
    """
    from app.settings import settings

    if settings.reranker_provider == "bedrock_cohere":
        from app.service.reranking.bedrock_reranker import BedrockCohereReranker

        return BedrockCohereReranker()
    from app.service.reranking.cross_encoder_reranker import CrossEncoderReranker

    return CrossEncoderReranker()
