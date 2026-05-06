"""SenseNova-U1 backend: thin client over the persistent worker daemon.

Model loading + inference lives in :mod:`studio.sensenova_worker` (started
separately under the SenseNova venv). This module preserves the previous
subprocess-based ``generate(...)`` interface so callers in ``server.py``
don't change shape.

The worker holds the model GPU-resident, so a render now skips the ~25 s
cold-load every previous run paid. Model tier (final 50-step vs draft
8-step) is fixed at worker startup via its ``--model_path`` flag — the
``tier`` arg here is accepted for API compatibility but does not switch
loaded weights mid-process. Run a second worker on a different port if
both tiers are needed simultaneously.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Awaitable, Callable

from backends import sensenova_client
from backends.sensenova_client import SenseNovaWorkerError


ProgressCallback = Callable[[int, str], Awaitable[None]]


class SenseNovaError(RuntimeError):
    """Backend or worker reported an error."""


# Resolution buckets the SenseNova-U1 T2I path was trained on. Editing /
# interleave use a smaller table (top-1536 instead of top-2048); we expose
# the larger T2I set here and the worker enforces interleave's own limits.
ASPECT_BUCKETS: dict[str, tuple[int, int]] = {
    "1:1": (1536, 1536), "16:9": (2048, 1152), "9:16": (1152, 2048),
    "3:2": (1888, 1248), "2:3": (1248, 1888), "4:3": (1760, 1312),
    "3:4": (1312, 1760), "1:2": (1088, 2144), "2:1": (2144, 1088),
    "1:3": (864, 2592),  "3:1": (2592, 864),
}

_IMAGE_TOKEN_RE = re.compile(r"\[Image (\d+)\]")

# Default end-to-end ceiling. Worker doesn't time-bound itself; this just
# protects the Wyltek event loop from a stuck render.
DEFAULT_TIMEOUT_S = 1800


def _resolve_image_refs(prompt: str, image_paths: list[str]) -> tuple[str, list[str]]:
    """Walk the prompt and resolve `[Image N]` tokens to actual files.

    Returns (rewritten_prompt, used_images). Each `[Image N]` becomes a
    `<image>` token; `used_images` is built in left-to-right encounter
    order so the model's positional matching aligns with intent. Refs to
    nonexistent indices are left as literal text.
    """
    used: list[str] = []

    def _replace(m: "re.Match[str]") -> str:
        n = int(m.group(1)) - 1
        if 0 <= n < len(image_paths):
            used.append(image_paths[n])
            return "<image>"
        return m.group(0)

    rewritten = _IMAGE_TOKEN_RE.sub(_replace, prompt)
    return rewritten, used


def _resolve_dims(aspect: str | None) -> tuple[int, int]:
    """Aspect ratio → (width, height). Defaults to 1:1 when unspecified."""
    if aspect is None:
        aspect = "1:1"
    if aspect not in ASPECT_BUCKETS:
        raise SenseNovaError(
            f"aspect={aspect!r} not in {sorted(ASPECT_BUCKETS)}")
    return ASPECT_BUCKETS[aspect]


async def generate(
    *,
    prompt: str,
    image_paths: list[str],
    aspect: str | None,
    seed: int,
    tier: str,  # accepted for backward-compat; worker controls the loaded tier
    output_dir: Path,
    on_progress: ProgressCallback | None = None,
    timeout_s: int | None = None,
) -> Path:
    """Run a SenseNova render via the worker. Returns the PNG path.

    Routes to interleave when the resolved prompt actually references
    uploaded images; otherwise routes to T2I (lighter, no autoregressive
    prefill). Raises :class:`SenseNovaError` on worker failure.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if image_paths:
        rewritten, used_images = _resolve_image_refs(prompt, list(image_paths))
    else:
        rewritten, used_images = prompt, []

    width, height = _resolve_dims(aspect)
    timeout = timeout_s if timeout_s is not None else DEFAULT_TIMEOUT_S

    from progress_smooth import SmoothProgress

    if on_progress is None:
        async def _noop(_p: int, _m: str = "") -> None:
            return None
        cb: ProgressCallback = _noop
    else:
        cb = on_progress

    async with SmoothProgress(cb, tick_seconds=2.0, max_creep=85) as sp:
        await sp.set(10, "rendering")
        try:
            if used_images:
                png = await sensenova_client.render_interleave(
                    prompt=rewritten,
                    image_paths=used_images,
                    output_dir=output_dir,
                    width=width, height=height,
                    seed=seed,
                    num_steps=50,
                    think_mode=False,
                    timeout_s=timeout,
                )
            else:
                png = await sensenova_client.render_t2i(
                    prompt=rewritten,
                    output_dir=output_dir,
                    width=width, height=height,
                    seed=seed,
                    num_steps=50,
                    timeout_s=timeout,
                )
        except SenseNovaWorkerError as exc:
            raise SenseNovaError(str(exc)) from exc
        await sp.set(95, "saving")

    if on_progress is not None:
        await on_progress(100, "done")
    return png
