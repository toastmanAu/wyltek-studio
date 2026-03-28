"""Replicate API backend."""

import asyncio
import os

import aiohttp

from backends.base import BaseBackend


class ReplicateBackend(BaseBackend):
    async def generate(self, params, output_path, on_progress):
        api_key = self.api_key or os.environ.get("REPLICATE_API_TOKEN", "")
        if not api_key:
            raise RuntimeError("Replicate API token not configured")

        model = params.get("model", "black-forest-labs/flux-1.1-pro")
        await on_progress(10, f"Sending to Replicate ({model})...")

        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        payload = {
            "version": model,
            "input": {
                "prompt": params["prompt"],
                "width": params.get("width", 1024),
                "height": params.get("height", 1024),
                "num_inference_steps": params.get("steps", 30),
                "guidance_scale": params.get("cfg_scale", 7.0),
            },
        }
        seed = params.get("seed", -1)
        if seed != -1:
            payload["input"]["seed"] = seed

        async with aiohttp.ClientSession() as session:
            # Create prediction
            async with session.post("https://api.replicate.com/v1/predictions",
                                    json=payload, headers=headers) as resp:
                if resp.status not in (200, 201):
                    text = await resp.text()
                    raise RuntimeError(f"Replicate error: {text[:500]}")
                prediction = await resp.json()

            pred_url = prediction["urls"]["get"]
            await on_progress(30, "Waiting for generation...")

            # Poll until complete
            for i in range(120):
                await asyncio.sleep(2)
                async with session.get(pred_url, headers=headers) as resp:
                    status = await resp.json()

                if status["status"] == "succeeded":
                    break
                elif status["status"] == "failed":
                    raise RuntimeError(f"Replicate generation failed: {status.get('error', 'unknown')}")

                pct = min(30 + i * 2, 85)
                await on_progress(pct, f"Generating ({status['status']})...")
            else:
                raise RuntimeError("Replicate generation timed out")

            await on_progress(90, "Downloading...")

            # Download output image
            output_url = status["output"]
            if isinstance(output_url, list):
                output_url = output_url[0]

            async with session.get(output_url) as resp:
                with open(output_path, "wb") as f:
                    f.write(await resp.read())

        await on_progress(100, "Done")
