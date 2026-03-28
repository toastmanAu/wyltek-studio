"""Pollinations.ai backend — free tier (no signup), optional token for higher limits."""

import os
import urllib.parse

import aiohttp

from backends.base import BaseBackend


class PollinationsBackend(BaseBackend):
    async def generate(self, params, output_path, on_progress):
        api_key = self.api_key or os.environ.get("POLLINATIONS_API_KEY", "")
        prompt = params["prompt"]
        width = params.get("width", 1024)
        height = params.get("height", 1024)
        model = params.get("model", "flux")
        seed = params.get("seed", -1)

        await on_progress(10, "Sending to Pollinations.ai...")

        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}"
        url_params = {
            "width": width,
            "height": height,
            "model": model,
            "nologo": "true",
            "referrer": "open-palette",
        }
        if seed != -1:
            url_params["seed"] = seed

        headers = {"Referer": "https://open-palette.local"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        async with aiohttp.ClientSession() as session:
            await on_progress(30, "Generating (this may take 10-30s)...")
            async with session.get(url, params=url_params, headers=headers,
                                   allow_redirects=True,
                                   timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status == 401:
                    raise RuntimeError(
                        "Pollinations rate limited. Register at auth.pollinations.ai for a token, "
                        "or set POLLINATIONS_API_KEY in env / config."
                    )
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Pollinations error: HTTP {resp.status} — {text[:200]}")

                content_type = resp.headers.get("content-type", "")
                if "image" not in content_type:
                    text = await resp.text()
                    raise RuntimeError(f"Pollinations returned non-image: {text[:200]}")

                await on_progress(80, "Downloading image...")
                data = await resp.read()

        with open(output_path, "wb") as f:
            f.write(data)

        await on_progress(100, "Done")
