from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...

    @abstractmethod
    def dimension(self) -> int:
        ...


def get_embedding_provider() -> EmbeddingProvider:
    """Factory: dispatch to the configured embedding backend.

    Driven by ``settings.embedding_provider``:
      * ``sentence_transformer`` -> local SentenceTransformer (default)
      * ``bedrock_titan`` -> Titan Embed v2 via Bedrock (1024 dim, no marketplace)
      * ``bedrock_cohere`` -> Cohere Embed v3 via Bedrock (1024 dim, marketplace)
    """
    from app.settings import settings

    if settings.embedding_provider == "bedrock_titan":
        from app.service.embedding.bedrock_provider import BedrockTitanEmbeddingProvider

        return BedrockTitanEmbeddingProvider()
    if settings.embedding_provider == "bedrock_cohere":
        from app.service.embedding.bedrock_provider import BedrockCohereEmbeddingProvider

        return BedrockCohereEmbeddingProvider()
    from app.service.embedding.sentence_transformer_provider import (
        SentenceTransformerProvider,
    )

    return SentenceTransformerProvider()
