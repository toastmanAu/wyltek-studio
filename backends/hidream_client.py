"""HTTP client for the HiDream-O1-Image persistent worker daemon.

Talks to ``studio.hidream_worker`` over localhost HTTP. Worker holds the
model GPU-resident; this client just shuttles JSON in and a PNG path out.

Failure shape mirrors the worker's: a non-2xx response carries an
``{"error": ..., "detail": ..., "traceback": ...}`` body which the caller
should bubble up as a ``HiDreamWorkerError``.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx


WORKER_URL = os.environ.get("HIDREAM_WORKER_URL", "http://127.0.0.1:9092")


class HiDreamWorkerError(RuntimeError):
    """Worker reported an error or was unreachable."""


async def status(timeout_s: float = 2.0) -> dict[str, Any]:
    """Lightweight liveness probe; raises on connection failure."""
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        try:
            r = await client.get(f"{WORKER_URL}/status")
        except httpx.HTTPError as exc:
            raise HiDreamWorkerError(
                f"worker unreachable at {WORKER_URL}: {exc}") from exc
    r.raise_for_status()
    return r.json()


async def render_t2i(
    *,
    prompt: str,
    output_dir: Path,
    width: int = 2048,
    height: int = 2048,
    seed: int = 32,
    model_type: str = "full",
    guidance_scale: float = 5.0,
    shift: float = 3.0,
    layout_bboxes: Any | None = None,
    timeout_s: float = 1800.0,
) -> dict[str, Any]:
    """Run a T2I render. Returns the worker's response (png_path + metadata)."""
    body: dict[str, Any] = {
        "prompt": prompt,
        "output_dir": str(output_dir),
        "width": width, "height": height,
        "seed": seed,
        "model_type": model_type,
        "guidance_scale": guidance_scale,
        "shift": shift,
    }
    if layout_bboxes is not None:
        body["layout_bboxes"] = layout_bboxes
    return await _post_render(f"{WORKER_URL}/render/t2i", body, timeout_s)


async def render_edit(
    *,
    prompt: str,
    ref_image_path: str,
    output_dir: Path,
    width: int = 2048,
    height: int = 2048,
    seed: int = 32,
    model_type: str = "full",
    guidance_scale: float = 5.0,
    shift: float = 3.0,
    keep_original_aspect: bool = True,
    timeout_s: float = 1800.0,
) -> dict[str, Any]:
    """Run a single-reference editing render."""
    body = {
        "prompt": prompt,
        "ref_image_path": ref_image_path,
        "output_dir": str(output_dir),
        "width": width, "height": height,
        "seed": seed,
        "model_type": model_type,
        "guidance_scale": guidance_scale,
        "shift": shift,
        "keep_original_aspect": keep_original_aspect,
    }
    return await _post_render(f"{WORKER_URL}/render/edit", body, timeout_s)


async def shutdown(timeout_s: float = 5.0) -> None:
    """Tell the worker to exit (mainly for tests / dev cycles)."""
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        try:
            await client.post(f"{WORKER_URL}/shutdown")
        except httpx.HTTPError:
            pass  # worker may already be exiting


async def _post_render(url: str, body: dict, timeout_s: float) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        try:
            r = await client.post(url, json=body)
        except httpx.HTTPError as exc:
            raise HiDreamWorkerError(
                f"worker unreachable at {url}: {exc}") from exc

    if r.status_code >= 400:
        # Worker returns structured error on 5xx; bubble up the traceback if present.
        try:
            err = r.json()
        except ValueError:
            err = {"error": "non-json", "detail": r.text[:1000]}
        raise HiDreamWorkerError(
            f"{err.get('error', 'unknown')}: {err.get('detail', '')}\n"
            f"{err.get('traceback', '')}")

    return r.json()
