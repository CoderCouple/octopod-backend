import logging
from typing import Any

import httpx

from app.service.clients import PlatformClient
from app.settings import settings

logger = logging.getLogger(__name__)


class LinkedInClient(PlatformClient):
    BASE_URL = "https://nubela.co/proxycurl/api/v2/linkedin"

    def __init__(self) -> None:
        headers: dict[str, str] = {}
        if settings.proxycurl_api_key:
            headers["Authorization"] = f"Bearer {settings.proxycurl_api_key}"
        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=30.0,
        )

    async def fetch_profile_data(self, linkedin_url: str) -> dict[str, Any]:
        resp = await self._client.get(
            self.BASE_URL,
            params={"url": linkedin_url},
        )
        resp.raise_for_status()
        return resp.json()

    @staticmethod
    def extract(raw_data: dict[str, Any]) -> dict[str, Any]:
        experiences = raw_data.get("experiences", []) or []
        skills_raw = raw_data.get("skills", []) or []

        job_history = []
        for exp in experiences:
            entry: dict[str, Any] = {
                "company": exp.get("company"),
                "title": exp.get("title"),
            }
            starts_at = exp.get("starts_at")
            if starts_at and isinstance(starts_at, dict):
                entry["start"] = f"{starts_at.get('year', '')}-{starts_at.get('month', 1):02d}"
            ends_at = exp.get("ends_at")
            if ends_at and isinstance(ends_at, dict):
                entry["end"] = f"{ends_at.get('year', '')}-{ends_at.get('month', 1):02d}"
            job_history.append(entry)

        current_title = None
        current_company = None
        if job_history:
            current_title = job_history[0].get("title")
            current_company = job_history[0].get("company")

        years_of_experience = None
        if experiences:
            earliest = None
            for exp in experiences:
                starts_at = exp.get("starts_at")
                if starts_at and isinstance(starts_at, dict) and starts_at.get("year"):
                    year = starts_at["year"]
                    if earliest is None or year < earliest:
                        earliest = year
            if earliest:
                from datetime import datetime

                years_of_experience = datetime.now().year - earliest

        skills = skills_raw if isinstance(skills_raw, list) else []

        return {
            "display_name": raw_data.get("full_name"),
            "headline": raw_data.get("headline"),
            "bio": raw_data.get("summary"),
            "location": (
                f"{raw_data.get('city', '')}, {raw_data.get('country_full_name', '')}".strip(", ")
                if raw_data.get("city") or raw_data.get("country_full_name")
                else None
            ),
            "avatar_url": raw_data.get("profile_pic_url"),
            "company": current_company,
            "skills": skills,
            "job_history": job_history,
            "current_title": current_title,
            "current_company": current_company,
            "years_of_experience": years_of_experience,
        }

    async def close(self) -> None:
        await self._client.aclose()
