import logging
from typing import Any

import httpx

from app.service.clients import PlatformClient
from app.settings import settings

logger = logging.getLogger(__name__)


class HuggingFaceClient(PlatformClient):
    BASE_URL = "https://huggingface.co/api"

    def __init__(self) -> None:
        headers: dict[str, str] = {}
        if settings.huggingface_token:
            headers["Authorization"] = f"Bearer {settings.huggingface_token}"
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=headers,
            timeout=30.0,
        )

    async def fetch_profile_data(self, username: str) -> dict[str, Any]:
        user_resp = await self._client.get(f"/users/{username}/overview")
        user_resp.raise_for_status()
        user_data = user_resp.json()

        models_resp = await self._client.get("/models", params={"author": username})
        models_resp.raise_for_status()
        models_data = models_resp.json()

        datasets_resp = await self._client.get("/datasets", params={"author": username})
        datasets_resp.raise_for_status()
        datasets_data = datasets_resp.json()

        spaces_resp = await self._client.get("/spaces", params={"author": username})
        spaces_resp.raise_for_status()
        spaces_data = spaces_resp.json()

        return {
            "user": user_data,
            "models": models_data,
            "datasets": datasets_data,
            "spaces": spaces_data,
        }

    @staticmethod
    def extract(raw_data: dict[str, Any]) -> dict[str, Any]:
        user = raw_data.get("user", {})
        models = raw_data.get("models", [])
        datasets = raw_data.get("datasets", [])
        spaces = raw_data.get("spaces", [])

        total_downloads = sum(m.get("downloads", 0) for m in models)
        total_papers = sum(1 for m in models if m.get("paperswithcode_id"))

        return {
            "display_name": user.get("fullname") or user.get("user", ""),
            "avatar_url": user.get("avatarUrl"),
            "total_hf_models": len(models),
            "total_hf_datasets": len(datasets),
            "total_hf_spaces": len(spaces),
            "total_hf_downloads": total_downloads,
            "total_papers": total_papers,
        }

    async def close(self) -> None:
        await self._client.aclose()
