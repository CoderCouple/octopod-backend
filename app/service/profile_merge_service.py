import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.response.developer_profile_response import CohesiveProfileResponse
from app.common.enum.platform import Platform
from app.common.exceptions import EntityNotFoundError
from app.db.repository.cohesive_profile_repository import CohesiveProfileRepository
from app.db.repository.developer_profile_repository import DeveloperProfileRepository
from app.db.repository.platform_profile_repository import PlatformProfileRepository
from app.model.cohesive_profile_model import CohesiveProfile

logger = logging.getLogger(__name__)

# Source priority: which platform wins for each field
FIELD_PRIORITY = {
    "display_name": [Platform.LINKEDIN, Platform.GITHUB, Platform.HUGGINGFACE],
    "bio": [Platform.LINKEDIN, Platform.GITHUB, Platform.HUGGINGFACE],
    "headline": [Platform.LINKEDIN, Platform.GITHUB, Platform.HUGGINGFACE],
    "avatar_url": [Platform.GITHUB, Platform.LINKEDIN, Platform.HUGGINGFACE],
    "company": [Platform.LINKEDIN, Platform.GITHUB],
    "location": [Platform.LINKEDIN, Platform.GITHUB],
    "website": [Platform.GITHUB, Platform.LINKEDIN],
}


class ProfileMergeService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.dp_repo = DeveloperProfileRepository(db)
        self.pp_repo = PlatformProfileRepository(db)
        self.cp_repo = CohesiveProfileRepository(db)

    async def get_cohesive_profile(
        self, developer_profile_id: str
    ) -> CohesiveProfileResponse:
        cp = await self.cp_repo.get_by_developer_profile_id(developer_profile_id)
        if not cp:
            raise EntityNotFoundError("CohesiveProfile", developer_profile_id)
        return CohesiveProfileResponse.model_validate(cp)

    async def merge_profile(self, developer_profile_id: str) -> CohesiveProfileResponse:
        profile = await self.dp_repo.get_by_id(developer_profile_id)
        if not profile:
            raise EntityNotFoundError("DeveloperProfile", developer_profile_id)

        platforms = await self.pp_repo.list_by_developer(developer_profile_id)
        platform_data: dict[str, dict] = {}
        for pp in platforms:
            if pp.fetch_status == "success" and pp.extracted_data:
                platform_data[pp.platform] = pp.extracted_data

        merged = self._merge_fields(platform_data)

        cp = await self.cp_repo.get_by_developer_profile_id(developer_profile_id)
        if not cp:
            cp = CohesiveProfile(developer_profile_id=developer_profile_id)
            for key, value in merged.items():
                if key != "source_priority":
                    setattr(cp, key, value)
            cp.source_priority = merged.get("source_priority", {})
            cp.merged_at = datetime.now(timezone.utc)
            cp.embedding_text = self._build_embedding_text(cp, platform_data)
            cp = await self.cp_repo.create(cp)
        else:
            for key, value in merged.items():
                if key != "source_priority":
                    setattr(cp, key, value)
            cp.source_priority = merged.get("source_priority", {})
            cp.merged_at = datetime.now(timezone.utc)
            cp.embedding_text = self._build_embedding_text(cp, platform_data)
            cp = await self.cp_repo.update(cp)

        return CohesiveProfileResponse.model_validate(cp)

    def _merge_fields(self, platform_data: dict[str, dict]) -> dict:
        result: dict = {}
        source_priority: dict[str, str] = {}

        # Merge priority-based text fields
        for field, priorities in FIELD_PRIORITY.items():
            for platform in priorities:
                data = platform_data.get(platform.value, {})
                value = data.get(field)
                if value:
                    result[field] = value
                    source_priority[field] = platform.value
                    break

        # GitHub metrics
        gh = platform_data.get(Platform.GITHUB.value, {})
        result["total_repos"] = gh.get("total_repos", 0)
        result["total_stars"] = gh.get("total_stars", 0)
        result["total_contributions"] = gh.get("total_contributions", 0)
        result["total_followers"] = gh.get("total_followers", 0)

        # HuggingFace metrics
        hf = platform_data.get(Platform.HUGGINGFACE.value, {})
        result["total_hf_models"] = hf.get("total_hf_models", 0)
        result["total_hf_datasets"] = hf.get("total_hf_datasets", 0)
        result["total_hf_spaces"] = hf.get("total_hf_spaces", 0)
        result["total_hf_downloads"] = hf.get("total_hf_downloads", 0)
        result["total_papers"] = hf.get("total_papers", 0)

        # Languages from GitHub (authoritative)
        result["languages"] = gh.get("languages", [])
        if result["languages"]:
            source_priority["languages"] = Platform.GITHUB.value

        # Topics from GitHub
        result["topics"] = gh.get("topics", [])
        if result["topics"]:
            source_priority["topics"] = Platform.GITHUB.value

        # Skills: union from all sources
        all_skills: set[str] = set()
        for _platform_name, data in platform_data.items():
            skills = data.get("skills", [])
            if isinstance(skills, list):
                all_skills.update(s for s in skills if isinstance(s, str))
        result["skills"] = sorted(all_skills)
        if all_skills:
            source_priority["skills"] = "union"

        # Job history from LinkedIn (authoritative)
        li = platform_data.get(Platform.LINKEDIN.value, {})
        result["job_history"] = li.get("job_history", [])
        result["current_title"] = li.get("current_title")
        result["current_company"] = li.get("current_company")
        result["years_of_experience"] = li.get("years_of_experience")
        if result["job_history"]:
            source_priority["job_history"] = Platform.LINKEDIN.value

        result["source_priority"] = source_priority
        return result

    @staticmethod
    def _build_embedding_text(
        cp: CohesiveProfile, platform_data: dict[str, dict] | None = None
    ) -> str:
        parts: list[str] = []
        if cp.headline:
            parts.append(cp.headline)
        if cp.bio:
            parts.append(cp.bio)
        if cp.current_title and cp.current_company:
            parts.append(f"{cp.current_title} at {cp.current_company}")
        elif cp.current_title:
            parts.append(cp.current_title)
        if cp.location:
            parts.append(f"Located in {cp.location}")
        if cp.skills:
            parts.append(f"Skills: {', '.join(cp.skills[:20])}")
        if cp.languages:
            parts.append(f"Languages: {', '.join(cp.languages[:15])}")
        if cp.topics:
            parts.append(f"Topics: {', '.join(cp.topics[:15])}")
        if cp.total_contributions:
            parts.append(f"{cp.total_contributions} contributions")
        if cp.total_stars:
            parts.append(f"{cp.total_stars} GitHub stars")
        if cp.total_hf_models:
            parts.append(f"{cp.total_hf_models} HuggingFace models")

        # Top 5 repo descriptions from GitHub platform data
        if platform_data:
            gh = platform_data.get(Platform.GITHUB.value, {})
            repos = gh.get("top_repos", [])
            for repo in repos[:5]:
                name = repo.get("name", "")
                desc = repo.get("description", "")
                if name and desc:
                    parts.append(f"Repo {name}: {desc}")

            # Social accounts
            socials = gh.get("social_accounts", [])
            for social in socials[:3]:
                url = social.get("url", "")
                if url:
                    parts.append(url)

        if cp.website:
            parts.append(cp.website)

        if cp.job_history:
            for job in cp.job_history[:5]:
                title = job.get("title", "")
                company = job.get("company", "")
                if title and company:
                    parts.append(f"{title} at {company}")
        return ". ".join(parts)
