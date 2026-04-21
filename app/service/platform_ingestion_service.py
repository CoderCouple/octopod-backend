import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.response.developer_profile_response import (
    IngestionStatusResponse,
    PlatformProfileResponse,
)
from app.common.enum.platform import FetchStatus, IngestionStatus, Platform
from app.common.exceptions import EntityNotFoundError
from app.db.repository.developer_profile_repository import DeveloperProfileRepository
from app.db.repository.platform_profile_repository import PlatformProfileRepository
from app.model.platform_profile_model import PlatformProfile
from app.service.clients.github_client import GitHubClient
from app.service.clients.huggingface_client import HuggingFaceClient
from app.service.clients.linkedin_client import LinkedInClient

logger = logging.getLogger(__name__)


class PlatformIngestionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.dp_repo = DeveloperProfileRepository(db)
        self.pp_repo = PlatformProfileRepository(db)

    async def ingest_all(self, developer_profile_id: str) -> IngestionStatusResponse:
        profile = await self.dp_repo.get_by_id(developer_profile_id)
        if not profile:
            raise EntityNotFoundError("DeveloperProfile", developer_profile_id)

        profile.ingestion_status = IngestionStatus.INGESTING.value
        profile.updated_at = datetime.now(timezone.utc)
        await self.dp_repo.update(profile)

        results: list[PlatformProfile] = []
        failures = 0

        if profile.github_username:
            pp = await self._ingest_platform(
                developer_profile_id,
                Platform.GITHUB,
                profile.github_username,
                self._fetch_github,
            )
            results.append(pp)
            if pp.fetch_status == FetchStatus.FAILED.value:
                failures += 1

        if profile.linkedin_url:
            pp = await self._ingest_platform(
                developer_profile_id,
                Platform.LINKEDIN,
                profile.linkedin_url,
                self._fetch_linkedin,
            )
            results.append(pp)
            if pp.fetch_status == FetchStatus.FAILED.value:
                failures += 1

        if profile.huggingface_username:
            pp = await self._ingest_platform(
                developer_profile_id,
                Platform.HUGGINGFACE,
                profile.huggingface_username,
                self._fetch_huggingface,
            )
            results.append(pp)
            if pp.fetch_status == FetchStatus.FAILED.value:
                failures += 1

        total_platforms = len(results)
        if failures == 0:
            profile.ingestion_status = IngestionStatus.COMPLETED.value
        elif failures == total_platforms:
            profile.ingestion_status = IngestionStatus.FAILED.value
        else:
            profile.ingestion_status = IngestionStatus.PARTIAL_FAILURE.value

        profile.last_ingested_at = datetime.now(timezone.utc)
        await self.dp_repo.update(profile)

        return IngestionStatusResponse(
            developer_profile_id=developer_profile_id,
            ingestion_status=profile.ingestion_status,
            last_ingested_at=profile.last_ingested_at,
            platforms=[PlatformProfileResponse.model_validate(pp) for pp in results],
        )

    async def _ingest_platform(
        self,
        developer_profile_id: str,
        platform: Platform,
        identifier: str,
        fetch_fn: object,
    ) -> PlatformProfile:
        pp = await self.pp_repo.get_by_dev_and_platform(
            developer_profile_id, platform.value
        )
        if not pp:
            pp = PlatformProfile(
                developer_profile_id=developer_profile_id,
                platform=platform.value,
                platform_username=identifier,
                fetch_status=FetchStatus.PENDING.value,
            )
            pp = await self.pp_repo.create(pp)

        pp.fetch_status = FetchStatus.FETCHING.value
        pp.platform_username = identifier
        await self.pp_repo.update(pp)

        try:
            raw_data, extracted_data = await fetch_fn(identifier)
            pp.raw_data = raw_data
            pp.extracted_data = extracted_data
            pp.fetch_status = FetchStatus.SUCCESS.value
            pp.error_message = None
            pp.fetched_at = datetime.now(timezone.utc)
        except Exception as e:
            logger.error(f"Failed to fetch {platform.value} for {identifier}: {e}")
            pp.fetch_status = FetchStatus.FAILED.value
            pp.error_message = str(e)[:500]

        await self.pp_repo.update(pp)
        return pp

    async def _fetch_github(self, username: str) -> tuple[dict, dict]:
        client = GitHubClient()
        try:
            raw_data = await client.fetch_profile_data(username)
            extracted = GitHubClient.extract(raw_data)
            return raw_data, extracted
        finally:
            await client.close()

    async def _fetch_linkedin(self, url: str) -> tuple[dict, dict]:
        client = LinkedInClient()
        try:
            raw_data = await client.fetch_profile_data(url)
            extracted = LinkedInClient.extract(raw_data)
            return raw_data, extracted
        finally:
            await client.close()

    async def _fetch_huggingface(self, username: str) -> tuple[dict, dict]:
        client = HuggingFaceClient()
        try:
            raw_data = await client.fetch_profile_data(username)
            extracted = HuggingFaceClient.extract(raw_data)
            return raw_data, extracted
        finally:
            await client.close()

    async def get_status(self, developer_profile_id: str) -> IngestionStatusResponse:
        profile = await self.dp_repo.get_by_id(developer_profile_id)
        if not profile:
            raise EntityNotFoundError("DeveloperProfile", developer_profile_id)

        platforms = await self.pp_repo.list_by_developer(developer_profile_id)
        return IngestionStatusResponse(
            developer_profile_id=developer_profile_id,
            ingestion_status=profile.ingestion_status,
            last_ingested_at=profile.last_ingested_at,
            platforms=[PlatformProfileResponse.model_validate(pp) for pp in platforms],
        )
