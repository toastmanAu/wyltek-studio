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

import shutil
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

        # The worker writes its render to ``<worker_output_dir>/out.png`` and
        # leaves a ``stdout.log`` sidecar for debugging. We then copy the PNG
        # to the Wyltek-side ``output_path`` (gallery location) and delete
        # the worker dir.
        #
        # Two non-obvious constraints drive the path choice:
        # 1. **Absolute path** — the hidream-worker daemon runs with
        #    ``WorkingDirectory=/home/phill/hidream-o1-image`` per its
        #    systemd unit, but Path.mkdir() on a *relative* string lands
        #    wherever the worker happens to be cwd'd. Past sessions show
        #    inconsistent placement (empty dirs at one path, real outputs
        #    at another) because the cwd state isn't predictable across
        #    restarts. ``.resolve()`` forces an absolute path.
        # 2. **Outside ``storage/``** — placing the worker dir inside the
        #    gallery scan path (e.g. ``storage/unsorted/<date>/images/``)
        #    causes ``storage.list_unsorted`` to surface the directory as
        #    a gallery asset; the UI then hits 500 trying to fetch
        #    ``/storage/<dirname>`` as a file. Using ``outputs/hidream-
        #    render/`` keeps the debris out of the gallery's view.
        out = Path(output_path)
        worker_output_dir = (
            Path.cwd() / "outputs" / "hidream-render" / out.stem
        ).resolve()
        worker_output_dir.mkdir(parents=True, exist_ok=True)

        # Auto-orchestrate the worker. The 7900 XTX can only hold one
        # large model at a time, so ensure_loaded() will stop sensenova-
        # worker / comfyui (if they're holding VRAM) and start hidream-
        # worker before we issue the render. Skipped when hidream is
        # already loaded — same warm-path the infographic flow uses.
        from studio.worker_lifecycle import ensure_loaded, WorkerArbitrationError

        async def _on_arbitration(msg: str) -> None:
            # Surface worker-swap progress at a low percentage; the main
            # progress jump to 10% below takes over once the model is up.
            await on_progress(3, msg)

        try:
            await ensure_loaded("hidream", on_status=_on_arbitration)
        except WorkerArbitrationError as exc:
            raise HiDreamError(f"worker arbitration: {exc}") from exc

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
        # expects. We resolve the worker's reported path against
        # ``worker_output_dir`` because the worker may echo back the relative
        # path it received — anchoring on our absolute dir guarantees a
        # working ``exists()`` check regardless of the worker's cwd.
        reported = Path(result["png_path"])
        worker_png = (
            reported if reported.is_absolute() else worker_output_dir / reported.name
        )
        if not worker_png.exists():
            # Fall back to the canonical filename inside our dir before
            # giving up — the worker's contract is to always write
            # ``out.png`` there.
            fallback = worker_output_dir / "out.png"
            if fallback.exists():
                worker_png = fallback
            else:
                raise HiDreamError(
                    f"worker reported png_path={reported!s} but no PNG found "
                    f"at {worker_png!s} or {fallback!s}")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(worker_png.read_bytes())

        # Clean up the worker dir once the gallery PNG has landed. Best-
        # effort — if the rmtree fails the next render will reuse the same
        # dir via ``exist_ok=True`` and overwrite ``out.png`` cleanly.
        try:
            shutil.rmtree(worker_output_dir)
        except OSError:
            pass

        await on_progress(100, "done")
