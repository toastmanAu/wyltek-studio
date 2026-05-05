"""SenseNova-U1 subprocess backend (interleave mode).

Runs the `examples/interleave/inference.py` script from the SenseNova-U1
repo against a JSONL payload we write to /tmp. Two tiers select between
the 50-step and 8-step-preview weight sets. Output PNG path is returned
on success; non-zero exit raises :class:`SenseNovaError`.

Progress reporting is layered on top via :mod:`progress_smooth` (Task 6).
See spec: docs/superpowers/specs/2026-05-05-infographic-builder-design.md
"""
from __future__ import annotations
import asyncio, json, os, re, time
from asyncio import create_subprocess_exec as _start_subprocess
from pathlib import Path
from typing import Awaitable, Callable

SENSENOVA_REPO = Path(os.environ.get("SENSENOVA_REPO", "/home/phill/SenseNova-U1"))
SENSENOVA_VENV_PYTHON = Path(os.environ.get("SENSENOVA_VENV", "/data/venvs/sensenova-u1")) / "bin" / "python"
WEIGHTS_FINAL = Path(os.environ.get("SENSENOVA_WEIGHTS_FINAL", "/data/sensenova-u1-weights"))
WEIGHTS_DRAFT = Path(os.environ.get("SENSENOVA_WEIGHTS_DRAFT", "/data/sensenova-u1-weights-8step"))
INFER_SCRIPT = SENSENOVA_REPO / "examples" / "interleave" / "inference.py"

DEFAULT_DRAFT_TIMEOUT_S = 180
DEFAULT_FINAL_TIMEOUT_S = 600

ASPECT_BUCKETS: dict[str, tuple[int, int]] = {
    "1:1": (1536, 1536), "16:9": (2048, 1152), "9:16": (1152, 2048),
    "3:2": (1888, 1248), "2:3": (1248, 1888), "4:3": (1760, 1312),
    "3:4": (1312, 1760), "1:2": (1088, 2144), "2:1": (2144, 1088),
    "1:3": (864, 2592),  "3:1": (2592, 864),
}

ProgressCallback = Callable[[int, str], Awaitable[None]]
_IMAGE_TOKEN_RE = re.compile(r"\[Image \d+\]")


class SenseNovaError(RuntimeError):
    """Raised on bad config, malformed inputs, or non-zero subprocess exit."""


def _resolve_weights(tier: str) -> str:
    if tier == "final": return str(WEIGHTS_FINAL)
    if tier == "draft": return str(WEIGHTS_DRAFT)
    raise SenseNovaError(f"Unknown tier: {tier!r}")


def _build_jsonl_payload(prompt, image_paths, aspect, seed) -> dict:
    has_images = bool(image_paths)
    rewritten = _IMAGE_TOKEN_RE.sub("<image>", prompt) if has_images else prompt
    payload: dict = {
        "prompt": rewritten,
        "image": list(image_paths),
        "seed": seed,
        "think_mode": False,
    }
    if not has_images:
        if aspect is None:
            aspect = "1:1"
        if aspect not in ASPECT_BUCKETS:
            raise SenseNovaError(
                f"aspect={aspect!r} not in supported buckets {sorted(ASPECT_BUCKETS)}")
        w, h = ASPECT_BUCKETS[aspect]
        payload["width"], payload["height"] = w, h
    return payload


def _build_argv(*, jsonl_path: Path, output_dir: Path, tier: str) -> list[str]:
    return [
        str(SENSENOVA_VENV_PYTHON),
        str(INFER_SCRIPT),
        "--model_path", _resolve_weights(tier),
        "--jsonl", str(jsonl_path),
        "--output_dir", str(output_dir),
        "--no-think_mode",
    ]


def _validate_environment() -> None:
    if not INFER_SCRIPT.exists():
        raise SenseNovaError(f"Interleave script missing at {INFER_SCRIPT}")
    if not SENSENOVA_VENV_PYTHON.exists():
        raise SenseNovaError(f"SenseNova venv python missing at {SENSENOVA_VENV_PYTHON}")
    if not WEIGHTS_FINAL.exists() or not WEIGHTS_DRAFT.exists():
        raise SenseNovaError("SenseNova weights missing")


async def generate(*, prompt, image_paths, aspect, seed, tier,
                   output_dir: Path,
                   on_progress: ProgressCallback | None = None,
                   timeout_s: int | None = None) -> Path:
    """Run a single SenseNova interleave render and return the PNG path."""
    _validate_environment()
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = _build_jsonl_payload(prompt, image_paths, aspect, seed)
    jsonl = output_dir / "input.jsonl"
    jsonl.write_text(json.dumps(payload) + "\n")

    argv = _build_argv(jsonl_path=jsonl, output_dir=output_dir, tier=tier)
    timeout = timeout_s or (DEFAULT_DRAFT_TIMEOUT_S if tier == "draft" else DEFAULT_FINAL_TIMEOUT_S)

    start = time.monotonic()
    proc = await _start_subprocess(*argv,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    stdout = bytearray()

    from progress_smooth import SmoothProgress

    if on_progress is None:
        async def _noop(_p, _m=""): return None
        cb: ProgressCallback = _noop
    else:
        cb = on_progress

    async with SmoothProgress(cb, tick_seconds=2.0, max_creep=85) as sp:
        await sp.set(5, "loading model")
        try:
            async for raw in proc.stdout:  # type: ignore[union-attr]
                stdout.extend(raw)
                if (time.monotonic() - start) > timeout:
                    proc.terminate()
                    raise SenseNovaError(f"SenseNova render exceeded {timeout}s")
            rc = await proc.wait()
        except asyncio.CancelledError:
            proc.terminate()
            await proc.wait()
            raise
        await sp.set(95, "saving image")

    if rc != 0:
        raise SenseNovaError(
            f"SenseNova subprocess exited {rc}; tail:\n"
            + stdout.decode("utf-8", errors="replace")[-2000:])

    pngs = sorted(output_dir.glob("*.png"))
    if not pngs:
        raise SenseNovaError(f"No PNG produced in {output_dir}")
    if on_progress is not None:
        await on_progress(100, "done")
    return pngs[-1]
