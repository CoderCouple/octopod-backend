import re
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.response.project_response import ProjectResponse
from app.common.exceptions import DuplicateEntityError, EntityNotFoundError
from app.db.repository.project_repository import ProjectRepository
from app.model.project_model import Project


def _slugify(text: str) -> str:
    slug = text.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


class ProjectService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.project_repo = ProjectRepository(db)

    async def create_project(
        self, org_id: str, name: str, description: str | None = None,
        slug: str | None = None, actor_id: str | None = None,
    ) -> ProjectResponse:
        final_slug = slug or _slugify(name)
        existing = await self.project_repo.get_by_org_and_slug(org_id, final_slug)
        if existing:
            raise DuplicateEntityError("Project", "slug", final_slug)

        project = Project(
            org_id=org_id,
            name=name,
            slug=final_slug,
            description=description,
            created_by=actor_id,
            updated_by=actor_id,
        )
        project = await self.project_repo.create(project)
        return ProjectResponse.model_validate(project)

    async def get_project(self, project_id: str) -> ProjectResponse:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise EntityNotFoundError("Project", project_id)
        return ProjectResponse.model_validate(project)

    async def list_projects(
        self, org_id: str, offset: int = 0, limit: int = 20
    ) -> tuple[list[ProjectResponse], int]:
        projects, total = await self.project_repo.list_by_org(org_id, offset, limit)
        return [ProjectResponse.model_validate(p) for p in projects], total

    async def update_project(
        self, project_id: str, name: str | None = None,
        description: str | None = None, actor_id: str | None = None,
    ) -> ProjectResponse:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise EntityNotFoundError("Project", project_id)

        if name is not None:
            project.name = name
        if description is not None:
            project.description = description
        project.updated_by = actor_id
        project.updated_at = datetime.now(timezone.utc)
        project = await self.project_repo.update(project)
        return ProjectResponse.model_validate(project)

    async def delete_project(
        self, project_id: str, actor_id: str | None = None
    ) -> None:
        project = await self.project_repo.get_by_id(project_id)
        if not project:
            raise EntityNotFoundError("Project", project_id)
        await self.project_repo.soft_delete(project, actor_id)
