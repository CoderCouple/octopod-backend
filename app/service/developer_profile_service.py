from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.request.developer_profile_request import (
    CreateDeveloperProfileRequest,
    UpdateDeveloperProfileRequest,
)
from app.api.v1.response.developer_profile_response import DeveloperProfileResponse
from app.common.exceptions import DuplicateEntityError, EntityNotFoundError
from app.db.repository.developer_profile_repository import DeveloperProfileRepository
from app.model.developer_profile_model import DeveloperProfile


class DeveloperProfileService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = DeveloperProfileRepository(db)

    async def _check_duplicates(
        self, data: CreateDeveloperProfileRequest | UpdateDeveloperProfileRequest,
        exclude_id: str | None = None,
    ) -> None:
        if data.github_username:
            existing = await self.repo.get_by_github_username(data.github_username, exclude_id)
            if existing:
                raise DuplicateEntityError(
                    "DeveloperProfile", "github_username", data.github_username
                )
        if data.huggingface_username:
            existing = await self.repo.get_by_huggingface_username(
                data.huggingface_username, exclude_id
            )
            if existing:
                raise DuplicateEntityError(
                    "DeveloperProfile", "huggingface_username", data.huggingface_username
                )

    async def create_profile(
        self, data: CreateDeveloperProfileRequest, actor_id: str | None = None
    ) -> DeveloperProfileResponse:
        await self._check_duplicates(data)

        profile = DeveloperProfile(
            github_username=data.github_username,
            huggingface_username=data.huggingface_username,
            email_hint=data.email_hint,
            ingestion_status="pending",
            created_by=actor_id,
            updated_by=actor_id,
        )
        profile = await self.repo.create(profile)
        return DeveloperProfileResponse.model_validate(profile)

    async def get_profile(self, profile_id: str) -> DeveloperProfileResponse:
        profile = await self.repo.get_by_id(profile_id)
        if not profile:
            raise EntityNotFoundError("DeveloperProfile", profile_id)
        return DeveloperProfileResponse.model_validate(profile)

    async def get_profile_entity(self, profile_id: str) -> DeveloperProfile:
        profile = await self.repo.get_by_id(profile_id)
        if not profile:
            raise EntityNotFoundError("DeveloperProfile", profile_id)
        return profile

    async def list_profiles(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[DeveloperProfileResponse], int]:
        profiles, total = await self.repo.list_all(offset, limit)
        return [DeveloperProfileResponse.model_validate(p) for p in profiles], total

    async def update_profile(
        self,
        profile_id: str,
        data: UpdateDeveloperProfileRequest,
        actor_id: str | None = None,
    ) -> DeveloperProfileResponse:
        profile = await self.repo.get_by_id(profile_id)
        if not profile:
            raise EntityNotFoundError("DeveloperProfile", profile_id)

        await self._check_duplicates(data, exclude_id=profile_id)

        update_data = data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(profile, key, value)
        profile.updated_by = actor_id
        profile.updated_at = datetime.now(timezone.utc)

        profile = await self.repo.update(profile)
        return DeveloperProfileResponse.model_validate(profile)
