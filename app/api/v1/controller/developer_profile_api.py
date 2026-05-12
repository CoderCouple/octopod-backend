from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tags import Tags
from app.api.v1.request.developer_profile_request import (
    CreateDeveloperProfileRequest,
    RankProfilesRequest,
    SemanticSearchRequest,
    UpdateDeveloperProfileRequest,
)
from app.api.v1.response.base_response import BaseResponse, success_response
from app.api.v1.response.developer_profile_response import (
    CohesiveProfileResponse,
    DeveloperProfileResponse,
    ProfileRankingResponse,
    SearchResultResponse,
)
from app.common.auth.auth import UserContext, get_user_context
from app.common.pagination import PaginatedResponse
from app.db.session import get_db
from app.service.developer_profile_service import DeveloperProfileService
from app.service.profile_merge_service import ProfileMergeService
from app.service.profile_ranking_service import ProfileRankingService
from app.service.profile_search_service import ProfileSearchService

router = APIRouter(tags=[Tags.DeveloperProfile])


def get_profile_service(db: AsyncSession = Depends(get_db)) -> DeveloperProfileService:
    return DeveloperProfileService(db)


def get_merge_service(db: AsyncSession = Depends(get_db)) -> ProfileMergeService:
    return ProfileMergeService(db)


def get_ranking_service(db: AsyncSession = Depends(get_db)) -> ProfileRankingService:
    return ProfileRankingService(db)


def get_search_service(db: AsyncSession = Depends(get_db)) -> ProfileSearchService:
    return ProfileSearchService(db)


@router.post(
    "/developer-profile",
    response_model=BaseResponse[DeveloperProfileResponse],
    status_code=201,
)
async def create_developer_profile(
    body: CreateDeveloperProfileRequest,
    ctx: UserContext = Depends(get_user_context),
    service: DeveloperProfileService = Depends(get_profile_service),
) -> BaseResponse:
    profile = await service.create_profile(
        body, ctx.user_id, project_id=ctx.project_id, org_id=ctx.organization_id
    )
    return success_response(profile, "Developer profile created", 201)


@router.get(
    "/developer-profile",
    response_model=BaseResponse[PaginatedResponse[DeveloperProfileResponse]],
)
async def list_developer_profiles(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    _ctx: UserContext = Depends(get_user_context),
    service: DeveloperProfileService = Depends(get_profile_service),
) -> BaseResponse:
    profiles, total = await service.list_profiles(offset, limit)
    page = PaginatedResponse(items=profiles, total=total, offset=offset, limit=limit)
    return success_response(page, "Developer profiles fetched")


@router.get(
    "/developer-profile/{profile_id}",
    response_model=BaseResponse[DeveloperProfileResponse],
)
async def get_developer_profile(
    profile_id: str,
    _ctx: UserContext = Depends(get_user_context),
    service: DeveloperProfileService = Depends(get_profile_service),
) -> BaseResponse:
    profile = await service.get_profile(profile_id)
    return success_response(profile, "Developer profile fetched")


@router.patch(
    "/developer-profile/{profile_id}",
    response_model=BaseResponse[DeveloperProfileResponse],
)
async def update_developer_profile(
    profile_id: str,
    body: UpdateDeveloperProfileRequest,
    ctx: UserContext = Depends(get_user_context),
    service: DeveloperProfileService = Depends(get_profile_service),
) -> BaseResponse:
    profile = await service.update_profile(profile_id, body, ctx.user_id)
    return success_response(profile, "Developer profile updated")


@router.get(
    "/developer-profile/{profile_id}/cohesive",
    response_model=BaseResponse[CohesiveProfileResponse],
)
async def get_cohesive_profile(
    profile_id: str,
    _ctx: UserContext = Depends(get_user_context),
    merge_service: ProfileMergeService = Depends(get_merge_service),
) -> BaseResponse:
    cohesive = await merge_service.get_cohesive_profile(profile_id)
    return success_response(cohesive, "Cohesive profile fetched")


@router.post(
    "/developer-profile/{profile_id}/merge",
    response_model=BaseResponse[CohesiveProfileResponse],
)
async def force_merge(
    profile_id: str,
    _ctx: UserContext = Depends(get_user_context),
    merge_service: ProfileMergeService = Depends(get_merge_service),
) -> BaseResponse:
    cohesive = await merge_service.merge_profile(profile_id)
    return success_response(cohesive, "Profile merged")


@router.get(
    "/developer-profile/{profile_id}/ranking",
    response_model=BaseResponse[ProfileRankingResponse],
)
async def get_ranking(
    profile_id: str,
    _ctx: UserContext = Depends(get_user_context),
    ranking_service: ProfileRankingService = Depends(get_ranking_service),
) -> BaseResponse:
    ranking = await ranking_service.get_ranking(profile_id)
    return success_response(ranking, "Ranking fetched")


@router.post(
    "/developer-profile/rank",
    response_model=BaseResponse[PaginatedResponse[SearchResultResponse]],
)
async def rank_profiles(
    body: RankProfilesRequest,
    _ctx: UserContext = Depends(get_user_context),
    ranking_service: ProfileRankingService = Depends(get_ranking_service),
) -> BaseResponse:
    results, total = await ranking_service.rank_profiles(body)
    page = PaginatedResponse(items=results, total=total, offset=body.offset, limit=body.limit)
    return success_response(page, "Profiles ranked")


@router.post(
    "/developer-profile/search",
    response_model=BaseResponse[list[SearchResultResponse]],
)
async def search_profiles(
    body: SemanticSearchRequest,
    _ctx: UserContext = Depends(get_user_context),
    search_service: ProfileSearchService = Depends(get_search_service),
) -> BaseResponse:
    results = await search_service.search(body)
    return success_response(results, "Search completed")


@router.post(
    "/developer-profile/embed-all",
    response_model=BaseResponse[dict],
    status_code=202,
)
async def embed_all_profiles(
    background_tasks: BackgroundTasks,
    batch_size: int = Query(default=100, ge=1, le=1000),
    force: bool = Query(default=False),
    _ctx: UserContext = Depends(get_user_context),
    search_service: ProfileSearchService = Depends(get_search_service),
) -> BaseResponse:
    """Trigger batch embedding of all cohesive profiles."""

    async def _run_embed() -> None:
        try:
            stats = await search_service.batch_embed_profiles(
                batch_size=batch_size, force=force
            )
            import logging

            logging.getLogger(__name__).info(f"Batch embedding completed: {stats}")
        except Exception:
            import logging

            logging.getLogger(__name__).exception("Batch embedding failed")

    background_tasks.add_task(_run_embed)
    return success_response(
        {"status": "started", "batch_size": batch_size, "force": force},
        "Batch embedding started",
        202,
    )
