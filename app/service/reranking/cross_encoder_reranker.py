import asyncio
import logging

from app.service.reranking import RerankCandidate, Reranker, RerankResult
from app.settings import settings

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder

        logger.info(f"Loading reranker model: {settings.reranker_model}")
        _model = CrossEncoder(settings.reranker_model)
        logger.info("Reranker model loaded")
    return _model


class CrossEncoderReranker(Reranker):
    async def rerank(
        self, query: str, candidates: list[RerankCandidate], top_k: int = 20
    ) -> list[RerankResult]:
        if not candidates:
            return []

        model = _get_model()
        pairs = [[query, c.text] for c in candidates]
        scores = await asyncio.to_thread(model.predict, pairs)

        results = [
            RerankResult(
                profile_id=c.profile_id,
                rerank_score=float(score),
                original_score=c.original_score,
            )
            for c, score in zip(candidates, scores, strict=True)
        ]
        results.sort(key=lambda r: r.rerank_score, reverse=True)
        return results[:top_k]
