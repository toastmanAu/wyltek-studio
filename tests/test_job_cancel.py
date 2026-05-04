"""Tests for job cancellation pathway.

Property under test: a cancelled job's coroutine receives CancelledError,
the JobQueue cleans up, and a subsequent status() shows the slot freed.
"""

import asyncio

import pytest

from job_queue import JobQueue


@pytest.mark.asyncio
async def test_cancel_in_flight_job_unblocks_lane():
    queue = JobQueue()
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def long_running():
        started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    job_id = "cancel-test-1"
    queue.submit_background(long_running(), lane="gpu", job_id=job_id, timeout=120)

    await asyncio.wait_for(started.wait(), timeout=2.0)
    # Job is now running.
    assert queue.status()["gpu"]["running"] == 1

    ok = await queue.cancel(job_id)
    assert ok is True
    await asyncio.wait_for(cancelled.wait(), timeout=2.0)

    # Slot should free within a beat.
    await asyncio.sleep(0.1)
    assert queue.status()["gpu"]["running"] == 0


@pytest.mark.asyncio
async def test_cancel_unknown_job_returns_false():
    queue = JobQueue()
    ok = await queue.cancel("does-not-exist")
    assert ok is False


@pytest.mark.asyncio
async def test_cancel_queued_but_not_started_job():
    queue = JobQueue()
    blocker_started = asyncio.Event()

    async def blocker():
        blocker_started.set()
        await asyncio.sleep(60)

    async def queued_job():
        # Should never start — gets cancelled while queued.
        return "should not reach"

    queue.submit_background(blocker(), lane="gpu", job_id="blocker", timeout=120)
    await asyncio.wait_for(blocker_started.wait(), timeout=2.0)

    queue.submit_background(queued_job(), lane="gpu", job_id="queued", timeout=120)
    await asyncio.sleep(0.05)  # let it land in the queued deque
    assert queue.status()["gpu"]["queued"] >= 1

    ok = await queue.cancel("queued")
    assert ok is True
    await asyncio.sleep(0.05)

    # Cleanup: cancel the blocker so the test ends.
    await queue.cancel("blocker")
