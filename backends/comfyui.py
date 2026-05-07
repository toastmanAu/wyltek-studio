"""ComfyUI backend — most flexible local option."""

import asyncio
import base64
import io
import json
import logging
import time
import uuid
from pathlib import Path

import aiohttp

logger = logging.getLogger(__name__)

from backends.base import BaseBackend
from model_catalog import LORA_TRIGGERS

# Server-side optimal defaults per model — applied before workflow build.
# Compare mode sends flat params, so these ensure each model gets sane settings.
# Keys: sampler, scheduler, steps, cfg, width, height (all optional — only override if set)
MODEL_DEFAULTS = {
    # --- SD 1.5 ---
    "v1-5-pruned-emaonly.safetensors": {
        "sampler": "euler_ancestral", "scheduler": "normal",
        "steps": 20, "cfg": 7.0, "width": 512, "height": 512,
    },
    # --- SDXL checkpoints (full safetensors) ---
    "sd_xl_base_1.0.safetensors": {
        "sampler": "dpmpp_2m", "scheduler": "karras",
        "steps": 25, "cfg": 7.0,
    },
    "juggernautXL_v9.safetensors": {
        "sampler": "dpmpp_2m", "scheduler": "karras",
        "steps": 30, "cfg": 6.0,
    },
    "realvisxl-v4.safetensors": {
        "sampler": "dpmpp_2m", "scheduler": "karras",
        "steps": 28, "cfg": 5.5,
    },
    "dreamshaper-xl-v21.safetensors": {
        "sampler": "dpmpp_sde", "scheduler": "karras",
        "steps": 8, "cfg": 2.0,
    },
    # --- SDXL GGUF ---
    "sdxl_base_1.0-Q4_0.gguf": {
        "sampler": "dpmpp_2m", "scheduler": "karras",
        "steps": 25, "cfg": 7.0,
    },
    "juggernautXL_juggXIByRundiffusion-Q4_0.gguf": {
        "sampler": "dpmpp_2m", "scheduler": "karras",
        "steps": 30, "cfg": 6.0,
    },
    "RealVisXL_V4.0-Q4_0.gguf": {
        "sampler": "dpmpp_2m", "scheduler": "karras",
        "steps": 28, "cfg": 5.5,
    },
    # --- RealVisXL V5 (upgraded realism) ---
    "RealVisXL_V5.0-Q4_0.gguf": {
        "sampler": "dpmpp_2m", "scheduler": "karras",
        "steps": 28, "cfg": 5.5,
    },
    # --- ZavyChromaXL (vibrant fantasy/sci-fi) ---
    "zavychromaxl_v100-Q4_0.gguf": {
        "sampler": "dpmpp_2m", "scheduler": "karras",
        "steps": 30, "cfg": 7.0,
    },
    # --- SDXL Lightning (distilled 4-step) ---
    "sdxl-lightning-4step.safetensors": {
        "sampler": "euler", "scheduler": "sgm_uniform",
        "steps": 4, "cfg": 1.0,
    },
    # --- Flux Dev GGUF ---
    # NOTE: "cfg" here is remapped to FluxGuidance.guidance in the workflow
    # builder — Flux-dev is guidance-distilled, so KSampler.cfg is forced to
    # 1.0 and this value drives the FluxGuidance node instead. 3.5 is the
    # Black Forest Labs reference value; 2.0 = looser/painterly, 5.0 = tighter.
    # NOTE: Flux Dev struggles with monochrome subjects on white backgrounds
    # (e.g. green frog). This is a Flux architecture limitation, not tunable
    # via guidance. Schnell handles these subjects fine. Keep guidance at 3.5 which
    # produces excellent results on varied-color subjects (dogs, cats, etc).
    "flux1-dev-Q4_0.gguf": {
        "sampler": "euler", "scheduler": "simple",
        "steps": 20, "cfg": 3.5,
    },
    "flux1-dev-Q5_K_S.gguf": {
        "sampler": "euler", "scheduler": "simple",
        "steps": 20, "cfg": 3.5,
    },
    "flux1-dev-Q8_0.gguf": {
        "sampler": "euler", "scheduler": "simple",
        "steps": 20, "cfg": 3.5,
    },
    # --- Flux Schnell (distilled 4-step) ---
    "flux1-schnell-Q4_0.gguf": {
        "sampler": "euler", "scheduler": "simple",
        "steps": 4, "cfg": 1.0,
    },
    # --- SD3 / SD3.5 (MMDiT, triple CLIP: CLIP-L + CLIP-G + T5-XXL) ---
    # Shared defaults: dpmpp_2m + sgm_uniform, cfg ~4.5-5, steps ~25-30.
    # Use TripleCLIPLoaderGGUF so the GGUF T5 is picked up alongside the
    # safetensors CLIP-L/G — without T5, SD3 prompts degrade badly.
    "sd3-medium-Q4_0.gguf": {
        "sampler": "dpmpp_2m", "scheduler": "sgm_uniform",
        "steps": 28, "cfg": 5.0,
    },
    "sd3.5_medium-Q4_0.gguf": {
        "sampler": "dpmpp_2m", "scheduler": "sgm_uniform",
        "steps": 28, "cfg": 4.5,
    },
    "sd3.5_medium-Q8_0.gguf": {
        "sampler": "dpmpp_2m", "scheduler": "sgm_uniform",
        "steps": 28, "cfg": 4.5,
    },
    # SD 3.5 Large uses Stability's reference recipe: euler + simple.
    # dpmpp_2m + sgm_uniform that works for SD3 Medium under-steps the
    # high-noise region for the 8B Large variant and produces soft output.
    "sd3.5_large-Q4_0.gguf": {
        "sampler": "euler", "scheduler": "simple",
        "steps": 28, "cfg": 4.5,
    },
    "sd3.5_large-Q8_0.gguf": {
        "sampler": "euler", "scheduler": "simple",
        "steps": 28, "cfg": 4.5,
    },
    # --- PixArt-Sigma (DiT, requires ExtraModels / PixArt loader node) ---
    "pixart_sigma_xl_1024.safetensors": {
        "sampler": "dpmpp_2m", "scheduler": "karras",
        "steps": 20, "cfg": 4.5, "width": 1024, "height": 1024,
    },
    # --- FLUX.2 Klein base (non-distilled) ---
    # Klein has its own sampler chain (Flux2Scheduler + SamplerCustomAdvanced)
    # so sampler/scheduler are omitted — they don't apply to this branch.
    # cfg routes to FluxGuidance.guidance (see klein branch ~line 2110); BFL
    # recommends 1.0-5.0. Without this entry, /api/compare's generic cfg=7.0
    # over-bakes Klein output and reads as waxy / under-detailed next to other
    # backends in the comparison. 34 steps + guidance 3.25 sits between the
    # bring-up-verified sweet spot (28/3.5) and a detail-heavy profile (40/3.0).
    "flux-2-klein-base-4b.safetensors": {
        "steps": 34, "cfg": 3.25,
    },
}

# Speed/distillation LoRAs override the base model's sampler/steps/cfg.
# When one of these is active (params["lora_model"]), its settings take
# precedence over MODEL_DEFAULTS. CLIP strength is reduced relative to
# model strength because distillation LoRAs over-imprint on text encoding.
LORA_DEFAULTS = {
    "sdxl_lightning_4step_lora.safetensors": {
        "sampler": "euler", "scheduler": "sgm_uniform",
        "steps": 4, "cfg": 1.0,
        "lora_strength_model": 1.0, "lora_strength_clip": 1.0,
    },
    "sdxl_lightning_8step_lora.safetensors": {
        "sampler": "euler", "scheduler": "sgm_uniform",
        "steps": 8, "cfg": 1.0,
        "lora_strength_model": 1.0, "lora_strength_clip": 1.0,
    },
}


# Common style cues users write deliberately. If any appear in the prompt,
# a prompt is "not bare" — we shouldn't fight an explicit choice like
# "photograph" or "oil painting" by appending a conflicting style trigger.
STYLE_CUES = (
    "photo", "photograph", "photorealistic", "cinematic",
    "painting", "oil painting", "acrylic", "gouache",
    "illustration", "drawing", "sketch", "line art",
    "3d", "3d render", "cgi", "octane", "unreal engine",
    "anime", "manga", "cartoon",
)


def _is_bare_prompt(prompt: str, triggers: list[str]) -> bool:
    """Return True if ``prompt`` lacks any cue that would tell the LoRA what to do.

    Hybrid / combined rule:
      - not bare if any of the LoRA's registered triggers already appear
      - not bare if the prompt declares a deliberate style (STYLE_CUES)
      - bare otherwise — short crude prompts AND long detail-rich prompts
        that never mention a style both get the LoRA's canonical trigger
        appended. This is what makes OP-my-prompt's enriched output work:
        the enhancer adds descriptive detail but rarely style keywords, so
        we still inject on its behalf.
    """
    lowered = prompt.lower()
    if any(t.lower() in lowered for t in triggers):
        return False
    return not any(cue in lowered for cue in STYLE_CUES)


def _maybe_inject_trigger(params: dict) -> dict:
    """If a style LoRA is active and its trigger is missing from the prompt,
    append the canonical trigger. Records the original prompt and the injected
    trigger in ``params`` so the sidecar JSON preserves an audit trail.

    Returns the (possibly modified) params dict. Never mutates the input.
    """
    params = dict(params)
    lora = params.get("lora_model", "")
    triggers = LORA_TRIGGERS.get(lora, [])
    prompt = params.get("prompt", "") or ""

    # Skip when there's nothing to inject — no LoRA, no triggers registered,
    # or the LoRA has explicitly-empty triggers (e.g. Lightning speed-LoRAs).
    if not lora or not triggers:
        return params

    if _is_bare_prompt(prompt, triggers):
        canonical = triggers[0]
        params["original_prompt"] = prompt
        params["trigger_injected"] = canonical
        params["prompt"] = f"{prompt}, {canonical}" if prompt else canonical
        logger.info("LoRA trigger injected: %r → %r (lora=%s)",
                    prompt, params["prompt"], lora)
    return params


def _resolve_defaults(params: dict) -> dict:
    """Apply per-model optimal defaults. User-chosen values that differ from
    the generic UI defaults (steps=30, cfg=7.0, 1024x1024) are preserved;
    generic values get overridden by model-specific ones."""
    model = params.get("model", "")
    defaults = MODEL_DEFAULTS.get(model)

    params = dict(params)  # shallow copy so we don't mutate the original

    # These are the "generic" values the compare endpoint or UI sends when
    # the user hasn't deliberately changed them.  If we see these, replace
    # with the model's optimal settings.
    GENERIC = {"steps": {20, 25, 30}, "cfg_scale": {7.0}, "width": {1024}, "height": {1024}}

    if defaults:
        if "steps" in defaults and params.get("steps") in GENERIC["steps"]:
            params["steps"] = defaults["steps"]
        if "cfg" in defaults and params.get("cfg_scale") in GENERIC["cfg_scale"]:
            params["cfg_scale"] = defaults["cfg"]
        if "width" in defaults and params.get("width") in GENERIC["width"]:
            params["width"] = defaults["width"]
        if "height" in defaults and params.get("height") in GENERIC["height"]:
            params["height"] = defaults["height"]

        # Sampler and scheduler always come from model defaults (not user-settable yet)
        if "sampler" in defaults:
            params["_sampler"] = defaults["sampler"]
        if "scheduler" in defaults:
            params["_scheduler"] = defaults["scheduler"]

    # Speed-LoRA override: a distillation LoRA like SDXL Lightning replaces
    # the base model's sampler/steps/cfg regardless of which base is chosen.
    # This runs AFTER model defaults so the LoRA wins the tie.
    lora = params.get("lora_model", "")
    lora_defaults = LORA_DEFAULTS.get(lora)
    if lora_defaults:
        # Steps and CFG are always forced — Lightning at steps=30/cfg=7 is garbage.
        if "steps" in lora_defaults:
            params["steps"] = lora_defaults["steps"]
        if "cfg" in lora_defaults:
            params["cfg_scale"] = lora_defaults["cfg"]
        if "sampler" in lora_defaults:
            params["_sampler"] = lora_defaults["sampler"]
        if "scheduler" in lora_defaults:
            params["_scheduler"] = lora_defaults["scheduler"]
        # LoRA strengths: only set if the user hasn't overridden them.
        if "lora_strength_model" in lora_defaults and "lora_strength_model" not in params and "lora_strength" not in params:
            params["lora_strength_model"] = lora_defaults["lora_strength_model"]
        if "lora_strength_clip" in lora_defaults and "lora_strength_clip" not in params:
            params["lora_strength_clip"] = lora_defaults["lora_strength_clip"]

    # Hybrid trigger-word injection for style LoRAs. Runs last so it sees the
    # final resolved prompt (in case any earlier step rewrites it).
    params = _maybe_inject_trigger(params)

    return params


# Minimal ComfyUI workflow templates
BASIC_TXT2IMG = {
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 0, "steps": 30, "cfg": 7.0,
            "sampler_name": "euler_ancestral", "scheduler": "normal",
            "denoise": 1.0, "model": ["4", 0], "positive": ["6", 0],
            "negative": ["7", 0], "latent_image": ["5", 0],
        },
    },
    "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"},
    },
    "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": 1024, "height": 1024, "batch_size": 1},
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "", "clip": ["4", 1]},
    },
    "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "", "clip": ["4", 1]},
    },
    "8": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
    },
    "9": {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "wyltek-studio", "images": ["8", 0]},
    },
}


# Img2img workflow template for Style Remix.
# Differs from BASIC_TXT2IMG by replacing EmptyLatentImage with a
# LoadImage -> VAEEncode pair. KSampler starts from a partially-denoised
# version of the source image rather than random noise.
BASIC_IMG2IMG = {
    "1": {
        "class_type": "LoadImage",
        "inputs": {"image": ""},
    },
    "2": {
        "class_type": "VAEEncode",
        "inputs": {"pixels": ["1", 0], "vae": ["4", 2]},
    },
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 0, "steps": 30, "cfg": 7.0,
            "sampler_name": "dpmpp_2m", "scheduler": "karras",
            "denoise": 0.55,
            "model": ["4", 0], "positive": ["6", 0],
            "negative": ["7", 0], "latent_image": ["2", 0],
        },
    },
    "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"},
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "", "clip": ["4", 1]},
    },
    "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "", "clip": ["4", 1]},
    },
    "8": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
    },
    "9": {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "wyltek-remix", "images": ["8", 0]},
    },
}


# Sprite generation workflow: SDXL checkpoint + pixel-art LoRA, batch output
# Default: JuggernautXL v9 (best creature/character detail)
# Switchable to DreamShaper XL (fast, 8 steps) or ZavyChroma (vibrant)
SPRITE_MODELS = {
    "juggernautXL_v9": {
        "checkpoint": "juggernautXL_v9.safetensors",
        "sampler": "dpmpp_2m", "scheduler": "karras",
        "steps": 30, "cfg": 6.0,
    },
    "dreamshaper-xl": {
        "checkpoint": "dreamshaper-xl-v21.safetensors",
        "sampler": "dpmpp_sde", "scheduler": "karras",
        "steps": 8, "cfg": 2.0,
    },
    "zavychroma": {
        "checkpoint": "zavychromaxl_v100-Q4_0.gguf",
        "sampler": "dpmpp_2m", "scheduler": "karras",
        "steps": 30, "cfg": 7.0,
        "is_gguf": True,
    },
    "realvisxl-v5": {
        "checkpoint": "RealVisXL_V5.0-Q4_0.gguf",
        "sampler": "dpmpp_2m", "scheduler": "karras",
        "steps": 28, "cfg": 5.5,
        "is_gguf": True,
    },
    "sd15": {
        "checkpoint": "v1-5-pruned-emaonly.safetensors",
        "sampler": "euler_ancestral", "scheduler": "normal",
        "steps": 20, "cfg": 7.0,
        "resolution": 512,
    },
}

SPRITE_TXT2IMG = {
    "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "juggernautXL_v9.safetensors"},
    },
    "20": {
        "class_type": "LoraLoader",
        "inputs": {
            "lora_name": "pixel-art-xl.safetensors",
            "strength_model": 0.8,
            "strength_clip": 0.48,
            "model": ["4", 0],
            "clip": ["4", 1],
        },
    },
    "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": 1024, "height": 1024, "batch_size": 4},
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "", "clip": ["20", 1]},
    },
    "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "blurry, low quality, watermark, 3d render, photograph, realistic, text, logo, complex background",
            "clip": ["20", 1],
        },
    },
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 0, "steps": 30, "cfg": 6.0,
            "sampler_name": "dpmpp_2m", "scheduler": "karras",
            "denoise": 1.0,
            "model": ["20", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0],
        },
    },
    "8": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
    },
    "9": {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "wyltek-sprite", "images": ["8", 0]},
    },
}


# AnimateDiff workflow: SD1.5 checkpoint + motion model → frames via SaveImage
# Frames are downloaded individually and composed into MP4 server-side via ffmpeg.
ANIMATEDIFF_WORKFLOW = {
    "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "v1-5-pruned-emaonly.safetensors"},
    },
    "30": {
        "class_type": "ADE_LoadAnimateDiffModel",
        "inputs": {"model_name": "mm_sd_v15_v2.ckpt"},
    },
    # UseEvolvedSampling: takes base MODEL + motion models → modified MODEL
    "31": {
        "class_type": "ADE_UseEvolvedSampling",
        "inputs": {
            "model": ["4", 0],
            "beta_schedule": "autoselect",
            "m_models": ["32", 0],
        },
    },
    # ApplyAnimateDiffModelSimple: wraps motion model → M_MODELS group
    "32": {
        "class_type": "ADE_ApplyAnimateDiffModelSimple",
        "inputs": {
            "motion_model": ["30", 0],
        },
    },
    "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": 512, "height": 512, "batch_size": 16},
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "", "clip": ["4", 1]},
    },
    "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "low quality, blurry, distorted, watermark", "clip": ["4", 1]},
    },
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 0, "steps": 20, "cfg": 7.0,
            "sampler_name": "euler_ancestral", "scheduler": "normal",
            "denoise": 1.0, "model": ["31", 0], "positive": ["6", 0],
            "negative": ["7", 0], "latent_image": ["5", 0],
        },
    },
    "8": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
    },
    # SaveImage outputs individual frames — we compose to MP4 server-side
    "9": {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "wyltek-video", "images": ["8", 0]},
    },
}


# Hunyuan3D image-to-3D workflows.
# Hy3D is image-conditioned (not text), so all 3D generations require a
# reference image. We expose two pipelines:
#   - "shape":  ~10–20s, untextured white .glb (DiT + VAE decode + cleanup)
#   - "pbr":    ~3–5min, full-color .glb with baked PBR textures via
#               multi-view paint diffusion (DiT shape + delight + paint
#               sampling + bake + UV apply)
# The Hy3D wrapper's Hy3DModelLoader returns a (HY3DMODEL, HY3DVAE) tuple,
# so the same node feeds both Hy3DGenerateMesh and Hy3DVAEDecode.
def preprocess_hy3d_image(src_path: str, dst_path: str, *, border_ratio: float = 0.2) -> bool:
    """Mirror the official Tencent Hunyuan3D-2 paint pipeline preprocessing.

    Two operations the kijai wrapper doesn't do but the Tencent reference
    pipeline insists on:

    1. **Background removal** if input is RGB. The Hy3D conditioner explicitly
       warns "no alpha channel, make sure background is already black" — and
       silently produces worse texture/shape when the warning is ignored.

    2. **Recenter + 20% pad** (matches official `recenter_image()`). Crop to
       the alpha bbox, add a 20%-of-subject border on every side, then square
       up the canvas. This standardizes subject scale + offset so the DiT and
       paint diffusion see the subject in the position they were trained on.

    Returns True if the image was modified, False if untouched (reads were
    fine but writes are skipped — caller can copy original).
    """
    from PIL import Image
    import numpy as np

    try:
        img = Image.open(src_path)
    except Exception:
        return False

    # Background removal: only when input is RGB. Skip if already RGBA/LA
    # since the user has either pre-cut it or Lift Subject did it on iOS.
    if img.mode == "RGB":
        try:
            from rembg import remove
            img = remove(img).convert("RGBA")
        except Exception:
            # rembg failure shouldn't block the whole job; fall back to
            # original RGB and let the wrapper warn (and degrade) gracefully.
            img.save(dst_path)
            return True
    elif img.mode != "RGBA":
        img = img.convert("RGBA")

    # Recenter + pad. Lifted from the official Tencent recenter_image() at
    # hy3dgen/texgen/pipelines.py — same border_ratio default, same logic.
    alpha = np.array(img)[:, :, 3]
    nz = np.argwhere(alpha > 0)
    if nz.size == 0:
        # Fully transparent (or rembg ate everything) — write original ref so
        # the user sees the same input they uploaded; the wrapper will surface
        # the proper "no subject detected" failure.
        img.save(dst_path)
        return True
    min_row, min_col = nz.min(axis=0)
    max_row, max_col = nz.max(axis=0)
    cropped = img.crop((min_col, min_row, max_col + 1, max_row + 1))

    w, h = cropped.size
    bw = int(w * border_ratio)
    bh = int(h * border_ratio)
    new_w, new_h = w + 2 * bw, h + 2 * bh
    sq = max(new_w, new_h)
    canvas = Image.new("RGBA", (sq, sq), (255, 255, 255, 0))
    paste_x = (sq - new_w) // 2 + bw
    paste_y = (sq - new_h) // 2 + bh
    canvas.paste(cropped, (paste_x, paste_y))
    canvas.save(dst_path)
    return True


def build_3d_workflow(
    model: str,
    image_filename: str,
    *,
    mode: str = "shape",
    seed: int = 0,
    cfg: float = 5.5,
    steps: int = 50,
    paint_model: str = "hunyuan3d-paint-v2-0",
    delight_model: str = "hunyuan3d-delight-v2-0",
    file_prefix: str = "3D/wyltek-3d",
    octree: int = 384,
    max_facenum: int = 50000,
    cam_azimuths: str = "0, 90, 180, 270, 0, 180",
    cam_elevations: str = "0, 0, 0, 0, 90, -90",
) -> dict:
    """Build a ComfyUI API-format workflow for Hy3D image-to-3D.

    Args:
        model: filename in ComfyUI/models/diffusion_models (e.g.
            "hy3dgen/hunyuan3d-dit-v2-0-fp16.safetensors").
        image_filename: name of an image already placed in ComfyUI's
            input/ directory (LoadImage reads from there only).
        mode: "shape" or "pbr".
        file_prefix: ComfyUI's filename_prefix; the actual saved file
            will be <output_dir>/<file_prefix>_NNNNN_.glb.
    """
    if mode not in ("shape", "pbr"):
        raise ValueError(f"mode must be 'shape' or 'pbr', got {mode!r}")

    wf: dict = {
        # Reference image — must already be uploaded to ComfyUI/input/
        "1": {
            "class_type": "LoadImage",
            "inputs": {"image": image_filename},
        },
        # Hy3D DiT + VAE bundle. attention_mode='sdpa' is the only widely
        # supported one across ROCm/CUDA; flash isn't built for ROCm here.
        "2": {
            "class_type": "Hy3DModelLoader",
            "inputs": {"model": model, "attention_mode": "sdpa"},
        },
        # Image-conditioned mesh sampler — the slow step (~5–15s on 7900XTX).
        "3": {
            "class_type": "Hy3DGenerateMesh",
            "inputs": {
                "pipeline": ["2", 0],
                "image": ["1", 0],
                "guidance_scale": cfg,
                "steps": steps,
                "seed": seed,
            },
        },
        # Decode latent → trimesh. octree=384 is a balance of detail vs RAM;
        # 512 doubles VRAM use, 256 loses small features.
        "4": {
            "class_type": "Hy3DVAEDecode",
            "inputs": {
                "vae": ["2", 1],
                "latents": ["3", 0],
                "box_v": 1.01,
                "octree_resolution": octree,
                "num_chunks": 32000,
                "mc_level": 0.0,
                "mc_algo": "mc",
            },
        },
        # Cleanup: remove disconnected floaters, degenerate faces, decimate
        # to <max_facenum> faces. smooth_normals off keeps sharp features.
        "5": {
            "class_type": "Hy3DPostprocessMesh",
            "inputs": {
                "trimesh": ["4", 0],
                "remove_floaters": True,
                "remove_degenerate_faces": True,
                "reduce_faces": True,
                "max_facenum": max_facenum,
                "smooth_normals": False,
            },
        },
    }

    if mode == "shape":
        # Single export — untextured shape only.
        wf["6"] = {
            "class_type": "Hy3DExportMesh",
            "inputs": {
                "trimesh": ["5", 0],
                "filename_prefix": file_prefix,
                "file_format": "glb",
                "save_file": True,
            },
        }
        return wf

    # ----- PBR pipeline: shape mesh + texture-from-multiview-diffusion -----
    # Auto-downloads paint + delight models on first run (~12 GB).
    # Hy3DSampleMultiView expects normal+position maps from the shape mesh,
    # samples views from the paint diffusion model conditioned on the
    # delighted reference image, then bakes back to a UV texture.
    wf.update({
        # UV-unwrap the cleaned shape so we can bake into texture-space later.
        "10": {
            "class_type": "Hy3DMeshUVWrap",
            "inputs": {"trimesh": ["5", 0]},
        },
        # 6-view camera rig: 4 azimuths around horizon + top + bottom.
        # Weights deprioritise top/bottom because front views carry most signal.
        "11": {
            "class_type": "Hy3DCameraConfig",
            "inputs": {
                "camera_azimuths": cam_azimuths,
                "camera_elevations": cam_elevations,
                "view_weights": "1, 0.1, 0.5, 0.1, 0.05, 0.05",
                "camera_distance": 1.45,
                "ortho_scale": 1.2,
            },
        },
        # Render normal+position maps of the bare mesh from each camera.
        # render_size matches official Tencent reference (2048) — was 1024
        # which halved texture detail. 4× pixel cost is OK on 24GB VRAM.
        "12": {
            "class_type": "Hy3DRenderMultiView",
            "inputs": {
                "trimesh": ["10", 0],
                "render_size": 2048,
                "texture_size": 2048,
                "camera_config": ["11", 0],
                "normal_space": "world",
            },
        },
        # Auto-download paint diffusion model. v2-0 is the highest quality;
        # -turbo halves time at a small fidelity cost.
        "13": {
            "class_type": "DownloadAndLoadHy3DPaintModel",
            "inputs": {"model": paint_model},
        },
        # Auto-download delight model (removes baked-in lighting from
        # the reference image so paint sampler doesn't double-shade).
        "14": {
            "class_type": "DownloadAndLoadHy3DDelightModel",
            "inputs": {"model": delight_model},
        },
        # Strip lighting from reference image first.
        "15": {
            "class_type": "Hy3DDelightImage",
            "inputs": {
                "delight_pipe": ["14", 0],
                "image": ["1", 0],
                "steps": 50,
                "width": 512,
                "height": 512,
                "cfg_image": 1.0,
                "seed": seed,
            },
        },
        # Default scheduler ('Euler A' / 'default') — same one example uses.
        "16": {
            "class_type": "Hy3DDiffusersSchedulerConfig",
            "inputs": {
                "pipeline": ["13", 0],
                "scheduler": "Euler A",
                "sigmas": "default",
            },
        },
        # Paint sampler — generates view-consistent multi-view textures
        # conditioned on (delighted_ref, normal_maps, position_maps).
        "17": {
            "class_type": "Hy3DSampleMultiView",
            "inputs": {
                "pipeline": ["13", 0],
                "ref_image": ["15", 0],
                "normal_maps": ["12", 0],
                "position_maps": ["12", 1],
                "view_size": 512,
                "steps": 25,
                "seed": seed + 1024,
                "camera_config": ["11", 0],
                "scheduler": ["16", 0],
            },
        },
        # Project the multi-view textures back onto the UV atlas.
        "18": {
            "class_type": "Hy3DBakeFromMultiview",
            "inputs": {
                "images": ["17", 0],
                "renderer": ["12", 2],
                "camera_config": ["11", 0],
            },
        },
        # Apply the baked texture image to the trimesh.
        "19": {
            "class_type": "Hy3DApplyTexture",
            "inputs": {"texture": ["18", 0], "renderer": ["12", 2]},
        },
        # Final export with textures embedded in the .glb.
        "20": {
            "class_type": "Hy3DExportMesh",
            "inputs": {
                "trimesh": ["19", 0],
                "filename_prefix": f"{file_prefix}_textured",
                "file_format": "glb",
                "save_file": True,
            },
        },
    })
    return wf


def build_hy3d_multiview_workflow(
    model: str,
    view_filenames: dict,  # {"front": "f.png", "back": ..., "left": ..., "right": ...}
    *,
    mode: str = "shape",  # "shape" or "pbr"
    seed: int = 0,
    cfg: float = 5.5,
    steps: int = 30,
    paint_model: str = "hunyuan3d-paint-v2-0",
    delight_model: str = "hunyuan3d-delight-v2-0",
    file_prefix: str = "3D/wyltek-3d-mv",
    octree: int = 384,
    max_facenum: int = 50000,
    scheduler: str = "FlowMatchEulerDiscreteScheduler",
    cam_azimuths: str = "0, 90, 180, 270, 0, 180",
    cam_elevations: str = "0, 0, 0, 0, 90, -90",
) -> dict:
    """Build a Hy3D multi-view shape (or shape+PBR) workflow.

    Shape: routes through Hy3DGenerateMeshMultiView which accepts up to 4
    optional view inputs (front/back/left/right) and conditions the DiT on
    all provided views jointly. Front is required.

    PBR (mode="pbr"): the multi-view shape feeds into the same paint pipeline
    used by single-view PBR (UV-unwrap → render normals/positions → paint
    sample → bake → apply). The paint pipeline's wrapper node hardcodes a
    single ref_image, so we use the FRONT view as paint conditioning — this
    is good enough for the texture step since the shape geometry already
    incorporates back/left/right. Multi-image paint conditioning would need
    a wrapper-side change which the user has declined.

    Hy3D's multi-view DiT has a different inductive bias from TRELLIS's —
    better at man-made / hard-surface / rectilinear subjects (boxes,
    electronics, vehicles) where TRELLIS regresses toward organic curvature.
    """
    if mode not in ("shape", "pbr"):
        raise ValueError(f"mode must be 'shape' or 'pbr', got {mode!r}")
    if "front" not in view_filenames:
        raise ValueError("Hy3D multi-view requires at least 'front'")

    # The wrapper's conditioner runs torchvision Resize on 4D NCHW tensors,
    # which silently no-ops (Resize expects 3D CHW or PIL). Result: views
    # with different aspect ratios reach torch.cat unresized and crash with
    # "Sizes of tensors must match except in dimension 0". Workaround: drop
    # ComfyUI's built-in ImageScale between each LoadImage and the generator
    # so all views arrive at the wrapper at a consistent 518x518 — the size
    # the conditioner is built around (image_size=518 in conditioner.py).
    SCALE_TARGET = 518

    wf: dict = {
        # Front view + its scale step.
        "1": {"class_type": "LoadImage", "inputs": {"image": view_filenames["front"]}},
        "1_scale": {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["1", 0],
                "upscale_method": "lanczos",
                "width": SCALE_TARGET,
                "height": SCALE_TARGET,
                "crop": "center",
            },
        },
        # Same DiT loader as single-view — Hy3DGenerateMeshMultiView reuses
        # the standard HY3DMODEL pipeline; no special multi-view checkpoint.
        "2": {
            "class_type": "Hy3DModelLoader",
            "inputs": {"model": model, "attention_mode": "sdpa"},
        },
    }
    # Conditionally add LoadImage + ImageScale pairs for back/left/right.
    next_id = 21  # leave 3-20 free for the main pipeline below
    view_to_node = {"front": "1_scale"}
    for v in ("back", "left", "right"):
        if v in view_filenames:
            load_id = str(next_id)
            scale_id = f"{next_id}_scale"
            wf[load_id] = {
                "class_type": "LoadImage",
                "inputs": {"image": view_filenames[v]},
            }
            wf[scale_id] = {
                "class_type": "ImageScale",
                "inputs": {
                    "image": [load_id, 0],
                    "upscale_method": "lanczos",
                    "width": SCALE_TARGET,
                    "height": SCALE_TARGET,
                    "crop": "center",
                },
            }
            view_to_node[v] = scale_id
            next_id += 1

    # Multi-view mesh generator. front is required, others are optional —
    # only include keys for views the caller actually provided so unset
    # views default to None on the wrapper side (which the DiT handles).
    mv_inputs = {
        "pipeline": ["2", 0],
        "guidance_scale": cfg,
        "steps": steps,
        "seed": seed,
        "scheduler": scheduler,
        "front": [view_to_node["front"], 0],
    }
    for v in ("back", "left", "right"):
        if v in view_to_node:
            mv_inputs[v] = [view_to_node[v], 0]
    wf["3"] = {
        "class_type": "Hy3DGenerateMeshMultiView",
        "inputs": mv_inputs,
    }

    # Standard decode + cleanup chain — identical to single-view.
    wf["4"] = {
        "class_type": "Hy3DVAEDecode",
        "inputs": {
            "vae": ["2", 1],
            "latents": ["3", 0],
            "box_v": 1.01,
            "octree_resolution": octree,
            "num_chunks": 32000,
            "mc_level": 0.0,
            "mc_algo": "mc",
        },
    }
    wf["5"] = {
        "class_type": "Hy3DPostprocessMesh",
        "inputs": {
            "trimesh": ["4", 0],
            "remove_floaters": True,
            "remove_degenerate_faces": True,
            "reduce_faces": True,
            "max_facenum": max_facenum,
            "smooth_normals": False,
        },
    }
    if mode == "shape":
        wf["6"] = {
            "class_type": "Hy3DExportMesh",
            "inputs": {
                "trimesh": ["5", 0],
                "filename_prefix": file_prefix,
                "file_format": "glb",
                "save_file": True,
            },
        }
        return wf

    # ----- PBR pipeline (multi-view shape + textured) -----
    # Same chain as build_3d_workflow but reading the multi-view-derived mesh
    # at node "5" and using the FRONT view (node "1", pre-resize) as the paint
    # conditioning ref. Wrapper's Hy3DSampleMultiView only accepts one ref;
    # back/left/right would need a wrapper change to also condition paint.
    wf.update({
        "10": {
            "class_type": "Hy3DMeshUVWrap",
            "inputs": {"trimesh": ["5", 0]},
        },
        "11": {
            "class_type": "Hy3DCameraConfig",
            "inputs": {
                "camera_azimuths": cam_azimuths,
                "camera_elevations": cam_elevations,
                "view_weights": "1, 0.1, 0.5, 0.1, 0.05, 0.05",
                "camera_distance": 1.45,
                "ortho_scale": 1.2,
            },
        },
        "12": {
            "class_type": "Hy3DRenderMultiView",
            "inputs": {
                "trimesh": ["10", 0],
                "render_size": 2048,
                "texture_size": 2048,
                "camera_config": ["11", 0],
                "normal_space": "world",
            },
        },
        "13": {
            "class_type": "DownloadAndLoadHy3DPaintModel",
            "inputs": {"model": paint_model},
        },
        "14": {
            "class_type": "DownloadAndLoadHy3DDelightModel",
            "inputs": {"model": delight_model},
        },
        "15": {
            "class_type": "Hy3DDelightImage",
            "inputs": {
                # Use the original front LoadImage (not the 518² scaled one) —
                # delight runs at 512 internally and re-resizes itself.
                "delight_pipe": ["14", 0],
                "image": ["1", 0],
                "steps": 50,
                "width": 512,
                "height": 512,
                "cfg_image": 1.0,
                "seed": seed,
            },
        },
        "16": {
            "class_type": "Hy3DDiffusersSchedulerConfig",
            "inputs": {
                "pipeline": ["13", 0],
                "scheduler": "Euler A",
                "sigmas": "default",
            },
        },
        "17": {
            "class_type": "Hy3DSampleMultiView",
            "inputs": {
                "pipeline": ["13", 0],
                "ref_image": ["15", 0],
                "normal_maps": ["12", 0],
                "position_maps": ["12", 1],
                "view_size": 512,
                "steps": 25,
                "seed": seed + 1024,
                "camera_config": ["11", 0],
                "scheduler": ["16", 0],
            },
        },
        "18": {
            "class_type": "Hy3DBakeFromMultiview",
            "inputs": {
                "images": ["17", 0],
                "renderer": ["12", 2],
                "camera_config": ["11", 0],
            },
        },
        "19": {
            "class_type": "Hy3DApplyTexture",
            "inputs": {
                # Hy3DApplyTexture wants `texture` (IMAGE) and `renderer`
                # (MESHRENDER) — NOT trimesh/image/mask. The node calls
                # renderer.set_texture(texture) then renderer.save_mesh()
                # which returns the textured trimesh. The trimesh implicitly
                # comes from the renderer (carried since UV-unwrap at node 10).
                "texture": ["18", 0],
                "renderer": ["12", 2],
            },
        },
        "20": {
            "class_type": "Hy3DExportMesh",
            "inputs": {
                "trimesh": ["19", 0],
                "filename_prefix": f"{file_prefix}_textured",
                "file_format": "glb",
                "save_file": True,
            },
        },
    })
    return wf


# TRELLIS quality presets — coarse scenario buckets that map well-tuned
# combos of the wrapper's ~20 hyperparameters onto a single user choice.
# Returned dict is overlaid onto the generator node's `inputs` block, so any
# key not set falls through to the LowPoly.json defaults.
TRELLIS_QUALITY_PRESETS = {
    # Default — fast, balanced, matches LowPoly.json's tested values.
    "balanced": {},
    # Hard surface (mech, vehicles, furniture, hard-edged objects). Higher
    # CFG sticks closer to reference, RK4 sampler resolves edges sharply,
    # bumped sparse_structure_resolution gives the skeleton more bins to
    # represent corners cleanly.
    "hard_surface": {
        "shape_steps": 18,
        "shape_guidance_strength": 8.0,
        "sparse_structure_resolution": 48,
        "max_num_tokens": 65536,
        "shape_sampler": "rk4",
    },
    # Organic (creatures, characters, plants). Softer guidance lets the
    # model contribute its prior for skin/cloth/feathers; heun is smoother
    # than euler at the same step count.
    "organic": {
        "shape_steps": 20,
        "shape_guidance_strength": 5.5,
        "shape_sampler": "heun",
    },
    # Asymmetric / detailed (irregular poses, broken/aged objects, anything
    # that needs to NOT regress to symmetry). Highest shape CFG.
    "asymmetric": {
        "shape_steps": 16,
        "shape_guidance_strength": 9.0,
        "sparse_structure_resolution": 40,
    },
    # Max quality — burns time, prioritizes everything.
    "max_quality": {
        "shape_steps": 30,
        "shape_guidance_strength": 8.5,
        "sparse_structure_steps": 20,
        "sparse_structure_resolution": 64,
        "max_num_tokens": 98304,
        "shape_sampler": "rk4",
        "sparse_structure_sampler": "rk4",
    },
}


def _fmt_eta(seconds: float) -> str:
    """Compact ETA string: '12s' under a minute, '2m18s' otherwise.

    Used by the TRELLIS DiT heartbeat — keeps user-facing messages short.
    """
    s = int(max(0, seconds))
    if s < 60:
        return f"{s}s"
    m, sec = divmod(s, 60)
    return f"{m}m{sec:02d}s"


def _resolve_trellis_quality_params(
    preset: str = "balanced",
    *,
    tweak_faithful: bool = False,
    tweak_fine_detail: bool = False,
    tweak_sharp_edges: bool = False,
) -> dict:
    """Resolve a quality preset + 3 toggle modifiers into a flat overrides dict.

    Toggles compose ON TOP of the preset — each one nudges a specific knob
    without rewriting the whole bucket. They're additive, so combining them
    produces predictable layered effects (e.g. hard_surface + faithful =
    even higher CFG; organic + fine_detail = soft + dense).
    """
    overrides = dict(TRELLIS_QUALITY_PRESETS.get(preset, {}))
    if tweak_faithful:
        # Bump shape CFG to glue the result to the reference image's quirks.
        overrides["shape_guidance_strength"] = max(
            overrides.get("shape_guidance_strength", 6.5), 9.0
        )
    if tweak_fine_detail:
        # Increase voxel-budget capacity + initial skeleton resolution so
        # the model has room to encode small features.
        overrides["sparse_structure_resolution"] = max(
            overrides.get("sparse_structure_resolution", 32), 48
        )
        overrides["max_num_tokens"] = max(
            overrides.get("max_num_tokens", 49152), 65536
        )
    if tweak_sharp_edges:
        # RK4 is 4th-order vs euler 1st — sharper edge transitions at the
        # same step count, ~30% slower per step.
        overrides["shape_sampler"] = "rk4"
        overrides["sparse_structure_resolution"] = max(
            overrides.get("sparse_structure_resolution", 32), 48
        )
    return overrides


# TRELLIS 2 image-to-3D workflows (egore/Aero-Ex GGUF wrapper).
# Different family from Hy3D — uses its own pipeline object (TRELLIS2PIPELINE),
# its own image preprocessing, and a 4B parameter model that comes in 6 quant
# formats (BF16 / FP8 / GGUF Q4–Q8). The wrapper auto-downloads weights from
# microsoft/TRELLIS.2-4B on first use.
#
# Pipeline shape mirrors example_workflows/LowPoly.json's graph:
#   shape:    voxel_gen → Remesh → Simplify → FillHoles → ToTrimesh → Export(.glb)
#   textured: + Continue → MeshTexturing → SmoothNormals → Export(textured.glb)
#
# Continue_GGUF is an ordering primitive — it returns input_1 unchanged but
# blocks until input_2 (the white-mesh export side-effect) has run. Without
# it, ComfyUI's scheduler can interleave the two exports unpredictably.
def build_trellis_workflow(
    image_filename: str,
    *,
    mode: str = "shape",  # "shape" or "textured"
    model_format: str = "GGUF Q8_0",
    seed: int = 0,
    file_prefix: str = "3D/wyltek-trellis",
    pipeline_type: str = "512",  # "512" | "1024" | "1024_cascade"
    target_face_num: int = 50000,
    backend: str = "sdpa",
    low_vram: bool = True,
    auto_bg_removal: bool = True,
    quality_overrides: dict | None = None,
) -> dict:
    """Build a ComfyUI API-format workflow for TRELLIS 2 image-to-3D.

    Args:
        image_filename: name of an image already in ComfyUI/input/.
        mode: "shape" (untextured ~30s) or "textured" (~3-5min).
        model_format: TRELLIS quant — "Safetensors (BF16)" | "Safetensors (FP8)"
                      | "GGUF Q8_0" | "GGUF Q6_K" | "GGUF Q5_K_M" | "GGUF Q4_K_M".
        pipeline_type: voxel-grid resolution. 512 is the fast default;
                       1024_cascade is highest quality at ~3x time.
        backend: attention backend. "sdpa" is the only ROCm-compatible one
                 (flash_attn / xformers are CUDA-only).
    """
    if mode not in ("shape", "textured"):
        raise ValueError(f"mode must be 'shape' or 'textured', got {mode!r}")

    # low_vram dispatches between two wrapper code paths with opposite bugs:
    #   • low_vram=True:  trellis2_image_to_3d.py:1651 calls flow_model.to(self.device)
    #                     before sampling — REQUIRED for non-cascade pipelines
    #                     (512, 1024) because the wrapper's load path doesn't
    #                     pre-place those models on GPU.
    #   • low_vram=False: skips that move on the assumption "you loaded on GPU
    #                     already" — only safe for the cascade pipelines, which
    #                     route through sample_shape_slat_cascade_multiview and
    #                     don't hit the same guard.
    # The DINOv3 multi-view shape encoder bug that originally drove low_vram=False
    # is fixed by our explicit self.model.cuda() patch in image_feature_extractor.py.
    is_cascade = pipeline_type in ("1024_cascade", "1536_cascade")
    low_vram = not is_cascade

    # Voxel generator widget defaults — copied from LowPoly.json's tested values.
    # Format: 13 sampler/guidance params spread across sparse-structure / shape /
    # texture stages. These are pre-tuned for the 4B model and shouldn't be
    # exposed to users without a clear reason to deviate.
    wf: dict = {
        "1": {  # ref image
            "class_type": "Trellis2LoadImageWithTransparency_GGUF",
            "inputs": {"image": image_filename},
        },
        "2": {  # preprocess. remove_background gates the rembg pre-step:
                #   ON  → rembg adds alpha (safe for raw RGB photos, but rembg's
                #         u2net default over-segments devices/keyboards)
                #   OFF → trust the user's uploaded alpha; LoadImageWithTransparency
                #         crashes with "index 3 out of bounds" if input is RGB,
                #         so OFF requires a pre-cut transparent PNG.
            "class_type": "Trellis2PreProcessImage_GGUF",
            "inputs": {
                "image": ["1", 2],
                "padding": 25,
                "remove_background": bool(auto_bg_removal),
            },
        },
        "3": {  # 4B DiT pipeline. low_vram=True keeps VRAM under 16GB even at BF16,
                # which leaves headroom for paint/delight if the user runs Hy3D after.
            "class_type": "Trellis2LoadModel_GGUF",
            "inputs": {
                "modelname": "TRELLIS.2-4B",
                "model_format": model_format,
                "backend": backend,
                "device": "cuda",
                "low_vram": low_vram,
                "keep_models_loaded": True,
            },
        },
        "4": {  # the heavy step — voxel grid generation. ~10–60s depending on
                # pipeline_type and quant.
            "class_type": "Trellis2MeshWithVoxelAdvancedGenerator_GGUF",
            "inputs": {
                "pipeline": ["3", 0],
                "image": ["2", 0],
                "seed": seed,
                "pipeline_type": pipeline_type,
                # Sparse-structure stage (coarse occupancy):
                "sparse_structure_steps": 12,
                "sparse_structure_guidance_strength": 6.5,
                "sparse_structure_guidance_rescale": 0.2,
                "sparse_structure_rescale_t": 4.0,
                # Shape stage (fine geometry):
                "shape_steps": 12,
                "shape_guidance_strength": 6.5,
                "shape_guidance_rescale": 0.2,
                "shape_rescale_t": 4.0,
                # Texture-slat stage (latent texture, only used if generate_texture_slat=True):
                "texture_steps": 12,
                "texture_guidance_strength": 3.0,
                "texture_guidance_rescale": 0.2,
                "texture_rescale_t": 3.0,
                "max_num_tokens": 999999,
                "max_views": 4,
                "sparse_structure_resolution": 32,
                "generate_texture_slat": False,
                # Guidance intervals (start=0, end=1 → guidance applied throughout):
                "sparse_structure_guidance_interval_start": 0.0,
                "sparse_structure_guidance_interval_end": 1.0,
                "shape_guidance_interval_start": 0.0,
                "shape_guidance_interval_end": 1.0,
                "texture_guidance_interval_start": 0.0,
                "texture_guidance_interval_end": 1.0,
                "use_tiled_decoder": False,
                # Samplers — euler is fast + stable for shape work.
                "sparse_structure_sampler": "euler",
                "shape_sampler": "euler",
                "texture_sampler": "euler",
                # Caller-provided preset overrides applied last so they win.
                **(quality_overrides or {}),
            },
        },
        "5": {  # remesh: clean up dual-contouring artifacts. 512 res matches LowPoly.
            "class_type": "Trellis2Remesh_GGUF",
            "inputs": {
                "mesh": ["4", 0],
                "remesh_band": 1.0,
                "remesh_project": 0.0,
                "dual_contouring_resolution": "512",
                "remove_floaters": True,
                "remove_inner_faces": True,
            },
        },
        "6": {  # decimate to user-requested face budget. Cumesh is faster than Meshlib.
            "class_type": "Trellis2SimplifyMesh_GGUF",
            "inputs": {
                "mesh": ["5", 0],
                "target_face_num": target_face_num,
                "method": "Cumesh",
            },
        },
        "7": {  # plug topological holes from sparse coverage.
            "class_type": "Trellis2FillHolesWithMeshlib_GGUF",
            "inputs": {"mesh": ["6", 0]},
        },
        "8": {  # voxel/sparse mesh → trimesh for export. 90deg reorient matches
                # the convention in LowPoly (Z-up → Y-up Blender/glTF).
            "class_type": "Trellis2MeshWithVoxelToTrimesh_GGUF",
            "inputs": {"mesh": ["7", 0], "reorient_vertices": "90 degrees"},
        },
    }

    if mode == "shape":
        wf["9"] = {  # final shape export
            "class_type": "Trellis2ExportMesh_GGUF",
            "inputs": {
                "trimesh": ["8", 0],
                "filename_prefix": file_prefix,
                "file_format": "glb",
                "save_file": True,
            },
        }
        return wf

    # ----- Textured path -----
    # Mirror LowPoly: white-mesh export → Continue (forces ordering) →
    # MeshTexturing → SmoothNormals → final textured export.
    wf.update({
        "9": {  # white-mesh sidecar — saves the geometry-only .glb first
            "class_type": "Trellis2ExportMesh_GGUF",
            "inputs": {
                "trimesh": ["8", 0],
                "filename_prefix": f"{file_prefix}_white",
                "file_format": "glb",
                "save_file": True,
            },
        },
        "10": {  # Continue: passes input_1 through, but waits for input_2 to fire
                 # so the white-mesh export completes before texturing starts.
            "class_type": "Trellis2Continue_GGUF",
            "inputs": {"input_1": ["8", 0], "input_2": ["9", 0]},
        },
        "11": {  # paint diffusion — ~3-4 min on 7900XTX at 1024 resolution.
            "class_type": "Trellis2MeshTexturing_GGUF",
            "inputs": {
                "pipeline": ["3", 0],
                "image": ["2", 0],
                "trimesh": ["10", 0],
                "seed": seed,
                "texture_steps": 12,
                "texture_guidance_strength": 3.0,
                "texture_guidance_rescale": 0.2,
                "texture_rescale_t": 3.0,
                "resolution": 1024,
                "texture_size": 1024,
                "texture_alpha_mode": "OPAQUE",
                "double_side_material": False,
                "texture_guidance_interval_start": 0.0,
                "texture_guidance_interval_end": 0.9,
                "max_views": 4,
                "bake_on_vertices": False,
                "use_custom_normals": False,
                "uv_unwrap_method": "Xatlas",  # robust default; Blender requires bpy
                "mesh_cluster_threshold_cone_half_angle_rad": 60.0,
                "use_tiled_encoder": False,
                "encoder_tile_size": 512,
                "encoder_overlap": 64,
                "use_tiled_decoder_for_texture": False,
                "decoder_tile_size": 512,
                "decoder_overlap": 64,
                "sampler": "euler",
            },
        },
        "12": {  # de-block the textured normals (matches LowPoly final touch).
            "class_type": "Trellis2SmoothNormals_GGUF",
            "inputs": {"trimesh": ["11", 0]},
        },
        "13": {  # final textured glb — this is the file we report back as the result.
            "class_type": "Trellis2ExportMesh_GGUF",
            "inputs": {
                "trimesh": ["12", 0],
                "filename_prefix": f"{file_prefix}_textured",
                "file_format": "glb",
                "save_file": True,
            },
        },
    })
    return wf


def build_trellis_multiview_workflow(
    view_filenames: dict,  # {"front": "f.png", "back": "b.png", "left": ..., "right": ...}
    *,
    mode: str = "shape",  # "shape" or "textured"
    model_format: str = "GGUF Q8_0",
    seed: int = 0,
    file_prefix: str = "3D/wyltek-trellis-mv",
    pipeline_type: str = "512",  # "512" | "1024" | "1024_cascade" | "1536_cascade"
    target_face_num: int = 50000,
    backend: str = "sdpa",
    low_vram: bool = True,
    auto_bg_removal: bool = True,
    auto_bg_removal_per_view: dict | None = None,  # per-view override map
    front_axis: str = "z",
    blend_temperature: float = 1.0,
    quality_overrides: dict | None = None,
) -> dict:
    """Build a TRELLIS multi-view workflow.

    `view_filenames` keys: "front" (required), and any of "back", "left",
    "right" (optional). Each maps to an image filename in ComfyUI/input/.
    Views the user didn't supply are simply not connected to the generator
    — the multi-view DiT handles missing views by falling back to its prior.

    Output structure mirrors build_trellis_workflow (shape or textured) but
    routes through Trellis2MeshWithVoxelMultiViewGenerator_GGUF and, in
    textured mode, Trellis2MeshTexturingMultiView_GGUF — both of which
    accept the additional view inputs.
    """
    if mode not in ("shape", "textured"):
        raise ValueError(f"mode must be 'shape' or 'textured', got {mode!r}")
    if "front" not in view_filenames:
        raise ValueError("multi-view workflow requires at least 'front'")

    # See build_trellis_workflow() for the full reasoning on low_vram.
    # Summary: cascade pipelines need False (different sampler), non-cascade
    # need True (relies on the wrapper's .to(self.device) guard at line 1651).
    is_cascade = pipeline_type in ("1024_cascade", "1536_cascade")
    low_vram = not is_cascade

    # One LoadImage + PreProcess pair per supplied view. We use a stable
    # node-id scheme so the multi-view generator + texturing nodes can wire
    # up cleanly: 100 + i for LoadImage, 200 + i for PreProcess, where i is
    # the slot index (front=0, back=1, left=2, right=3).
    slot_for = {"front": 0, "back": 1, "left": 2, "right": 3}
    wf: dict = {}
    preprocessed_for = {}  # view_name -> [node_id, output_slot]
    per_view_bg = auto_bg_removal_per_view or {}
    for view_name, img_filename in view_filenames.items():
        if view_name not in slot_for:
            continue
        i = slot_for[view_name]
        load_id = str(100 + i)
        prep_id = str(200 + i)
        # Per-view override beats the global toggle. This protects against
        # the "index 3 out of bounds" crash on RGB inputs even when the
        # user has Auto-BG-Removal off (e.g. they pre-cut some views via
        # iPhone Lift Subject but left others as raw RGB photos).
        view_bg_removal = per_view_bg.get(view_name, bool(auto_bg_removal))
        wf[load_id] = {
            "class_type": "Trellis2LoadImageWithTransparency_GGUF",
            "inputs": {"image": img_filename},
        }
        wf[prep_id] = {
            "class_type": "Trellis2PreProcessImage_GGUF",
            "inputs": {
                "image": [load_id, 2],  # slot 2 = transparency-aware IMAGE output
                "padding": 25,
                "remove_background": view_bg_removal,
            },
        }
        preprocessed_for[view_name] = [prep_id, 0]

    # 4B DiT pipeline loader.
    wf["3"] = {
        "class_type": "Trellis2LoadModel_GGUF",
        "inputs": {
            "modelname": "TRELLIS.2-4B",
            "model_format": model_format,
            "backend": backend,
            "device": "cuda",
            "low_vram": low_vram,
            "keep_models_loaded": True,
        },
    }

    # Multi-view voxel generator. front_image is required; others optional —
    # we only set keys for views the caller actually provided. Unset optional
    # inputs are treated as None by ComfyUI (the wrapper handles None internally).
    mv_inputs = {
        "pipeline": ["3", 0],
        "front_image": preprocessed_for["front"],
        "seed": seed,
        "pipeline_type": pipeline_type,
        # Same hyperparameter defaults as the single-view path — they're
        # tuned for the 4B model and don't differ meaningfully across views.
        "sparse_structure_steps": 12,
        "sparse_structure_guidance_strength": 6.5,
        "sparse_structure_guidance_rescale": 0.2,
        "sparse_structure_rescale_t": 4.0,
        "shape_steps": 12,
        "shape_guidance_strength": 6.5,
        "shape_guidance_rescale": 0.2,
        "shape_rescale_t": 4.0,
        "texture_steps": 12,
        "texture_guidance_strength": 3.0,
        "texture_guidance_rescale": 0.2,
        "texture_rescale_t": 3.0,
        "max_num_tokens": 999999,
        "sparse_structure_resolution": 32,
        "generate_texture_slat": False,
        "sparse_structure_guidance_interval_start": 0.0,
        "sparse_structure_guidance_interval_end": 1.0,
        "shape_guidance_interval_start": 0.0,
        "shape_guidance_interval_end": 1.0,
        "texture_guidance_interval_start": 0.0,
        "texture_guidance_interval_end": 1.0,
        "use_tiled_decoder": False,
        "front_axis": front_axis,
        "blend_temperature": blend_temperature,
        "sparse_structure_sampler": "euler",
        "shape_sampler": "euler",
        "texture_sampler": "euler",
    }
    if quality_overrides:
        mv_inputs.update(quality_overrides)
    for v in ("back", "left", "right"):
        if v in preprocessed_for:
            mv_inputs[f"{v}_image"] = preprocessed_for[v]
    wf["4"] = {
        "class_type": "Trellis2MeshWithVoxelMultiViewGenerator_GGUF",
        "inputs": mv_inputs,
    }

    # Standard cleanup chain (same as single-view).
    wf["5"] = {
        "class_type": "Trellis2Remesh_GGUF",
        "inputs": {
            "mesh": ["4", 0], "remesh_band": 1.0, "remesh_project": 0.0,
            "dual_contouring_resolution": "512",
            "remove_floaters": True, "remove_inner_faces": True,
        },
    }
    wf["6"] = {
        "class_type": "Trellis2SimplifyMesh_GGUF",
        "inputs": {"mesh": ["5", 0], "target_face_num": target_face_num, "method": "Cumesh"},
    }
    wf["7"] = {
        "class_type": "Trellis2FillHolesWithMeshlib_GGUF",
        "inputs": {"mesh": ["6", 0]},
    }
    wf["8"] = {
        "class_type": "Trellis2MeshWithVoxelToTrimesh_GGUF",
        "inputs": {"mesh": ["7", 0], "reorient_vertices": "90 degrees"},
    }

    if mode == "shape":
        wf["9"] = {
            "class_type": "Trellis2ExportMesh_GGUF",
            "inputs": {
                "trimesh": ["8", 0], "filename_prefix": file_prefix,
                "file_format": "glb", "save_file": True,
            },
        }
        return wf

    # ----- Textured (multi-view) -----
    # Trellis2MeshTexturingMultiView_GGUF accepts the same view set as the
    # generator. front_image is required; back/left/right are required at
    # the schema level (no [opt] in object_info) but pass empty/zero IMAGE
    # tensors when missing — easier to just route the same preprocessed_for
    # dict and only set keys that exist. ComfyUI rejects missing required
    # inputs, so for views the user didn't supply we route the front image
    # as a fallback (the texturing node handles repeated views gracefully).
    fallback = preprocessed_for["front"]
    tx_inputs = {
        "pipeline": ["3", 0],
        "front_image": preprocessed_for["front"],
        "back_image":  preprocessed_for.get("back",  fallback),
        "left_image":  preprocessed_for.get("left",  fallback),
        "right_image": preprocessed_for.get("right", fallback),
        "trimesh": ["8", 0],
        "seed": seed,
        "texture_steps": 12,
        "texture_guidance_strength": 3.0,
        "texture_guidance_rescale": 0.2,
        "texture_rescale_t": 3.0,
        "resolution": 1024,
        "texture_size": 1024,
        "texture_alpha_mode": "OPAQUE",
        "double_side_material": False,
        "texture_guidance_interval_start": 0.0,
        "texture_guidance_interval_end": 0.9,
        "bake_on_vertices": False,
        "use_custom_normals": False,
        "uv_unwrap_method": "Xatlas",
        "mesh_cluster_threshold_cone_half_angle_rad": 60.0,
        "front_axis": front_axis,
        "blend_temperature": blend_temperature,
        "use_tiled_encoder": False,
        "encoder_tile_size": 512,
        "encoder_overlap": 64,
        "use_tiled_decoder_for_texture": False,
        "decoder_tile_size": 512,
        "decoder_overlap": 64,
        "sampler": "euler",
    }
    wf.update({
        "9": {
            "class_type": "Trellis2ExportMesh_GGUF",
            "inputs": {
                "trimesh": ["8", 0],
                "filename_prefix": f"{file_prefix}_white",
                "file_format": "glb", "save_file": True,
            },
        },
        "10": {
            "class_type": "Trellis2Continue_GGUF",
            "inputs": {"input_1": ["8", 0], "input_2": ["9", 0]},
        },
        "11": {
            "class_type": "Trellis2MeshTexturingMultiView_GGUF",
            "inputs": {**tx_inputs, "trimesh": ["10", 0]},
        },
        "12": {
            "class_type": "Trellis2SmoothNormals_GGUF",
            "inputs": {"trimesh": ["11", 0]},
        },
        "13": {
            "class_type": "Trellis2ExportMesh_GGUF",
            "inputs": {
                "trimesh": ["12", 0],
                "filename_prefix": f"{file_prefix}_textured",
                "file_format": "glb", "save_file": True,
            },
        },
    })
    return wf


async def _rescue_orphan_glb(
    file_prefix: str,
    output_path: str,
    *,
    grace_seconds: int = 30,
    poll_interval: float = 2.0,
    comfy_output_dir: Path = Path("/home/phill/ComfyUI/output"),
) -> dict | None:
    """Best-effort recovery of a `.glb` that ComfyUI may write *after* an
    open-palette TimeoutError. Polls the ComfyUI output dir for up to
    `grace_seconds` looking for a file matching ``<file_prefix>*_.glb``.
    If a textured variant exists, prefers it. On match: copies to
    `output_path` (preserving mtime) and returns a dict with rescue metadata.
    Returns None on timeout or no match.

    Caller should wrap this in ``asyncio.shield()`` if invoked from inside
    an outer ``asyncio.wait_for`` cancellation path — otherwise the rescue
    itself gets cancelled before it can copy.
    """
    from glob import glob
    from datetime import datetime
    import shutil
    deadline = asyncio.get_event_loop().time() + grace_seconds
    pattern = str(comfy_output_dir / f"{file_prefix}*_.glb")
    while asyncio.get_event_loop().time() < deadline:
        matches = sorted(glob(pattern))
        # Match _textured_ on the basename only — directory names can
        # legitimately contain "_textured_" (e.g. user's repo path) and
        # would otherwise sweep every glb into the textured bucket.
        textured = [m for m in matches if "_textured_" in Path(m).name]
        chosen = textured[-1] if textured else (matches[-1] if matches else None)
        if chosen:
            shutil.copy2(chosen, output_path)
            return {
                "rescued": True,
                "source": chosen,
                "rescued_at": datetime.now().isoformat(),
            }
        await asyncio.sleep(poll_interval)
    return None


class ComfyUIBackend(BaseBackend):
    async def generate_video(self, params: dict, output_path: str,
                             on_progress) -> dict:
        """Generate a short video clip via AnimateDiff through ComfyUI.

        Pipeline: submit AnimateDiff workflow → get frames via SaveImage →
        download frames → compose to MP4 with ffmpeg.
        """
        import os
        import random
        import shutil
        import tempfile

        url = self.url.rstrip("/")
        prompt_api = f"{url}/prompt"
        ws_url = url.replace("http", "ws") + "/ws"
        client_id = str(uuid.uuid4())

        workflow = json.loads(json.dumps(ANIMATEDIFF_WORKFLOW))

        fps = int(params.get("fps", 8))
        duration = int(params.get("duration", 4))
        frames = fps * duration

        workflow["5"]["inputs"]["batch_size"] = frames
        workflow["5"]["inputs"]["width"] = params.get("width", 512)
        workflow["5"]["inputs"]["height"] = params.get("height", 512)
        workflow["6"]["inputs"]["text"] = params["prompt"]
        workflow["7"]["inputs"]["text"] = params.get("negative_prompt",
                                                     "low quality, blurry, distorted, watermark")

        # Motion model selection — defaults to v15_v2, accepts Lightning variants.
        # Lightning forces euler/sgm_uniform/CFG 1.0 and pins step count to match
        # the distilled variant (4-step or 8-step). User-provided steps are ignored
        # for Lightning because off-spec values produce garbage.
        motion_model = params.get("motion_model", "mm_sd_v15_v2.ckpt")
        workflow["30"]["inputs"]["model_name"] = motion_model

        if "lightning_4step" in motion_model:
            workflow["3"]["inputs"]["steps"] = 4
            workflow["3"]["inputs"]["cfg"] = 1.0
            workflow["3"]["inputs"]["sampler_name"] = "euler"
            workflow["3"]["inputs"]["scheduler"] = "sgm_uniform"
        elif "lightning_8step" in motion_model:
            workflow["3"]["inputs"]["steps"] = 8
            workflow["3"]["inputs"]["cfg"] = 1.0
            workflow["3"]["inputs"]["sampler_name"] = "euler"
            workflow["3"]["inputs"]["scheduler"] = "sgm_uniform"
        else:
            workflow["3"]["inputs"]["steps"] = params.get("steps", 20)
            workflow["3"]["inputs"]["cfg"] = params.get("cfg", 7.0)

        seed = params.get("seed", -1)
        if seed == -1:
            seed = random.randint(0, 2**32 - 1)
        workflow["3"]["inputs"]["seed"] = seed

        await on_progress(5, "Submitting to ComfyUI (AnimateDiff)...")

        async with aiohttp.ClientSession() as session:
            payload = {"prompt": workflow, "client_id": client_id}
            async with session.post(prompt_api, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    # Extract readable message from ComfyUI's verbose JSON errors
                    try:
                        err = json.loads(text)
                        msgs = []
                        if err.get("error", {}).get("message"):
                            msgs.append(err["error"]["message"])
                        for nid, nerr in err.get("node_errors", {}).items():
                            for e in nerr.get("errors", []):
                                msgs.append(e.get("message", ""))
                        raise RuntimeError("; ".join(msgs) or f"ComfyUI error {resp.status}")
                    except (json.JSONDecodeError, KeyError):
                        raise RuntimeError(f"ComfyUI error: {text[:300]}")
                result = await resp.json()
                prompt_id = result["prompt_id"]

            await on_progress(10, "Generating frames...")

            # Poll via WebSocket
            try:
                async with session.ws_connect(f"{ws_url}?clientId={client_id}") as ws:
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("type") == "progress":
                                d = data["data"]
                                pct = int(10 + (d["value"] / d["max"]) * 70)
                                await on_progress(pct, f"Step {d['value']}/{d['max']}")
                            elif data.get("type") == "executed":
                                if data["data"].get("prompt_id") == prompt_id:
                                    break
                            elif data.get("type") == "execution_error":
                                raise RuntimeError(
                                    f"ComfyUI execution error: {data['data']}")
            except aiohttp.ClientError:
                await self._poll_history(session, url, prompt_id, on_progress)

            await on_progress(82, "Downloading frames...")

            # Get output frames from history
            async with session.get(f"{url}/history/{prompt_id}") as resp:
                history = await resp.json()

            outputs = history[prompt_id]["outputs"]
            image_list = []
            for node_output in outputs.values():
                if "images" in node_output:
                    image_list = node_output["images"]
                    break

            if not image_list:
                raise RuntimeError("No frames output from AnimateDiff")

            # Download all frames to temp dir
            tmp_dir = tempfile.mkdtemp(prefix="wyltek-vid-")
            try:
                for i, img_info in enumerate(image_list):
                    img_url = (f"{url}/view?filename={img_info['filename']}"
                               f"&subfolder={img_info.get('subfolder', '')}"
                               f"&type={img_info['type']}")
                    async with session.get(img_url) as resp:
                        img_data = await resp.read()
                    frame_path = os.path.join(tmp_dir, f"frame_{i:04d}.png")
                    with open(frame_path, "wb") as f:
                        f.write(img_data)

                await on_progress(90, f"Composing {len(image_list)} frames to MP4...")

                # ffmpeg: frames → MP4
                cmd = [
                    "ffmpeg", "-y",
                    "-framerate", str(fps),
                    "-i", os.path.join(tmp_dir, "frame_%04d.png"),
                    "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                    "-pix_fmt", "yuv420p",
                    "-r", str(fps),
                    output_path,
                ]
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await proc.communicate()
                if proc.returncode != 0:
                    raise RuntimeError(f"FFmpeg failed: {stderr.decode()[-500:]}")

                file_size = os.path.getsize(output_path)
                await on_progress(100, "Done")

                return {
                    "duration": duration,
                    "frames": len(image_list),
                    "fps": fps,
                    "file_size": file_size,
                    "seed": seed,
                }
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)

    async def generate_sprites(self, params: dict, output_dir: str,
                               on_progress) -> dict:
        """Generate batch of sprite images via SDXL + pixel-art LoRA.

        Supports model selection: juggernautXL_v9 (default), dreamshaper-xl,
        zavychroma, realvisxl-v5, sd15.
        """
        import os
        import random
        import shutil

        url = self.url.rstrip("/")
        prompt_api = f"{url}/prompt"
        ws_url = url.replace("http", "ws") + "/ws"
        client_id = str(uuid.uuid4())

        workflow = json.loads(json.dumps(SPRITE_TXT2IMG))

        # Model selection
        model_id = params.get("model", "juggernautXL_v9")
        model_cfg = SPRITE_MODELS.get(model_id, SPRITE_MODELS["juggernautXL_v9"])
        checkpoint = model_cfg["checkpoint"]
        is_gguf = model_cfg.get("is_gguf", False)
        gen_resolution = model_cfg.get("resolution", 1024)

        if is_gguf:
            # GGUF needs UnetLoaderGGUF + DualCLIPLoader + VAELoader
            workflow["4"] = {
                "class_type": "UnetLoaderGGUF",
                "inputs": {"unet_name": checkpoint},
            }
            workflow["14"] = {
                "class_type": "DualCLIPLoader",
                "inputs": {
                    "clip_name1": "clip_l.safetensors",
                    "clip_name2": "clip_g.safetensors",
                    "type": "sdxl",
                },
            }
            workflow["15"] = {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "sdxl_vae_fp16_fix.safetensors"},
            }
            # Rewire LoRA to use GGUF model + separate CLIP
            workflow["20"]["inputs"]["model"] = ["4", 0]
            workflow["20"]["inputs"]["clip"] = ["14", 0]
            # Rewire VAE
            workflow["8"]["inputs"]["vae"] = ["15", 0]
        else:
            workflow["4"]["inputs"]["ckpt_name"] = checkpoint

        # Resolution
        workflow["5"]["inputs"]["width"] = gen_resolution
        workflow["5"]["inputs"]["height"] = gen_resolution

        batch_size = int(params.get("batch_size", 4))
        workflow["5"]["inputs"]["batch_size"] = batch_size

        # Apply model-specific sampler/scheduler/steps/cfg
        workflow["3"]["inputs"]["sampler_name"] = model_cfg["sampler"]
        workflow["3"]["inputs"]["scheduler"] = model_cfg["scheduler"]
        workflow["3"]["inputs"]["steps"] = params.get("steps", model_cfg["steps"])
        workflow["3"]["inputs"]["cfg"] = params.get("cfg", model_cfg["cfg"])

        # Prefix prompt with pixel art tokens
        user_prompt = params.get("prompt", "")
        workflow["6"]["inputs"]["text"] = (
            f"pixel art sprite, {user_prompt}, game asset, clean lines, "
            "transparent background, 16-bit style"
        )
        if params.get("negative_prompt"):
            workflow["7"]["inputs"]["text"] = params["negative_prompt"]

        # LoRA strength
        lora_strength = float(params.get("lora_strength", 0.55))
        workflow["20"]["inputs"]["strength_model"] = lora_strength
        workflow["20"]["inputs"]["strength_clip"] = lora_strength * 0.6

        seed = params.get("seed", -1)
        if seed == -1:
            seed = random.randint(0, 2**32 - 1)
        workflow["3"]["inputs"]["seed"] = seed

        # IP-Adapter for reference images
        ref_images = params.get("reference_images", [])
        logger.info("IP-Adapter: ref_images=%s", ref_images)
        if ref_images:
            copied_refs = []
            comfy_input_dir = Path("/home/phill/ComfyUI/input")
            for rp in ref_images:
                src = Path(rp)
                logger.info("IP-Adapter: checking ref %s exists=%s", src, src.exists())
                if src.exists():
                    prepared = self._prepare_ref_image(src, comfy_input_dir)
                    copied_refs.append(prepared)
            logger.info("IP-Adapter: copied_refs=%s", copied_refs)
            if copied_refs:
                params_copy = {
                    **params,
                    "ip_adapter_strength": float(params.get("ip_adapter_strength", 0.75)),
                    "ip_adapter_weight_type": params.get("ip_adapter_weight_type", "style transfer"),
                    "ip_adapter_start": float(params.get("ip_adapter_start", 0.0)),
                    "ip_adapter_end": float(params.get("ip_adapter_end", 0.8)),
                    "ip_adapter_model": "ip-adapter-plus_sdxl_vit-h.safetensors",
                }
                logger.info("IP-Adapter: injecting weight=%.2f type=%s range=%.2f-%.2f",
                            params_copy["ip_adapter_strength"],
                            params_copy["ip_adapter_weight_type"],
                            params_copy["ip_adapter_start"],
                            params_copy["ip_adapter_end"])
                workflow = self._add_ip_adapter(workflow, copied_refs, params_copy)
            else:
                logger.warning("IP-Adapter: no refs survived copy — skipping")
        else:
            logger.info("IP-Adapter: no reference images provided")

        await on_progress(5, "Submitting sprite generation...")

        async with aiohttp.ClientSession() as session:
            payload = {"prompt": workflow, "client_id": client_id}
            async with session.post(prompt_api, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    try:
                        err = json.loads(text)
                        msgs = []
                        if err.get("error", {}).get("message"):
                            msgs.append(err["error"]["message"])
                        for nid, nerr in err.get("node_errors", {}).items():
                            for e in nerr.get("errors", []):
                                msgs.append(e.get("message", ""))
                        raise RuntimeError("; ".join(msgs) or f"ComfyUI error {resp.status}")
                    except (json.JSONDecodeError, KeyError):
                        raise RuntimeError(f"ComfyUI error: {text[:300]}")
                result = await resp.json()
                prompt_id = result["prompt_id"]

            await on_progress(10, f"Generating {batch_size} sprites...")

            # Poll via WebSocket
            try:
                async with session.ws_connect(f"{ws_url}?clientId={client_id}") as ws:
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("type") == "progress":
                                d = data["data"]
                                pct = int(10 + (d["value"] / d["max"]) * 75)
                                await on_progress(pct, f"Step {d['value']}/{d['max']}")
                            elif data.get("type") == "executed":
                                if data["data"].get("prompt_id") == prompt_id:
                                    break
                            elif data.get("type") == "execution_error":
                                raise RuntimeError(
                                    f"ComfyUI execution error: {data['data']}")
            except aiohttp.ClientError:
                await self._poll_history(session, url, prompt_id, on_progress)

            await on_progress(88, "Downloading sprites...")

            # Get ALL output images (batch)
            async with session.get(f"{url}/history/{prompt_id}") as resp:
                history = await resp.json()

            outputs = history[prompt_id]["outputs"]
            image_list = []
            for node_output in outputs.values():
                if "images" in node_output:
                    image_list = node_output["images"]
                    break

            if not image_list:
                raise RuntimeError("No sprite output from ComfyUI")

            os.makedirs(output_dir, exist_ok=True)
            saved = []
            for i, img_info in enumerate(image_list):
                img_url = (f"{url}/view?filename={img_info['filename']}"
                           f"&subfolder={img_info.get('subfolder', '')}"
                           f"&type={img_info['type']}")
                async with session.get(img_url) as resp:
                    img_data = await resp.read()
                out_path = os.path.join(output_dir, f"sprite_{i}.png")
                with open(out_path, "wb") as f:
                    f.write(img_data)
                saved.append(out_path)

            await on_progress(100, "Done")
            return {
                "count": len(saved),
                "files": saved,
                "seed": seed,
                "batch_size": batch_size,
            }

    async def generate(self, params, output_path, on_progress):
        # Apply per-model optimal defaults before building workflow
        resolved = _resolve_defaults(params)
        # Propagate audit fields (effective prompt + injection record) back to
        # the caller's dict so the sidecar JSON captures what actually went to
        # the model, not just what the user typed.
        for key in ("prompt", "original_prompt", "trigger_injected"):
            if key in resolved:
                params[key] = resolved[key]
        params = resolved

        url = self.url.rstrip("/")
        prompt_api = f"{url}/prompt"
        ws_url = url.replace("http", "ws") + "/ws"
        client_id = str(uuid.uuid4())

        model_name = params.get("model", "")
        is_gguf = model_name.endswith(".gguf")

        workflow = json.loads(json.dumps(BASIC_TXT2IMG))

        is_flux = is_gguf and "flux" in model_name.lower()
        # SD3/3.5 detection covers both "sd3" and "stable-diffusion-3" naming,
        # GGUF-only (the only SD3 path Wyltek Studio ships today).
        lower_name = model_name.lower()
        is_sd3 = is_gguf and ("sd3" in lower_name or "sd3.5" in lower_name
                              or "stable-diffusion-3" in lower_name)
        # SD 3.5 (Medium + Large) was trained with shift=3.0; SD 3 original
        # used shift~1.0. Distinguishing here so only SD 3.5 gets the
        # ModelSamplingSD3 shift node injected below.
        is_sd35 = is_sd3 and "sd3.5" in lower_name
        is_klein = "klein" in lower_name
        # SDXL Lightning is guidance-distilled like Flux/Klein: cfg MUST be 1.0
        # and step count is fixed (4 or 8). The post-branch param loop below
        # would otherwise clobber these invariants with user-set slider values.
        is_lightning = model_name.startswith("sdxl-lightning")
        # PixArt-Sigma is a bare DiT transformer — no CLIP or VAE in the
        # checkpoint — so we need ExtraModels's PixArt-specific loaders.
        is_pixart = "pixart" in lower_name

        if is_klein:
            # FLUX.2-klein canonical recipe (per feedback_comfyui_rocm_rdna3.md
            # bring-up 2026-04-14):
            #   Flux2Scheduler + SamplerCustomAdvanced + BasicGuider + RandomNoise
            # with FluxGuidance=3.5 and steps=4.
            #
            # Why NOT plain KSampler + ModelSamplingFlux: Flux2Scheduler is
            # aspect-ratio-aware — it computes the correct timestep shift
            # from (steps, width, height). ModelSamplingFlux with a hardcoded
            # flat shift value overrides that adaptive logic and produces
            # malformed geometry / bad anatomy at non-square aspect ratios.
            workflow["4"] = {
                "class_type": "UNETLoader",
                # weight_dtype="default" (NOT fp8_e4m3fn) — on-the-fly fp8
                # quantization during weight load produces malformed output
                # for FLUX.2-klein on AMD gfx1100. Verified by comparing
                # against known-good ComfyUI-direct generations whose
                # workflow JSON is embedded in ~/ComfyUI/output/flux2_*.png.
                "inputs": {"unet_name": model_name, "weight_dtype": "default"},
            }
            workflow["14"] = {
                "class_type": "CLIPLoader",
                "inputs": {
                    "clip_name": "flux2_klein_qwen3_merged.safetensors",
                    "type": "flux2",
                },
            }
            workflow["15"] = {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "flux2-klein-vae.safetensors"},
            }
            # FLUX.2 has its own latent initialiser with the correct
            # 16-channel scale. Replace BASIC_TXT2IMG's generic
            # EmptyLatentImage (node 5) to match the canonical klein
            # workflow captured from prior successful generations.
            workflow["5"] = {
                "class_type": "EmptyFlux2LatentImage",
                "inputs": {
                    "width": params.get("width", 1024),
                    "height": params.get("height", 1024),
                    "batch_size": 1,
                },
            }
            workflow["6"]["inputs"]["clip"] = ["14", 0]
            workflow["7"]["inputs"]["clip"] = ["14", 0]
            workflow["22"] = {
                "class_type": "FluxGuidance",
                "inputs": {
                    "conditioning": ["6", 0],
                    # Klein's "cfg_scale" slider routes here as distilled
                    # guidance. BFL's recommended range is 1.0-5.0; 3.5 is
                    # the bring-up-verified sweet spot. Default fallback
                    # covers the case where _resolve_defaults left cfg at
                    # the klein-defaults "1.0" value (which would
                    # desaturate output — 3.5 is safer for un-tuned users).
                    "guidance": float(params.get("cfg_scale", 3.5))
                               if params.get("cfg_scale", 3.5) >= 1.5 else 3.5,
                },
            }
            workflow["23"] = {
                "class_type": "BasicGuider",
                "inputs": {"model": ["4", 0], "conditioning": ["22", 0]},
            }
            workflow["24"] = {
                "class_type": "KSamplerSelect",
                "inputs": {"sampler_name": "euler"},
            }
            workflow["25"] = {
                "class_type": "Flux2Scheduler",
                "inputs": {
                    "steps": int(params.get("steps", 4) or 4),
                    "width": params.get("width", 1024),
                    "height": params.get("height", 1024),
                },
            }
            # Resolve seed up-front (RandomNoise needs a concrete int; we
            # can't wait for the post-branch seed resolver because that
            # writes into workflow["3"] which we're about to delete).
            _klein_seed = params.get("seed", -1)
            if _klein_seed == -1:
                import random
                _klein_seed = random.randint(0, 2**32 - 1)
            params["seed"] = _klein_seed  # stabilises audit trail downstream
            workflow["26"] = {
                "class_type": "RandomNoise",
                "inputs": {"noise_seed": _klein_seed},
            }
            workflow["27"] = {
                "class_type": "SamplerCustomAdvanced",
                "inputs": {
                    "noise": ["26", 0],
                    "guider": ["23", 0],
                    "sampler": ["24", 0],
                    "sigmas": ["25", 0],
                    "latent_image": ["5", 0],
                },
            }
            # Re-route VAEDecode to pull from the advanced sampler.
            workflow["8"]["inputs"]["samples"] = ["27", 0]
            workflow["8"]["inputs"]["vae"] = ["15", 0]
            # Drop the stock KSampler — all its writes below are guarded.
            del workflow["3"]
        elif is_flux:
            # Flux uses GGUF UNet + T5-XXL + CLIP-L + Flux VAE + different sampler
            is_schnell = "schnell" in model_name.lower()
            workflow["4"] = {
                "class_type": "UnetLoaderGGUF",
                "inputs": {"unet_name": model_name},
            }
            workflow["14"] = {
                "class_type": "DualCLIPLoaderGGUF",
                "inputs": {
                    "clip_name1": "clip_l.safetensors",
                    "clip_name2": "t5-v1_1-xxl-encoder-Q4_K_M.gguf",
                    "type": "flux",
                },
            }
            workflow["15"] = {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "ae.safetensors"},
            }
            # Flux-dev is guidance-distilled: KSampler.cfg MUST be 1.0, and the
            # "guidance" value (what users think of as CFG) is injected via a
            # FluxGuidance node on the positive conditioning. Running real CFG
            # against a distilled model produces washed-out, low-contrast output.
            workflow["22"] = {
                "class_type": "FluxGuidance",
                "inputs": {
                    "conditioning": ["6", 0],
                    "guidance": params.get("cfg_scale", 3.5) if not is_schnell else 3.5,
                },
            }
            workflow["3"]["inputs"]["model"] = ["4", 0]
            workflow["6"]["inputs"]["clip"] = ["14", 0]
            workflow["7"]["inputs"]["clip"] = ["14", 0]
            workflow["3"]["inputs"]["positive"] = ["22", 0]
            workflow["8"]["inputs"]["vae"] = ["15", 0]
            workflow["3"]["inputs"]["sampler_name"] = "euler"
            workflow["3"]["inputs"]["scheduler"] = "simple"
            workflow["3"]["inputs"]["cfg"] = 1.0
            if is_schnell:
                workflow["3"]["inputs"]["steps"] = params.get("steps", 4)
        elif is_sd3:
            # SD3 / SD3.5: MMDiT architecture with THREE text encoders
            # (CLIP-L + CLIP-G + T5-XXL). Dropping T5 gives visibly worse
            # prompt following — TripleCLIPLoaderGGUF handles the mixed
            # safetensors-CLIP + GGUF-T5 situation.
            # VAE: use Stability's own sd3.5_vae.safetensors (16-ch f8). The
            # Flux VAE (ae.safetensors) is architecturally compatible but
            # has different latent-scale statistics — decoding SD3 latents
            # through it produces a "metal-stamped" embossed artefact.
            workflow["4"] = {
                "class_type": "UnetLoaderGGUF",
                "inputs": {"unet_name": model_name},
            }
            workflow["14"] = {
                "class_type": "TripleCLIPLoaderGGUF",
                "inputs": {
                    "clip_name1": "clip_l.safetensors",
                    "clip_name2": "clip_g.safetensors",
                    "clip_name3": "t5-v1_1-xxl-encoder-Q4_K_M.gguf",
                },
            }
            workflow["15"] = {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "sd3.5_vae.safetensors"},
            }
            workflow["6"]["inputs"]["clip"] = ["14", 0]
            workflow["7"]["inputs"]["clip"] = ["14", 0]
            workflow["8"]["inputs"]["vae"] = ["15", 0]
            # SD 3.5 (Medium + Large) was trained with shift=3.0 — the
            # rectified-flow timestep reshape that concentrates sampling
            # effort in the high-noise region. Without ModelSamplingSD3,
            # KSampler uses a linear schedule and output is visibly soft /
            # under-converged. SD 3 original (non-3.5) keeps the default.
            if is_sd35:
                workflow["21"] = {
                    "class_type": "ModelSamplingSD3",
                    "inputs": {"model": ["4", 0], "shift": 3.0},
                }
                workflow["3"]["inputs"]["model"] = ["21", 0]
            else:
                workflow["3"]["inputs"]["model"] = ["4", 0]
        elif is_pixart:
            # PixArt-Sigma: DiT transformer using T5-XXL only (no CLIP-L/G).
            # The .safetensors file is a bare transformer — no CLIP or VAE
            # bundled — so CheckpointLoaderSimple can't handle it. We use
            # ExtraModels' PixArtCheckpointLoader for the transformer, reuse
            # the SD3 TripleCLIPLoaderGGUF to get a handle on our existing
            # T5-XXL GGUF, extract just the T5 portion via PixArtT5FromSD3CLIP,
            # and pair with the SDXL VAE (PixArt was trained against it).
            workflow["4"] = {
                "class_type": "PixArtCheckpointLoader",
                "inputs": {
                    "ckpt_name": model_name,
                    "model": "PixArtMS_Sigma_XL_2",
                },
            }
            workflow["14"] = {
                "class_type": "TripleCLIPLoaderGGUF",
                "inputs": {
                    "clip_name1": "clip_l.safetensors",
                    "clip_name2": "clip_g.safetensors",
                    "clip_name3": "t5-v1_1-xxl-encoder-Q4_K_M.gguf",
                },
            }
            # PixArtT5FromSD3CLIP outputs a CLIP-typed handle (not T5) that
            # wraps just the T5 portion of the SD3-style CLIP bundle. We keep
            # the stock CLIPTextEncode nodes (6 + 7) and point them at this
            # T5-only CLIP — that's the intended "Path B" in ExtraModels.
            # (Path A uses T5v11Loader + PixArtT5TextEncode but needs T5
            # weights pre-staged in models/t5/ which we don't have.)
            workflow["16"] = {
                "class_type": "PixArtT5FromSD3CLIP",
                "inputs": {"sd3_clip": ["14", 0], "padding": 1},
            }
            workflow["15"] = {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "sdxl_vae_fp16_fix.safetensors"},
            }
            workflow["6"]["inputs"]["clip"] = ["16", 0]
            workflow["7"]["inputs"]["clip"] = ["16", 0]
            workflow["3"]["inputs"]["model"] = ["4", 0]
            workflow["8"]["inputs"]["vae"] = ["15", 0]
        elif model_name.startswith("sdxl-lightning"):
            # SDXL Lightning is a UNet-only safetensor, needs separate CLIP + VAE
            workflow["4"] = {
                "class_type": "UNETLoader",
                "inputs": {"unet_name": model_name, "weight_dtype": "default"},
            }
            workflow["14"] = {
                "class_type": "DualCLIPLoader",
                "inputs": {
                    "clip_name1": "clip_l.safetensors",
                    "clip_name2": "clip_g.safetensors",
                    "type": "sdxl",
                },
            }
            workflow["15"] = {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "sdxl_vae_fp16_fix.safetensors"},
            }
            workflow["3"]["inputs"]["model"] = ["4", 0]
            workflow["6"]["inputs"]["clip"] = ["14", 0]
            workflow["7"]["inputs"]["clip"] = ["14", 0]
            workflow["8"]["inputs"]["vae"] = ["15", 0]
            workflow["3"]["inputs"]["sampler_name"] = "euler"
            workflow["3"]["inputs"]["scheduler"] = "sgm_uniform"
            workflow["3"]["inputs"]["cfg"] = 1.0
            # Lightning's 4-step invariant — shielded by the is_lightning guard
            # in the post-branch loop so a user's slider can't override it.
            # Without this explicit set, BASIC_TXT2IMG's default 30 bleeds
            # through and the model over-denoises into a dark sludge.
            workflow["3"]["inputs"]["steps"] = 4
        elif is_gguf:
            # SDXL GGUF models use separate UNet + CLIP + VAE loaders
            workflow["4"] = {
                "class_type": "UnetLoaderGGUF",
                "inputs": {"unet_name": model_name},
            }
            workflow["14"] = {
                "class_type": "DualCLIPLoader",
                "inputs": {
                    "clip_name1": "clip_l.safetensors",
                    "clip_name2": "clip_g.safetensors",
                    "type": "sdxl",
                },
            }
            workflow["15"] = {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "sdxl_vae_fp16_fix.safetensors"},
            }
            # Rewire: KSampler model from GGUF UNet, CLIP from DualCLIPLoader, VAE from VAELoader
            workflow["3"]["inputs"]["model"] = ["4", 0]
            workflow["6"]["inputs"]["clip"] = ["14", 0]
            workflow["7"]["inputs"]["clip"] = ["14", 0]
            workflow["8"]["inputs"]["vae"] = ["15", 0]
        elif model_name:
            workflow["4"]["inputs"]["ckpt_name"] = model_name

        # Inject LoRA if specified
        lora_name = params.get("lora_model", "")
        lora_strength_model = float(params.get("lora_strength_model", params.get("lora_strength", 0.8)))
        lora_strength_clip = float(params.get("lora_strength_clip", lora_strength_model * 0.6))
        # PixArt uses its own PixArtLoraLoader (different wiring + DiT-specific
        # rank handling). Skip the generic LoRA injection path until we wire
        # PixArt LoRAs explicitly — otherwise workflow["6"]["inputs"]["clip"]
        # would KeyError since PixArt replaces CLIPTextEncode with T5 encoders.
        # Klein has workflow["3"] deleted (SamplerCustomAdvanced path) so
        # model_source = workflow["3"]["inputs"]["model"] below would also
        # KeyError. Flux.2-klein LoRAs would need a Flux2-specific loader
        # anyway — we don't support that yet.
        if lora_name and (is_pixart or is_klein):
            lora_name = ""
        if lora_name:
            # Pick the right loader: GGUF models need LoraLoaderModelOnly,
            # standard checkpoints use LoraLoader (which also modifies CLIP)
            model_source = workflow["3"]["inputs"]["model"]  # current model ref
            clip_source = workflow["6"]["inputs"]["clip"]    # current clip ref
            if is_gguf:
                # GGUF UNets don't work with standard LoraLoader — use
                # LoraLoaderModelOnly which patches the model without
                # needing a compatible CLIP output
                workflow["20"] = {
                    "class_type": "LoraLoaderModelOnly",
                    "inputs": {
                        "lora_name": lora_name,
                        "strength_model": lora_strength_model,
                        "model": model_source,
                    },
                }
                # Only rewire the model — CLIP stays on the original source
                workflow["3"]["inputs"]["model"] = ["20", 0]
            else:
                workflow["20"] = {
                    "class_type": "LoraLoader",
                    "inputs": {
                        "lora_name": lora_name,
                        "strength_model": lora_strength_model,
                        "strength_clip": lora_strength_clip,
                        "model": model_source,
                        "clip": clip_source,
                    },
                }
                # Rewire KSampler and CLIP encoders to use LoRA-modified outputs
                workflow["3"]["inputs"]["model"] = ["20", 0]
                workflow["6"]["inputs"]["clip"] = ["20", 1]
                workflow["7"]["inputs"]["clip"] = ["20", 1]

        workflow["5"]["inputs"]["width"] = params.get("width", 1024)
        workflow["5"]["inputs"]["height"] = params.get("height", 1024)
        workflow["6"]["inputs"]["text"] = params["prompt"]
        workflow["7"]["inputs"]["text"] = params.get("negative_prompt", "")
        # Klein uses SamplerCustomAdvanced (node 27) — KSampler (node 3) was
        # deleted in its branch. All the setters below target node 3 and
        # would KeyError if run against klein. Klein's steps/guidance/seed
        # are resolved inside its branch via Flux2Scheduler, FluxGuidance,
        # and RandomNoise respectively.
        if not is_klein:
            # Lightning needs exactly 4 steps — its branch has already set
            # that. A user slider at 20/25/30 would undo the distillation
            # invariant and produce dark, under-denoised output.
            if not is_lightning:
                workflow["3"]["inputs"]["steps"] = params.get("steps", 30)
            # Distilled models (Flux-dev, Schnell, SDXL Lightning) require
            # KSampler.cfg=1.0 and have already set it correctly above. The
            # user-facing cfg_scale is routed through FluxGuidance for Flux,
            # or simply ignored for Schnell/Lightning. Don't clobber the
            # invariant here.
            if not is_flux and not is_lightning:
                workflow["3"]["inputs"]["cfg"] = params.get("cfg_scale", 7.0)
            # Apply resolved sampler/scheduler from model defaults
            if "_sampler" in params:
                workflow["3"]["inputs"]["sampler_name"] = params["_sampler"]
            if "_scheduler" in params:
                workflow["3"]["inputs"]["scheduler"] = params["_scheduler"]
            seed = params.get("seed", -1)
            if seed == -1:
                import random
                seed = random.randint(0, 2**32 - 1)
            workflow["3"]["inputs"]["seed"] = seed

        # Add IP-Adapter nodes if reference images provided
        ref_images = params.get("reference_images", [])
        if ref_images and params.get("ip_adapter_model"):
            # Copy ref images to ComfyUI input dir (LoadImage only reads from there)
            import shutil
            comfy_input = Path(self.url.replace("http://", "").replace("https://", "").split(":")[0])  # won't work
            # Use config or derive from known path
            comfy_input_dir = Path("/home/phill/ComfyUI/input")
            copied_refs = []
            for rp in ref_images:
                src = Path(rp)
                if src.exists():
                    dest = comfy_input_dir / src.name
                    shutil.copy2(src, dest)
                    copied_refs.append(src.name)  # just filename, ComfyUI resolves from its input dir
            if copied_refs:
                workflow = self._add_ip_adapter(workflow, copied_refs, params)
        elif ref_images:
            logger.warning(
                "IP-Adapter: %d reference image(s) attached but ip_adapter_model is empty — "
                "refs will be ignored and the model will run text-only.",
                len(ref_images),
            )

        await on_progress(5, "Submitting to ComfyUI...")

        async with aiohttp.ClientSession() as session:
            # Submit prompt
            payload = {"prompt": workflow, "client_id": client_id}
            async with session.post(prompt_api, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    try:
                        err = json.loads(text)
                        msgs = []
                        if err.get("error", {}).get("message"):
                            msgs.append(err["error"]["message"])
                        for nid, nerr in err.get("node_errors", {}).items():
                            for e in nerr.get("errors", []):
                                msgs.append(e.get("message", ""))
                        raise RuntimeError("; ".join(msgs) or f"ComfyUI error {resp.status}")
                    except (json.JSONDecodeError, KeyError):
                        raise RuntimeError(f"ComfyUI error: {text[:300]}")
                result = await resp.json()
                prompt_id = result["prompt_id"]

            await on_progress(10, "Queued, waiting for generation...")

            # Poll via WebSocket for progress
            try:
                async with session.ws_connect(f"{ws_url}?clientId={client_id}") as ws:
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("type") == "progress":
                                d = data["data"]
                                pct = int(10 + (d["value"] / d["max"]) * 80)
                                await on_progress(pct, f"Step {d['value']}/{d['max']}")
                            elif data.get("type") == "executed":
                                if data["data"].get("prompt_id") == prompt_id:
                                    break
                            elif data.get("type") == "execution_error":
                                raise RuntimeError(f"ComfyUI execution error: {data['data']}")
            except aiohttp.ClientError:
                # Fallback: poll history
                await self._poll_history(session, url, prompt_id, on_progress)

            await on_progress(90, "Downloading result...")

            # Get output image from history
            async with session.get(f"{url}/history/{prompt_id}") as resp:
                history = await resp.json()

            outputs = history[prompt_id]["outputs"]
            # Find the SaveImage node output
            for node_output in outputs.values():
                if "images" in node_output:
                    img_info = node_output["images"][0]
                    img_url = f"{url}/view?filename={img_info['filename']}&subfolder={img_info.get('subfolder', '')}&type={img_info['type']}"
                    async with session.get(img_url) as resp:
                        img_data = await resp.read()
                    with open(output_path, "wb") as f:
                        f.write(img_data)
                    await on_progress(100, "Done")
                    return

            raise RuntimeError("No image output found in ComfyUI result")

    @staticmethod
    def _prepare_ref_image(src: Path, output_dir: Path) -> str:
        """Pre-process a reference image for CLIP Vision / IP-Adapter.

        Handles edge cases that produce zero signal:
        - Transparent backgrounds → composite onto white
        - Monochrome black logos → invert to white-on-dark for color signal
        - Crops to content bounds to maximise signal-to-noise
        """
        from PIL import Image
        import numpy as np

        img = Image.open(src).convert("RGBA")
        arr = np.array(img)

        # Analyze: how much is transparent? how much color vs black?
        alpha = arr[:, :, 3]
        opaque_mask = alpha > 0
        opaque_count = int(np.sum(opaque_mask))
        total = arr.shape[0] * arr.shape[1]

        needs_fix = False

        composite = None

        if opaque_count > 0:
            opaque_pixels = arr[opaque_mask][:, :3]
            mean_rgb = opaque_pixels.mean(axis=0)
            luminance = mean_rgb[0] * 0.299 + mean_rgb[1] * 0.587 + mean_rgb[2] * 0.114
            is_dark = luminance < 30
            mostly_transparent = (total - opaque_count) / total > 0.4

            if is_dark and mostly_transparent:
                # Dark logo on transparent = invisible to CLIP Vision.
                # Composite onto contrasting background so CLIP sees the shape.
                logger.info("IP-Adapter prep: dark logo on transparent — light background (lum=%.0f)", luminance)
                bg = Image.new("RGBA", img.size, (200, 220, 240, 255))
                composite = Image.alpha_composite(bg, Image.fromarray(arr, "RGBA")).convert("RGB")

        # Any remaining transparency → composite onto white
        if composite is None and np.any(alpha < 255):
            logger.info("IP-Adapter prep: compositing onto white background")
            bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
            composite = Image.alpha_composite(bg, Image.fromarray(arr, "RGBA")).convert("RGB")

        if composite is None:
            composite = Image.fromarray(arr[:, :, :3], "RGB")

        # Crop to content bounds (add 10% padding)
        if opaque_count > 0 and opaque_count < total * 0.9:
            rows = np.any(opaque_mask, axis=1)
            cols = np.any(opaque_mask, axis=0)
            rmin, rmax = int(np.argmax(rows)), int(arr.shape[0] - np.argmax(rows[::-1]))
            cmin, cmax = int(np.argmax(cols)), int(arr.shape[1] - np.argmax(cols[::-1]))
            # Add 10% padding
            pad_h = max(1, int((rmax - rmin) * 0.1))
            pad_w = max(1, int((cmax - cmin) * 0.1))
            rmin = max(0, rmin - pad_h)
            rmax = min(arr.shape[0], rmax + pad_h)
            cmin = max(0, cmin - pad_w)
            cmax = min(arr.shape[1], cmax + pad_w)
            composite = composite.crop((cmin, rmin, cmax, rmax))
            logger.info("IP-Adapter prep: cropped to content %dx%d", composite.width, composite.height)

        out_name = f"ipref_{src.stem}.png"
        composite.save(output_dir / out_name, "PNG")
        return out_name

    def _add_ip_adapter(self, workflow, ref_images, params):
        """Inject IP-Adapter nodes for reference image conditioning.

        weight_type controls how the reference image influences generation:
          - "style transfer"  — colors, texture, mood (no shape forcing)
          - "composition"     — structural layout and shapes
          - "linear"          — balanced linear blend
          - "standard"        — general purpose
          - "style and composition" — both aspects

        start_at / end_at control which denoising steps are influenced:
          - Early steps (0.0-0.4) decide composition/layout
          - Mid steps (0.3-0.7) decide style and colour
          - Late steps (0.6-1.0) decide fine detail
        """
        strength = params.get("ip_adapter_strength", 0.75)
        weight_type = params.get("ip_adapter_weight_type", "style transfer")
        start_at = float(params.get("ip_adapter_start", 0.0))
        end_at = float(params.get("ip_adapter_end", 0.8))
        ip_model = params.get("ip_adapter_model", "")

        # Determine preset from model name
        preset = "PLUS (high strength)"
        if "sd15" in ip_model.lower():
            preset = "STANDARD (medium strength)"

        # Load reference images — each gets its own LoadImage node
        # Node IDs: 10, 110, 111, 112, ... for images 0, 1, 2, 3, ...
        img_node_ids = []
        for i, ref in enumerate(ref_images):
            nid = "10" if i == 0 else str(110 + i - 1)
            workflow[nid] = {
                "class_type": "LoadImage",
                "inputs": {"image": ref},
            }
            img_node_ids.append(nid)

        # Batch multiple images together if more than one reference
        if len(img_node_ids) > 1:
            # Chain ImageBatch nodes: batch(img0, img1) -> batch(result, img2) -> ...
            prev = [img_node_ids[0], 0]
            for i in range(1, len(img_node_ids)):
                batch_nid = str(120 + i - 1)
                workflow[batch_nid] = {
                    "class_type": "ImageBatch",
                    "inputs": {
                        "image1": prev,
                        "image2": [img_node_ids[i], 0],
                    },
                }
                prev = [batch_nid, 0]
            image_source = prev
        else:
            image_source = [img_node_ids[0], 0]

        # Unified loader — auto-selects correct IP-Adapter + CLIP Vision
        model_source = workflow["3"]["inputs"]["model"]
        workflow["11"] = {
            "class_type": "IPAdapterUnifiedLoader",
            "inputs": {
                "model": model_source,
                "preset": preset,
            },
        }
        # Apply IP-Adapter with batched images.
        # `embeds_scaling` and `encode_batch_size` are required by
        # IPAdapterBatch (see ComfyUI_IPAdapter_plus/IPAdapterPlus.py
        # IPAdapterBatch.INPUT_TYPES). Omitting either triggers ComfyUI's
        # "Required input is missing" validation failure.
        workflow["13"] = {
            "class_type": "IPAdapterBatch",
            "inputs": {
                "model": ["11", 0],
                "ipadapter": ["11", 1],
                "image": image_source,
                "weight": strength,
                "start_at": start_at,
                "end_at": end_at,
                "weight_type": weight_type,
                "embeds_scaling": "V only",
                "encode_batch_size": 0,
            },
        }
        # Rewire KSampler to use IP-Adapter model output
        workflow["3"]["inputs"]["model"] = ["13", 0]

        return workflow

    def _build_remix_workflow(self, params: dict) -> dict:
        """Build an img2img + IPAdapter workflow for Style Remix.

        Mirrors generate() but uses BASIC_IMG2IMG as the base. SDXL-only
        for v1 (no GGUF / Flux / PixArt / Klein paths).

        `params` must already be resolved - filenames refer to files
        already copied into the ComfyUI input directory.
        """
        import json as _json

        workflow = _json.loads(_json.dumps(BASIC_IMG2IMG))

        workflow["1"]["inputs"]["image"] = params["base_filename"]

        model_name = params.get("model", "")
        if model_name:
            workflow["4"]["inputs"]["ckpt_name"] = model_name

        workflow["3"]["inputs"]["seed"] = int(params["seed"])
        workflow["3"]["inputs"]["steps"] = int(params["steps"])
        workflow["3"]["inputs"]["cfg"] = float(params["cfg"])
        preserve = float(params["preserve_character"])
        workflow["3"]["inputs"]["denoise"] = round(1.0 - preserve, 4)

        workflow["6"]["inputs"]["text"] = params.get("hint", "") or ""
        workflow["7"]["inputs"]["text"] = params.get("negative_prompt", "") or ""

        lora_name = params.get("lora_model", "")
        if lora_name:
            lora_strength = float(params.get("lora_strength", 0.55))
            lora_strength_clip = float(params.get("lora_strength_clip", lora_strength * 0.6))
            model_source = workflow["3"]["inputs"]["model"]
            clip_source = workflow["6"]["inputs"]["clip"]
            workflow["20"] = {
                "class_type": "LoraLoader",
                "inputs": {
                    "lora_name": lora_name,
                    "strength_model": lora_strength,
                    "strength_clip": lora_strength_clip,
                    "model": model_source,
                    "clip": clip_source,
                },
            }
            workflow["3"]["inputs"]["model"] = ["20", 0]
            workflow["6"]["inputs"]["clip"] = ["20", 1]
            workflow["7"]["inputs"]["clip"] = ["20", 1]

        style_filename = params.get("style_ref_filename", "")
        if style_filename:
            ip_params = {
                "ip_adapter_model": params.get("ip_adapter_model", "sdxl_models/ip-adapter_sdxl_vit-h.safetensors"),
                "ip_adapter_strength": float(params.get("style_strength", 0.75)),
                "ip_adapter_weight_type": params.get("blend_mode", "style transfer"),
                "ip_adapter_start": float(params.get("ip_start", 0.0)),
                "ip_adapter_end": float(params.get("ip_end", 0.8)),
            }
            workflow = self._add_ip_adapter(workflow, [style_filename], ip_params)

        return workflow

    async def generate_remix(self, params: dict, output_path: str, on_progress) -> dict:
        """Run a single remix job through ComfyUI.

        `params` keys (server.py resolves filenames before calling):
          base_filename, style_ref_filename, model, lora_model, lora_strength,
          preserve_character, style_strength, ip_start, ip_end, blend_mode,
          steps, cfg, seed, hint, width, height.
        """
        import aiohttp

        workflow = self._build_remix_workflow(params)

        url = self.url.rstrip("/")
        client_id = str(uuid.uuid4())

        await on_progress(5, "Submitting to ComfyUI...")

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{url}/prompt",
                                    json={"prompt": workflow, "client_id": client_id}) as resp:
                resp.raise_for_status()
                submit_resp = await resp.json()
                if "error" in submit_resp:
                    err = submit_resp.get("error")
                    node_errors = submit_resp.get("node_errors", {})
                    raise RuntimeError(f"ComfyUI rejected workflow: {err} {node_errors}")
                prompt_id = submit_resp["prompt_id"]

            for i in range(300):
                await asyncio.sleep(1)
                async with session.get(f"{url}/history/{prompt_id}") as resp:
                    history = await resp.json()
                if prompt_id in history:
                    break
                if i % 5 == 0:
                    await on_progress(min(10 + i, 85), "Remixing...")
            else:
                raise RuntimeError("ComfyUI remix timed out")

            record = history[prompt_id]
            outputs = record.get("outputs", {})
            save_node = outputs.get("9", {})
            images = save_node.get("images", [])
            if not images:
                raise RuntimeError("ComfyUI finished but produced no images")
            img = images[0]
            filename = img["filename"]
            subfolder = img.get("subfolder", "")
            view_url = f"{url}/view"
            qs = {"filename": filename, "subfolder": subfolder, "type": img.get("type", "output")}
            async with session.get(view_url, params=qs) as resp:
                resp.raise_for_status()
                image_bytes = await resp.read()

        # Atlas-SAM re-texture path: when the caller supplied a mask,
        # composite the generated atlas back into the original base
        # atlas so unmasked regions stay byte-stable. The base + mask
        # both live in ComfyUI's input dir (server.py copied them).
        mask_filename = params.get("mask_filename")
        if mask_filename:
            from PIL import Image as _PIL
            from texture_io import composite_with_mask
            comfy_input_dir = Path("/home/phill/ComfyUI/input")
            with _PIL.open(comfy_input_dir / params["base_filename"]) as base_img, \
                 _PIL.open(comfy_input_dir / mask_filename) as mask_img, \
                 _PIL.open(io.BytesIO(image_bytes)) as gen_img:
                composited = composite_with_mask(gen_img, base_img, mask_img)
                composited.save(output_path, format="PNG")
        else:
            with open(output_path, "wb") as f:
                f.write(image_bytes)

        await on_progress(100, "Done")
        return {"filename": Path(output_path).name}

    async def generate_3d(self, params: dict, output_path: str, on_progress) -> dict:
        """Generate a 3D mesh (.glb) via Hunyuan3D image-to-3D.

        Required params:
            reference_images: list[str] — at least one path; the first is used.
            model: str — Hy3D DiT filename in ComfyUI/models/diffusion_models
                   (e.g. "hy3dgen/hunyuan3d-dit-v2-0-fp16.safetensors").
            mode_3d: "shape" or "pbr" (default "shape").
            seed: int (default 0)
        Optional:
            paint_model, delight_model, octree, max_facenum, cfg_scale, steps.

        Output: writes a .glb to ``output_path``. Returns dict with filename.
        """
        import shutil
        from glob import glob

        ref_images = params.get("reference_images") or []
        if not ref_images:
            raise RuntimeError(
                "3D generation requires a reference image. "
                "Hy3D is image-conditioned — generate or upload an image first."
            )

        url = self.url
        ws_url = url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
        client_id = str(uuid.uuid4())
        prompt_api = f"{url}/prompt"

        # Copy ALL provided refs into ComfyUI's input dir, keyed by view slot.
        # Slot order matches the multi-view convention: 0=front, 1=back, 2=left, 3=right.
        # Each ref runs through the Hy3D preprocess (rembg + recenter+pad) so
        # the wrapper sees alpha-cut, properly-framed subjects regardless of
        # what the user uploads. PNG output keeps the alpha channel intact.
        comfy_input = Path("/home/phill/ComfyUI/input")
        VIEW_NAMES = ["front", "back", "left", "right"]
        view_filenames = {}
        for slot_idx, ref_path in enumerate(ref_images[:4]):
            if not ref_path:
                continue
            src = Path(ref_path)
            if not src.exists():
                raise RuntimeError(f"Reference image not found: {src}")
            view_name = VIEW_NAMES[slot_idx]
            v_name = f"hy3d_{client_id[:8]}_{view_name}.png"
            dst = comfy_input / v_name
            preprocessed = preprocess_hy3d_image(str(src), str(dst))
            if not preprocessed:
                shutil.copy2(src, dst)
            view_filenames[view_name] = v_name
        # Backward-compat alias for single-view path.
        ref_name = view_filenames.get("front") or list(view_filenames.values())[0]

        mode = params.get("mode_3d", "shape")
        # Use a per-job unique prefix so we can find the saved .glb on disk
        # without parsing ComfyUI's history. Subfolder "3D" keeps outputs tidy.
        file_prefix = f"3D/wyltek-3d_{client_id[:8]}"

        model_name = params.get("model", "")
        if not model_name:
            raise RuntimeError("3D generation: 'model' param required (Hy3D DiT filename)")

        # 2D side uses seed=-1 to mean "random", but Hy3DGenerateMesh /
        # Hy3DDelightImage declare seed with min=0 — passing -1 fails
        # validation on every Hy3D node that touches it. Normalize here.
        import random
        raw_seed = int(params.get("seed", 0) or 0)
        if raw_seed < 0:
            raw_seed = random.randint(0, 2**31 - 1)

        # Multi-view dispatch: 2+ slots filled → Hy3DGenerateMeshMultiView,
        # works for both shape and PBR modes. PBR multi-view uses the same
        # paint chain as single-view but feeds in the multi-view-derived mesh.
        # Camera rig overrides — empty string from UI means "use defaults".
        # Both builders default to the official Tencent 6-view rig.
        cam_az = (params.get("hy3d_cam_azimuths") or "").strip() or "0, 90, 180, 270, 0, 180"
        cam_el = (params.get("hy3d_cam_elevations") or "").strip() or "0, 0, 0, 0, 90, -90"

        is_multiview = len(view_filenames) >= 2
        if is_multiview:
            workflow = build_hy3d_multiview_workflow(
                model=model_name,
                view_filenames=view_filenames,
                mode=mode,
                seed=raw_seed,
                cfg=float(params.get("cfg_scale", 5.5) or 5.5),
                steps=int(params.get("steps", 30) or 30),
                paint_model=params.get("paint_model", "hunyuan3d-paint-v2-0"),
                delight_model=params.get("delight_model", "hunyuan3d-delight-v2-0"),
                file_prefix=file_prefix,
                octree=int(params.get("octree", 384) or 384),
                max_facenum=int(params.get("max_facenum", 50000) or 50000),
                cam_azimuths=cam_az,
                cam_elevations=cam_el,
            )
        else:
            workflow = build_3d_workflow(
                model=model_name,
                image_filename=ref_name,
                mode=mode,
                seed=raw_seed,
                cfg=float(params.get("cfg_scale", 5.5) or 5.5),
                steps=int(params.get("steps", 50) or 50),
                paint_model=params.get("paint_model", "hunyuan3d-paint-v2-0"),
                delight_model=params.get("delight_model", "hunyuan3d-delight-v2-0"),
                file_prefix=file_prefix,
                octree=int(params.get("octree", 384) or 384),
                max_facenum=int(params.get("max_facenum", 50000) or 50000),
                cam_azimuths=cam_az,
                cam_elevations=cam_el,
            )

        view_count = len(view_filenames)
        view_label = f"{view_count}-view multi" if is_multiview else "single-view"
        await on_progress(5, f"Submitting Hy3D {view_label} workflow ({mode})...")

        # PBR pipeline can take several minutes; shape ~30s. Use a generous
        # cap and rely on WebSocket events to track progress when available.
        # Honour server.py's resolved per-mode inner timeout when present;
        # fall back to the legacy values for tests / direct callers.
        timeout_s = int(params.get("_inner_timeout_s") or (2100 if mode == "pbr" else 300))

        async with aiohttp.ClientSession() as session:
            payload = {"prompt": workflow, "client_id": client_id}
            async with session.post(prompt_api, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    try:
                        err = json.loads(text)
                        msgs = []
                        if err.get("error", {}).get("message"):
                            msgs.append(err["error"]["message"])
                        for _, nerr in err.get("node_errors", {}).items():
                            for e in nerr.get("errors", []):
                                msgs.append(e.get("message", ""))
                        raise RuntimeError("; ".join(m for m in msgs if m) or f"ComfyUI error {resp.status}")
                    except (json.JSONDecodeError, KeyError):
                        raise RuntimeError(f"ComfyUI error: {text[:300]}")
                result = await resp.json()
                prompt_id = result["prompt_id"]

            await on_progress(8, "Queued — Hy3D loading model...")

            rescued_meta: dict | None = None
            try:
                try:
                    async with session.ws_connect(f"{ws_url}?clientId={client_id}", timeout=30) as ws:
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                mtype = data.get("type")
                                if mtype == "progress":
                                    d = data["data"]
                                    # Hy3D step counts vary: shape uses ~50, paint uses ~25.
                                    # Map to 10-85% so download has room.
                                    pct = int(10 + (d.get("value", 0) / max(d.get("max", 1), 1)) * 75)
                                    await on_progress(pct, f"Hy3D step {d.get('value')}/{d.get('max')}")
                                elif mtype == "execution_success" and data["data"].get("prompt_id") == prompt_id:
                                    # ComfyUI 0.18+ emits this as the workflow-end event.
                                    break
                                elif mtype == "executing":
                                    node = data["data"].get("node")
                                    if node is None and data["data"].get("prompt_id") == prompt_id:
                                        break  # legacy/null-node end event
                                    if node:
                                        label = workflow.get(node, {}).get("class_type", node)
                                        await on_progress(None, f"Hy3D: {label}")
                                elif mtype == "execution_error":
                                    raise RuntimeError(f"ComfyUI execution error: {data['data']}")
                except aiohttp.ClientError:
                    # WS hiccup — fall back to history polling with the inner timeout.
                    await self._poll_history_long(session, url, prompt_id, on_progress, timeout_s)
            except (asyncio.CancelledError, RuntimeError) as e:
                # Outer asyncio.wait_for cancelled OR inner poll/exec raised.
                # Try to rescue any GLB ComfyUI may have written before/after.
                # Shield so the rescue completes even if outer is cancelling us.
                rescued_meta = await asyncio.shield(
                    _rescue_orphan_glb(file_prefix, output_path)
                )
                if rescued_meta:
                    await on_progress(95, "Hy3D finished late; rescued .glb")
                else:
                    raise

            if rescued_meta:
                # Rescue already copied the .glb to output_path; skip locate+copy.
                await on_progress(100, "Done (rescued)")
                return {
                    "filename": Path(output_path).name,
                    "format": "glb",
                    "mode": mode,
                    **rescued_meta,
                }

            await on_progress(90, "Locating .glb output...")

            # Hy3DExportMesh returns relative_path under outputs[node]['glb_path'],
            # but the structure is wrapper-version dependent. We use the unique
            # filename_prefix to glob the output dir directly — robust either way.
            comfy_output_dir = Path("/home/phill/ComfyUI/output")
            pattern = str(comfy_output_dir / f"{file_prefix}*_.glb")
            # PBR pipeline writes both untextured (file_prefix_*.glb) and
            # textured (file_prefix_textured_*.glb). Prefer textured.
            matches = sorted(glob(pattern))
            textured = [m for m in matches if "_textured_" in m]
            chosen = textured[-1] if textured else (matches[-1] if matches else None)
            if not chosen:
                raise RuntimeError(
                    f"Hy3D finished but no .glb produced at {pattern}. "
                    "Check ComfyUI logs for an error."
                )

            shutil.copy2(chosen, output_path)

        await on_progress(100, "Done")
        result = {"filename": Path(output_path).name, "format": "glb", "mode": mode}
        if rescued_meta:
            result.update(rescued_meta)
        return result

    async def generate_trellis(self, params: dict, output_path: str, on_progress) -> dict:
        """Generate a 3D mesh (.glb) via TRELLIS 2 image-to-3D.

        Mirrors the generate_3d (Hy3D) contract — same image-conditioned input,
        same output_path semantics — so the upstream `_run_job` dispatcher can
        treat the two engines symmetrically.

        Required params:
            reference_images: list[str], at least one.
            mode_3d: "shape" or "textured" (default "shape").
        Optional:
            trellis_format: e.g. "GGUF Q8_0" (default), "Safetensors (BF16)" etc.
            trellis_pipeline_type: "512" | "1024" | "1024_cascade".
            seed, max_facenum.
        """
        import shutil
        from glob import glob

        ref_images = params.get("reference_images") or []
        if not ref_images:
            raise RuntimeError(
                "TRELLIS generation requires a reference image — image-conditioned only."
            )

        url = self.url
        ws_url = url.replace("http://", "ws://").replace("https://", "wss://") + "/ws"
        client_id = str(uuid.uuid4())
        prompt_api = f"{url}/prompt"

        # Copy each provided reference image into ComfyUI's input dir under a
        # unique per-job filename. Slot order is meaningful for multi-view:
        # 0=front (required), 1=back, 2=left, 3=right.
        comfy_input = Path("/home/phill/ComfyUI/input")
        VIEW_NAMES = ["front", "back", "left", "right"]
        view_filenames = {}        # view_name -> uploaded filename in input/
        per_view_needs_bg = {}     # view_name -> True if RGB (no alpha)
        for slot_idx, ref_path in enumerate(ref_images[:4]):
            if not ref_path:
                continue
            src = Path(ref_path)
            if not src.exists():
                raise RuntimeError(f"Reference image not found: {src}")
            view_name = VIEW_NAMES[slot_idx]
            ref_name = f"trellis_{client_id[:8]}_{view_name}{src.suffix or '.png'}"
            shutil.copy2(src, comfy_input / ref_name)
            view_filenames[view_name] = ref_name
            # Per-view alpha probe — RGB inputs MUST go through rembg or
            # Trellis2PreProcessImage_GGUF crashes with "index 3 out of
            # bounds" when it tries to read a missing alpha channel. We
            # detect server-side and override the user's auto_bg_removal
            # toggle to True for those views only.
            try:
                from PIL import Image
                with Image.open(src) as im:
                    has_alpha = (im.mode in ("RGBA", "LA", "PA")) or (
                        "transparency" in im.info
                    )
                    per_view_needs_bg[view_name] = not has_alpha
            except Exception:
                # If PIL can't open it, leave to the user's setting and let
                # the workflow surface the error.
                pass
        # Backward-compat alias for single-view path below.
        ref_name = view_filenames.get("front") or list(view_filenames.values())[0]

        # 2D's seed=-1 ("random") is a UI convention — TRELLIS nodes also reject
        # negatives. Normalize the same way generate_3d does for consistency.
        import random
        raw_seed = int(params.get("seed", 0) or 0)
        if raw_seed < 0:
            raw_seed = random.randint(0, 2**31 - 1)

        # Map UI mode names to TRELLIS pipeline names. Hy3D uses (shape, pbr);
        # we expose (shape, textured) to TRELLIS to mirror the example file names.
        mode_3d = params.get("mode_3d", "shape")
        trellis_mode = "textured" if mode_3d in ("pbr", "textured") else "shape"

        file_prefix = f"3D/wyltek-trellis_{client_id[:8]}"
        # Pick single-view vs multi-view based on how many slots are filled.
        # A single front view → single-view DiT (faster, established path).
        # 2+ views → multi-view DiT, which uses the actual back/left/right
        # pixel data instead of inferring it from the prior. Multi-view
        # produces materially better samples for asymmetric subjects.
        # Resolve quality preset + tweak toggles into a flat overrides dict
        # that both single-view and multi-view builders can apply uniformly.
        quality_overrides = _resolve_trellis_quality_params(
            preset=params.get("trellis_preset", "balanced"),
            tweak_faithful=bool(params.get("trellis_tweak_faithful", False)),
            tweak_fine_detail=bool(params.get("trellis_tweak_fine_detail", False)),
            tweak_sharp_edges=bool(params.get("trellis_tweak_sharp_edges", False)),
        )

        is_multiview = len(view_filenames) >= 2
        if is_multiview:
            # If the user disabled auto-bg-removal but supplied any RGB
            # views, override per-view to True so PreProcess doesn't crash.
            global_bg = bool(params.get("auto_bg_removal", True))
            per_view_override = {
                v: True if needs_bg else global_bg
                for v, needs_bg in per_view_needs_bg.items()
            }
            workflow = build_trellis_multiview_workflow(
                view_filenames=view_filenames,
                mode=trellis_mode,
                model_format=params.get("trellis_format", "GGUF Q8_0"),
                seed=raw_seed,
                file_prefix=file_prefix,
                pipeline_type=params.get("trellis_pipeline_type", "512"),
                target_face_num=int(params.get("max_facenum", 50000) or 50000),
                auto_bg_removal=global_bg,
                auto_bg_removal_per_view=per_view_override,
                quality_overrides=quality_overrides,
            )
        else:
            workflow = build_trellis_workflow(
                image_filename=ref_name,
                mode=trellis_mode,
                model_format=params.get("trellis_format", "GGUF Q8_0"),
                seed=raw_seed,
                file_prefix=file_prefix,
                pipeline_type=params.get("trellis_pipeline_type", "512"),
                target_face_num=int(params.get("max_facenum", 50000) or 50000),
                auto_bg_removal=bool(params.get("auto_bg_removal", True)),
                quality_overrides=quality_overrides,
            )

        view_count = len(view_filenames)
        view_label = f"{view_count}-view multi" if view_count >= 2 else "single-view"
        await on_progress(5, f"Submitting TRELLIS {view_label} workflow ({trellis_mode})...")

        # Textured pipeline runs the paint diffusion model, which is slow.
        # First-ever run also auto-downloads the 4B weights (~3-8GB depending
        # on quant) — that download has no progress event, so the timeout
        # has to swallow it.
        # Honour server.py's resolved per-mode inner timeout when present;
        # fall back to the legacy values for tests / direct callers.
        timeout_s = int(params.get("_inner_timeout_s") or (3000 if trellis_mode == "textured" else 600))

        async with aiohttp.ClientSession() as session:
            payload = {"prompt": workflow, "client_id": client_id}
            async with session.post(prompt_api, json=payload) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    try:
                        err = json.loads(text)
                        msgs = []
                        if err.get("error", {}).get("message"):
                            msgs.append(err["error"]["message"])
                        for _, nerr in err.get("node_errors", {}).items():
                            for e in nerr.get("errors", []):
                                msgs.append(e.get("message", ""))
                        raise RuntimeError("; ".join(m for m in msgs if m) or f"ComfyUI error {resp.status}")
                    except (json.JSONDecodeError, KeyError):
                        raise RuntimeError(f"ComfyUI error: {text[:300]}")
                result = await resp.json()
                prompt_id = result["prompt_id"]

            await on_progress(8, "Queued — TRELLIS loading model (first run downloads weights)...")

            # Find the LoadModel node ID once so we can detect when execution
            # enters it and start a download ticker. Subsequent nodes get
            # generic step-progress events; only the LoadModel step is silent
            # for ~5-10min during the first-ever HF download.
            load_node_id = next(
                (nid for nid, n in workflow.items() if n.get("class_type") == "Trellis2LoadModel_GGUF"),
                None,
            )
            # The egore wrapper has its own model_manager (not HF cache) — it
            # pulls weights from Aero-Ex/Trellis2-GGUF directly into
            # ComfyUI/models/Trellis2/ via hf_hub_download(local_dir=...).
            hf_trellis_dir = Path.home() / "ComfyUI/models/Trellis2"

            def hf_dir_size_mb() -> int:
                """Return total bytes of the TRELLIS HF cache as MB (0 if absent)."""
                if not hf_trellis_dir.exists():
                    return 0
                total = 0
                try:
                    for f in hf_trellis_dir.rglob("*"):
                        if f.is_file():
                            total += f.stat().st_size
                except (OSError, PermissionError):
                    pass
                return total // (1024 * 1024)

            async def poll_hf_download():
                """Tick every 3s while LoadModel runs; surface MB downloaded
                so the user sees movement instead of a silent 5–10min wait."""
                # ~2.5GB for Q4_K_M, ~8GB for BF16. Hard to predict exact size
                # so we just show absolute progress without an ETA.
                while True:
                    try:
                        mb = hf_dir_size_mb()
                        if mb > 0:
                            await on_progress(None, f"Downloading TRELLIS weights: {mb} MB on disk")
                        else:
                            await on_progress(None, "Loading TRELLIS model (HF download starting...)")
                        await asyncio.sleep(3)
                    except asyncio.CancelledError:
                        return

            download_task = None

            # Per-step timing state for the DiT heartbeat. Slat-shape at 1024
            # res can run ~14s/step on ROCm, which leaves the WS quiet for
            # long stretches and reads as a hang. The heartbeat surfaces
            # avg-step + ETA between real progress events. Reset on every
            # node transition so SS-DiT step rate doesn't poison Slat-shape.
            step_state = {
                "last_t": None,    # monotonic ts of most recent progress event
                "durations": [],   # rolling window of step intervals
                "value": 0,
                "max": 1,
            }

            async def heartbeat():
                """Tick every 3s when the DiT has been silent >5s since its
                last step. Stays quiet during non-sampler nodes (no last_t)."""
                while True:
                    try:
                        await asyncio.sleep(3)
                        last_t = step_state["last_t"]
                        if last_t is None:
                            continue
                        elapsed = time.monotonic() - last_t
                        if elapsed < 5:
                            continue
                        durations = step_state["durations"]
                        avg = (sum(durations) / len(durations)) if durations else elapsed
                        value = step_state["value"]
                        mx = step_state["max"]
                        eta_s = max(0, mx - value) * avg
                        await on_progress(
                            None,
                            f"TRELLIS step {value}/{mx} — working "
                            f"(+{int(elapsed)}s, ~{avg:.1f}s/step, ETA {_fmt_eta(eta_s)})",
                        )
                    except asyncio.CancelledError:
                        return

            heartbeat_task = None

            rescued_meta: dict | None = None
            try:
                try:
                    async with session.ws_connect(f"{ws_url}?clientId={client_id}", timeout=30) as ws:
                        async for msg in ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                data = json.loads(msg.data)
                                mtype = data.get("type")
                                if mtype == "progress":
                                    d = data["data"]
                                    value = int(d.get("value", 0))
                                    mx = max(int(d.get("max", 1)), 1)
                                    pct = int(10 + (value / mx) * 75)
                                    now = time.monotonic()
                                    last_t = step_state["last_t"]
                                    if last_t is not None:
                                        step_state["durations"].append(now - last_t)
                                        if len(step_state["durations"]) > 10:
                                            step_state["durations"].pop(0)
                                    step_state["last_t"] = now
                                    step_state["value"] = value
                                    step_state["max"] = mx
                                    if heartbeat_task is None or heartbeat_task.done():
                                        heartbeat_task = asyncio.create_task(heartbeat())
                                    await on_progress(pct, f"TRELLIS step {value}/{mx}")
                                elif mtype == "executing":
                                    node = data["data"].get("node")
                                    if node is None and data["data"].get("prompt_id") == prompt_id:
                                        break
                                    # When LoadModel starts, kick the HF download ticker.
                                    # When any OTHER node starts, kill it — that means
                                    # the model finished loading and execution moved on.
                                    if node == load_node_id and download_task is None:
                                        download_task = asyncio.create_task(poll_hf_download())
                                    elif node and node != load_node_id and download_task is not None:
                                        download_task.cancel()
                                        download_task = None
                                    # Reset per-step timing on every node transition.
                                    # Heartbeat task itself stays alive but goes quiet
                                    # (last_t=None) until the next progress event.
                                    if node:
                                        step_state["last_t"] = None
                                        step_state["durations"] = []
                                        label = workflow.get(node, {}).get("class_type", node)
                                        # Strip the GGUF suffix from progress labels — feels less noisy.
                                        label = label.replace("Trellis2", "").replace("_GGUF", "")
                                        await on_progress(None, f"TRELLIS: {label}")
                                elif mtype == "execution_error":
                                    raise RuntimeError(f"ComfyUI execution error: {data['data']}")
                except aiohttp.ClientError:
                    await self._poll_history_long(session, url, prompt_id, on_progress, timeout_s)
                finally:
                    if download_task is not None:
                        download_task.cancel()
                    if heartbeat_task is not None:
                        heartbeat_task.cancel()
            except (asyncio.CancelledError, RuntimeError):
                # Outer asyncio.wait_for cancelled OR inner poll/exec raised.
                # Try to rescue any GLB ComfyUI may have written before/after.
                # Shield so the rescue completes even if outer is cancelling us.
                rescued_meta = await asyncio.shield(
                    _rescue_orphan_glb(file_prefix, output_path)
                )
                if rescued_meta:
                    await on_progress(95, "TRELLIS finished late; rescued .glb")
                else:
                    raise

            if rescued_meta:
                # Rescue already copied the .glb to output_path; skip locate+copy.
                await on_progress(100, "Done (rescued)")
                return {
                    "filename": Path(output_path).name,
                    "format": "glb",
                    "mode": trellis_mode,
                    "engine": "trellis",
                    **rescued_meta,
                }

            await on_progress(90, "Locating TRELLIS .glb...")

            # Same disk-scan trick as Hy3D — finding the textured output reliably
            # is easier via globbing the file_prefix than parsing the variable
            # output structure of Trellis2ExportMesh_GGUF across versions.
            comfy_output_dir = Path("/home/phill/ComfyUI/output")
            pattern = str(comfy_output_dir / f"{file_prefix}*_.glb")
            matches = sorted(glob(pattern))
            textured = [m for m in matches if "_textured_" in m]
            chosen = textured[-1] if textured else (matches[-1] if matches else None)
            if not chosen:
                raise RuntimeError(
                    f"TRELLIS finished but no .glb produced at {pattern}. "
                    "Check ComfyUI logs for an error."
                )

            shutil.copy2(chosen, output_path)

        await on_progress(100, "Done")
        return {
            "filename": Path(output_path).name,
            "format": "glb",
            "mode": trellis_mode,
            "engine": "trellis",
        }

    async def _poll_history_long(self, session, url, prompt_id, on_progress, timeout_s: int):
        """History-poll variant with caller-set timeout (for the slow PBR path)."""
        ticks = max(1, timeout_s)
        for i in range(ticks):
            await asyncio.sleep(1)
            async with session.get(f"{url}/history/{prompt_id}") as resp:
                history = await resp.json()
            if prompt_id in history:
                return
            if i % 10 == 0:
                pct = min(10 + int(75 * i / ticks), 85)
                await on_progress(pct, "Generating 3D mesh...")
        raise RuntimeError(f"Hy3D generation timed out after {timeout_s}s")

    async def _poll_history(self, session, url, prompt_id, on_progress):
        """Fallback polling when WebSocket unavailable."""
        for i in range(300):  # 5 min max
            await asyncio.sleep(1)
            async with session.get(f"{url}/history/{prompt_id}") as resp:
                history = await resp.json()
            if prompt_id in history:
                return
            if i % 5 == 0:
                await on_progress(min(10 + i, 85), "Generating...")
        raise RuntimeError("ComfyUI generation timed out")
