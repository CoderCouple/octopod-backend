"""User API controller."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tags import Tags
from app.api.v1.request.user_request import SwitchContextRequest, UpdateProfileRequest
from app.api.v1.response.base_response import BaseResponse, success_response
from app.api.v1.response.user_response import UserContextResponse, UserResponse
from app.common.auth.auth import UserContext, get_user_context
from app.db.session import get_db
from app.service.user_service import UserService

router = APIRouter(tags=[Tags.User])


def get_user_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


@router.get("/me", response_model=BaseResponse[UserContextResponse])
async def get_current_user_profile(
    ctx: UserContext = Depends(get_user_context),
    service: UserService = Depends(get_user_service),
):
    """Get the current authenticated user with active org/project context."""
    user = await service.get_user(ctx.user_id)
    user_resp = UserResponse.model_validate(user)
    result = UserContextResponse(
        user=user_resp,
        organization_id=ctx.organization_id,
        project_id=ctx.project_id,
        role=ctx.role,
    )
    return success_response(result, "User profile fetched")


@router.patch("/me", response_model=BaseResponse[UserResponse])
async def update_current_user_profile(
    body: UpdateProfileRequest,
    ctx: UserContext = Depends(get_user_context),
    service: UserService = Depends(get_user_service),
):
    """Update the current user's display name or avatar."""
    user = await service.update_profile(
        ctx.user_id, display_name=body.display_name, avatar_url=body.avatar_url
    )
    return success_response(UserResponse.model_validate(user), "Profile updated")


@router.put("/me/context", response_model=BaseResponse[UserResponse])
async def switch_context(
    body: SwitchContextRequest,
    ctx: UserContext = Depends(get_user_context),
    service: UserService = Depends(get_user_service),
):
    """Switch the active organization and/or project."""
    user = await service.switch_context(
        ctx.user_id, org_id=body.organization_id, project_id=body.project_id
    )
    return success_response(UserResponse.model_validate(user), "Context switched")
