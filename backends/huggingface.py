"""HuggingFace Inference API backend."""

import os

import aiohttp

from backends.base import BaseBackend


class HuggingFaceBackend(BaseBackend):
    async def generate(self, params, output_path, on_progress):
        api_key = self.api_key or os.environ.get("HF_TOKEN", "")
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        model = params.get("model", "stabilityai/stable-diffusion-xl-base-1.0")
        await on_progress(10, f"Sending to HuggingFace ({model.split('/')[-1]})...")

        url = f"https://api-inference.huggingface.co/models/{model}"
        payload = {"inputs": params["prompt"]}

        await on_progress(30, "Generating (free tier may queue)...")

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=300)) as resp:
                if resp.status == 503:
                    # Model loading — retry
                    result = await resp.json()
                    wait = result.get("estimated_time", 30)
                    await on_progress(40, f"Model loading, ~{int(wait)}s wait...")
                    import asyncio
                    await asyncio.sleep(min(wait, 60))
                    async with session.post(url, json=payload, headers=headers,
                                            timeout=aiohttp.ClientTimeout(total=300)) as retry_resp:
                        if retry_resp.status != 200:
                            text = await retry_resp.text()
                            raise RuntimeError(f"HuggingFace error: {text[:500]}")
                        data = await retry_resp.read()
                elif resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"HuggingFace error: {text[:500]}")
                else:
                    data = await resp.read()

        with open(output_path, "wb") as f:
            f.write(data)

        await on_progress(100, "Done")
