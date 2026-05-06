"""HTTP client for the SenseNova-U1 persistent worker daemon.

Talks to ``studio.sensenova_worker`` over localhost HTTP. Worker holds the
model GPU-resident; this client just shuttles JSON in and a PNG path out.

Failure shape mirrors the worker's: a non-2xx response carries an
``{"error": ..., "detail": ..., "traceback": ...}`` body which the caller
should bubble up as a ``SenseNovaWorkerError``.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import httpx


WORKER_URL = os.environ.get("SENSENOVA_WORKER_URL", "http://127.0.0.1:9091")


class SenseNovaWorkerError(RuntimeError):
    """Worker reported an error or was unreachable."""


async def status(timeout_s: float = 2.0) -> dict[str, Any]:
    """Lightweight liveness probe; raises on connection failure."""
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        try:
            r = await client.get(f"{WORKER_URL}/status")
        except httpx.HTTPError as exc:
            raise SenseNovaWorkerError(f"worker unreachable at {WORKER_URL}: {exc}") from exc
    r.raise_for_status()
    return r.json()


async def render_t2i(
    *,
    prompt: str,
    output_dir: Path,
    width: int = 2048,
    height: int = 1152,
    seed: int = 42,
    cfg_scale: float = 4.0,
    num_steps: int = 50,
    timeout_s: float = 1800.0,
) -> Path:
    """Run a T2I render. Returns the PNG path written by the worker."""
    body = {
        "prompt": prompt,
        "output_dir": str(output_dir),
        "width": width, "height": height,
        "seed": seed, "cfg_scale": cfg_scale, "num_steps": num_steps,
    }
    return await _post_render(f"{WORKER_URL}/render/t2i", body, timeout_s)


async def render_interleave(
    *,
    prompt: str,
    image_paths: list[str],
    output_dir: Path,
    width: int = 1536,
    height: int = 1536,
    seed: int = 42,
    cfg_scale: float = 4.0,
    img_cfg_scale: float = 1.0,
    num_steps: int = 50,
    think_mode: bool = False,
    timeout_s: float = 1800.0,
) -> Path:
    """Run an interleaved render. Returns the PNG path written by the worker."""
    body = {
        "prompt": prompt,
        "image_paths": list(image_paths),
        "output_dir": str(output_dir),
        "width": width, "height": height,
        "seed": seed,
        "cfg_scale": cfg_scale, "img_cfg_scale": img_cfg_scale,
        "num_steps": num_steps,
        "think_mode": think_mode,
    }
    return await _post_render(f"{WORKER_URL}/render/interleave", body, timeout_s)


async def shutdown(timeout_s: float = 5.0) -> None:
    """Tell the worker to exit (mainly for tests / dev cycles)."""
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        try:
            await client.post(f"{WORKER_URL}/shutdown")
        except httpx.HTTPError:
            pass  # worker may already be exiting


async def _post_render(url: str, body: dict, timeout_s: float) -> Path:
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        try:
            r = await client.post(url, json=body)
        except httpx.HTTPError as exc:
            raise SenseNovaWorkerError(f"worker unreachable at {url}: {exc}") from exc

    if r.status_code >= 400:
        # Worker returns structured error on 5xx; bubble up the traceback if present.
        try:
            err = r.json()
        except ValueError:
            err = {"error": "non-json", "detail": r.text[:1000]}
        raise SenseNovaWorkerError(
            f"{err.get('error', 'unknown')}: {err.get('detail', '')}\n"
            f"{err.get('traceback', '')}")

    data = r.json()
    return Path(data["png_path"])
