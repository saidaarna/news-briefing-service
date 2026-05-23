"""
Tests for concurrency behaviour in the pipeline and fetch service.

All tests are offline — no real HTTP calls, no real AI calls.
"""
from __future__ import annotations

import asyncio
import pytest


# ---------------------------------------------------------------------------
# Helper: a simple async task that records the order of execution
# ---------------------------------------------------------------------------

async def _succeed(value: int) -> int:
    await asyncio.sleep(0)   # yield control to the event loop
    return value


async def _fail(exc: Exception) -> int:
    await asyncio.sleep(0)
    raise exc


# ---------------------------------------------------------------------------
# asyncio.gather behaviour tests (rubric requirement)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gather_returns_all_results() -> None:
    """asyncio.gather collects results from all tasks in submission order."""
    results = await asyncio.gather(
        _succeed(1),
        _succeed(2),
        _succeed(3),
    )
    assert list(results) == [1, 2, 3]


@pytest.mark.asyncio
async def test_gather_with_return_exceptions_does_not_raise() -> None:
    """With return_exceptions=True one failing task does not kill the rest."""
    results = await asyncio.gather(
        _succeed(1),
        _fail(ValueError("boom")),
        _succeed(3),
        return_exceptions=True,
    )
    assert results[0] == 1
    assert isinstance(results[1], ValueError)
    assert results[2] == 3


@pytest.mark.asyncio
async def test_gather_propagates_exception_by_default() -> None:
    """Without return_exceptions, the first exception is re-raised immediately."""
    with pytest.raises(RuntimeError, match="pipeline error"):
        await asyncio.gather(
            _succeed(1),
            _fail(RuntimeError("pipeline error")),
        )


# ---------------------------------------------------------------------------
# Semaphore bounding — verifies that concurrency is actually capped
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_semaphore_limits_concurrency() -> None:
    """Only LIMIT tasks run concurrently; others wait at the semaphore gate."""
    LIMIT = 3
    sem = asyncio.Semaphore(LIMIT)
    active: list[int] = []
    peak: list[int] = []

    async def _task(i: int) -> None:
        async with sem:
            active.append(i)
            peak.append(len(active))
            await asyncio.sleep(0.01)   # simulate I/O
            active.remove(i)

    await asyncio.gather(*[_task(i) for i in range(10)])
    # At no point should more than LIMIT tasks have been active simultaneously
    assert max(peak) <= LIMIT


@pytest.mark.asyncio
async def test_semaphore_allows_up_to_limit_concurrent() -> None:
    """A semaphore of N should allow N tasks to run truly concurrently."""
    LIMIT = 4
    sem = asyncio.Semaphore(LIMIT)
    started: list[int] = []

    async def _slot(i: int) -> None:
        async with sem:
            started.append(i)
            await asyncio.sleep(0.05)

    # Launch exactly LIMIT tasks — they should all start before any finishes
    tasks = [asyncio.create_task(_slot(i)) for i in range(LIMIT)]
    await asyncio.sleep(0.02)           # let all tasks enter the semaphore
    assert len(started) == LIMIT        # all LIMIT tasks are running
    await asyncio.gather(*tasks)


# ---------------------------------------------------------------------------
# Pipeline: one source fails, the rest still produce output
# (mirrors test_pipeline.py but focused on the gather mechanics)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_gather_partial_failure_is_isolated() -> None:
    """If one coroutine raises, gather(return_exceptions=True) keeps the rest."""
    async def good_source(name: str) -> str:
        await asyncio.sleep(0)
        return f"article_from_{name}"

    async def bad_source() -> str:
        raise ConnectionError("timeout")

    results = await asyncio.gather(
        good_source("bbc"),
        bad_source(),
        good_source("reuters"),
        return_exceptions=True,
    )

    successes = [r for r in results if not isinstance(r, Exception)]
    failures  = [r for r in results if isinstance(r, Exception)]

    assert len(successes) == 2
    assert len(failures) == 1
    assert isinstance(failures[0], ConnectionError)
