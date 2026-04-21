"""
Async Hugging Face API client.

Endpoints used:
- GET /api/users/{username}/overview       - profile
- GET /api/models?author={u}&full=true     - list models by author
- GET /api/datasets?author={u}&full=true   - list datasets by author
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any

import httpx

from app.ingest.common.errors import PermanentError, TransientError
from app.ingest.common.metrics import hf_request_seconds, hf_requests

from .config import HFConfig

log = logging.getLogger(__name__)


class HFClient:
    def __init__(self, config: HFConfig) -> None:
        self.config = config
        self._tokens = config.hf_tokens
        self._token_idx = 0
        headers = {"User-Agent": "octopod-hf-ingest/1.0", "Accept": "application/json"}
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.request_timeout),
            limits=httpx.Limits(
                max_connections=config.concurrency * 2,
                max_keepalive_connections=config.concurrency,
            ),
            headers=headers,
            base_url=config.endpoint,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> HFClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    def _next_token(self) -> str | None:
        if not self._tokens:
            return None
        tok = self._tokens[self._token_idx % len(self._tokens)]
        self._token_idx += 1
        return tok

    # ---- Core request with retry ----

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        attempt = 0
        while True:
            attempt += 1
            headers = dict(kwargs.pop("headers", {}))
            tok = self._next_token()
            if tok:
                headers["Authorization"] = f"Bearer {tok}"

            start = time.monotonic()
            try:
                resp = await self._client.request(method, path, headers=headers, **kwargs)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                hf_requests.labels(api="rest", status="transient").inc()
                if attempt > self.config.max_retries:
                    raise TransientError(
                        f"network error after {attempt} attempts: {e}"
                    ) from e
                await self._backoff(attempt)
                continue
            finally:
                hf_request_seconds.labels(api="rest").observe(time.monotonic() - start)

            if 200 <= resp.status_code < 300:
                hf_requests.labels(api="rest", status="ok").inc()
                return resp

            if resp.status_code == 429:
                retry_after = _int_header(resp, "Retry-After")
                hf_requests.labels(api="rest", status="retry").inc()
                if retry_after:
                    log.warning("HF rate limit; sleeping %ds", retry_after)
                    await asyncio.sleep(retry_after)
                    continue
                if attempt > self.config.max_retries:
                    raise TransientError(f"429 after {attempt} attempts")
                await self._backoff(attempt)
                continue

            if resp.status_code in (401, 403, 404, 410):
                hf_requests.labels(api="rest", status="permanent").inc()
                raise PermanentError(f"{resp.status_code} {path}: {resp.text[:200]}")

            if resp.status_code >= 500:
                hf_requests.labels(api="rest", status="transient").inc()
                if attempt > self.config.max_retries:
                    raise TransientError(
                        f"server error {resp.status_code} after {attempt} attempts"
                    )
                await self._backoff(attempt)
                continue

            hf_requests.labels(api="rest", status="permanent").inc()
            raise PermanentError(f"{resp.status_code} {path}: {resp.text[:200]}")

    async def _backoff(self, attempt: int) -> None:
        delay = min(self.config.base_backoff_seconds * (2 ** (attempt - 1)), 60.0)
        delay += random.uniform(0, 1.0)
        await asyncio.sleep(delay)

    # ---- Public API ----

    async def fetch_user(self, username: str) -> dict[str, Any]:
        """Profile for a user OR org. Tries /api/users first; falls back to /api/organizations."""
        try:
            resp = await self._request("GET", f"/api/users/{username}/overview")
            data = resp.json()
            data["_type"] = "user"
            return data
        except PermanentError as e:
            if "404" not in str(e):
                raise
            resp = await self._request(
                "GET", f"/api/organizations/{username}/overview"
            )
            data = resp.json()
            data["_type"] = "org"
            return data

    async def list_models(self, username: str) -> list[dict[str, Any]]:
        return await self._paginated_list(
            "/api/models",
            {"author": username, "full": "true", "limit": 100},
            self.config.max_models_per_user,
        )

    async def list_datasets(self, username: str) -> list[dict[str, Any]]:
        return await self._paginated_list(
            "/api/datasets",
            {"author": username, "full": "true", "limit": 100},
            self.config.max_datasets_per_user,
        )

    async def _paginated_list(
        self, path: str, params: dict[str, Any], max_items: int
    ) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        next_url: str | None = None
        current_params: dict[str, Any] | None = dict(params)

        while len(items) < max_items:
            if next_url:
                resp = await self._request("GET", next_url)
            else:
                resp = await self._request("GET", path, params=current_params)
                current_params = None

            page = resp.json()
            if not isinstance(page, list):
                break
            items.extend(page)
            if len(page) < params.get("limit", 100):
                break

            next_url = _parse_next_link(resp.headers.get("Link"))
            if not next_url:
                break

        return items[:max_items]


def _int_header(resp: httpx.Response, name: str) -> int | None:
    v = resp.headers.get(name)
    try:
        return int(v) if v is not None else None
    except ValueError:
        return None


def _parse_next_link(link_header: str | None) -> str | None:
    """Parse a Link header like:
    <https://huggingface.co/api/models?...&cursor=XYZ>; rel="next"
    """
    if not link_header:
        return None
    for part in link_header.split(","):
        section = part.strip().split(";")
        if len(section) < 2:
            continue
        url = section[0].strip().strip("<>")
        rel = [p.strip() for p in section[1:]]
        if any(r == 'rel="next"' for r in rel):
            return url
    return None
