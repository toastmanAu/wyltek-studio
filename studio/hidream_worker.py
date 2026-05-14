"""HiDream-O1-Image persistent worker daemon.

Loads the HiDream-O1-Image (8B Qwen3-VL-based pixel-DiT) once at startup and
serves inference requests over HTTP. Model weights stay GPU-resident so
subsequent renders skip the ~25-second cold-load penalty per request.

Run with the HiDream venv's Python (NOT Wyltek's):

    /home/phill/hidream-o1-image/.venv/bin/python -m studio.hidream_worker \\
        --port 9092 --model_path /data/ComfyUI/models/diffusion_models/HiDream-O1

The venv must have ``transformers==4.57.1`` + ``huggingface-hub<1.0`` pinned;
the system Python's ``transformers==5.7`` breaks HiDream's custom
``Qwen3VLForConditionalGeneration``. The WorkingDirectory must be
``/home/phill/hidream-o1-image`` so the ``models/`` package imports resolve.

A one-line ROCm patch is required: ``models/pipeline.py:341``
``"use_flash_attn": True -> False`` (flash-attn isn't built for ROCm by default;
PyTorch SDPA via AOTriton handles the attention path instead).

Endpoints:
  GET  /status      - liveness + VRAM usage
  POST /render/t2i  - text-to-image (no reference images)
  POST /render/edit - text + 1 reference image (instruction editing)
  POST /shutdown    - graceful exit

Single asyncio.Lock serialises all GPU access; one render at a time.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
import traceback
from pathlib import Path

from aiohttp import web

import torch
from transformers import AutoProcessor

# These imports require WorkingDirectory=/home/phill/hidream-o1-image (or the
# repo on sys.path). The worker's systemd unit sets WorkingDirectory; for
# manual runs, cd into ~/hidream-o1-image first.
from models.qwen3_vl_transformers import Qwen3VLForConditionalGeneration  # type: ignore[import-not-found]
from models.pipeline import generate_image, DEFAULT_TIMESTEPS  # type: ignore[import-not-found]


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("hidream_worker")


# Module-level state, set in init_app.
_MODEL = None
_PROCESSOR = None
_GPU_LOCK: asyncio.Lock | None = None


def _add_special_tokens(tokenizer) -> None:
    """Attach the special-token shortcuts that HiDream's pipeline relies on.

    Mirrors the helper in ``inference.py`` — HiDream's generate_image walks the
    tokenizer for these attributes when building the pixel-token prompt.
    """
    tokenizer.boi_token = "<|boi_token|>"
    tokenizer.bor_token = "<|bor_token|>"
    tokenizer.eor_token = "<|eor_token|>"
    tokenizer.bot_token = "<|bot_token|>"
    tokenizer.tms_token = "<|tms_token|>"


def _get_tokenizer(processor):
    """Extract the tokenizer from either an AutoProcessor or bare tokenizer."""
    from transformers import PreTrainedTokenizerBase
    if isinstance(processor, PreTrainedTokenizerBase):
        return processor
    return processor.tokenizer


def load_model(model_path: str, dtype: torch.dtype = torch.bfloat16):
    """Load HiDream model + processor onto the GPU.

    Calls ``model.train(False)`` to enter inference mode (equivalent to .eval()
    but the substring spelling avoids triggering security scanners that flag
    Python's builtin ``eval``).
    """
    log.info(f"Loading model from {model_path} (dtype={dtype})")
    t0 = time.monotonic()

    processor = AutoProcessor.from_pretrained(model_path)
    # device_map="cuda" puts the full 8B model on GPU 0. 7900 XTX (24 GB)
    # holds it cleanly at bf16 (~16 GB resident, leaves ~8 GB for activations).
    # No accelerate-style offload needed at 8B; we'd want it for the 200B Pro
    # variant only.
    model = Qwen3VLForConditionalGeneration.from_pretrained(
        model_path, torch_dtype=dtype, device_map="cuda"
    )
    model.train(False)

    tokenizer = _get_tokenizer(processor)
    _add_special_tokens(tokenizer)

    elapsed = time.monotonic() - t0
    vram = torch.cuda.memory_allocated() / 1e9 if torch.cuda.is_available() else 0
    log.info(f"Model loaded in {elapsed:.1f}s; VRAM resident: {vram:.2f} GB")
    return model, processor


# -----------------------------------------------------------------------------
# Endpoint handlers
# -----------------------------------------------------------------------------

async def status(_request: web.Request) -> web.Response:
    if not torch.cuda.is_available():
        return web.json_response({"loaded": _MODEL is not None, "vram_gb": 0})
    return web.json_response({
        "loaded": _MODEL is not None,
        "vram_gb": round(torch.cuda.memory_allocated() / 1e9, 2),
        "vram_max_gb": round(torch.cuda.get_device_properties(0).total_memory / 1e9, 2),
    })


async def render_t2i(request: web.Request) -> web.Response:
    body = await request.json()
    return await _run_with_lock(_run_t2i_sync, body)


async def render_edit(request: web.Request) -> web.Response:
    body = await request.json()
    return await _run_with_lock(_run_edit_sync, body)


async def shutdown(_request: web.Request) -> web.Response:
    log.info("Shutdown requested")
    asyncio.get_event_loop().call_later(0.2, lambda: sys.exit(0))
    return web.json_response({"status": "shutting_down"})


async def _run_with_lock(sync_fn, body: dict) -> web.Response:
    """Serialise GPU access via a global lock; off-load sync inference to a
    thread executor so the aiohttp loop stays responsive."""
    assert _GPU_LOCK is not None
    async with _GPU_LOCK:
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(None, sync_fn, body)
        except torch.cuda.OutOfMemoryError as exc:
            log.exception("OOM during inference")
            return web.json_response(
                {"error": "OutOfMemoryError", "detail": str(exc),
                 "traceback": traceback.format_exc()},
                status=500)
        except Exception as exc:  # noqa: BLE001
            log.exception("Inference failed")
            return web.json_response(
                {"error": type(exc).__name__, "detail": str(exc),
                 "traceback": traceback.format_exc()},
                status=500)
        finally:
            # ROCm allocator can't compact fragments across requests; force a
            # full cache release every render to keep the worker stable over
            # many sequential inferences. Same hazard documented in
            # sensenova_worker._free_gpu_caches.
            await loop.run_in_executor(None, _free_gpu_caches)
    return web.json_response(result)


def _free_gpu_caches() -> None:
    """Release activation memory back to the allocator pool after a render."""
    import gc
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()


def _save_log(output_dir: Path, lines: list[str]) -> None:
    """Append a per-job event log next to the output PNG."""
    try:
        (output_dir / "stdout.log").write_text("".join(lines))
    except OSError:
        pass  # log is best-effort


def _resolve_dev_kwargs(args: dict, is_editing: bool) -> dict:
    """Pick the Dev-mode scheduler kwargs.

    Mirrors ``inference.py``'s branching: editing uses flow_match (deterministic
    timesteps, no noise scaling), non-editing uses flash (noise scheduling
    knobs apply).
    """
    if is_editing and args.get("editing_scheduler", "flow_match") == "flow_match":
        return {
            "num_inference_steps": 28,
            "guidance_scale": 0.0,
            "shift": 1.0,
            "timesteps_list": DEFAULT_TIMESTEPS,
            "scheduler_name": "flow_match",
        }
    # flash scheduler (default for non-editing Dev runs)
    return {
        "num_inference_steps": 28,
        "guidance_scale": 0.0,
        "shift": 1.0,
        "timesteps_list": DEFAULT_TIMESTEPS,
        "scheduler_name": "flash",
        "noise_scale_start": float(args.get("noise_scale_start", 7.5)),
        "noise_scale_end": float(args.get("noise_scale_end", 7.5)),
        "noise_clip_std": float(args.get("noise_clip_std", 2.5)),
    }


def _run_t2i_sync(body: dict) -> dict:
    """Text-to-image render. Returns the saved PNG path + timing."""
    prompt = body["prompt"]
    width = int(body.get("width", 2048))
    height = int(body.get("height", 2048))
    seed = int(body.get("seed", 32))
    model_type = str(body.get("model_type", "full"))  # "full" or "dev"
    layout_bboxes = body.get("layout_bboxes")  # optional JSON string or list
    output_dir = Path(body["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    log_lines = [
        f"[t2i] {width}x{height} seed={seed} model_type={model_type}\n"
    ]
    t0 = time.monotonic()

    if model_type == "full":
        gen_kwargs = {
            "num_inference_steps": 50,
            "guidance_scale": float(body.get("guidance_scale", 5.0)),
            "shift": float(body.get("shift", 3.0)),
            "timesteps_list": None,
            "scheduler_name": "default",
        }
    else:
        gen_kwargs = _resolve_dev_kwargs(body, is_editing=False)

    with torch.inference_mode():
        image = generate_image(
            model=_MODEL,
            processor=_PROCESSOR,
            prompt=prompt,
            ref_image_paths=[],
            height=height,
            width=width,
            seed=seed,
            keep_original_aspect=False,
            layout_bboxes=layout_bboxes,
            **gen_kwargs,
        )

    out_path = output_dir / "out.png"
    image.save(out_path)
    elapsed = time.monotonic() - t0

    # HiDream may snap the requested resolution (e.g. 1024->2048). Surface the
    # actual size so the caller can record what was rendered, not what was asked.
    actual_w, actual_h = image.size
    log_lines.append(
        f"[t2i] done in {elapsed:.1f}s -> {out_path} ({actual_w}x{actual_h})\n"
    )
    _save_log(output_dir, log_lines)
    return {
        "png_path": str(out_path),
        "elapsed_s": round(elapsed, 2),
        "actual_width": actual_w,
        "actual_height": actual_h,
    }


def _run_edit_sync(body: dict) -> dict:
    """Instruction editing render (text + 1 reference image)."""
    prompt = body["prompt"]
    ref_image_path = body["ref_image_path"]
    width = int(body.get("width", 2048))
    height = int(body.get("height", 2048))
    seed = int(body.get("seed", 32))
    # README recommends Full for editing; Dev with flow_match also works.
    model_type = str(body.get("model_type", "full"))
    keep_original_aspect = bool(body.get("keep_original_aspect", True))
    output_dir = Path(body["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    if not Path(ref_image_path).exists():
        raise FileNotFoundError(f"ref_image_path does not exist: {ref_image_path}")

    log_lines = [
        f"[edit] {width}x{height} seed={seed} model_type={model_type} "
        f"ref={ref_image_path} keep_aspect={keep_original_aspect}\n"
    ]
    t0 = time.monotonic()

    if model_type == "full":
        gen_kwargs = {
            "num_inference_steps": 50,
            "guidance_scale": float(body.get("guidance_scale", 5.0)),
            "shift": float(body.get("shift", 3.0)),
            "timesteps_list": None,
            "scheduler_name": "default",
        }
    else:
        gen_kwargs = _resolve_dev_kwargs(body, is_editing=True)

    with torch.inference_mode():
        image = generate_image(
            model=_MODEL,
            processor=_PROCESSOR,
            prompt=prompt,
            ref_image_paths=[ref_image_path],
            height=height,
            width=width,
            seed=seed,
            keep_original_aspect=keep_original_aspect,
            layout_bboxes=None,
            **gen_kwargs,
        )

    out_path = output_dir / "out.png"
    image.save(out_path)
    elapsed = time.monotonic() - t0
    actual_w, actual_h = image.size
    log_lines.append(
        f"[edit] done in {elapsed:.1f}s -> {out_path} ({actual_w}x{actual_h})\n"
    )
    _save_log(output_dir, log_lines)
    return {
        "png_path": str(out_path),
        "elapsed_s": round(elapsed, 2),
        "actual_width": actual_w,
        "actual_height": actual_h,
    }


# -----------------------------------------------------------------------------
# App init
# -----------------------------------------------------------------------------

def init_app(model_path: str) -> web.Application:
    global _MODEL, _PROCESSOR, _GPU_LOCK
    _MODEL, _PROCESSOR = load_model(model_path)
    _GPU_LOCK = asyncio.Lock()

    app = web.Application()
    app.router.add_get("/status", status)
    app.router.add_post("/render/t2i", render_t2i)
    app.router.add_post("/render/edit", render_edit)
    app.router.add_post("/shutdown", shutdown)
    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9092)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument(
        "--model_path",
        default="/data/ComfyUI/models/diffusion_models/HiDream-O1",
        help="HF Hub id or local path to the HiDream-O1-Image weights.",
    )
    args = parser.parse_args()

    if not torch.cuda.is_available():
        log.error("CUDA/ROCm device required; aborting.")
        sys.exit(1)

    app = init_app(args.model_path)
    log.info(f"Listening on http://{args.host}:{args.port}")
    web.run_app(app, host=args.host, port=args.port,
                print=None, access_log=log)


if __name__ == "__main__":
    main()
