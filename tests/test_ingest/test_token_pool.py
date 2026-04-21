"""Unit tests for the GitHub token pool — no network or DB."""
import asyncio
import time

import pytest

from app.ingest.gh.token_pool import TokenPool


@pytest.mark.asyncio
async def test_basic_acquire_release():
    pool = TokenPool(["a", "b"])
    s1 = await pool.acquire()
    s2 = await pool.acquire()
    assert s1.token != s2.token
    await pool.release(s1)
    await pool.release(s2)


@pytest.mark.asyncio
async def test_blocks_when_all_in_use():
    pool = TokenPool(["only"])
    s1 = await pool.acquire()

    async def try_acquire():
        s = await pool.acquire()
        await pool.release(s)
        return True

    task = asyncio.create_task(try_acquire())
    await asyncio.sleep(0.05)
    assert not task.done(), "should block with no available tokens"
    await pool.release(s1)
    assert await asyncio.wait_for(task, timeout=1.0)


@pytest.mark.asyncio
async def test_prefers_higher_remaining():
    pool = TokenPool(["low", "high"])
    s_low = await pool.acquire()
    await pool.release(s_low, remaining=10)
    s_high = await pool.acquire()
    await pool.release(s_high, remaining=5000)

    chosen = await pool.acquire()
    assert chosen.remaining == 5000
    await pool.release(chosen)


@pytest.mark.asyncio
async def test_exhausted_token_waits_for_reset():
    pool = TokenPool(["t"])
    s = await pool.acquire()
    await pool.release(s, remaining=0, reset_at=time.time() + 0.3)

    start = time.time()
    s2 = await pool.acquire()
    elapsed = time.time() - start
    assert elapsed >= 0.25
    await pool.release(s2)


def test_snapshot():
    pool = TokenPool(["a", "b"])
    snap = pool.snapshot()
    assert len(snap) == 2
    assert all("remaining" in s for s in snap)


def test_empty_tokens_raises():
    with pytest.raises(ValueError, match="at least one token"):
        TokenPool([])
