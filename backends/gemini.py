"""Google Gemini image generation backend."""

import base64
import json
import os

import aiohttp

from backends.base import BaseBackend


class GeminiBackend(BaseBackend):
    async def generate(self, params, output_path, on_progress):
        api_key = self.api_key or os.environ.get("GEMINI_API_KEY", "")
        if not api_key:
            raise RuntimeError("Gemini API key not configured (set GEMINI_API_KEY or config)")

        model = params.get("model", "gemini-2.0-flash-exp-image-generation")
        prompt = params["prompt"]

        await on_progress(10, "Sending to Gemini...")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

        # Build request with optional reference images
        parts = []
        ref_images = params.get("reference_images", [])
        for ref_path in ref_images[:4]:
            with open(ref_path, "rb") as f:
                img_data = base64.b64encode(f.read()).decode()
            parts.append({
                "inline_data": {"mime_type": "image/png", "data": img_data}
            })
        parts.append({"text": prompt})

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]},
        }

        await on_progress(30, "Waiting for Gemini response...")

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Gemini error: {text[:500]}")
                result = await resp.json()

        await on_progress(80, "Processing response...")

        # Extract image from response
        for candidate in result.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                if "inlineData" in part:
                    img_b64 = part["inlineData"]["data"]
                    with open(output_path, "wb") as f:
                        f.write(base64.b64decode(img_b64))
                    await on_progress(100, "Done")
                    return

        raise RuntimeError("No image in Gemini response")
