"""Automatic1111 / Stable Diffusion WebUI backend."""

import base64

import aiohttp

from backends.base import BaseBackend


class A1111Backend(BaseBackend):
    async def generate(self, params, output_path, on_progress):
        url = self.url.rstrip("/")
        await on_progress(10, "Sending to Stable Diffusion WebUI...")

        payload = {
            "prompt": params["prompt"],
            "negative_prompt": params.get("negative_prompt", ""),
            "width": params.get("width", 1024),
            "height": params.get("height", 1024),
            "steps": params.get("steps", 30),
            "cfg_scale": params.get("cfg_scale", 7.0),
            "seed": params.get("seed", -1),
            "sampler_name": "Euler a",
            "batch_size": 1,
        }

        if params.get("model"):
            # Switch model if needed
            async with aiohttp.ClientSession() as session:
                await session.post(f"{url}/sdapi/v1/options",
                                   json={"sd_model_checkpoint": params["model"]})

        await on_progress(20, "Generating...")

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{url}/sdapi/v1/txt2img", json=payload,
                                    timeout=aiohttp.ClientTimeout(total=300)) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"A1111 error: {text[:500]}")
                result = await resp.json()

        await on_progress(90, "Saving...")

        img_b64 = result["images"][0]
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(img_b64))

        await on_progress(100, "Done")
