"""ComfyUI backend — most flexible local option."""

import asyncio
import base64
import json
import uuid
from pathlib import Path

import aiohttp

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
        "inputs": {"filename_prefix": "open-palette", "images": ["8", 0]},
    },
}


class ComfyUIBackend(BaseBackend):
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
                    raise RuntimeError(f"ComfyUI error: {text}")
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

    def _add_ip_adapter(self, workflow, ref_images, params):
        """Inject IP-Adapter nodes for reference image conditioning."""
        strength = params.get("ip_adapter_strength", 0.6)
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
                "start_at": 0.0,
                "end_at": 1.0,
                "weight_type": "standard",
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
