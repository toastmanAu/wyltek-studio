# Modly Tier-1 Ports — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port four polished patterns from `lightningpixel/modly` into open-palette to close the lift gaps identified in the 2026-05-04 audit: smooth_progress interpolator, pymeshlab mesh optimisation, trimesh format conversion, and a real subprocess-aware cancel pathway.

**Architecture:** Three new self-contained Python modules at the repo root (`progress_smooth.py`, `mesh_optimize.py`, `mesh_export.py`) plus surgical edits to `job_queue.py` and `server.py` for the cancel pathway. All four ports are CPU-only, ROCm-irrelevant — they slot above the GPU layer that ComfyUI already isolates. Each module is independently testable; tests use the existing pytest + `@pytest.mark.asyncio` pattern (see `tests/test_orphan_rescue.py`).

**Tech Stack:** FastAPI, asyncio, pymeshlab (new), trimesh (new), pytest, pytest-asyncio. No frontend changes in scope.

**Pre-flight:** Working tree currently has uncommitted edits to `job_queue.py`, `server.py`, `backends/comfyui.py`, and several frontend files. Tasks 1–3 only create new files and edit `requirements.txt`, so they're safe on the dirty tree. **Task 4 must not start until those existing modifications are committed or stashed** — a checkpoint at the top of Task 4 enforces this.

**Three decision points need Phill's input** (marked `🟦 DECISION` below). Each is 5–10 lines of code that encodes a real product/UX choice — not boilerplate.

---

## Task 1 — `smooth_progress` interpolator

**Why:** Open-palette has a TRELLIS-specific heartbeat (`backends/comfyui.py:3232-3255`) that ticks every 3 s when DiT is silent for >5 s. Modly's `smooth_progress` (`api/services/generators/base.py:602-624`) is a more general primitive: between two explicit progress anchors, advance the reported pct on a fixed cadence so the UI bar never stalls. Modly's version is a sync daemon thread; open-palette's `on_progress` is async, so this port becomes an `asyncio.Task` instead of a `threading.Thread`. Same idea, idiomatic for our stack.

**Files:**
- Create: `/home/phill/open-palette/progress_smooth.py`
- Test: `/home/phill/open-palette/tests/test_progress_smooth.py`

- [ ] **Step 1 — Write the failing tests**

Create `tests/test_progress_smooth.py`:

```python
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
```

- [ ] **Step 2 — Run tests to verify they fail**

```
cd /home/phill/open-palette
pytest tests/test_progress_smooth.py -v
```

Expected: ImportError — `progress_smooth` does not exist yet.

- [ ] **Step 3 — Implement `progress_smooth.py`**

Create `progress_smooth.py`:

```python
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
```

- [ ] **Step 4 — Run tests to verify they pass**

```
pytest tests/test_progress_smooth.py -v
```

Expected: 5 passed.

- [ ] **Step 5 — Commit**

```bash
cd /home/phill/open-palette
git add progress_smooth.py tests/test_progress_smooth.py
git commit -m "feat: add smooth_progress async interpolator (modly tier-1 port 1/4)"
```

🟦 **DECISION D3 (deferred to follow-up, NOT in this plan):** Whether to retire the TRELLIS-specific heartbeat at `backends/comfyui.py:3232-3255` and replace it with a `SmoothProgress` wrapper around the existing `on_progress`. The heartbeat has TRELLIS-specific knowledge (avg-step + ETA from DiT silence detection) that pure smooth_progress doesn't replicate. **Leave heartbeat in place after this task.** Phill can decide whether to consolidate after the new primitive proves itself in a calmer flow (e.g. 2D image gen progress).

---

## Task 2 — Mesh optimisation (pymeshlab decimate + smooth)

**Why:** All open-palette mesh post-processing currently lives inside ComfyUI graphs (`Hy3DPostprocessMesh`, `Trellis2SimplifyMesh_GGUF`). Re-decimating means re-running the whole graph. Modly's `api/routers/optimize.py:1313-1448` does decimation and Laplacian smoothing in-process via pymeshlab, with a regex-patch on the intermediate `.mtl` to keep texture references valid through the OBJ round-trip.

**Files:**
- Create: `/home/phill/open-palette/mesh_optimize.py`
- Modify: `/home/phill/open-palette/requirements.txt`
- Test: `/home/phill/open-palette/tests/test_mesh_optimize.py`

- [ ] **Step 1 — Add dependencies**

Edit `requirements.txt`. After line 16 (`pydub>=0.25.0`), append:

```
# Mesh post-processing (modly tier-1 port)
pymeshlab>=2023.12
trimesh>=4.0.0
```

Install:

```bash
cd /home/phill/open-palette
pip install pymeshlab trimesh
```

- [ ] **Step 2 — Write the failing tests**

Create `tests/test_mesh_optimize.py`:

```python
"""Tests for mesh_optimize (pymeshlab-backed decimation/smoothing).

Uses trimesh to author tiny synthetic meshes so tests don't depend on
real model output. pymeshlab itself is not mocked — these are integration
tests against the real library, gated by import availability.
"""

import importlib.util

import pytest
import trimesh

PYMESHLAB_AVAILABLE = importlib.util.find_spec("pymeshlab") is not None


@pytest.fixture
def cube_glb(tmp_path):
    """A simple textured cube as GLB (12 triangles)."""
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    out = tmp_path / "cube.glb"
    mesh.export(str(out))
    return out


@pytest.fixture
def dense_sphere_glb(tmp_path):
    """A subdivided sphere with ~5000 triangles for decimation tests."""
    mesh = trimesh.creation.icosphere(subdivisions=4)
    out = tmp_path / "sphere.glb"
    mesh.export(str(out))
    return out


@pytest.mark.skipif(not PYMESHLAB_AVAILABLE, reason="pymeshlab not installed")
def test_decimate_reduces_face_count(dense_sphere_glb, tmp_path):
    from mesh_optimize import decimate_mesh

    out = tmp_path / "decimated.glb"
    target = 500
    decimate_mesh(str(dense_sphere_glb), str(out), target_faces=target)

    result = trimesh.load(str(out), force="mesh")
    assert len(result.faces) <= target * 1.05, (
        f"got {len(result.faces)} faces, expected ≤{target}"
    )
    assert len(result.faces) >= target * 0.5, (
        f"decimator over-shot: {len(result.faces)} ≪ target {target}"
    )


@pytest.mark.skipif(not PYMESHLAB_AVAILABLE, reason="pymeshlab not installed")
def test_decimate_clamps_target_to_minimum(cube_glb, tmp_path):
    from mesh_optimize import decimate_mesh, MIN_TARGET_FACES

    out = tmp_path / "tiny.glb"
    decimate_mesh(str(cube_glb), str(out), target_faces=10)

    result = trimesh.load(str(out), force="mesh")
    # Cube starts at 12 faces; floor clamps to MIN_TARGET_FACES.
    assert len(result.faces) >= min(12, MIN_TARGET_FACES)


@pytest.mark.skipif(not PYMESHLAB_AVAILABLE, reason="pymeshlab not installed")
def test_decimate_clamps_target_to_maximum(dense_sphere_glb, tmp_path):
    from mesh_optimize import decimate_mesh, MAX_TARGET_FACES

    out = tmp_path / "huge.glb"
    decimate_mesh(str(dense_sphere_glb), str(out), target_faces=10_000_000)

    result = trimesh.load(str(out), force="mesh")
    # We requested an absurd target; resolver should cap at MAX_TARGET_FACES.
    assert len(result.faces) <= MAX_TARGET_FACES


@pytest.mark.skipif(not PYMESHLAB_AVAILABLE, reason="pymeshlab not installed")
def test_smooth_changes_vertex_positions(cube_glb, tmp_path):
    from mesh_optimize import smooth_mesh
    import numpy as np

    before = trimesh.load(str(cube_glb), force="mesh")
    out = tmp_path / "smoothed.glb"
    smooth_mesh(str(cube_glb), str(out), iterations=3)

    after = trimesh.load(str(out), force="mesh")
    assert before.vertices.shape == after.vertices.shape
    # Smoothing must have moved vertices (Laplacian shrinks a cube).
    assert not np.allclose(before.vertices, after.vertices)


@pytest.mark.skipif(not PYMESHLAB_AVAILABLE, reason="pymeshlab not installed")
def test_smooth_iterations_are_clamped(cube_glb, tmp_path):
    from mesh_optimize import smooth_mesh, MAX_SMOOTH_ITERATIONS

    out = tmp_path / "smoothed.glb"
    # Should not raise even with absurdly high count — just clamps.
    smooth_mesh(str(cube_glb), str(out), iterations=10_000)

    result = trimesh.load(str(out), force="mesh")
    assert len(result.vertices) > 0
```

- [ ] **Step 3 — Run tests to verify they fail**

```
pytest tests/test_mesh_optimize.py -v
```

Expected: ImportError — `mesh_optimize` doesn't exist.

🟦 **DECISION D2 — Decimation defaults.** Pick the constants that bound `decimate_mesh`. Modly hard-codes 100 ≤ target ≤ 500 000. Open-palette serves Hy3D (typically 50–100k after Hy3D's own postprocess) and TRELLIS at 512/768/1024 res (often 200k–800k). For a "decimate without re-running the graph" workflow, the target is usually a preview (5–20k) or a "downsize for game use" (30–60k). Set the bounds and the default before continuing. Replace the values below with what you want, then commit them as the new constants in Step 4:

```python
# 🟦 Phill: choose these
MIN_TARGET_FACES = 100         # absolute floor
MAX_TARGET_FACES = 1_000_000   # absolute ceiling
DEFAULT_TARGET_FACES = 50_000  # used when caller passes 0 or None
MAX_SMOOTH_ITERATIONS = 20     # Laplacian smooth cap
```

The defaults above are sensible starting values lifted from modly with TRELLIS headroom; adjust to taste before Step 4.

- [ ] **Step 4 — Implement `mesh_optimize.py`**

Create `mesh_optimize.py`:

```python
"""In-process mesh optimisation via pymeshlab.

Decimation and Laplacian smoothing for GLB inputs. CPU-only — pymeshlab
is a C++ library with no GPU dep, so this is ROCm-safe.

Ported from modly's api/routers/optimize.py:1313-1448. Modly handles
textured-OBJ round-trip with a regex-patched .mtl; this port intentionally
keeps the GLB→GLB path only for now, since open-palette's GLB outputs
either embed textures (TRELLIS) or are geometry-only (Hy3D shape mode).
The textured OBJ intermediate is a follow-up if texture-preserving
decimation becomes a real need.
"""

from pathlib import Path

# 🟦 Phill: confirm/adjust these in Step 3 before implementing
MIN_TARGET_FACES = 100
MAX_TARGET_FACES = 1_000_000
DEFAULT_TARGET_FACES = 50_000
MAX_SMOOTH_ITERATIONS = 20


def _clamp_faces(target: int) -> int:
    if not target:
        return DEFAULT_TARGET_FACES
    return max(MIN_TARGET_FACES, min(MAX_TARGET_FACES, int(target)))


def _clamp_iterations(n: int) -> int:
    return max(1, min(MAX_SMOOTH_ITERATIONS, int(n)))


def decimate_mesh(input_path: str, output_path: str, target_faces: int = 0) -> None:
    """Decimate a mesh to target face count via quadric edge collapse.

    Loads input (any format pymeshlab supports), writes output as GLB.
    Raises FileNotFoundError if input is missing.
    """
    import pymeshlab

    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"input mesh not found: {input_path}")

    target = _clamp_faces(target_faces)
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(str(src))
    ms.apply_filter(
        "meshing_decimation_quadric_edge_collapse",
        targetfacenum=target,
        preservenormal=True,
        preservetopology=True,
    )
    ms.save_current_mesh(str(output_path))


def smooth_mesh(input_path: str, output_path: str, iterations: int = 3) -> None:
    """Apply Laplacian smoothing to a mesh.

    Loads input, applies coord laplacian smoothing N times, writes output.
    """
    import pymeshlab

    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"input mesh not found: {input_path}")

    n = _clamp_iterations(iterations)
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(str(src))
    ms.apply_filter("apply_coord_laplacian_smoothing", stepsmoothnum=n)
    ms.save_current_mesh(str(output_path))
```

- [ ] **Step 5 — Run tests to verify they pass**

```
pytest tests/test_mesh_optimize.py -v
```

Expected: 6 passed.

- [ ] **Step 6 — Wire up FastAPI endpoints in `server.py`**

Endpoints expose the helpers under `/api/mesh/*`. Find a good insertion point — the `_backend_type` helper at the end of `server.py:3582` is a natural anchor; insert *after* it (before any `app.include_router` calls).

Add this block at end of `server.py`:

```python
# ===== Mesh post-processing (modly tier-1 port) =====
from pydantic import BaseModel as _MeshOptModel  # local alias to avoid clobber


class _MeshOptimizeRequest(_MeshOptModel):
    job_id: str
    target_faces: int = 0  # 0 = use DEFAULT_TARGET_FACES


class _MeshSmoothRequest(_MeshOptModel):
    job_id: str
    iterations: int = 3


@app.post("/api/mesh/decimate")
async def api_mesh_decimate(req: _MeshOptimizeRequest):
    """Decimate the GLB attached to job_id, writing a sibling _decimated.glb."""
    import storage as store
    import mesh_optimize

    src = store.asset_path(req.job_id, "mesh", ".glb")
    if not src.exists():
        return {"ok": False, "error": f"no mesh for job {req.job_id}"}

    dst = src.with_name(src.stem + "_decimated.glb")
    try:
        mesh_optimize.decimate_mesh(str(src), str(dst), req.target_faces)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "output_url": f"/storage/{req.job_id}_decimated.glb",
        "target_faces": req.target_faces or mesh_optimize.DEFAULT_TARGET_FACES,
    }


@app.post("/api/mesh/smooth")
async def api_mesh_smooth(req: _MeshSmoothRequest):
    """Smooth the GLB attached to job_id, writing a sibling _smoothed.glb."""
    import storage as store
    import mesh_optimize

    src = store.asset_path(req.job_id, "mesh", ".glb")
    if not src.exists():
        return {"ok": False, "error": f"no mesh for job {req.job_id}"}

    dst = src.with_name(src.stem + "_smoothed.glb")
    try:
        mesh_optimize.smooth_mesh(str(src), str(dst), req.iterations)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "output_url": f"/storage/{req.job_id}_smoothed.glb",
        "iterations": req.iterations,
    }
```

- [ ] **Step 7 — Smoke-test the endpoints**

Start the server briefly and curl the endpoints with a real job_id from `storage/unsorted/`:

```bash
# Pick any existing 3D job
ls storage/unsorted/*/meshes/*.glb | head -1
# Run server in another terminal: python server.py
# Then:
curl -s -X POST http://127.0.0.1:7860/api/mesh/decimate \
  -H 'Content-Type: application/json' \
  -d '{"job_id": "<paste real job_id>", "target_faces": 5000}' | python -m json.tool
```

Expected: `{"ok": true, "output_url": "/storage/<id>_decimated.glb", "target_faces": 5000}` and the file exists on disk.

- [ ] **Step 8 — Commit**

```bash
cd /home/phill/open-palette
git add mesh_optimize.py tests/test_mesh_optimize.py requirements.txt
git add server.py    # only the new mesh-endpoint block; review with `git diff --cached`
git commit -m "feat: in-process mesh decimate/smooth via pymeshlab (modly tier-1 port 2/4)"
```

⚠️ Before staging `server.py`, run `git diff --cached server.py` and verify the diff is **only** the appended block. If unrelated in-flight changes are also staged, unstage them with `git restore --staged server.py` and re-add the new block in isolation (e.g. `git add -p server.py`).

---

## Task 3 — Format conversion (trimesh-based export)

**Why:** Open-palette is GLB-only on output. Modly exposes `{glb, stl, obj, ply}` via `api/routers/export.py` with a single trimesh call. ~50 lines, no GPU. Adding FBX/USDZ is out of scope (modly doesn't have them either; trimesh can't write them).

**Files:**
- Create: `/home/phill/open-palette/mesh_export.py`
- Modify: `/home/phill/open-palette/server.py` (append endpoint)
- Test: `/home/phill/open-palette/tests/test_mesh_export.py`

- [ ] **Step 1 — Write the failing tests**

Create `tests/test_mesh_export.py`:

```python
"""Tests for mesh_export (trimesh-based format conversion).

Verifies geometry survives round-trip and that unsupported formats raise.
"""

import importlib.util
from pathlib import Path

import pytest
import trimesh

TRIMESH_AVAILABLE = importlib.util.find_spec("trimesh") is not None


@pytest.fixture
def src_glb(tmp_path):
    mesh = trimesh.creation.icosphere(subdivisions=2)
    out = tmp_path / "src.glb"
    mesh.export(str(out))
    return out


@pytest.mark.skipif(not TRIMESH_AVAILABLE, reason="trimesh not installed")
@pytest.mark.parametrize("fmt", ["stl", "obj", "ply", "glb"])
def test_export_to_each_supported_format(src_glb, tmp_path, fmt):
    from mesh_export import export_mesh, SUPPORTED_FORMATS

    assert fmt in SUPPORTED_FORMATS
    out = tmp_path / f"out.{fmt}"
    export_mesh(str(src_glb), str(out), fmt)
    assert out.exists()
    assert out.stat().st_size > 0

    # Round-trip: load result, vertex count should match source.
    src = trimesh.load(str(src_glb), force="mesh")
    dst = trimesh.load(str(out), force="mesh")
    assert len(dst.vertices) == len(src.vertices)


@pytest.mark.skipif(not TRIMESH_AVAILABLE, reason="trimesh not installed")
def test_unsupported_format_raises(src_glb, tmp_path):
    from mesh_export import export_mesh, UnsupportedFormatError

    out = tmp_path / "out.fbx"
    with pytest.raises(UnsupportedFormatError):
        export_mesh(str(src_glb), str(out), "fbx")


@pytest.mark.skipif(not TRIMESH_AVAILABLE, reason="trimesh not installed")
def test_missing_input_raises(tmp_path):
    from mesh_export import export_mesh

    with pytest.raises(FileNotFoundError):
        export_mesh(str(tmp_path / "missing.glb"), str(tmp_path / "out.stl"), "stl")
```

- [ ] **Step 2 — Run tests to verify they fail**

```
pytest tests/test_mesh_export.py -v
```

Expected: ImportError — `mesh_export` doesn't exist.

- [ ] **Step 3 — Implement `mesh_export.py`**

Create `mesh_export.py`:

```python
"""Mesh format conversion via trimesh.

Ported from modly's api/routers/export.py. Loads with trimesh.load,
flattens any Scene to a single concatenated mesh, exports via the
target format's writer. Pure Python except for trimesh's optional C
deps. ROCm-safe.
"""

from pathlib import Path

SUPPORTED_FORMATS = frozenset({"glb", "stl", "obj", "ply"})


class UnsupportedFormatError(ValueError):
    pass


def export_mesh(input_path: str, output_path: str, fmt: str) -> None:
    """Convert a mesh from any trimesh-supported format to {glb,stl,obj,ply}.

    Raises:
        FileNotFoundError: input does not exist.
        UnsupportedFormatError: fmt not in SUPPORTED_FORMATS.
    """
    import trimesh

    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"input mesh not found: {input_path}")

    fmt_lower = fmt.lower().lstrip(".")
    if fmt_lower not in SUPPORTED_FORMATS:
        raise UnsupportedFormatError(
            f"format {fmt!r} not supported; pick from {sorted(SUPPORTED_FORMATS)}"
        )

    loaded = trimesh.load(str(src), force="mesh")
    # `force='mesh'` flattens Scene objects to a single concatenated mesh.
    if isinstance(loaded, trimesh.Scene):
        loaded = trimesh.util.concatenate(tuple(loaded.geometry.values()))

    loaded.export(str(output_path), file_type=fmt_lower)
```

- [ ] **Step 4 — Run tests to verify they pass**

```
pytest tests/test_mesh_export.py -v
```

Expected: 6 passed (4 parametrised + 2 named).

- [ ] **Step 5 — Wire up FastAPI endpoint in `server.py`**

Append after the mesh-optimisation block from Task 2:

```python
@app.get("/api/mesh/export")
async def api_mesh_export(job_id: str, fmt: str):
    """Convert the GLB attached to job_id into {glb,stl,obj,ply} on demand."""
    import storage as store
    import mesh_export
    from fastapi.responses import FileResponse

    src = store.asset_path(job_id, "mesh", ".glb")
    if not src.exists():
        return {"ok": False, "error": f"no mesh for job {job_id}"}

    dst = src.with_name(f"{src.stem}.{fmt.lower()}")
    try:
        mesh_export.export_mesh(str(src), str(dst), fmt)
    except mesh_export.UnsupportedFormatError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    media = {
        "glb": "model/gltf-binary",
        "stl": "model/stl",
        "obj": "model/obj",
        "ply": "model/ply",
    }.get(fmt.lower(), "application/octet-stream")
    return FileResponse(str(dst), media_type=media, filename=dst.name)
```

- [ ] **Step 6 — Smoke-test the endpoint**

```bash
# server running on 7860
curl -s -o /tmp/out.stl "http://127.0.0.1:7860/api/mesh/export?job_id=<real_id>&fmt=stl" \
  && file /tmp/out.stl
```

Expected: `/tmp/out.stl: data` (or specifically `STL ASCII` / `data` depending on file magic).

- [ ] **Step 7 — Commit**

```bash
cd /home/phill/open-palette
git add mesh_export.py tests/test_mesh_export.py
git add -p server.py    # only the new export endpoint
git commit -m "feat: mesh format conversion via trimesh (modly tier-1 port 3/4)"
```

---

## Task 4 — Cancel pathway (cooperative event + subprocess kill)

**Why:** Open-palette has no `/api/job/{id}/cancel` endpoint. The orphan rescue at `backends/comfyui.py:3315-3325` is a one-shot `asyncio.shield` after a *timeout* fires — there's no user-initiated cancel. Modly's pattern (`api/routers/generation.py:1066-1072`) is two-layer: a cooperative `asyncio.Event` checked between pipeline stages, and a hard `proc.kill()` on the underlying subprocess if cooperative doesn't catch within a grace window.

For open-palette, the "subprocess" equivalent is ComfyUI itself running on its own port. The cooperative event lives in the JobQueue; the hard-kill equivalent has three options that you (Phill) need to pick between in DECISION D1.

**⚠️ Pre-Task checkpoint:** The working tree currently has uncommitted edits to `job_queue.py` and `server.py` (and `backends/comfyui.py`, frontend files). **Before starting Task 4**, decide:

- **Option A:** Commit the in-flight changes first (`git add -A && git commit -m "wip: <describe>"`). Tasks 4 modifications go in a fresh commit on top.
- **Option B:** Stash the in-flight changes (`git stash push -m "pre-tier1-task4"`). Run Task 4 against clean state, commit, then `git stash pop` and resolve any conflicts.

Option A is safer. Option B is faster if the in-flight work is incomplete.

**Files:**
- Modify: `/home/phill/open-palette/job_queue.py` (add cancel event registry)
- Modify: `/home/phill/open-palette/server.py` (add `/api/job/{id}/cancel` endpoint, propagate to JobQueue)
- Test: `/home/phill/open-palette/tests/test_job_cancel.py`

🟦 **DECISION D1 — Cancel propagation to ComfyUI.** When the user cancels an in-flight 3D job, what happens to ComfyUI?

```
(i)   Cancel only our wrapper coroutine (cooperative event fires,
      asyncio.wait_for unwinds). ComfyUI keeps running and may finish
      the GLB; existing orphan-rescue (comfyui.py:3315) salvages it.
      Cleanest, but ComfyUI burns a few minutes of GPU.

(ii)  Send ComfyUI's HTTP DELETE /queue/<prompt_id> via aiohttp.
      ComfyUI's documented graceful path. It marks the prompt as
      cancelled and stops processing at the next node boundary. May
      leave partial outputs in ComfyUI's output dir.

(iii) Both: send DELETE first, then if ComfyUI is still alive after
      grace_seconds, kill our wrapper anyway (drop into option i).
      Most robust; most code.
```

Pick one and write the 5–10 lines that implement it inside `_cancel_in_flight()` below (skeleton in Step 4). The default in the skeleton is **(i)** — change it before committing if you want (ii) or (iii).

- [ ] **Step 1 — Write the failing tests**

Create `tests/test_job_cancel.py`:

```python
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
```

- [ ] **Step 2 — Run tests to verify they fail**

```
pytest tests/test_job_cancel.py -v
```

Expected: AttributeError — `JobQueue.cancel` doesn't exist.

- [ ] **Step 3 — Add cancel support to `job_queue.py`**

Edit `job_queue.py`. Track each job's `asyncio.Task` so we can cancel it. The current `submit_background` discards the task — change that.

Replace the body of `submit_background` (currently `job_queue.py:87-96`) with:

```python
    def submit_background(self, coro, lane: str = "gpu", job_id: str = "",
                          timeout: float = 0):
        """Submit without awaiting — returns immediately, job runs when slot opens.

        Args:
            timeout: Max seconds for this job. 0 = use lane default. Use a
                     long override (e.g. 1800) for 3D mesh runs which can take
                     10–15 min on cascade + textured pipelines.
        """
        task = asyncio.create_task(
            self.submit(coro, lane=lane, job_id=job_id, timeout=timeout)
        )
        if job_id:
            self._tasks[job_id] = task
            task.add_done_callback(lambda _t: self._tasks.pop(job_id, None))
        return task
```

In `__init__` (around line 37–47), add a tasks registry. Replace `__init__` with:

```python
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
        # Map job_id → asyncio.Task so cancel() can find and cancel running
        # or queued jobs. Tasks self-remove via add_done_callback.
        self._tasks: dict[str, asyncio.Task] = {}
```

Add a new `cancel` method at the end of the class (after `position`, around line 120):

```python
    async def cancel(self, job_id: str) -> bool:
        """Cancel a queued or running job by id.

        Returns True if a matching job was found and cancellation was
        requested, False if no such job exists.

        For queued jobs, the task is cancelled before it acquires the
        semaphore. For running jobs, the task is cancelled inside
        `await asyncio.wait_for(coro, ...)` which propagates
        CancelledError into the user coroutine.
        """
        task = self._tasks.get(job_id)
        if task is None or task.done():
            return False
        task.cancel()
        return True
```

- [ ] **Step 4 — Run tests to verify they pass**

```
pytest tests/test_job_cancel.py -v
```

Expected: 3 passed.

- [ ] **Step 5 — Wire up `/api/job/{id}/cancel` endpoint in `server.py`**

Append to the bottom of `server.py` (after the mesh-export endpoint from Task 3):

```python
# ===== Job cancellation (modly tier-1 port) =====
@app.post("/api/job/{job_id}/cancel")
async def api_job_cancel(job_id: str):
    """Cancel an in-flight or queued job.

    Cooperative: cancels the wrapping asyncio.Task, which propagates
    CancelledError into _run_job. ComfyUI handling depends on which
    branch you picked in DECISION D1 (see _cancel_in_flight below).
    """
    if job_id not in jobs:
        return {"ok": False, "error": "unknown job_id"}

    cancelled = await job_queue.cancel(job_id)
    await _cancel_in_flight(job_id)

    jobs[job_id].update({"status": "cancelled"})
    await broadcast({
        "type": "job_update", "job_id": job_id,
        "status": "cancelled",
    })
    return {"ok": cancelled, "job_id": job_id, "status": "cancelled"}


async def _cancel_in_flight(job_id: str) -> None:
    """🟦 DECISION D1: how does cancel propagate to ComfyUI?

    Default below is option (i): cancel only our wrapper. ComfyUI continues
    until next prompt boundary; orphan-rescue (backends/comfyui.py:3315)
    salvages any GLB it manages to write before teardown.

    To switch to option (ii) — graceful ComfyUI DELETE — replace the body
    with something like:

        import aiohttp
        prompt_id = jobs.get(job_id, {}).get("comfy_prompt_id")
        if not prompt_id:
            return
        async with aiohttp.ClientSession() as s:
            try:
                async with s.post(
                    f"{COMFYUI_URL}/queue",
                    json={"delete": [prompt_id]},
                    timeout=aiohttp.ClientTimeout(total=2.0),
                ) as r:
                    await r.read()
            except Exception:
                pass  # best-effort
        # Note: requires backends/comfyui.py to stash prompt_id into
        # jobs[job_id]["comfy_prompt_id"] when it submits.

    To switch to option (iii) — DELETE then kill — combine the above
    with a 2 s grace window before falling back to option (i).
    """
    return  # option (i): no-op, wrapper cancel was enough
```

- [ ] **Step 6 — Smoke-test against a real running job**

```bash
# Start server: python server.py
# Submit a 3D job from the UI (any TRELLIS or Hy3D prompt).
# Grab the job_id from the network tab or job list, then:

curl -s -X POST http://127.0.0.1:7860/api/job/<job_id>/cancel | python -m json.tool
```

Expected: `{"ok": true, "job_id": "<id>", "status": "cancelled"}`. The UI WS should receive a `job_update` with `status: "cancelled"`. The job slot in `/api/queue/status` (or wherever you surface it) should free up.

Verify orphan rescue still works in this path: ComfyUI may finish writing the GLB after we cancel — check `storage/unsorted/` or run `python -c "import health_actions; print(health_actions._rescue_orphan_meshes())"` to confirm late-arriving meshes are picked up.

- [ ] **Step 7 — Commit**

```bash
cd /home/phill/open-palette
git add job_queue.py tests/test_job_cancel.py
git add -p server.py    # only the cancel endpoint block
git commit -m "feat: cancel endpoint with cooperative cancel + orphan-rescue fallback (modly tier-1 port 4/4)"
```

---

## Self-review checklist

After all four tasks are complete, run end-to-end:

- [ ] `pytest tests/test_progress_smooth.py tests/test_mesh_optimize.py tests/test_mesh_export.py tests/test_job_cancel.py -v` — all green
- [ ] `pytest` (full suite) — no regressions in pre-existing tests
- [ ] `python -c "import progress_smooth, mesh_optimize, mesh_export"` — no import errors at module load
- [ ] Server starts cleanly: `python server.py` → no startup exceptions
- [ ] Manual: hit `/api/mesh/decimate`, `/api/mesh/export`, `/api/job/{id}/cancel` against real jobs
- [ ] `git log --oneline -6` shows four `feat:` commits, each scoped to one port

## Out of scope for this plan (deferred)

- Texture-preserving OBJ round-trip in `mesh_optimize` (modly does this with regex-patched `.mtl`; needed only when GLB textures must survive decimation)
- FBX / USDZ export (trimesh can't write either; would need `pymeshlab` for FBX or a Blender CLI bridge for USDZ)
- Manifest-driven backend registration (Tier 2 lift — replaces the if/elif at `server.py:3493-3506`)
- HF download SSE streamer for 3D weights (Tier 3 lift)
- Retiring the TRELLIS-specific heartbeat in favour of `SmoothProgress` (DECISION D3 — see Task 1)
- Frontend UI for any of the new endpoints (intentionally backend-only this round)
