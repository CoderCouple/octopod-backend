"""Proxycurl API client with rate limiting and budget tracking."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp

from app.ingest.ln.config import LNConfig

log = logging.getLogger(__name__)

PROXYCURL_PERSON_ENDPOINT = "https://nubela.co/proxycurl/api/v2/linkedin"


class ProxycurlClient:
    def __init__(self, config: LNConfig) -> None:
        self._config = config
        self._session: aiohttp.ClientSession | None = None
        self._semaphore = asyncio.Semaphore(config.concurrency)
        self._budget_spent: float = 0.0
        self._request_count: int = 0
        self._rpm_window_start: float = time.monotonic()
        self._rpm_count: int = 0

    async def __aenter__(self) -> ProxycurlClient:
        self._session = aiohttp.ClientSession(
            headers={"Authorization": f"Bearer {self._config.api_key}"},
            timeout=aiohttp.ClientTimeout(total=self._config.request_timeout),
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._session:
            await self._session.close()

    @property
    def budget_remaining(self) -> float:
        return self._config.daily_budget_usd - self._budget_spent

    @property
    def budget_exhausted(self) -> bool:
        return self._budget_spent >= self._config.daily_budget_usd

    async def fetch_profile(self, linkedin_url: str) -> dict[str, Any] | None:
        """Fetch a LinkedIn profile via Proxycurl.

        Returns parsed profile dict or None on error.
        """
        if self.budget_exhausted:
            log.warning("Daily budget exhausted ($%.2f spent)", self._budget_spent)
            return None

        await self._rate_limit()

        async with self._semaphore:
            if not self._session:
                raise RuntimeError("Client not initialized; use async with")

            params = {
                "linkedin_profile_url": linkedin_url,
                "use_cache": "if-present",
                "skills": "include",
                "inferred_salary": "exclude",
                "personal_email": "exclude",
                "personal_contact_number": "exclude",
                "twitter_profile_id": "exclude",
                "facebook_profile_id": "exclude",
                "github_profile_id": "exclude",
                "extra": "exclude",
            }

            try:
                async with self._session.get(
                    PROXYCURL_PERSON_ENDPOINT, params=params
                ) as resp:
                    self._budget_spent += self._config.cost_per_profile
                    self._request_count += 1

                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status == 404:
                        log.debug("Profile not found: %s", linkedin_url)
                        return None
                    elif resp.status == 429:
                        log.warning("Rate limited by Proxycurl, waiting 60s")
                        await asyncio.sleep(60)
                        return None
                    else:
                        text = await resp.text()
                        log.warning(
                            "Proxycurl %d for %s: %s",
                            resp.status, linkedin_url, text[:200],
                        )
                        return None
            except TimeoutError:
                log.warning("Timeout fetching %s", linkedin_url)
                return None
            except Exception:
                log.exception("Error fetching %s", linkedin_url)
                return None

    async def _rate_limit(self) -> None:
        """Simple sliding window rate limiter."""
        now = time.monotonic()
        elapsed = now - self._rpm_window_start

        if elapsed >= 60:
            self._rpm_window_start = now
            self._rpm_count = 0

        if self._rpm_count >= self._config.rate_limit_rpm:
            wait = 60 - elapsed
            if wait > 0:
                log.debug("Rate limit: waiting %.1fs", wait)
                await asyncio.sleep(wait)
            self._rpm_window_start = time.monotonic()
            self._rpm_count = 0

        self._rpm_count += 1
