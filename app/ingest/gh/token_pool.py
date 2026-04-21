"""
Token pool with round-robin rotation and rate-limit awareness.

GitHub rate limits are per-token (5000/hr for GraphQL points, 5000/hr REST).
With N tokens you effectively get Nx the throughput. When a token is
rate-limited we park it until its reset time and hand out another.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

log = logging.getLogger(__name__)


@dataclass
class TokenState:
    token: str
    remaining: int = 5000
    reset_at: float = 0.0
    in_use: bool = False

    @property
    def is_available(self) -> bool:
        if self.in_use:
            return False
        if self.remaining > 0:
            return True
        return time.time() >= self.reset_at


class TokenPool:
    """Thread-safe async token pool. Blocks when all tokens exhausted."""

    def __init__(self, tokens: list[str]) -> None:
        if not tokens:
            raise ValueError("TokenPool requires at least one token")
        self._states: list[TokenState] = [TokenState(token=t) for t in tokens]
        self._lock = asyncio.Lock()
        self._cond = asyncio.Condition(self._lock)

    async def acquire(self) -> TokenState:
        """Wait for an available token, mark it in-use, return it."""
        async with self._cond:
            while True:
                candidates = [s for s in self._states if s.is_available]
                if candidates:
                    chosen = max(candidates, key=lambda s: s.remaining)
                    chosen.in_use = True
                    return chosen

                sleeping = [s for s in self._states if not s.in_use and s.remaining <= 0]
                if sleeping:
                    soonest = min(s.reset_at for s in sleeping)
                    wait = max(0.5, soonest - time.time())
                    log.warning("All tokens exhausted; sleeping %.1fs until reset", wait)
                    try:
                        await asyncio.wait_for(self._cond.wait(), timeout=wait)
                    except TimeoutError:
                        pass
                else:
                    await self._cond.wait()

    async def release(
        self,
        state: TokenState,
        remaining: int | None = None,
        reset_at: float | None = None,
    ) -> None:
        async with self._cond:
            state.in_use = False
            if remaining is not None:
                state.remaining = remaining
            if reset_at is not None:
                state.reset_at = reset_at
            self._cond.notify_all()

    def snapshot(self) -> list[dict]:
        return [
            {"remaining": s.remaining, "reset_in_s": max(0, int(s.reset_at - time.time()))}
            for s in self._states
        ]
