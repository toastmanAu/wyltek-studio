"""Tests for the smooth_progress interpolator.

Property under test: between explicit anchors, the reported pct should
creep upward at a fixed cadence without ever exceeding (anchor + max_creep)
or 99 (we never auto-tick to 100 — only an explicit set() can do that).
"""

import asyncio
import pytest

from progress_smooth import SmoothProgress


@pytest.mark.asyncio
async def test_explicit_set_fires_callback_immediately():
    seen = []

    async def cb(pct, msg=""):
        seen.append((pct, msg))

    async with SmoothProgress(cb, tick_seconds=10.0) as sp:
        await sp.set(25, "loaded")

    # Single explicit anchor, no creep yet (tick is far in the future).
    assert seen[0] == (25, "loaded")


@pytest.mark.asyncio
async def test_creep_advances_between_anchors():
    seen = []

    async def cb(pct, msg=""):
        seen.append(pct)

    async with SmoothProgress(cb, tick_seconds=0.05, max_creep=5) as sp:
        await sp.set(10, "stage A")
        await asyncio.sleep(0.20)  # ~4 ticks of creep allowed
        await sp.set(50, "stage B")

    # Creep should have advanced past 10 but never above 15 (10 + max_creep).
    creep_values = [p for p in seen if 10 < p <= 15]
    assert creep_values, f"expected creep between anchors, got {seen}"
    assert max(seen[: seen.index(50)]) <= 15


@pytest.mark.asyncio
async def test_creep_never_reaches_100_implicitly():
    seen = []

    async def cb(pct, msg=""):
        seen.append(pct)

    async with SmoothProgress(cb, tick_seconds=0.02, max_creep=10) as sp:
        await sp.set(95, "almost there")
        await asyncio.sleep(0.30)  # plenty of ticks

    # Anchor was 95, max_creep is 10, but ceiling is 99 — never auto-100.
    assert max(seen) <= 99
    assert 100 not in seen


@pytest.mark.asyncio
async def test_explicit_set_to_100_passes_through():
    seen = []

    async def cb(pct, msg=""):
        seen.append(pct)

    async with SmoothProgress(cb, tick_seconds=10.0) as sp:
        await sp.set(50, "halfway")
        await sp.set(100, "done")

    assert seen[-1] == 100


@pytest.mark.asyncio
async def test_context_exit_stops_ticking():
    seen = []

    async def cb(pct, msg=""):
        seen.append(pct)

    async with SmoothProgress(cb, tick_seconds=0.02, max_creep=5) as sp:
        await sp.set(10, "")
        await asyncio.sleep(0.10)

    count_before = len(seen)
    await asyncio.sleep(0.10)
    # After the context closed, no further callbacks should fire.
    assert len(seen) == count_before
