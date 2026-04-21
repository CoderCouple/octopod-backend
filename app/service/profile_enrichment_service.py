import logging

import httpx

from app.settings import settings

logger = logging.getLogger(__name__)


class ProfileEnrichmentService:
    async def discover_github_from_email(self, email: str) -> str | None:
        headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"

        async with httpx.AsyncClient(
            base_url="https://api.github.com", headers=headers, timeout=15.0
        ) as client:
            try:
                resp = await client.get(
                    "/search/users",
                    params={"q": f"{email} in:email", "per_page": 1},
                )
                resp.raise_for_status()
                data = resp.json()
                items = data.get("items", [])
                if items:
                    return items[0].get("login")
            except Exception as e:
                logger.warning(f"GitHub email discovery failed for {email}: {e}")
        return None

    async def discover_huggingface_from_email(self, email: str) -> str | None:
        # HuggingFace does not have a public email search API
        # This is a placeholder for future enrichment
        return None
