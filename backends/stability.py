"""Stability AI API backend."""

import base64
import os

import aiohttp

from backends.base import BaseBackend


class StabilityBackend(BaseBackend):
    async def generate(self, params, output_path, on_progress):
        api_key = self.api_key or os.environ.get("STABILITY_API_KEY", "")
        if not api_key:
            raise RuntimeError("Stability API key not configured")

        model = params.get("model", "stable-diffusion-xl-1024-v1-0")
        await on_progress(10, "Sending to Stability AI...")

        url = f"https://api.stability.ai/v1/generation/{model}/text-to-image"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        payload = {
            "text_prompts": [
                {"text": params["prompt"], "weight": 1.0},
            ],
            "cfg_scale": params.get("cfg_scale", 7.0),
            "width": params.get("width", 1024),
            "height": params.get("height", 1024),
            "steps": params.get("steps", 30),
            "samples": 1,
        }
        if params.get("negative_prompt"):
            payload["text_prompts"].append({"text": params["negative_prompt"], "weight": -1.0})
        seed = params.get("seed", -1)
        if seed != -1:
            payload["seed"] = seed

        await on_progress(30, "Generating...")

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Stability AI error: {text[:500]}")
                result = await resp.json()

        img_b64 = result["artifacts"][0]["base64"]
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(img_b64))

        await on_progress(100, "Done")
