"""Fooocus API backend."""

import asyncio
import base64

import aiohttp

from backends.base import BaseBackend


class FooocusBackend(BaseBackend):
    async def generate(self, params, output_path, on_progress):
        url = self.url.rstrip("/")
        await on_progress(10, "Sending to Fooocus...")

        payload = {
            "prompt": params["prompt"],
            "negative_prompt": params.get("negative_prompt", ""),
            "style_selections": [],
            "performance_selection": "Quality",
            "aspect_ratios_selection": f"{params.get('width', 1024)}×{params.get('height', 1024)}",
            "image_number": 1,
            "image_seed": params.get("seed", -1),
            "sharpness": 2.0,
            "guidance_scale": params.get("cfg_scale", 7.0),
        }

        # Add reference images as image prompts
        ref_images = params.get("reference_images", [])
        if ref_images:
            image_prompts = []
            for ref_path in ref_images[:4]:
                with open(ref_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                image_prompts.append({
                    "cn_img": b64,
                    "cn_stop": 0.8,
                    "cn_weight": params.get("ip_adapter_strength", 0.6),
                    "cn_type": "ImagePrompt",
                })
            payload["image_prompts"] = image_prompts

        async with aiohttp.ClientSession() as session:
            # Start async generation
            async with session.post(f"{url}/v2/generation/text-to-image-with-ip",
                                    json=payload,
                                    timeout=aiohttp.ClientTimeout(total=300)) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"Fooocus error: {text[:500]}")

                await on_progress(30, "Generating...")

                # Fooocus v2 API returns the image directly
                result = await resp.json()

            await on_progress(80, "Processing result...")

            # Result contains base64 images
            if isinstance(result, list) and result:
                img_data = result[0]
                if isinstance(img_data, dict) and "base64" in img_data:
                    with open(output_path, "wb") as f:
                        f.write(base64.b64decode(img_data["base64"]))
                elif isinstance(img_data, dict) and "url" in img_data:
                    async with session.get(img_data["url"]) as img_resp:
                        with open(output_path, "wb") as f:
                            f.write(await img_resp.read())
                else:
                    raise RuntimeError("Unexpected Fooocus response format")
            else:
                raise RuntimeError("No image in Fooocus response")

        await on_progress(100, "Done")
