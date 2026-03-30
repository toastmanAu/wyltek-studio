"""Resource-aware job queue with concurrency lanes.

GPU jobs run serially (ComfyUI processes one at a time).
CPU jobs run in parallel (TTS, scoring, prompt enhancement).
Render jobs run serially (FFmpeg is disk I/O heavy).

Usage:
    queue = JobQueue()
    await queue.submit(my_coroutine(), lane="gpu", job_id="abc123")
    status = queue.status()  # {"gpu": {"running": 1, "queued": 3}, ...}
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class QueuedJob:
    job_id: str
    lane: str
    coro: asyncio.coroutines = None
    task: asyncio.Task = None
    queued_at: datetime = field(default_factory=datetime.now)
    started_at: datetime = None


class JobQueue:
    # Max concurrent jobs per lane
    LANE_LIMITS = {
        "gpu": 1,       # ComfyUI processes serially
        "cpu": 3,        # TTS, scoring, prompt enhancement
        "render": 1,     # FFmpeg video rendering
    }

    def __init__(self):
        self._semaphores = {
            lane: asyncio.Semaphore(limit)
            for lane, limit in self.LANE_LIMITS.items()
        }
        self._queued: dict[str, deque[QueuedJob]] = {
            lane: deque() for lane in self.LANE_LIMITS
        }
        self._running: dict[str, list[QueuedJob]] = {
            lane: [] for lane in self.LANE_LIMITS
        }

    async def submit(self, coro, lane: str = "gpu", job_id: str = ""):
        """Submit a coroutine to a resource lane. Waits for slot, then runs."""
        if lane not in self._semaphores:
            lane = "cpu"  # fallback

        job = QueuedJob(job_id=job_id, lane=lane)
        self._queued[lane].append(job)

        async with self._semaphores[lane]:
            # Move from queued to running
            if job in self._queued[lane]:
                self._queued[lane].remove(job)
            job.started_at = datetime.now()
            self._running[lane].append(job)

            try:
                return await coro
            finally:
                self._running[lane].remove(job)

    def submit_background(self, coro, lane: str = "gpu", job_id: str = ""):
        """Submit without awaiting — returns immediately, job runs when slot opens."""
        asyncio.create_task(self.submit(coro, lane=lane, job_id=job_id))

    def status(self) -> dict:
        """Current queue status per lane."""
        result = {}
        for lane in self.LANE_LIMITS:
            result[lane] = {
                "running": len(self._running[lane]),
                "queued": len(self._queued[lane]),
                "limit": self.LANE_LIMITS[lane],
                "running_jobs": [j.job_id for j in self._running[lane]],
                "queued_jobs": [j.job_id for j in self._queued[lane]],
            }
        return result

    def position(self, job_id: str) -> dict | None:
        """Get queue position for a specific job."""
        for lane in self.LANE_LIMITS:
            for i, job in enumerate(self._queued[lane]):
                if job.job_id == job_id:
                    return {"lane": lane, "position": i + 1, "status": "queued"}
            for job in self._running[lane]:
                if job.job_id == job_id:
                    return {"lane": lane, "position": 0, "status": "running"}
        return None
