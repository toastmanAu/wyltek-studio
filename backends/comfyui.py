"""ComfyUI backend — most flexible local option."""

import asyncio
import base64
import json
import uuid
from pathlib import Path

import aiohttp

from backends.base import BaseBackend

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
        url = self.url.rstrip("/")
        prompt_api = f"{url}/prompt"
        ws_url = url.replace("http", "ws") + "/ws"
        client_id = str(uuid.uuid4())

        workflow = json.loads(json.dumps(BASIC_TXT2IMG))

        # Apply params
        if params.get("model"):
            workflow["4"]["inputs"]["ckpt_name"] = params["model"]
        workflow["5"]["inputs"]["width"] = params.get("width", 1024)
        workflow["5"]["inputs"]["height"] = params.get("height", 1024)
        workflow["6"]["inputs"]["text"] = params["prompt"]
        workflow["7"]["inputs"]["text"] = params.get("negative_prompt", "")
        workflow["3"]["inputs"]["steps"] = params.get("steps", 30)
        workflow["3"]["inputs"]["cfg"] = params.get("cfg_scale", 7.0)
        seed = params.get("seed", -1)
        if seed == -1:
            import random
            seed = random.randint(0, 2**32 - 1)
        workflow["3"]["inputs"]["seed"] = seed

        # Add IP-Adapter nodes if reference images provided
        ref_images = params.get("reference_images", [])
        if ref_images and params.get("ip_adapter_model"):
            workflow = self._add_ip_adapter(workflow, ref_images, params)

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

        # Load first reference image
        workflow["10"] = {
            "class_type": "LoadImage",
            "inputs": {"image": ref_images[0]},
        }
        workflow["11"] = {
            "class_type": "IPAdapterModelLoader",
            "inputs": {"ipadapter_file": ip_model},
        }
        workflow["12"] = {
            "class_type": "CLIPVisionLoader",
            "inputs": {"clip_name": "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors"},
        }
        workflow["13"] = {
            "class_type": "IPAdapterApply",
            "inputs": {
                "ipadapter": ["11", 0],
                "clip_vision": ["12", 0],
                "image": ["10", 0],
                "model": ["4", 0],
                "weight": strength,
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
