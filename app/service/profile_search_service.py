import asyncio
import logging
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.request.developer_profile_request import SemanticSearchRequest
from app.api.v1.response.developer_profile_response import (
    CohesiveProfileResponse,
    ProfileRankingResponse,
    SearchResultResponse,
)
from app.db.repository.cohesive_individual_profile_repository import (
    CohesiveIndividualProfileRepository,
)
from app.db.repository.profile_ranking_repository import ProfileRankingRepository
from app.model.cohesive_individual_profile_model import CohesiveIndividualProfile
from app.service.embedding import EmbeddingProvider
from app.service.reranking import RerankCandidate, Reranker
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
        self.cip_repo = CohesiveIndividualProfileRepository(db)
        self.pr_repo = ProfileRankingRepository(db)
        self._embedding_provider = embedding_provider
        self._qdrant_client = qdrant_client
        self._reranker = reranker

    def _get_embedding_provider(self) -> EmbeddingProvider:
        if self._embedding_provider:
            return self._embedding_provider
        from app.service.embedding import get_embedding_provider

        self._embedding_provider = get_embedding_provider()
        return self._embedding_provider

    def _get_qdrant_client(self) -> Any:
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
        from app.service.reranking import get_reranker

        self._reranker = get_reranker()
        return self._reranker

    @staticmethod
    def _build_qdrant_filter(filters: dict | None) -> Any:
        if not filters:
            return None

        from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue, Range

        conditions: list[Any] = []
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
    def _build_payload(cip: CohesiveIndividualProfile) -> dict:
        return {
            "cohesive_individual_profile_id": cip.id,
            "developer_profile_id": cip.developer_profile_id,
            "languages": cip.languages or [],
            "skills": cip.skills or [],
            "total_stars": cip.total_stars or 0,
            "years_of_experience": cip.years_of_experience or 0,
            "location": (cip.location or "").lower(),
            "company": (cip.company or "").lower(),
            "topics": cip.topics or [],
            "total_contributions": cip.total_contributions or 0,
            "total_followers": cip.total_followers or 0,
            "total_hf_downloads": cip.total_hf_downloads or 0,
            "embedding_text": cip.embedding_text or "",
        }

    async def upsert_profile(self, cip: CohesiveIndividualProfile) -> str:
        from qdrant_client.models import PointStruct

        provider = self._get_embedding_provider()
        client = self._get_qdrant_client()

        text = str(cip.embedding_text or "")
        if not text:
            return ""

        vector = await provider.embed(text)
        point_id = str(cip.embedding_vector_id or uuid.uuid4())
        payload = self._build_payload(cip)

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
            cip_id = hit.payload.get("cohesive_individual_profile_id")
            if cip_id:
                results.append((cip_id, hit.score, hit.payload.get("embedding_text", "")))
        return results

    async def _keyword_search(
        self,
        query: str,
        request: SemanticSearchRequest,
        limit: int,
    ) -> list[tuple[str, float]]:
        try:
            results = await self.cip_repo.keyword_search(
                query=query,
                limit=limit,
                filters=request.filters,
            )
            return [(str(cip.id), score) for cip, score in results]
        except Exception:
            logger.debug("Keyword search unavailable (likely non-Postgres DB), skipping")
            return []

    async def _opensearch_search(
        self,
        query: str,
        request: SemanticSearchRequest,
        limit: int,
    ) -> list[tuple[str, float]]:
        """OpenSearch keyword search. Returns (profile_id, score) pairs."""
        if not settings.opensearch_enabled:
            return []
        try:
            from app.db.opensearch_client import search_profiles

            return search_profiles(query, limit=limit, filters=request.filters)
        except Exception:
            logger.debug("OpenSearch search unavailable, skipping")
            return []

    async def search(self, request: SemanticSearchRequest) -> list[SearchResultResponse]:
        provider = self._get_embedding_provider()

        # Step 1: Embed query
        query_vector = await provider.embed(request.query)

        # Step 2: Parallel vector + keyword + opensearch search
        vector_limit = min(request.limit * 15, 300)
        keyword_limit = min(request.limit * 10, 200)
        os_limit = min(request.limit * 10, 200)

        vector_task = self._vector_search(query_vector, request, vector_limit)
        keyword_task = self._keyword_search(request.query, request, keyword_limit)
        os_task = self._opensearch_search(request.query, request, os_limit)

        vector_hits, keyword_hits, os_hits = await asyncio.gather(
            vector_task, keyword_task, os_task
        )

        # Step 3: N-way RRF fusion
        vector_for_rrf = [(cip_id, score) for cip_id, score, _text in vector_hits]
        ranked_lists = [vector_for_rrf, keyword_hits]
        if os_hits:
            ranked_lists.append(os_hits)
        fused = reciprocal_rank_fusion(*ranked_lists)

        # Build id->embedding_text map from vector hits for reranking
        id_to_text: dict[str, str] = {}
        for cip_id, _score, emb_text in vector_hits:
            if emb_text:
                id_to_text[cip_id] = emb_text

        # Step 4: Rerank (if enabled)
        reranker = self._get_reranker() if request.rerank else None
        if reranker and fused:
            candidate_ids = [f.profile_id for f in fused[:200]]
            missing_ids = [cid for cid in candidate_ids if cid not in id_to_text]
            if missing_ids:
                missing_profiles = await self.cip_repo.list_by_ids(missing_ids)
                for mp in missing_profiles:
                    id_to_text[str(mp.id)] = str(mp.embedding_text or "")

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

        # Step 5: Batch fetch profiles + rankings
        profiles = await self.cip_repo.list_by_ids(final_ids)
        rankings = await self.pr_repo.list_by_cohesive_individual_profile_ids(final_ids)

        profile_map: dict[str, CohesiveIndividualProfile] = {
            str(cip.id): cip for cip in profiles
        }
        ranking_map = {str(r.cohesive_individual_profile_id): r for r in rankings}

        results: list[SearchResultResponse] = []
        for cip_id in final_ids:
            cip = profile_map.get(cip_id)
            if not cip:
                continue
            ranking = ranking_map.get(cip_id)
            ranking_resp = ProfileRankingResponse.model_validate(ranking) if ranking else None
            results.append(
                SearchResultResponse(
                    profile=CohesiveProfileResponse.model_validate(cip),
                    score=final_scores.get(cip_id, 0.0),
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
        from qdrant_client.models import PointStruct

        from app.db.qdrant_client import COLLECTION_NAME

        provider = self._get_embedding_provider()
        client = self._get_qdrant_client()

        stats = {"total": 0, "embedded": 0, "skipped": 0, "errors": 0}
        offset = 0

        while True:
            profiles, total = await self.cip_repo.list_all(offset=offset, limit=batch_size)
            if stats["total"] == 0:
                stats["total"] = total

            if not profiles:
                break

            points: list = []
            for cip in profiles:
                text = cip.embedding_text or ""
                if not text:
                    stats["skipped"] += 1
                    continue

                if not force and cip.embedding_vector_id:
                    stats["skipped"] += 1
                    continue

                try:
                    vector = await provider.embed(str(text))
                    point_id = str(cip.embedding_vector_id or uuid.uuid4())
                    payload = self._build_payload(cip)
                    points.append(PointStruct(id=point_id, vector=vector, payload=payload))

                    if not cip.embedding_vector_id:
                        cip.embedding_vector_id = point_id  # type: ignore[assignment]
                    stats["embedded"] += 1
                except Exception:
                    logger.exception(f"Failed to embed profile {cip.id}")
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
