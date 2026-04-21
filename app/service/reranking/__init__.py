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
