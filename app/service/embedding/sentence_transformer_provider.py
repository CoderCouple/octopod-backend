import asyncio
import logging

from app.service.embedding import EmbeddingProvider
from app.settings import settings

logger = logging.getLogger(__name__)

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        logger.info(f"Loading embedding model: {settings.embedding_model}")
        _model = SentenceTransformer(settings.embedding_model)
        logger.info("Embedding model loaded")
    return _model


class SentenceTransformerProvider(EmbeddingProvider):
    def __init__(self) -> None:
        self._model_name = settings.embedding_model

    async def embed(self, text: str) -> list[float]:
        model = _get_model()
        embedding = await asyncio.to_thread(model.encode, text, normalize_embeddings=True)
        return embedding.tolist()

    def dimension(self) -> int:
        return _get_model().get_sentence_embedding_dimension()
