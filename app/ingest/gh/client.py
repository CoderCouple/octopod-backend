"""
Async GitHub client: GraphQL for structured data (profile + repos in one query),
REST for public events (not exposed via GraphQL).

Key properties:
- Exponential backoff with jitter on transient errors (5xx, 502, timeouts).
- Honors secondary rate limits (Retry-After header).
- Classifies 404 / 451 / 403 as permanent per-user failures (don't retry forever).
- Updates token pool with remaining budget from response headers.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from typing import Any

import httpx

from app.ingest.common.errors import PermanentError, TransientError
from app.ingest.common.metrics import github_request_seconds, github_requests, tokens_remaining

from .config import GHConfig
from .token_pool import TokenPool

log = logging.getLogger(__name__)


USER_QUERY = """
query($login: String!, $repoCount: Int!, $commitCount: Int!) {
  user(login: $login) {
    databaseId
    login
    name
    email
    bio
    company
    location
    websiteUrl
    twitterUsername
    avatarUrl
    isHireable
    createdAt
    updatedAt
    followers { totalCount }
    following { totalCount }
    socialAccounts(first: 10) {
      nodes { provider url displayName }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      totalRepositoryContributions
      contributionCalendar {
        totalContributions
        weeks {
          contributionDays {
            contributionCount
            date
          }
        }
      }
    }
    repositories(
      first: $repoCount
      ownerAffiliations: OWNER
      orderBy: {field: UPDATED_AT, direction: DESC}
    ) {
      nodes {
        databaseId
        name
        nameWithOwner
        description
        isFork
        isArchived
        stargazerCount
        forkCount
        watchers { totalCount }
        issues(states: OPEN) { totalCount }
        diskUsage
        createdAt
        updatedAt
        pushedAt
        primaryLanguage { name }
        repositoryTopics(first: 20) { nodes { topic { name } } }
        defaultBranchRef {
          target {
            ... on Commit {
              history(first: $commitCount) {
                nodes {
                  oid
                  message
                  committedDate
                  additions
                  deletions
                  changedFilesIfAvailable
                  author {
                    email
                    user { databaseId login }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""


class GitHubClient:
    def __init__(self, config: GHConfig, pool: TokenPool) -> None:
        self.config = config
        self.pool = pool
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.request_timeout),
            limits=httpx.Limits(
                max_connections=config.concurrency * 2,
                max_keepalive_connections=config.concurrency,
            ),
            headers={
                "Accept": "application/vnd.github+json",
                "User-Agent": "octopod-gh-ingest/1.0",
            },
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> GitHubClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # ---------- Core request with retry ----------

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        api_label = "graphql" if url == self.config.graphql_endpoint else "rest"
        attempt = 0
        while True:
            attempt += 1
            state = await self.pool.acquire()
            headers = dict(kwargs.pop("headers", {}))
            headers["Authorization"] = f"bearer {state.token}"

            start = time.monotonic()
            try:
                resp = await self._client.request(method, url, headers=headers, **kwargs)
            except (httpx.TimeoutException, httpx.TransportError) as e:
                await self.pool.release(state)
                github_requests.labels(api=api_label, status="transient").inc()
                if attempt > self.config.max_retries:
                    raise TransientError(
                        f"network error after {attempt} attempts: {e}"
                    ) from e
                await self._backoff(attempt)
                continue
            finally:
                github_request_seconds.labels(api=api_label).observe(
                    time.monotonic() - start
                )

            remaining = _int_header(resp, "X-RateLimit-Remaining")
            reset = _int_header(resp, "X-RateLimit-Reset")
            await self.pool.release(
                state,
                remaining=remaining,
                reset_at=float(reset) if reset else None,
            )
            try:
                idx = self.pool._states.index(state)
                if remaining is not None:
                    tokens_remaining.labels(
                        platform="github", token_index=str(idx)
                    ).set(remaining)
            except ValueError:
                pass

            if 200 <= resp.status_code < 300:
                github_requests.labels(api=api_label, status="ok").inc()
                return resp

            if resp.status_code in (403, 429):
                retry_after = _int_header(resp, "Retry-After")
                body = resp.text[:200]
                github_requests.labels(api=api_label, status="retry").inc()
                if retry_after:
                    log.warning("Secondary rate limit; sleeping %ds", retry_after)
                    await asyncio.sleep(retry_after)
                    continue
                if remaining == 0:
                    log.warning("Primary rate limit hit on token; rotating")
                    continue
                if attempt > self.config.max_retries:
                    raise TransientError(
                        f"403/429 after {attempt} attempts: {body}"
                    )
                await self._backoff(attempt)
                continue

            if resp.status_code in (404, 410, 451):
                github_requests.labels(api=api_label, status="permanent").inc()
                raise PermanentError(f"{resp.status_code}: {resp.text[:200]}")

            if resp.status_code >= 500:
                github_requests.labels(api=api_label, status="transient").inc()
                if attempt > self.config.max_retries:
                    raise TransientError(
                        f"server error {resp.status_code} after {attempt} attempts"
                    )
                await self._backoff(attempt)
                continue

            github_requests.labels(api=api_label, status="permanent").inc()
            raise PermanentError(f"{resp.status_code}: {resp.text[:200]}")

    async def _backoff(self, attempt: int) -> None:
        delay = self.config.base_backoff_seconds * (2 ** (attempt - 1))
        delay = min(delay, 60.0) + random.uniform(0, 1.0)
        log.debug("Backing off %.2fs (attempt %d)", delay, attempt)
        await asyncio.sleep(delay)

    # ---------- Public API ----------

    async def fetch_user_bundle(self, login: str) -> dict[str, Any]:
        """Fetch profile + repos + recent commits in one GraphQL round-trip."""
        payload = {
            "query": USER_QUERY,
            "variables": {
                "login": login,
                "repoCount": self.config.max_repos_per_user,
                "commitCount": self.config.max_commits_per_repo,
            },
        }
        resp = await self._request("POST", self.config.graphql_endpoint, json=payload)
        data = resp.json()

        if "errors" in data and data["errors"]:
            err_types = {e.get("type") for e in data["errors"]}
            msg = "; ".join(e.get("message", "") for e in data["errors"])
            if "NOT_FOUND" in err_types:
                raise PermanentError(f"user {login} not found")
            raise TransientError(f"graphql errors: {msg}")

        user = data.get("data", {}).get("user")
        if not user:
            raise PermanentError(f"user {login} returned null")
        return user

    async def fetch_user_events(self, login: str) -> list[dict[str, Any]]:
        """Public activity events (REST — not in GraphQL)."""
        url = f"{self.config.rest_endpoint}/users/{login}/events/public"
        params = {"per_page": min(100, self.config.max_events_per_user)}
        resp = await self._request("GET", url, params=params)
        return resp.json()

    async def fetch_repo_commits_paginated(
        self,
        owner: str,
        name: str,
        max_commits: int,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        """Deep commit history via GraphQL cursor pagination (for backfill)."""
        query = """
        query($owner: String!, $name: String!, $after: String, $since: GitTimestamp) {
          repository(owner: $owner, name: $name) {
            defaultBranchRef {
              target {
                ... on Commit {
                  history(first: 100, after: $after, since: $since) {
                    pageInfo { hasNextPage endCursor }
                    nodes {
                      oid message committedDate
                      additions deletions changedFilesIfAvailable
                      author { email user { databaseId login } }
                    }
                  }
                }
              }
            }
          }
        }
        """
        commits: list[dict[str, Any]] = []
        cursor: str | None = None
        while len(commits) < max_commits:
            variables = {
                "owner": owner,
                "name": name,
                "after": cursor,
                "since": since,
            }
            resp = await self._request(
                "POST",
                self.config.graphql_endpoint,
                json={"query": query, "variables": variables},
            )
            data = resp.json()
            if "errors" in data and data["errors"]:
                err_types = {e.get("type") for e in data["errors"]}
                msg = "; ".join(e.get("message", "") for e in data["errors"])
                if "NOT_FOUND" in err_types:
                    raise PermanentError(f"repo {owner}/{name} not found")
                raise TransientError(f"graphql errors: {msg}")
            repo = (data.get("data") or {}).get("repository")
            if not repo:
                raise PermanentError(f"repo {owner}/{name} returned null")
            ref = repo.get("defaultBranchRef") or {}
            target = ref.get("target") or {}
            history = target.get("history") or {}
            nodes = history.get("nodes") or []
            commits.extend(nodes)
            page = history.get("pageInfo") or {}
            if not page.get("hasNextPage"):
                break
            cursor = page.get("endCursor")
        return commits[:max_commits]

    async def fetch_contributions(self, login: str) -> dict[str, Any]:
        """Fetch contributionsCollection for the past year."""
        query = """
        query($login: String!) {
          user(login: $login) {
            contributionsCollection {
              totalCommitContributions
              totalPullRequestContributions
              totalIssueContributions
              totalRepositoryContributions
              pullRequestContributionsByRepository(maxRepositories: 100) {
                repository { nameWithOwner owner { login } }
                contributions { totalCount }
              }
              commitContributionsByRepository(maxRepositories: 100) {
                repository { nameWithOwner owner { login } }
                contributions { totalCount }
              }
            }
          }
        }
        """
        resp = await self._request(
            "POST",
            self.config.graphql_endpoint,
            json={"query": query, "variables": {"login": login}},
        )
        data = resp.json()
        if "errors" in data and data["errors"]:
            err_types = {e.get("type") for e in data["errors"]}
            if "NOT_FOUND" in err_types:
                raise PermanentError(f"user {login} not found")
            msg = "; ".join(e.get("message", "") for e in data["errors"])
            raise TransientError(f"graphql errors: {msg}")
        user = (data.get("data") or {}).get("user")
        if not user:
            raise PermanentError(f"user {login} returned null")
        return user.get("contributionsCollection") or {}


def _int_header(resp: httpx.Response, name: str) -> int | None:
    v = resp.headers.get(name)
    try:
        return int(v) if v is not None else None
    except ValueError:
        return None
