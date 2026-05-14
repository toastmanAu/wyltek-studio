"""HiDream-O1-Image backend: thin client over the persistent worker daemon.

Model loading + inference lives in :mod:`studio.hidream_worker` (started
separately under the HiDream venv at ``~/hidream-o1-image/.venv``). This
module adapts the worker client to Wyltek's ``BaseBackend.generate`` shape so
``server.py`` and the job queue don't need HiDream-specific code paths.

The worker holds the model GPU-resident, so a render skips the ~25 s
cold-load every previous run would pay. Tier (Full 50-step vs Dev 28-step)
is selected per-request via the ``model_type`` parameter — both share the
same loaded weights; only the sampler schedule differs.
"""
from __future__ import annotations

from pathlib import Path

from backends import hidream_client
from backends.base import BaseBackend
from backends.hidream_client import HiDreamWorkerError


# Aspect-ratio buckets HiDream supports at its training resolution. The model
# was trained at 2048-px-class resolutions; smaller requests get snapped up
# inside the pipeline. We expose 2048-side buckets so the UI matches what the
# worker will actually emit, instead of advertising 1024 and silently doubling.
ASPECT_BUCKETS: dict[str, tuple[int, int]] = {
    "1:1": (2048, 2048),
    "16:9": (2304, 1280),
    "9:16": (1280, 2304),
    "3:2": (2048, 1408),
    "2:3": (1408, 2048),
    "4:3": (2048, 1536),
    "3:4": (1536, 2048),
}


class HiDreamError(RuntimeError):
    """Backend or worker reported an error."""


def _resolve_dims(aspect: str | None) -> tuple[int, int]:
    """Aspect ratio → (width, height). Defaults to 1:1 when unspecified."""
    if aspect is None:
        aspect = "1:1"
    if aspect not in ASPECT_BUCKETS:
        raise HiDreamError(
            f"aspect={aspect!r} not in {sorted(ASPECT_BUCKETS)}")
    return ASPECT_BUCKETS[aspect]


class HiDreamBackend(BaseBackend):
    """Wyltek BaseBackend that proxies to the HiDream worker daemon.

    Params consumed from ``params``:

    * ``prompt`` (required) – text prompt
    * ``aspect`` (optional, default "1:1") – one of ASPECT_BUCKETS
    * ``seed`` (optional, default 32)
    * ``model_type`` (optional, default "full") – "full" (50 steps) or "dev" (28 steps)
    * ``ref_image_path`` (optional) – when set, routes to the edit endpoint
    * ``keep_original_aspect`` (optional, default True for edits)
    * ``guidance_scale`` (optional, default 5.0; ignored in dev mode)
    * ``shift`` (optional, default 3.0; ignored in dev mode)
    """

    async def generate(self, params, output_path, on_progress):
        prompt = params.get("prompt")
        if not prompt:
            raise HiDreamError("prompt is required")

        aspect = params.get("aspect", "1:1")
        width, height = _resolve_dims(aspect)

        seed = int(params.get("seed", 32))
        # The image-gen dropdown sends the selected option's `id` as `model`.
        # config.yaml advertises ids of "full" and "dev" which map directly to
        # HiDream's two scheduler tiers; `model_type` stays accepted for
        # direct-API callers that prefer the original name.
        model_type = str(params.get("model") or params.get("model_type") or "full")
        guidance_scale = float(params.get("guidance_scale", 5.0))
        shift = float(params.get("shift", 3.0))
        ref_image_path = params.get("ref_image_path") or None
        keep_original_aspect = bool(params.get("keep_original_aspect", True))

        # Output_dir for the worker = parent of the requested output_path. The
        # worker writes to ``output_dir/out.png``; we move/copy to output_path
        # afterwards so Wyltek's job queue sees the file at its expected path.
        out = Path(output_path)
        worker_output_dir = out.parent / f"hidream_{out.stem}"

        await on_progress(10, f"rendering ({model_type}, {width}x{height})")

        try:
            if ref_image_path:
                result = await hidream_client.render_edit(
                    prompt=prompt,
                    ref_image_path=ref_image_path,
                    output_dir=worker_output_dir,
                    width=width, height=height,
                    seed=seed,
                    model_type=model_type,
                    guidance_scale=guidance_scale,
                    shift=shift,
                    keep_original_aspect=keep_original_aspect,
                )
            else:
                result = await hidream_client.render_t2i(
                    prompt=prompt,
                    output_dir=worker_output_dir,
                    width=width, height=height,
                    seed=seed,
                    model_type=model_type,
                    guidance_scale=guidance_scale,
                    shift=shift,
                )
        except HiDreamWorkerError as exc:
            raise HiDreamError(str(exc)) from exc

        await on_progress(90, "saving")

        # Worker wrote to worker_output_dir/out.png; copy to the path Wyltek
        # expects. Copy (not move) preserves the worker-side log file for
        # debugging when something looks off.
        worker_png = Path(result["png_path"])
        if not worker_png.exists():
            raise HiDreamError(
                f"worker reported png_path={worker_png} but file missing")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(worker_png.read_bytes())

        await on_progress(100, "done")
