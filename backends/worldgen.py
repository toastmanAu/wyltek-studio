"""Worldgen subprocess backend.

Runs ZiYang-xie/WorldGen end-to-end in a separate Python process per job:
text/image prompt -> FLUX.1-dev panorama -> DA-2 depth -> mesh.glb.

server.py's _run_job dispatches here directly when params.engine == "worldgen".
See memory/project_worldgen_rocm.md for the patch recipe applied to the
ZiYang-xie/WorldGen clone.
"""
from __future__ import annotations

import asyncio
import os
import shlex
from pathlib import Path
from typing import Awaitable, Callable

WORLDGEN_REPO = Path("/home/phill/repos/WorldGen")
WORKER_SCRIPT = WORLDGEN_REPO / "run_worker.py"
SMOKE_OK_MARKER = Path("/data/wyltek/worldgen/smoke_ok")
DEFAULT_TIMEOUT_S = 600  # 184s baseline + headroom for higher resolutions

ProgressCallback = Callable[[int, str], Awaitable[None]]


class WorldgenError(RuntimeError):
    """Raised when the worker subprocess exits non-zero or misbehaves."""


def _validate_environment() -> None:
    if not WORKER_SCRIPT.exists():
        raise WorldgenError(
            f"Worker script missing at {WORKER_SCRIPT}."
        )
    if not SMOKE_OK_MARKER.exists():
        raise WorldgenError(
            f"Smoke test marker missing at {SMOKE_OK_MARKER}."
        )


def _build_argv(params: dict, output_path: str) -> list[str]:
    argv = [
        "python3", str(WORKER_SCRIPT),
        "--prompt", params.get("prompt", "") or "",
        "--mode", params.get("worldgen_mode", "t2s"),
        "--resolution", str(params.get("resolution", 1600)),
        "--seed", str(params.get("seed", 42)),
        "--output", output_path,
        "--output-format", params.get("output_format", "mesh"),
    ]
    refs = params.get("reference_images") or []
    if params.get("worldgen_mode") == "i2s" and refs:
        argv.extend(["--reference-image", refs[0]])
    return argv


def _parse_progress_line(line: str) -> tuple[int, str] | None:
    """Map a worker PROGRESS line to (percent, stage)."""
    parts = line.strip().split(maxsplit=2)
    if len(parts) < 2 or parts[0] != "PROGRESS:":
        return None
    try:
        frac = float(parts[1])
    except ValueError:
        return None
    stage = parts[2] if len(parts) >= 3 else ""
    pct = max(0, min(99, int(frac * 100)))
    return pct, stage


async def _consume_stream(
    proc: asyncio.subprocess.Process,
    on_progress: ProgressCallback,
    state: dict,
) -> None:
    """Read worker stdout line-by-line, push progress updates, capture DONE/ERROR."""
    assert proc.stdout is not None
    async for raw in proc.stdout:
        line = raw.decode("utf-8", errors="replace").rstrip()
        if not line:
            continue
        if line.startswith("DONE:"):
            state["final_path"] = line.split(":", 1)[1].strip()
            await on_progress(99, "writing output")
        elif line.startswith("ERROR:"):
            state["last_error"] = line.split(":", 1)[1].strip()
        elif line.startswith("PROGRESS:"):
            parsed = _parse_progress_line(line)
            if parsed:
                pct, stage = parsed
                await on_progress(pct, stage)


async def _drain_stderr(proc: asyncio.subprocess.Process, buf: list[str]) -> None:
    """Drain stderr to avoid pipe-buffer deadlock; keep last 80 lines."""
    assert proc.stderr is not None
    async for raw in proc.stderr:
        line = raw.decode("utf-8", errors="replace").rstrip()
        if line:
            buf.append(line)
            if len(buf) > 80:
                del buf[: len(buf) - 80]


async def generate_world(
    params: dict,
    output_path: str,
    on_progress: ProgressCallback,
) -> dict:
    """Run a Worldgen scene generation. Returns metadata dict for sidecar.

    Compat note: avoid `async with asyncio.timeout(...)` (3.11+); use
    `asyncio.wait_for` on the entire coroutine for our 3.10 runtime. The
    outer JobQueue also has its own timeout, so this is belt-and-suspenders.
    """
    _validate_environment()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    argv = _build_argv(params, output_path)
    env = {
        **os.environ,
        "HF_HOME": os.environ.get("HF_HOME", "/data/huggingface-cache"),
        "PYTORCH_HIP_ALLOC_CONF": "expandable_segments:True",
        "PYTHONPATH": str(WORLDGEN_REPO / "src"),
        "PYTHONUNBUFFERED": "1",
    }

    await on_progress(1, "starting worldgen worker")

    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd=str(WORLDGEN_REPO),
    )

    state: dict = {"final_path": None, "last_error": None}
    stderr_buf: list[str] = []
    stderr_task = asyncio.create_task(_drain_stderr(proc, stderr_buf))

    try:
        await asyncio.wait_for(
            _consume_stream(proc, on_progress, state),
            timeout=DEFAULT_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except ProcessLookupError:
            pass
        await proc.wait()
        raise WorldgenError(
            f"Worldgen worker exceeded {DEFAULT_TIMEOUT_S}s timeout. "
            f"stderr tail: {stderr_buf[-3:] if stderr_buf else '(empty)'}"
        )
    finally:
        stderr_task.cancel()
        try:
            await stderr_task
        except (asyncio.CancelledError, Exception):
            pass

    rc = await proc.wait()
    if rc != 0:
        tail = "\n".join(stderr_buf[-20:]) if stderr_buf else "(no stderr captured)"
        raise WorldgenError(
            f"Worldgen worker exited {rc}. "
            f"{('error: ' + state['last_error']) if state['last_error'] else ''}\n"
            f"stderr tail:\n{tail}"
        )

    final_path = state["final_path"]
    if not final_path or not Path(final_path).exists():
        raise WorldgenError(
            f"Worker exited 0 but output not found at {final_path or output_path}"
        )

    sz = Path(final_path).stat().st_size
    await on_progress(100, "complete")
    return {
        "engine": "worldgen",
        "format": "glb",
        "filename": Path(final_path).name,
        "bytes": sz,
        "argv": shlex.join(argv),
    }
