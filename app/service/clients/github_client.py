import logging
from typing import Any

import httpx

from app.service.clients import PlatformClient
from app.settings import settings

logger = logging.getLogger(__name__)


class GitHubClient(PlatformClient):
    BASE_URL = "https://api.github.com"

    def __init__(self) -> None:
        headers: dict[str, str] = {"Accept": "application/vnd.github.v3+json"}
        if settings.github_token:
            headers["Authorization"] = f"Bearer {settings.github_token}"
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=headers,
            timeout=30.0,
        )

    async def fetch_profile_data(self, username: str) -> dict[str, Any]:
        user_resp = await self._client.get(f"/users/{username}")
        user_resp.raise_for_status()
        user_data = user_resp.json()

        repos_resp = await self._client.get(
            f"/users/{username}/repos",
            params={"sort": "updated", "per_page": 100, "type": "owner"},
        )
        repos_resp.raise_for_status()
        repos_data = repos_resp.json()

        return {"user": user_data, "repos": repos_data}

    @staticmethod
    def extract(raw_data: dict[str, Any]) -> dict[str, Any]:
        user = raw_data.get("user", {})
        repos = raw_data.get("repos", [])

        languages: dict[str, int] = {}
        topics: set[str] = set()
        total_stars = 0
        non_fork_repos = 0

        for repo in repos:
            if repo.get("fork"):
                continue
            non_fork_repos += 1
            total_stars += repo.get("stargazers_count", 0)
            lang = repo.get("language")
            if lang:
                languages[lang] = languages.get(lang, 0) + 1
            for topic in repo.get("topics", []):
                topics.add(topic)

        sorted_langs = sorted(languages.keys(), key=lambda lang: languages[lang], reverse=True)

        return {
            "display_name": user.get("name") or user.get("login", ""),
            "bio": user.get("bio"),
            "avatar_url": user.get("avatar_url"),
            "company": user.get("company"),
            "location": user.get("location"),
            "website": user.get("blog"),
            "total_repos": user.get("public_repos", 0),
            "total_stars": total_stars,
            "total_followers": user.get("followers", 0),
            "total_contributions": non_fork_repos,
            "languages": sorted_langs,
            "topics": sorted(topics),
        }

    async def close(self) -> None:
        await self._client.aclose()
