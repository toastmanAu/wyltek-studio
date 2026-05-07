# TRELLIS Timeout Tuning + ComfyUI Orphan-Rescue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **Coordination note:** another instance is in this project — confirm no overlapping edits to `backends/comfyui.py`, `server.py`, or `job_queue.py` before each task.

**Goal:** Stop killing healthy TRELLIS textured / Hy3D PBR runs at 30:00, and stop orphaning their `.glb` outputs when the timeout *does* fire. The 2026-04-30 incident (job `7b63c9ba`, 31m47s actual runtime, killed at 30:00) shows both failures: timeout was too tight, AND when it fired the GLB ComfyUI eventually wrote was lost to the gallery because `_run_job` had already torn down.

**Architecture:** Three-layer timeout already exists (`server.py` per-job cap → `job_queue.py:asyncio.wait_for` → `comfyui.py` inner poll). Re-tune them so inner < outer with handoff slack, and split flat per-mode-flag values into per-mode tables that reflect actual wallclock for each engine/mode/resolution combo. Add a generic orphan-rescue helper that, on `TimeoutError`, globs the ComfyUI output dir for a fresh artifact matching the job's `file_prefix` and best-effort copies it into `storage/unsorted/{date}/{kind}/`, returning a "complete-late" status instead of "failed". Reusable for any ComfyUI-backed mode (TRELLIS, Hy3D, video render, anything that fires-and-forgets to ComfyUI).

**Tech Stack:** Python 3.10 / FastAPI / pytest, vanilla HTML+JS frontend, ComfyUI on `:8188`, `ComfyUI-Trellis2-GGUF` + `ComfyUI-Hunyuan3DWrapper` custom nodes.

---

## Background — incident reference (read first)

**Job `7b63c9ba`, 2026-04-30 14:45–15:17:**

| Time | Event |
|------|-------|
| 14:45:40 | `POST /api/generate` (mode=3d, engine=trellis, trellis_mode=textured) → JobQueue starts 1800s timer at server.py:1278 |
| 14:46:27 → 14:58:19 | ComfyUI: Shape Slat Flow 1024 sampling (silent — no per-step events) |
| 14:58:21 → 15:11:48 | ComfyUI: Shape Slat decoder + mesh extract (7.2M faces → floater removal → dual contouring → 1.3M faces) |
| 15:12:07 → 15:17:20 | ComfyUI: Texture Slat Flow 1024 sampling (silent) |
| **15:15:40** | **Open-palette: `TimeoutError: Job 7b63c9ba timed out after 1800s on gpu lane`** — task cancelled, `_run_job` unwinds. WS reader gets `CancelledError` mid-receive. |
| 15:17:20 | ComfyUI logs `[Trellis2] Offloading all models to CPU...` (deliberate VRAM free between flow and decoder, not a hang) |
| 15:17:28 | ComfyUI: `Prompt executed in 00:31:47`, writes `/home/phill/ComfyUI/output/3D/wyltek-trellis_219d59e9_textured_00001_.glb` (4.8 MB) |

**Result:** GLB exists on disk under ComfyUI's tree, but `shutil.copy2(chosen, output_path)` at `backends/comfyui.py:2960` never ran, so nothing landed in `/home/phill/open-palette/storage/unsorted/2026-04-30/meshes/`, so the gallery was empty. Manually rescued at 15:50 by copying to `7b63c9ba.glb` with a `rescued: true` sidecar — that file is in the gallery now and is what this plan exists because of.

**Three timeout sites that all converge on 1800s for this code path:**
- `server.py:1278` — `job_timeout = 1800 if is_3d else 0` (outer per-job cap for ALL 3D jobs regardless of engine/mode)
- `job_queue.py:78` — enforces via `asyncio.wait_for(coro, timeout=job_timeout)`
- `backends/comfyui.py:2842` — `timeout_s = 1800 if trellis_mode == "textured" else 600` (inner ComfyUI poll for TRELLIS)
- `backends/comfyui.py:2634` — `timeout_s = 1800 if mode == "pbr" else 300` (inner ComfyUI poll for Hy3D)

The two-layer 1800/1800 collision is the bug.

---

## Task 1: Per-mode timeout table (replace flat `is_3d ? 1800 : 0`)

**Files:**
- Modify: `server.py` (around line 1273–1280)
- Modify: `backends/comfyui.py` (around lines 2634, 2842)

**Why:** TRELLIS textured @ 1024 is empirically ~32 min on a 7900 XTX. Hy3D PBR is ~3–5 min. Hy3D shape-only is ~30s. TRELLIS shape-only is ~1–2 min. Lumping them as `is_3d ? 1800` gives the longest path zero headroom and the shortest path 60× more than it needs.

- [ ] **Step 1: Add a `_resolve_3d_job_timeouts()` helper in `server.py`**

Insert near the top of `server.py` (next to other module-level config), returning `(outer, inner)` so the two layers stay coupled but with a fixed handoff gap. **Pick `outer = inner + 180s`** — three minutes of slack covers the post-completion `shutil.copy2`, sidecar write, and gallery cache invalidation, without leaving zombie jobs around for too long.

```python
# 3D job timeouts — empirically tuned per engine/mode. The OUTER timeout
# (asyncio.wait_for in JobQueue) MUST be larger than the INNER timeout
# (ComfyUI poll in backends/comfyui.py) so that on a healthy completion
# the inner finishes first and the outer never fires. 180s slack covers
# post-completion copy, sidecar write, and gallery cache invalidation.
#
# Keys: ("engine", "mode-flag")
# Values: inner ComfyUI-poll timeout in seconds (outer = inner + 180)
_3D_INNER_TIMEOUTS = {
    ("trellis", "textured"): 3000,  # ~32 min observed; 8 min headroom
    ("trellis", "white"):     600,  # ~1–2 min observed
    ("hy3d",    "pbr"):      2100,  # ~3–5 min typical, 35 min hard cap
    ("hy3d",    "shape"):     300,  # ~30s typical
}
_3D_INNER_TIMEOUT_DEFAULT = 1800  # fallback for unknown combos
_3D_OUTER_HANDOFF_SLACK = 180


def resolve_3d_timeouts(engine: str, mode_flag: str) -> tuple[int, int]:
    """Return (outer_job_timeout, inner_comfy_timeout) in seconds.

    `engine` is "trellis" or "hy3d". `mode_flag` is "textured"/"white" for
    TRELLIS or "pbr"/"shape" for Hy3D. Outer is always inner + slack so a
    healthy run never trips the outer.
    """
    inner = _3D_INNER_TIMEOUTS.get((engine, mode_flag), _3D_INNER_TIMEOUT_DEFAULT)
    return inner + _3D_OUTER_HANDOFF_SLACK, inner
```

- [ ] **Step 2: Use the helper at `server.py:1278`**

Replace the existing block:

```python
    # OLD:
    # 2D jobs are <1min so the default 300s gpu-lane timeout is fine.
    # 3D jobs (Hy3D PBR / TRELLIS textured + cascade + multi-view) can hit
    # 10–15 min on max-quality settings. Bump the timeout so the asyncio.wait_for
    # in JobQueue doesn't cancel a perfectly healthy long-running TRELLIS job
    # at the 5-min mark and orphan its .glb output.
    job_timeout = 1800 if is_3d else 0  # 0 = use lane default (300s)
```

With:

```python
    # 2D jobs are <1min so the default 300s gpu-lane timeout is fine.
    # 3D jobs vary wildly (TRELLIS textured ~32 min, Hy3D shape ~30s),
    # so look up the per-(engine, mode) outer timeout. Outer is sized
    # so a healthy ComfyUI run finishes inside the inner timeout first;
    # the outer is just a backstop for genuine hangs.
    if is_3d:
        engine = params.get("engine", "hy3d")
        if engine == "trellis":
            mode_flag = params.get("trellis_mode", "white")
        else:
            mode_flag = "pbr" if params.get("texture") else "shape"
        params["_inner_timeout_s"], _ = resolve_3d_timeouts(engine, mode_flag)
        # Note: stash inner timeout on params so backends/comfyui.py can read it
        # without re-deriving the same logic.
        job_timeout, _inner = resolve_3d_timeouts(engine, mode_flag)
        # Fix above ordering: we want outer first.
        outer, inner = resolve_3d_timeouts(engine, mode_flag)
        params["_inner_timeout_s"] = inner
        job_timeout = outer
    else:
        job_timeout = 0  # use lane default (300s)
```

> ⚠️ Implementer note: confirm what flag distinguishes Hy3D PBR from Hy3D shape-only at this call site. Existing code at `comfyui.py:2634` uses `mode == "pbr"`. Check what `params.get("mode")` actually is for Hy3D paths in the working dispatch — `_run_job` uses `params.get("mode") == "3d"` as the is_3d gate, so Hy3D's textured-vs-shape distinction is a *different* param. Read `backends/comfyui.py:generate_3d` (lines ~2532–2700) to find which key gates PBR vs shape, then mirror that here.

- [ ] **Step 3: Have `comfyui.py:generate_trellis` and `generate_3d` honour the inner timeout from `params`**

In `backends/comfyui.py`, replace at line 2842:

```python
# OLD:
timeout_s = 1800 if trellis_mode == "textured" else 600
# NEW:
timeout_s = int(params.get("_inner_timeout_s") or (3000 if trellis_mode == "textured" else 600))
```

And at line 2634:

```python
# OLD:
timeout_s = 1800 if mode == "pbr" else 300
# NEW:
timeout_s = int(params.get("_inner_timeout_s") or (2100 if mode == "pbr" else 300))
```

Both fall back to a sensible default if `_inner_timeout_s` isn't set (e.g. tests, or callers that bypass `_run_job`).

---

## Task 2: Generic ComfyUI orphan-rescue helper

**Files:**
- Modify: `backends/comfyui.py` (add a module-level helper, modify `generate_trellis` + `generate_3d` exception paths)

**Why:** Even with right-sized timeouts, a genuinely hung ComfyUI (driver crash, OOM mid-decode, network hiccup) can still trip the outer cap. When that happens, ComfyUI may *still* finish the prompt afterward and write the GLB. The current code unconditionally raises and the artifact is lost. We can do better with a 30s grace window after `TimeoutError`: if the GLB now exists in ComfyUI's output dir matching the prompt's `file_prefix`, copy it and report `complete-late` instead of `failed`.

- [ ] **Step 1: Write the helper**

Add to `backends/comfyui.py` near other module-level helpers (above `class ComfyUIBackend`):

```python
async def _rescue_orphan_glb(
    file_prefix: str,
    output_path: str,
    *,
    grace_seconds: int = 30,
    poll_interval: float = 2.0,
    comfy_output_dir: Path = Path("/home/phill/ComfyUI/output"),
) -> str | None:
    """Best-effort recovery of a `.glb` that ComfyUI may write *after* an
    open-palette TimeoutError. Polls the ComfyUI output dir for up to
    `grace_seconds` looking for a file matching `<file_prefix>*_.glb`.
    If a textured variant exists, prefers it. On match: copies to
    `output_path` (preserving mtime) and returns the source path.
    Returns None on timeout or no match.
    """
    deadline = asyncio.get_event_loop().time() + grace_seconds
    pattern = str(comfy_output_dir / f"{file_prefix}*_.glb")
    while asyncio.get_event_loop().time() < deadline:
        matches = sorted(glob(pattern))
        textured = [m for m in matches if "_textured_" in m]
        chosen = textured[-1] if textured else (matches[-1] if matches else None)
        if chosen:
            shutil.copy2(chosen, output_path)
            return chosen
        await asyncio.sleep(poll_interval)
    return None
```

- [ ] **Step 2: Wrap `generate_trellis`'s timeout path**

Locate the `_poll_history_long` fallback at `comfyui.py:2939` and the surrounding `try:` block. The current shape (paraphrased):

```python
try:
    async with session.ws_connect(...) as ws:
        async for msg in ws:
            ...
except aiohttp.ClientError:
    await self._poll_history_long(session, url, prompt_id, on_progress, timeout_s)
```

`_poll_history_long` raises `RuntimeError("Hy3D generation timed out ...")` when the inner timeout expires. It does NOT raise on outer (`asyncio.wait_for`) cancellation — that propagates as `CancelledError` from above. We need to catch BOTH and try the rescue:

```python
try:
    async with session.ws_connect(...) as ws:
        ...
except (aiohttp.ClientError, asyncio.CancelledError, RuntimeError) as e:
    # First fallback to history poll if it was just a WS hiccup.
    if isinstance(e, aiohttp.ClientError):
        try:
            await self._poll_history_long(session, url, prompt_id, on_progress, timeout_s)
        except RuntimeError:
            pass  # fall through to orphan rescue
    # Orphan rescue: ComfyUI may finish after we gave up.
    rescued = await _rescue_orphan_glb(file_prefix, output_path)
    if rescued:
        await on_progress(95, "TRELLIS finished late; rescued .glb")
    else:
        raise  # re-raise the original; nothing to recover
```

> ⚠️ Implementer note: `asyncio.CancelledError` from outer `wait_for` will *also* tear down the rescue itself unless we shield it. Wrap the rescue in `asyncio.shield()` so the rescue completes even if the outer task is being cancelled:
>
> ```python
> rescued = await asyncio.shield(_rescue_orphan_glb(file_prefix, output_path))
> ```

- [ ] **Step 3: Mirror in `generate_3d` (Hy3D)**

Same pattern around `comfyui.py:2685–2705`. Hy3D's `file_prefix` is built the same way (`3D/wyltek-3d_<job_short>` style at line 2580ish — verify exact form).

- [ ] **Step 4: Surface "rescued" in the sidecar metadata**

In `server.py:_run_job`, when `generate_trellis` / `generate_3d` returns, check for a marker the rescue path should set. Update the helper to return a richer signal:

Change `_rescue_orphan_glb` return from `str | None` to `dict | None`:

```python
return {
    "rescued": True,
    "source": chosen,
    "rescued_at": datetime.now().isoformat(),
}
```

Have `generate_trellis` / `generate_3d` merge this into their return dict; `_run_job` already merges that into the sidecar at `server.py:2892`.

---

## Task 3: Tests

**Files:**
- Create: `tests/test_3d_timeouts.py`
- Create: `tests/test_orphan_rescue.py`

- [ ] **Step 1: Unit test the timeout resolver**

```python
# tests/test_3d_timeouts.py
from server import resolve_3d_timeouts, _3D_OUTER_HANDOFF_SLACK


def test_trellis_textured_outer_exceeds_inner_with_slack():
    outer, inner = resolve_3d_timeouts("trellis", "textured")
    assert inner == 3000
    assert outer == inner + _3D_OUTER_HANDOFF_SLACK


def test_hy3d_pbr_has_5min_room():
    outer, inner = resolve_3d_timeouts("hy3d", "pbr")
    assert inner >= 1800, "Hy3D PBR needs >= 30 min; observed 3–5 min typical"


def test_unknown_combo_falls_back():
    outer, inner = resolve_3d_timeouts("magic-box-3d", "ultra-mode")
    assert inner == 1800  # _3D_INNER_TIMEOUT_DEFAULT
    assert outer == inner + _3D_OUTER_HANDOFF_SLACK


def test_outer_always_strictly_greater_than_inner():
    """Property: every entry in the table must satisfy outer > inner so a
    healthy run never trips the outer."""
    for engine in ("trellis", "hy3d"):
        for mode in ("textured", "white", "pbr", "shape"):
            outer, inner = resolve_3d_timeouts(engine, mode)
            assert outer > inner
```

- [ ] **Step 2: Integration-ish test for orphan rescue**

```python
# tests/test_orphan_rescue.py
import asyncio
from pathlib import Path
import shutil
import tempfile

import pytest

from backends.comfyui import _rescue_orphan_glb


@pytest.mark.asyncio
async def test_rescue_finds_textured_glb_written_during_grace(tmp_path):
    """ComfyUI writes the GLB after we've timed out — rescue should find it."""
    comfy_out = tmp_path / "comfy"
    comfy_out.mkdir()
    file_prefix = "3D/wyltek-trellis_abc12345"
    (comfy_out / "3D").mkdir()

    output_path = tmp_path / "rescued.glb"

    async def write_late():
        await asyncio.sleep(1.0)  # simulate ComfyUI finishing 1s after we gave up
        target = comfy_out / f"{file_prefix}_textured_00001_.glb"
        target.write_bytes(b"fake glb content")

    writer = asyncio.create_task(write_late())
    result = await _rescue_orphan_glb(
        file_prefix, str(output_path),
        grace_seconds=5, poll_interval=0.2,
        comfy_output_dir=comfy_out,
    )
    await writer

    assert result is not None
    assert result["rescued"] is True
    assert "_textured_" in result["source"]
    assert output_path.exists()
    assert output_path.read_bytes() == b"fake glb content"


@pytest.mark.asyncio
async def test_rescue_returns_none_when_no_artifact_in_grace_window(tmp_path):
    comfy_out = tmp_path / "comfy"
    comfy_out.mkdir()
    output_path = tmp_path / "out.glb"
    result = await _rescue_orphan_glb(
        "3D/never-existed", str(output_path),
        grace_seconds=1, poll_interval=0.2,
        comfy_output_dir=comfy_out,
    )
    assert result is None
    assert not output_path.exists()


@pytest.mark.asyncio
async def test_rescue_prefers_textured_over_white_when_both_present(tmp_path):
    comfy_out = tmp_path / "comfy"
    (comfy_out / "3D").mkdir(parents=True)
    file_prefix = "3D/wyltek-trellis_xyz98765"
    (comfy_out / f"{file_prefix}_white_00001_.glb").write_bytes(b"white")
    (comfy_out / f"{file_prefix}_textured_00001_.glb").write_bytes(b"textured")

    output_path = tmp_path / "rescued.glb"
    result = await _rescue_orphan_glb(
        file_prefix, str(output_path),
        grace_seconds=2, poll_interval=0.2,
        comfy_output_dir=comfy_out,
    )
    assert result is not None
    assert "_textured_" in result["source"]
    assert output_path.read_bytes() == b"textured"
```

- [ ] **Step 3: Run the suite**

```bash
cd /home/phill/open-palette
python -m pytest tests/test_3d_timeouts.py tests/test_orphan_rescue.py -v
```

All four resolver tests + three rescue tests must pass before moving on.

---

## Task 4: One-time backfill of past orphans (optional but recommended)

**Files:**
- Create: `scripts/backfill_orphan_meshes.py`

**Why:** This isn't the first textured run that timed out. Whatever else is in `/home/phill/ComfyUI/output/3D/` matching `wyltek-trellis_*_textured_*.glb` and *not* present in `storage/unsorted/{any-date}/meshes/` is a past orphan we can surface retroactively.

- [ ] **Step 1: Write the script**

```python
#!/usr/bin/env python3
"""One-shot: find ComfyUI 3D outputs not present in open-palette storage
and copy them in with rescued=true sidecars. Idempotent — re-running is safe."""

from datetime import datetime
from glob import glob
import json
from pathlib import Path
import shutil
import sys

COMFY_3D = Path("/home/phill/ComfyUI/output/3D")
STORAGE = Path("/home/phill/open-palette/storage/unsorted")


def existing_glb_basenames() -> set[str]:
    """Set of all .glb filenames currently in any unsorted/{date}/meshes/."""
    return {p.name for p in STORAGE.glob("*/meshes/*.glb")}


def find_orphans() -> list[Path]:
    """ComfyUI .glb files whose mtime-day has no matching file in storage.
    Conservative match: we use the source filename's job-id-ish slice so a
    real run that DID land doesn't get duplicated."""
    have = existing_glb_basenames()
    orphans = []
    for p in sorted(COMFY_3D.glob("wyltek-*_textured_*.glb")):
        # If we have ANY .glb sized within ±1 byte of this one's size in
        # storage on the same day, assume it's already been copied in.
        day = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")
        target_dir = STORAGE / day / "meshes"
        if not target_dir.exists():
            orphans.append(p)
            continue
        already = any(
            abs(q.stat().st_size - p.stat().st_size) < 2
            for q in target_dir.glob("*.glb")
        )
        if not already:
            orphans.append(p)
    return orphans


def rescue(p: Path, dry_run: bool = True) -> Path:
    """Copy a single orphan into storage with a rescue sidecar."""
    day = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")
    target_dir = STORAGE / day / "meshes"
    # Job ID: take first 8 chars of the slice between "trellis_" and "_textured"
    # If we can't parse it, hash the path.
    try:
        job_id = p.name.split("_textured_")[0].split("_")[-1][:8]
    except Exception:
        job_id = p.stem[:8]
    target_glb = target_dir / f"{job_id}.glb"
    target_json = target_dir / f"{job_id}.json"
    if dry_run:
        print(f"DRY: {p}  ->  {target_glb}")
        return target_glb
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, target_glb)
    target_json.write_text(json.dumps({
        "job_id": job_id,
        "backend": "comfyui",
        "engine": "trellis",
        "mode": "3d",
        "trellis_mode": "textured",
        "format": "glb",
        "rescued": True,
        "rescue_reason": "Backfill from /home/phill/ComfyUI/output/3D/",
        "source": str(p),
        "rescued_at": datetime.now().isoformat(),
    }, indent=2))
    return target_glb


if __name__ == "__main__":
    dry = "--apply" not in sys.argv
    orphans = find_orphans()
    print(f"Found {len(orphans)} orphan(s).")
    for p in orphans:
        rescue(p, dry_run=dry)
    if dry and orphans:
        print("\nRe-run with --apply to actually copy.")
```

- [ ] **Step 2: Dry-run it**

```bash
python /home/phill/open-palette/scripts/backfill_orphan_meshes.py
```

Review the output. If sane, apply:

```bash
python /home/phill/open-palette/scripts/backfill_orphan_meshes.py --apply
```

> ⚠️ Implementer note: do NOT run `--apply` if the user's ComfyUI output dir contains test/scratch GLBs they explicitly don't want surfaced. Eyeball the dry-run list first.

---

## Task 5: Verify against the next live TRELLIS textured run

**Manual, run after Tasks 1–3 ship:**

- [ ] **Step 1: Trigger a TRELLIS textured run from the studio UI** (Phill said they'll do this).
- [ ] **Step 2: While running, confirm** `journalctl --user -u open-palette.service -f | grep -i timeout` produces nothing (no premature outer fire).
- [ ] **Step 3: After completion, confirm** the new GLB appears in `/api/gallery` automatically — no rescue path activated, no `rescued: true` in the sidecar JSON.
- [ ] **Step 4 (negative test):** Temporarily lower `_3D_INNER_TIMEOUTS[("trellis","textured")]` to `60` and re-trigger. The outer should fire at ~240s; rescue should kick in once ComfyUI finishes ~30 min later, surfacing the GLB with `rescued: true` in the sidecar. Restore the original value afterwards.

---

## Out of scope (note for follow-up)

- **TRELLIS resolution=512 path**: not currently exposed in our workflow builder; would have ~6× faster runtimes if added. Separate plan.
- **CPU offload behaviour** (`[Trellis2] Offloading all models to CPU...` in `ComfyUI-Trellis2-GGUF/.../trellis2_image_to_3d.py:205`): investigated and confirmed benign — single ~2s blip between texture-flow and texture-decoder, deliberate VRAM free. No change needed.
- **ComfyUI prompt-abort RPC**: there's no clean API to cancel an in-flight prompt from open-palette's side. Even with right-sized timeouts, a real hang means we leave ComfyUI grinding until it OOMs or finishes. Separate, larger plan if it becomes an issue.

---

## Success criteria

1. The 2026-04-30 incident pattern (32-min TRELLIS textured run killed at 30:00 by both layers) cannot recur — outer is 3180s, inner is 3000s.
2. If ComfyUI ever does run past the inner timeout, `_rescue_orphan_glb` recovers the artifact within 30s of ComfyUI writing it.
3. All four `tests/test_3d_timeouts.py` and three `tests/test_orphan_rescue.py` cases pass.
4. The next textured run Phill triggers shows `rescued: false` (i.e. doesn't need the rescue path) in its sidecar JSON.
