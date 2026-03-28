"""Pollinations.ai backend — free, no API key needed."""

import urllib.parse

import aiohttp

from backends.base import BaseBackend


class PollinationsBackend(BaseBackend):
    async def generate(self, params, output_path, on_progress):
        prompt = params["prompt"]
        width = params.get("width", 1024)
        height = params.get("height", 1024)
        model = params.get("model", "flux")
        seed = params.get("seed", -1)

        await on_progress(10, "Sending to Pollinations.ai...")

        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}"
        url_params = {"width": width, "height": height, "model": model, "nologo": "true"}
        if seed != -1:
            url_params["seed"] = seed

        async with aiohttp.ClientSession() as session:
            await on_progress(30, "Generating (this may take 10-30s)...")
            async with session.get(url, params=url_params, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"Pollinations error: HTTP {resp.status}")
                await on_progress(80, "Downloading image...")
                data = await resp.read()

        with open(output_path, "wb") as f:
            f.write(data)

        await on_progress(100, "Done")
