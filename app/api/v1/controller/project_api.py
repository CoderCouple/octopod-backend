"""Project API controller."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tags import Tags
from app.api.v1.request.project_request import CreateProjectRequest, UpdateProjectRequest
from app.api.v1.response.base_response import BaseResponse, success_response
from app.api.v1.response.project_response import ProjectResponse
from app.common.auth.auth import UserContext, get_user_context, require_role
from app.common.pagination import PaginatedResponse
from app.db.session import get_db
from app.service.project_service import ProjectService

router = APIRouter(tags=[Tags.Project])


def get_project_service(db: AsyncSession = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


@router.post("/project", response_model=BaseResponse[ProjectResponse], status_code=201)
async def create_project(
    body: CreateProjectRequest,
    ctx: UserContext = Depends(require_role("owner", "admin")),
    service: ProjectService = Depends(get_project_service),
):
    """Create a new project in the active organization."""
    result = await service.create_project(
        ctx.organization_id, body.name, body.description, body.slug, ctx.user_id
    )
    return success_response(result, "Project created", 201)


@router.get("/project", response_model=BaseResponse[PaginatedResponse[ProjectResponse]])
async def list_projects(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    ctx: UserContext = Depends(get_user_context),
    service: ProjectService = Depends(get_project_service),
):
    """List projects in the active organization."""
    projects, total = await service.list_projects(ctx.organization_id, offset, limit)
    page = PaginatedResponse(items=projects, total=total, offset=offset, limit=limit)
    return success_response(page, "Projects fetched")


@router.get("/project/{project_id}", response_model=BaseResponse[ProjectResponse])
async def get_project(
    project_id: str,
    _ctx: UserContext = Depends(get_user_context),
    service: ProjectService = Depends(get_project_service),
):
    """Get project details."""
    result = await service.get_project(project_id)
    return success_response(result, "Project fetched")


@router.patch("/project/{project_id}", response_model=BaseResponse[ProjectResponse])
async def update_project(
    project_id: str,
    body: UpdateProjectRequest,
    ctx: UserContext = Depends(require_role("owner", "admin")),
    service: ProjectService = Depends(get_project_service),
):
    """Update project details."""
    result = await service.update_project(
        project_id, name=body.name, description=body.description, actor_id=ctx.user_id
    )
    return success_response(result, "Project updated")


@router.delete("/project/{project_id}", response_model=BaseResponse)
async def delete_project(
    project_id: str,
    ctx: UserContext = Depends(require_role("owner", "admin")),
    service: ProjectService = Depends(get_project_service),
):
    """Soft-delete a project."""
    await service.delete_project(project_id, ctx.user_id)
    return success_response(None, "Project deleted")
