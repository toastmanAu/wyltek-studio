"""SenseNova-U1 persistent worker daemon.

Loads the SenseNova-U1 model once at startup and serves inference requests
over HTTP. Model weights stay GPU-resident so subsequent renders skip the
~25-second cold-load penalty per request.

Run with the SenseNova venv's Python (NOT Wyltek's):

    /data/venvs/sensenova-u1/bin/python -m studio.sensenova_worker \\
        --port 9091 --model_path /data/sensenova-u1-weights

Endpoints:
  GET  /status              - liveness + VRAM usage
  POST /render/t2i          - text-to-image
  POST /render/interleave   - text + reference images
  POST /shutdown            - graceful exit (terminates the worker)

Single asyncio.Lock serialises all GPU access; one render at a time.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
import traceback
from pathlib import Path
from typing import Any

from aiohttp import web

import numpy as np
import torch
from PIL import Image
from transformers import AutoConfig, AutoModel, AutoTokenizer


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("sensenova_worker")


NORM_MEAN = (0.5, 0.5, 0.5)
NORM_STD = (0.5, 0.5, 0.5)
DEFAULT_SYSTEM_MESSAGE = (
    "You are a multimodal assistant capable of reasoning with both text and "
    "images. You support two modes:\n\nThink Mode: When reasoning is needed, "
    "you MUST start with a <think></think> block and place all reasoning "
    "inside it. You MUST interleave text with generated images using tags "
    "like <image1>, <image2>. Images can ONLY be generated between <think> "
    "and </think>, and may be referenced in the final answer.\n\nNon-Think "
    "Mode: When no reasoning is needed, directly provide the answer without "
    "reasoning. Do not use tags like <image1>, <image2>; present any images "
    "naturally alongside the text.\n\nAfter the think block, always provide "
    "a concise, user-facing final answer. The answer may include text, "
    "images, or both. Match the user\'s language in both reasoning and the "
    "final answer."
)


# Module-level state, set in init_app.
_MODEL = None
_TOKENIZER = None
_GPU_LOCK: asyncio.Lock | None = None
# Prefetch count drives the layer-offload context: 0 = full GPU resident,
# 1 = synchronous per-layer swap (low RAM), >=2 = async prefetch (balanced).
# Set in load_model via vram_mode_to_prefetch_count.
_PREFETCH_COUNT: int = 0


def _to_pil(batch: torch.Tensor) -> Image.Image:
    mean = torch.tensor(NORM_MEAN, device=batch.device, dtype=batch.dtype).view(1, 3, 1, 1)
    std = torch.tensor(NORM_STD, device=batch.device, dtype=batch.dtype).view(1, 3, 1, 1)
    arr = ((batch * std + mean).clamp(0, 1)
           .float().permute(0, 2, 3, 1).cpu().numpy())
    arr = (arr * 255.0).round().astype(np.uint8)
    return Image.fromarray(arr[0])


def _save_log(output_dir: Path, lines: list[str]) -> None:
    """Append a per-job event log next to the output PNG."""
    try:
        (output_dir / "stdout.log").write_text("".join(lines))
    except OSError:
        pass  # log is best-effort


def _seed_all(seed: int) -> None:
    import random
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_model(model_path: str, vram_mode: str = "full", dtype=torch.bfloat16):
    """Load model + tokenizer with the right offload config for ``vram_mode``.

    ``vram_mode`` options (from sensenova_u1.utils.offload):

    * ``full`` — all weights GPU-resident, no offload. Fits dense U1-8B-MoT
      via accelerate's ``device_map="auto"`` + 20 GiB cap on the 7900 XTX.
    * ``low`` — synchronous per-layer swap. Required for U1-A3B (MoE, ~73 GB
      BF16 total) on a 24 GB card; peak resident weights ≈ active experts.
    * ``balanced`` — async prefetch. Trades a bit more VRAM for ~30% faster
      inference than ``low``.

    Returns (model, tokenizer, prefetch_count). The prefetch_count is stashed
    module-level so the inference handlers can build the offload context.
    """
    log.info(f"Loading model from {model_path} (dtype={dtype}, vram_mode={vram_mode})")
    t0 = time.monotonic()

    # Side-effect: registers the model class with transformers.
    import sensenova_u1  # noqa: F401
    from sensenova_u1 import check_checkpoint_compatibility
    from sensenova_u1.utils import (
        load_model_and_tokenizer,
        vram_mode_to_prefetch_count,
    )

    prefetch_count = vram_mode_to_prefetch_count(vram_mode)

    config = AutoConfig.from_pretrained(model_path)
    check_checkpoint_compatibility(config)

    # ``load_model_and_tokenizer`` handles both the legacy device_map='auto'
    # path (vram_mode='full') and the new layer-offload path (vram_mode in
    # {'low','balanced'}). For ``full`` we keep the same 20GiB/60GiB cap as
    # the prior pinned-on-GPU version to preserve activation headroom.
    # For layer-offload modes the model stays CPU-resident and individual
    # layers are streamed to GPU per forward step.
    if prefetch_count == 0:
        model, tokenizer = load_model_and_tokenizer(
            model_path,
            dtype=dtype,
            device="cuda",
            for_offload=False,
            device_map="auto",
            max_memory={0: "20GiB", "cpu": "40GiB"},
        )
    else:
        model, tokenizer = load_model_and_tokenizer(
            model_path,
            dtype=dtype,
            device="cuda",
            for_offload=True,
        )

    model.train(False)

    elapsed = time.monotonic() - t0
    vram = torch.cuda.memory_allocated() / 1e9 if torch.cuda.is_available() else 0
    log.info(
        f"Model loaded in {elapsed:.1f}s; VRAM resident: {vram:.2f} GB; "
        f"prefetch_count={prefetch_count}"
    )
    return model, tokenizer, prefetch_count


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


async def render_interleave(request: web.Request) -> web.Response:
    body = await request.json()
    return await _run_with_lock(_run_interleave_sync, body)


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
            # ROCm allocator can't compact fragments across requests, so
            # force a full cache release every render to keep the worker
            # stable over many sequential inferences. Runs on success AND
            # on every exception path (Python finally semantics).
            await loop.run_in_executor(None, _free_gpu_caches)
    return web.json_response(result)


def _free_gpu_caches() -> None:
    """Release activation memory back to the allocator pool after a render.

    ROCm 7.2 doesn't support PYTORCH_CUDA_ALLOC_CONF=expandable_segments
    (silently rejected), so the only way to prevent fragmentation
    accumulation across requests in a long-lived worker is to explicitly
    empty the cache. Without this, the second/third render OOMs at
    lm_head pre_forward despite plenty of GPU memory free in aggregate
    (locked up in unmovable fixed-size allocator arenas).
    """
    import gc
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.synchronize()


def _run_t2i_sync(body: dict) -> dict:
    prompt = body["prompt"]
    width = int(body.get("width", 2048))
    height = int(body.get("height", 1152))
    seed = int(body.get("seed", 42))
    cfg_scale = float(body.get("cfg_scale", 4.0))
    num_steps = int(body.get("num_steps", 50))
    output_dir = Path(body["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    log_lines = [f"[t2i] {width}x{height} seed={seed} steps={num_steps} cfg={cfg_scale}\n"]
    t0 = time.monotonic()
    _seed_all(seed)

    from sensenova_u1.utils import make_offload_ctx
    with torch.inference_mode(), make_offload_ctx(_MODEL, _PREFETCH_COUNT, "cuda"):
        out = _MODEL.t2i_generate(
            _TOKENIZER, prompt,
            # NEO-Unify expects (W, H), not (H, W) — modeling_neo_chat reads
            # image_size[0] as width, image_size[1] as height (see line 577-578
            # of the upstream package). Square smoke tests previously hid this.
            image_size=(width, height),
            cfg_scale=cfg_scale,
            num_steps=num_steps,
            seed=seed,
        )

    image_tensors = out if isinstance(out, list) else [out]
    if not image_tensors:
        log_lines.append("ERROR: no images returned\n")
        _save_log(output_dir, log_lines)
        raise RuntimeError("t2i_generate returned no images")

    pil = _to_pil(image_tensors[0])
    out_path = output_dir / "out.png"
    pil.save(out_path)
    elapsed = time.monotonic() - t0
    log_lines.append(f"[t2i] done in {elapsed:.1f}s -> {out_path}\n")
    _save_log(output_dir, log_lines)
    return {"png_path": str(out_path), "elapsed_s": round(elapsed, 2)}


def _run_interleave_sync(body: dict) -> dict:
    prompt = body["prompt"]
    image_paths = list(body.get("image_paths", []))
    width = int(body.get("width", 1536))
    height = int(body.get("height", 1536))
    seed = int(body.get("seed", 42))
    cfg_scale = float(body.get("cfg_scale", 4.0))
    img_cfg_scale = float(body.get("img_cfg_scale", 1.0))
    num_steps = int(body.get("num_steps", 50))
    think_mode = bool(body.get("think_mode", False))
    output_dir = Path(body["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    log_lines = [
        f"[interleave] {width}x{height} seed={seed} steps={num_steps} "
        f"think={think_mode} refs={len(image_paths)}\n"
    ]
    t0 = time.monotonic()
    _seed_all(seed)

    input_images: list[Image.Image] = []
    for p in image_paths:
        try:
            input_images.append(Image.open(p).convert("RGB"))
        except (OSError, FileNotFoundError) as exc:
            log_lines.append(f"ERROR opening {p!r}: {exc}\n")
            _save_log(output_dir, log_lines)
            raise

    from sensenova_u1.utils import make_offload_ctx
    with torch.inference_mode(), make_offload_ctx(_MODEL, _PREFETCH_COUNT, "cuda"):
        text, image_tensors = _MODEL.interleave_gen(
            _TOKENIZER, prompt,
            images=input_images,
            image_size=(width, height),  # (W, H) — see _run_t2i_sync comment
            cfg_scale=cfg_scale,
            img_cfg_scale=img_cfg_scale,
            num_steps=num_steps,
            system_message=DEFAULT_SYSTEM_MESSAGE,
            think_mode=think_mode,
            seed=seed,
        )

    if not image_tensors:
        log_lines.append("ERROR: no images returned\n")
        log_lines.append(f"text output: {text!r}\n")
        _save_log(output_dir, log_lines)
        raise RuntimeError("interleave_gen returned no images")

    # Save the LAST generated image (final answer, after any think-mode
    # intermediates). Matches our previous wrapper convention.
    pil = _to_pil(image_tensors[-1])
    out_path = output_dir / "out.png"
    pil.save(out_path)

    try:
        (output_dir / "model_text.txt").write_text(text or "")
    except OSError:
        pass

    elapsed = time.monotonic() - t0
    log_lines.append(f"[interleave] done in {elapsed:.1f}s -> {out_path}\n")
    if text:
        log_lines.append(f"[interleave] text output ({len(text)} chars):\n{text[:500]}\n")
    _save_log(output_dir, log_lines)
    return {
        "png_path": str(out_path),
        "text": text or "",
        "elapsed_s": round(elapsed, 2),
    }


# -----------------------------------------------------------------------------
# App init
# -----------------------------------------------------------------------------

def init_app(model_path: str, vram_mode: str = "full") -> web.Application:
    global _MODEL, _TOKENIZER, _GPU_LOCK, _PREFETCH_COUNT
    _MODEL, _TOKENIZER, _PREFETCH_COUNT = load_model(model_path, vram_mode=vram_mode)
    _GPU_LOCK = asyncio.Lock()

    app = web.Application()
    app.router.add_get("/status", status)
    app.router.add_post("/render/t2i", render_t2i)
    app.router.add_post("/render/interleave", render_interleave)
    app.router.add_post("/shutdown", shutdown)
    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9091)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--model_path", default="/data/sensenova-u1-weights",
                        help="HF Hub id or local path. 50-step final model.")
    parser.add_argument(
        "--vram_mode", default="full", choices=("full", "low", "balanced"),
        help="GPU memory mode. 'full' = all on GPU (dense U1-8B-MoT). 'low' "
             "= per-layer swap (required for U1-A3B MoE @ ~73GB BF16 on "
             "24GB cards). 'balanced' = async prefetch (some extra VRAM for "
             "~30% faster inference than 'low').",
    )
    args = parser.parse_args()

    app = init_app(args.model_path, vram_mode=args.vram_mode)
    log.info(f"Listening on http://{args.host}:{args.port}")
    web.run_app(app, host=args.host, port=args.port,
                print=None, access_log=log)


if __name__ == "__main__":
    main()
