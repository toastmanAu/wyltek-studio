"""OpenAI DALL-E / GPT Image backend."""

import base64
import os

import aiohttp

from backends.base import BaseBackend


class OpenAIBackend(BaseBackend):
    async def generate(self, params, output_path, on_progress):
        api_key = self.api_key or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OpenAI API key not configured")

        model = params.get("model", "dall-e-3")
        await on_progress(10, f"Sending to OpenAI ({model})...")

        url = "https://api.openai.com/v1/images/generations"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        size = self._closest_size(params.get("width", 1024), params.get("height", 1024))
        payload = {
            "model": model,
            "prompt": params["prompt"],
            "n": 1,
            "size": size,
            "response_format": "b64_json",
        }

        await on_progress(30, "Generating...")

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"OpenAI error: {text[:500]}")
                result = await resp.json()

        img_b64 = result["data"][0]["b64_json"]
        with open(output_path, "wb") as f:
            f.write(base64.b64decode(img_b64))

        await on_progress(100, "Done")

    def _closest_size(self, w, h):
        sizes = ["1024x1024", "1024x1792", "1792x1024"]
        if h > w * 1.3:
            return "1024x1792"
        if w > h * 1.3:
            return "1792x1024"
        return "1024x1024"
