"""ComfyUI backend — most flexible local option."""

import asyncio
import base64
import json
import logging
import uuid
from pathlib import Path

import aiohttp

logger = logging.getLogger(__name__)

from backends.base import BaseBackend

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
    # NOTE: Flux Dev struggles with monochrome subjects on white backgrounds
    # (e.g. green frog). This is a Flux architecture limitation, not tunable
    # via CFG. Schnell handles these subjects fine. Keep CFG at 3.5 which
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
    # --- SD3 Medium (disabled/broken at Q4 but keep defaults if re-enabled) ---
    "sd3-medium-Q4_0.gguf": {
        "sampler": "dpmpp_2m", "scheduler": "sgm_uniform",
        "steps": 28, "cfg": 5.0,
    },
}


def _resolve_defaults(params: dict) -> dict:
    """Apply per-model optimal defaults. User-chosen values that differ from
    the generic UI defaults (steps=30, cfg=7.0, 1024x1024) are preserved;
    generic values get overridden by model-specific ones."""
    model = params.get("model", "")
    defaults = MODEL_DEFAULTS.get(model)
    if not defaults:
        return params

    params = dict(params)  # shallow copy so we don't mutate the original

    # These are the "generic" values the compare endpoint or UI sends when
    # the user hasn't deliberately changed them.  If we see these, replace
    # with the model's optimal settings.
    GENERIC = {"steps": {20, 25, 30}, "cfg_scale": {7.0}, "width": {1024}, "height": {1024}}

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
                "inputs": {"vae_name": "sdxl_vae.safetensors"},
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
        params = _resolve_defaults(params)

        url = self.url.rstrip("/")
        prompt_api = f"{url}/prompt"
        ws_url = url.replace("http", "ws") + "/ws"
        client_id = str(uuid.uuid4())

        model_name = params.get("model", "")
        is_gguf = model_name.endswith(".gguf")

        workflow = json.loads(json.dumps(BASIC_TXT2IMG))

        is_flux = is_gguf and "flux" in model_name.lower()
        is_sd3 = is_gguf and "sd3" in model_name.lower()

        if is_flux:
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
            workflow["3"]["inputs"]["model"] = ["4", 0]
            workflow["6"]["inputs"]["clip"] = ["14", 0]
            workflow["7"]["inputs"]["clip"] = ["14", 0]
            workflow["8"]["inputs"]["vae"] = ["15", 0]
            # Flux uses euler sampler, normal scheduler, low CFG
            workflow["3"]["inputs"]["sampler_name"] = "euler"
            workflow["3"]["inputs"]["scheduler"] = "simple"
            if is_schnell:
                workflow["3"]["inputs"]["steps"] = params.get("steps", 4)
                workflow["3"]["inputs"]["cfg"] = 1.0  # Schnell ignores CFG
            else:
                workflow["3"]["inputs"]["cfg"] = params.get("cfg_scale", 3.5)
        elif is_sd3:
            # SD3 uses 16-channel latent space — needs Flux VAE (also 16-ch), not SDXL VAE (4-ch)
            workflow["4"] = {
                "class_type": "UnetLoaderGGUF",
                "inputs": {"unet_name": model_name},
            }
            workflow["14"] = {
                "class_type": "DualCLIPLoader",
                "inputs": {
                    "clip_name1": "clip_l.safetensors",
                    "clip_name2": "clip_g.safetensors",
                    "type": "sd3",
                },
            }
            workflow["15"] = {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "ae.safetensors"},
            }
            workflow["3"]["inputs"]["model"] = ["4", 0]
            workflow["6"]["inputs"]["clip"] = ["14", 0]
            workflow["7"]["inputs"]["clip"] = ["14", 0]
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
                "inputs": {"vae_name": "sdxl_vae.safetensors"},
            }
            workflow["3"]["inputs"]["model"] = ["4", 0]
            workflow["6"]["inputs"]["clip"] = ["14", 0]
            workflow["7"]["inputs"]["clip"] = ["14", 0]
            workflow["8"]["inputs"]["vae"] = ["15", 0]
            workflow["3"]["inputs"]["sampler_name"] = "euler"
            workflow["3"]["inputs"]["scheduler"] = "sgm_uniform"
            workflow["3"]["inputs"]["cfg"] = 1.0
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
                "inputs": {"vae_name": "sdxl_vae.safetensors"},
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
        if lora_name:
            # LoraLoader sits between model/clip source and KSampler/CLIP encoders
            # Input: model + clip from loader → Output: modified model + clip
            model_source = workflow["3"]["inputs"]["model"]  # current model ref
            clip_source = workflow["6"]["inputs"]["clip"]    # current clip ref
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
        workflow["3"]["inputs"]["steps"] = params.get("steps", 30)
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

        # Load reference image
        workflow["10"] = {
            "class_type": "LoadImage",
            "inputs": {"image": ref_images[0]},
        }
        # Unified loader — auto-selects correct IP-Adapter + CLIP Vision
        model_source = workflow["3"]["inputs"]["model"]
        workflow["11"] = {
            "class_type": "IPAdapterUnifiedLoader",
            "inputs": {
                "model": model_source,
                "preset": preset,
            },
        }
        # Apply IP-Adapter
        workflow["13"] = {
            "class_type": "IPAdapter",
            "inputs": {
                "model": ["11", 0],
                "ipadapter": ["11", 1],
                "image": ["10", 0],
                "weight": strength,
                "start_at": start_at,
                "end_at": end_at,
                "weight_type": weight_type,
            },
        }
        # Rewire KSampler to use IP-Adapter model output
        workflow["3"]["inputs"]["model"] = ["13", 0]

        return workflow

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
