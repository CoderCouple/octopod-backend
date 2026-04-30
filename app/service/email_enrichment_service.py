"""Service layer for email enrichment via waterfall lookup.

Attempts to find email addresses for developer profiles using multiple
sources in priority order: manual hint, GitHub public, GitHub commit,
HuggingFace, Hunter.io, Apollo.io.
"""

import logging

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.enum.email import EmailSource
from app.settings import settings

logger = logging.getLogger(__name__)


class EmailEnrichmentResult:
    """Result of an email enrichment attempt."""

    def __init__(
        self,
        email: str | None = None,
        source: str | None = None,
        confidence: float = 0.0,
        found: bool = False,
    ):
        self.email = email
        self.source = source
        self.confidence = confidence
        self.found = found


class EmailEnrichmentService:
    """Waterfall email finder for developer profiles."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_email(self, developer_profile_id: str) -> EmailEnrichmentResult:
        """Find email for a developer profile using waterfall strategy."""

        # 1. Check manual email hint on developer_profile
        result = await self.db.execute(
            text(
                "SELECT email_hint, github_username, huggingface_username "
                "FROM developer_profile WHERE id = :id AND is_deleted = false"
            ),
            {"id": developer_profile_id},
        )
        row = result.mappings().first()
        if not row:
            return EmailEnrichmentResult()

        if row["email_hint"]:
            return EmailEnrichmentResult(
                email=row["email_hint"],
                source=EmailSource.MANUAL.value,
                confidence=1.0,
                found=True,
            )

        github_username = row.get("github_username")
        hf_username = row.get("huggingface_username")

        # 2. GitHub public email
        if github_username:
            email = await self._github_public_email(github_username)
            if email:
                return EmailEnrichmentResult(
                    email=email,
                    source=EmailSource.GITHUB_PUBLIC.value,
                    confidence=0.95,
                    found=True,
                )

        # 3. GitHub commit emails
        if github_username:
            email = await self._github_commit_email(github_username)
            if email:
                return EmailEnrichmentResult(
                    email=email,
                    source=EmailSource.GITHUB_COMMIT.value,
                    confidence=0.85,
                    found=True,
                )

        # 4. HuggingFace (linked GitHub fallback)
        if hf_username and not github_username:
            email = await self._huggingface_email(hf_username)
            if email:
                return EmailEnrichmentResult(
                    email=email,
                    source=EmailSource.HUGGINGFACE.value,
                    confidence=0.7,
                    found=True,
                )

        # 5. Hunter.io
        if github_username and settings.hunter_api_key:
            email = await self._hunter_find(github_username)
            if email:
                return EmailEnrichmentResult(
                    email=email,
                    source=EmailSource.HUNTER.value,
                    confidence=0.6,
                    found=True,
                )

        # 6. Apollo.io
        if github_username and settings.apollo_api_key:
            email = await self._apollo_find(github_username)
            if email:
                return EmailEnrichmentResult(
                    email=email,
                    source=EmailSource.APOLLO.value,
                    confidence=0.5,
                    found=True,
                )

        return EmailEnrichmentResult()

    async def enrich_batch(self, profile_ids: list[str]) -> list[EmailEnrichmentResult]:
        """Find emails for multiple profiles."""
        results = []
        for pid in profile_ids:
            result = await self.find_email(pid)
            results.append(result)
        return results

    async def _github_public_email(self, username: str) -> str | None:
        """Check gh_users table for public email."""
        result = await self.db.execute(
            text("SELECT email FROM gh_users WHERE login = :login AND email IS NOT NULL"),
            {"login": username},
        )
        row = result.first()
        if row and row[0]:
            return row[0]
        return None

    async def _github_commit_email(self, username: str) -> str | None:
        """Check gh_commits for author email, filtering noreply addresses."""
        result = await self.db.execute(
            text(
                "SELECT DISTINCT author_email FROM gh_commits "
                "WHERE author_login = :login "
                "AND author_email IS NOT NULL "
                "AND author_email NOT LIKE '%noreply%' "
                "LIMIT 1"
            ),
            {"login": username},
        )
        row = result.first()
        if row and row[0]:
            return row[0]
        return None

    async def _huggingface_email(self, username: str) -> str | None:
        """Try to find email via HuggingFace profile."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"https://huggingface.co/api/users/{username}/overview",
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("email")
        except Exception:
            logger.debug(f"HuggingFace email lookup failed for {username}")
        return None

    async def _hunter_find(self, username: str) -> str | None:
        """Find email via Hunter.io email finder API."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.hunter.io/v2/email-finder",
                    params={
                        "full_name": username,
                        "api_key": settings.hunter_api_key,
                    },
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    email = data.get("data", {}).get("email")
                    if email:
                        return email
        except Exception:
            logger.debug(f"Hunter.io lookup failed for {username}")
        return None

    async def _apollo_find(self, username: str) -> str | None:
        """Find email via Apollo.io people match API."""
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.apollo.io/api/v1/people/match",
                    json={
                        "github_url": f"https://github.com/{username}",
                        "api_key": settings.apollo_api_key,
                    },
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    person = data.get("person", {})
                    email = person.get("email")
                    if email:
                        return email
        except Exception:
            logger.debug(f"Apollo.io lookup failed for {username}")
        return None
