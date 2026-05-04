"""Smooth progress interpolator for async progress callbacks.

Between explicit anchors set via `await sp.set(pct, msg)`, this scheduler
ticks at `tick_seconds` and advances the reported pct toward
`anchor + max_creep` (capped at 99). Stops the bar from looking frozen
during opaque kernel calls without ever lying about completion.

Ported from modly's `smooth_progress` daemon thread
(api/services/generators/base.py:602-624). Modly's version is sync because
its progress_cb is sync; ours is an asyncio.Task because open-palette's
on_progress is async.

Usage:
    async with SmoothProgress(on_progress, tick_seconds=2.0) as sp:
        await sp.set(10, "loading model")
        await run_opaque_thing()  # bar creeps 10 -> 15 while we wait
        await sp.set(50, "DiT step 1")
        ...
        await sp.set(100, "done")
"""

import asyncio
from typing import Awaitable, Callable

ProgressCallback = Callable[[int, str], Awaitable[None]]


class SmoothProgress:
    def __init__(
        self,
        callback: ProgressCallback,
        tick_seconds: float = 2.0,
        max_creep: int = 5,
        creep_ceiling: int = 99,
    ):
        self._cb = callback
        self._tick = tick_seconds
        self._max_creep = max_creep
        self._ceiling = creep_ceiling
        self._anchor: int = 0
        self._anchor_msg: str = ""
        self._reported: int = 0
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def set(self, pct: int, msg: str = "") -> None:
        """Set an explicit anchor and fire the callback immediately."""
        async with self._lock:
            self._anchor = pct
            self._anchor_msg = msg
            self._reported = pct
        await self._cb(pct, msg)

    async def _tick_loop(self) -> None:
        while True:
            await asyncio.sleep(self._tick)
            async with self._lock:
                ceiling = min(self._anchor + self._max_creep, self._ceiling)
                if self._reported < ceiling:
                    self._reported += 1
                    pct, msg = self._reported, self._anchor_msg
                else:
                    continue
            await self._cb(pct, msg)

    async def __aenter__(self) -> "SmoothProgress":
        self._task = asyncio.create_task(self._tick_loop())
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
