import asyncio
import logging
import uuid
from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.request.developer_profile_request import SemanticSearchRequest
from app.api.v1.response.developer_profile_response import (
    CohesiveProfileResponse,
    ProfileRankingResponse,
    SearchResultResponse,
)
from app.db.repository.cohesive_profile_repository import CohesiveProfileRepository
from app.db.repository.profile_ranking_repository import ProfileRankingRepository
from app.model.cohesive_profile_model import CohesiveProfile
from app.service.embedding import EmbeddingProvider
from app.service.reranking import Reranker, RerankCandidate
from app.service.search.fusion import reciprocal_rank_fusion
from app.settings import settings

logger = logging.getLogger(__name__)


class ProfileSearchService:
    def __init__(
        self,
        db: AsyncSession,
        embedding_provider: EmbeddingProvider | None = None,
        qdrant_client: object | None = None,
        reranker: Reranker | None = None,
    ):
        self.db = db
        self.cp_repo = CohesiveProfileRepository(db)
        self.pr_repo = ProfileRankingRepository(db)
        self._embedding_provider = embedding_provider
        self._qdrant_client = qdrant_client
        self._reranker = reranker

    def _get_embedding_provider(self) -> EmbeddingProvider:
        if self._embedding_provider:
            return self._embedding_provider
        from app.service.embedding.sentence_transformer_provider import (
            SentenceTransformerProvider,
        )

        self._embedding_provider = SentenceTransformerProvider()
        return self._embedding_provider

    def _get_qdrant_client(self):
        if self._qdrant_client:
            return self._qdrant_client
        from app.db.qdrant_client import get_qdrant_client

        self._qdrant_client = get_qdrant_client()
        return self._qdrant_client

    def _get_reranker(self) -> Reranker | None:
        if self._reranker:
            return self._reranker
        if not settings.reranker_enabled:
            return None
        from app.service.reranking.cross_encoder_reranker import CrossEncoderReranker

        self._reranker = CrossEncoderReranker()
        return self._reranker

    @staticmethod
    def _build_qdrant_filter(filters: dict | None):
        """Build a Qdrant Filter from request filters dict."""
        if not filters:
            return None

        from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue, Range

        conditions = []
        if filters.get("languages"):
            conditions.append(
                FieldCondition(key="languages", match=MatchAny(any=filters["languages"]))
            )
        if filters.get("skills"):
            conditions.append(
                FieldCondition(key="skills", match=MatchAny(any=filters["skills"]))
            )
        if filters.get("min_stars") is not None:
            conditions.append(
                FieldCondition(key="total_stars", range=Range(gte=filters["min_stars"]))
            )
        if filters.get("min_experience_years") is not None:
            conditions.append(
                FieldCondition(
                    key="years_of_experience",
                    range=Range(gte=filters["min_experience_years"]),
                )
            )
        if filters.get("location"):
            conditions.append(
                FieldCondition(key="location", match=MatchValue(value=filters["location"].lower()))
            )
        if filters.get("company"):
            conditions.append(
                FieldCondition(key="company", match=MatchValue(value=filters["company"].lower()))
            )
        if filters.get("topics"):
            conditions.append(
                FieldCondition(key="topics", match=MatchAny(any=filters["topics"]))
            )
        if filters.get("min_contributions") is not None:
            conditions.append(
                FieldCondition(
                    key="total_contributions",
                    range=Range(gte=filters["min_contributions"]),
                )
            )
        if filters.get("min_followers") is not None:
            conditions.append(
                FieldCondition(
                    key="total_followers",
                    range=Range(gte=filters["min_followers"]),
                )
            )

        return Filter(must=conditions) if conditions else None

    @staticmethod
    def _build_payload(cp: CohesiveProfile) -> dict:
        """Build Qdrant point payload from a CohesiveProfile."""
        return {
            "cohesive_profile_id": cp.id,
            "developer_profile_id": cp.developer_profile_id,
            "languages": cp.languages or [],
            "skills": cp.skills or [],
            "total_stars": cp.total_stars or 0,
            "years_of_experience": cp.years_of_experience or 0,
            "location": (cp.location or "").lower(),
            "company": (cp.company or "").lower(),
            "topics": cp.topics or [],
            "total_contributions": cp.total_contributions or 0,
            "total_followers": cp.total_followers or 0,
            "total_hf_downloads": cp.total_hf_downloads or 0,
        }

    async def upsert_profile(self, cp: CohesiveProfile) -> str:
        from qdrant_client.models import PointStruct

        provider = self._get_embedding_provider()
        client = self._get_qdrant_client()

        text = cp.embedding_text or ""
        if not text:
            return ""

        vector = await provider.embed(text)
        point_id = cp.embedding_vector_id or str(uuid.uuid4())
        payload = self._build_payload(cp)

        from app.db.qdrant_client import COLLECTION_NAME

        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )

        return point_id

    async def _vector_search(
        self,
        query_vector: list[float],
        request: SemanticSearchRequest,
        limit: int,
    ) -> list[tuple[str, float, str]]:
        """Vector ANN search via Qdrant. Returns (cohesive_profile_id, score, embedding_text)."""
        client = self._get_qdrant_client()
        query_filter = self._build_qdrant_filter(request.filters)

        from app.db.qdrant_client import COLLECTION_NAME

        response = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=query_filter,
            limit=limit,
            score_threshold=request.min_score if request.min_score > 0 else None,
        )

        results = []
        for hit in response.points:
            cp_id = hit.payload.get("cohesive_profile_id")
            if cp_id:
                results.append((cp_id, hit.score, ""))
        return results

    async def _keyword_search(
        self,
        query: str,
        request: SemanticSearchRequest,
        limit: int,
    ) -> list[tuple[str, float]]:
        """Postgres tsvector keyword search. Returns (cohesive_profile_id, ts_rank).
        Gracefully returns [] on failure (e.g. SQLite in tests).
        """
        try:
            results = await self.cp_repo.keyword_search(
                query=query,
                limit=limit,
                filters=request.filters,
            )
            return [(cp.id, score) for cp, score in results]
        except Exception:
            logger.debug("Keyword search unavailable (likely non-Postgres DB), skipping")
            return []

    async def search(self, request: SemanticSearchRequest) -> list[SearchResultResponse]:
        provider = self._get_embedding_provider()

        # Step 1: Embed query
        query_vector = await provider.embed(request.query)

        # Step 2: Parallel vector + keyword search (over-fetch for fusion)
        vector_limit = min(request.limit * 15, 300)
        keyword_limit = min(request.limit * 10, 200)

        vector_task = self._vector_search(query_vector, request, vector_limit)
        keyword_task = self._keyword_search(request.query, request, keyword_limit)
        vector_hits, keyword_hits = await asyncio.gather(vector_task, keyword_task)

        # Step 3: RRF fusion
        vector_for_rrf = [(cp_id, score) for cp_id, score, _text in vector_hits]
        fused = reciprocal_rank_fusion(vector_for_rrf, keyword_hits)

        # Build id->embedding_text map from vector hits for reranking
        id_to_text: dict[str, str] = {}
        for cp_id, _score, emb_text in vector_hits:
            if emb_text:
                id_to_text[cp_id] = emb_text

        # Step 4: Rerank (if enabled)
        reranker = self._get_reranker() if request.rerank else None
        if reranker and fused:
            # Fetch embedding_text for candidates that don't have it from vector hits
            candidate_ids = [f.profile_id for f in fused[:200]]
            missing_ids = [cid for cid in candidate_ids if cid not in id_to_text]
            if missing_ids:
                missing_profiles = await self.cp_repo.list_by_ids(missing_ids)
                for mp in missing_profiles:
                    id_to_text[mp.id] = mp.embedding_text or ""

            candidates = [
                RerankCandidate(
                    profile_id=f.profile_id,
                    text=id_to_text.get(f.profile_id, ""),
                    original_score=f.rrf_score,
                )
                for f in fused[:200]
            ]
            rerank_results = await reranker.rerank(
                request.query, candidates, top_k=request.limit
            )
            final_ids = [r.profile_id for r in rerank_results]
            final_scores = {r.profile_id: r.rerank_score for r in rerank_results}
        else:
            final_ids = [f.profile_id for f in fused[: request.limit]]
            final_scores = {f.profile_id: f.rrf_score for f in fused[: request.limit]}

        if not final_ids:
            return []

        # Step 5: Batch fetch profiles + rankings (fixes N+1)
        profiles = await self.cp_repo.list_by_ids(final_ids)
        rankings = await self.pr_repo.list_by_cohesive_profile_ids(final_ids)

        profile_map = {cp.id: cp for cp in profiles}
        ranking_map = {r.cohesive_profile_id: r for r in rankings}

        # Build results in score order
        results: list[SearchResultResponse] = []
        for cp_id in final_ids:
            cp = profile_map.get(cp_id)
            if not cp:
                continue
            ranking = ranking_map.get(cp_id)
            ranking_resp = ProfileRankingResponse.model_validate(ranking) if ranking else None
            results.append(
                SearchResultResponse(
                    profile=CohesiveProfileResponse.model_validate(cp),
                    score=final_scores.get(cp_id, 0.0),
                    ranking=ranking_resp,
                )
            )

        return results

    async def batch_embed_profiles(
        self,
        batch_size: int = 100,
        force: bool = False,
        progress_callback: Callable[[dict], None] | None = None,
    ) -> dict:
        """Embed all CohesiveProfiles and upsert to Qdrant in batches.

        Args:
            batch_size: Number of profiles per batch.
            force: Re-embed even if already embedded.
            progress_callback: Optional callback receiving progress dict.

        Returns:
            Dict with total, embedded, skipped, errors counts.
        """
        from qdrant_client.models import PointStruct

        from app.db.qdrant_client import COLLECTION_NAME

        provider = self._get_embedding_provider()
        client = self._get_qdrant_client()

        stats = {"total": 0, "embedded": 0, "skipped": 0, "errors": 0}
        offset = 0

        while True:
            profiles, total = await self.cp_repo.list_all(offset=offset, limit=batch_size)
            if stats["total"] == 0:
                stats["total"] = total

            if not profiles:
                break

            points: list = []
            for cp in profiles:
                text = cp.embedding_text or ""
                if not text:
                    stats["skipped"] += 1
                    continue

                if not force and cp.embedding_vector_id:
                    stats["skipped"] += 1
                    continue

                try:
                    vector = await provider.embed(text)
                    point_id = cp.embedding_vector_id or str(uuid.uuid4())
                    payload = self._build_payload(cp)
                    points.append(PointStruct(id=point_id, vector=vector, payload=payload))

                    if not cp.embedding_vector_id:
                        cp.embedding_vector_id = point_id
                    stats["embedded"] += 1
                except Exception:
                    logger.exception(f"Failed to embed profile {cp.id}")
                    stats["errors"] += 1

            if points:
                client.upsert(collection_name=COLLECTION_NAME, points=points)
                await self.db.flush()

            offset += batch_size

            if progress_callback:
                progress_callback(stats)

            logger.info(
                f"Batch embed progress: {stats['embedded']+stats['skipped']}/{stats['total']}"
            )

        return stats
