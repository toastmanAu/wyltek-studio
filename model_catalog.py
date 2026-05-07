"""Model catalog — downloadable models for ComfyUI, TTS, and Ollama."""

# Each entry: id, name, description, url, destination, size_mb, category, type
# type: "comfyui-unet" | "comfyui-checkpoint" | "comfyui-lora" | "comfyui-vae" |
#       "comfyui-clip" | "piper-voice" | "ollama"

CATALOG = [
    # --- SDXL GGUF Checkpoints (→ ComfyUI/models/unet/) ---
    {
        "id": "sdxl-base-q4", "name": "SDXL Base 1.0 (Q4)",
        "desc": "Foundation SDXL model. Good all-rounder for photo and art styles.",
        "url": "https://huggingface.co/hum-ma/SDXL-models-GGUF/resolve/main/sdxl_base_1.0-Q4_0.gguf",
        "filename": "sdxl_base_1.0-Q4_0.gguf",
        "size_mb": 1400, "category": "Image Generation", "type": "comfyui-unet",
    },
    {
        "id": "juggernaut-xi-q4", "name": "Juggernaut XI (Q4)",
        "desc": "Top-tier photorealism. Excellent for people, landscapes, products.",
        "url": "https://huggingface.co/hum-ma/SDXL-models-GGUF/resolve/main/juggernautXL_juggXIByRundiffusion-Q4_0.gguf",
        "filename": "juggernautXL_juggXIByRundiffusion-Q4_0.gguf",
        "size_mb": 1400, "category": "Image Generation", "type": "comfyui-unet",
    },
    {
        "id": "realvis-v4-q4", "name": "RealVisXL V4 (Q4)",
        "desc": "Realistic portraits and scenes. Great for people and architecture.",
        "url": "https://huggingface.co/hum-ma/SDXL-models-GGUF/resolve/main/RealVisXL_V4.0-Q4_0.gguf",
        "filename": "RealVisXL_V4.0-Q4_0.gguf",
        "size_mb": 1400, "category": "Image Generation", "type": "comfyui-unet",
    },
    {
        "id": "realvis-v5-q4", "name": "RealVisXL V5 (Q4)",
        "desc": "Upgraded realism. Better architecture, interiors, skin tones.",
        "url": "https://huggingface.co/hum-ma/SDXL-models-GGUF/resolve/main/RealVisXL_V5.0-Q4_0.gguf",
        "filename": "RealVisXL_V5.0-Q4_0.gguf",
        "size_mb": 1400, "category": "Image Generation", "type": "comfyui-unet",
    },
    {
        "id": "zavychroma-q4", "name": "ZavyChromaXL (Q4)",
        "desc": "Vibrant fantasy and sci-fi. Punchy saturated colors, concept art.",
        "url": "https://huggingface.co/hum-ma/SDXL-models-GGUF/resolve/main/zavychromaxl_v100-Q4_0.gguf",
        "filename": "zavychromaxl_v100-Q4_0.gguf",
        "size_mb": 1400, "category": "Image Generation", "type": "comfyui-unet",
    },
    # --- Flux GGUF ---
    {
        "id": "flux-dev-q4", "name": "Flux.1 Dev (Q4, 5.5GB)",
        "desc": "State-of-the-art quality. Excellent prompt following and photorealism.",
        "url": "https://huggingface.co/city96/FLUX.1-dev-gguf/resolve/main/flux1-dev-Q4_0.gguf",
        "filename": "flux1-dev-Q4_0.gguf",
        "size_mb": 6400, "category": "Image Generation", "type": "comfyui-unet",
    },
    {
        "id": "flux-schnell-q4", "name": "Flux.1 Schnell (Q4, 4-step fast)",
        "desc": "Distilled for speed. Only 4 steps needed. Great for rapid iteration.",
        "url": "https://huggingface.co/city96/FLUX.1-schnell-gguf/resolve/main/flux1-schnell-Q4_0.gguf",
        "filename": "flux1-schnell-Q4_0.gguf",
        "size_mb": 6400, "category": "Image Generation", "type": "comfyui-unet",
    },
    {
        "id": "flux-dev-q8", "name": "Flux.1 Dev (Q8, higher quality)",
        "desc": "Less quantized Flux Dev. Noticeably better detail than Q4. ~12GB, needs 16GB+ VRAM class.",
        "url": "https://huggingface.co/city96/FLUX.1-dev-gguf/resolve/main/flux1-dev-Q8_0.gguf",
        "filename": "flux1-dev-Q8_0.gguf",
        "size_mb": 12300, "category": "Image Generation", "type": "comfyui-unet",
    },
    # --- Stable Diffusion 3 / 3.5 (MMDiT, triple CLIP: CLIP-L + CLIP-G + T5-XXL) ---
    {
        "id": "sd3-medium-q4", "name": "SD 3 Medium (Q4)",
        "desc": "Original SD3 Medium at Q4. Uses triple text encoder (CLIP-L + CLIP-G + T5). ~1.2GB UNet.",
        "url": "https://huggingface.co/city96/stable-diffusion-3-medium-gguf/resolve/main/sd3_medium-Q4_0.gguf",
        "filename": "sd3-medium-Q4_0.gguf",
        "size_mb": 1200, "category": "Image Generation", "type": "comfyui-unet",
    },
    {
        "id": "sd35-medium-q4", "name": "SD 3.5 Medium (Q4)",
        "desc": "Stability's 2.5B SD3.5 Medium. Much better prompt following than SDXL at a similar VRAM footprint. Triple text encoder.",
        "url": "https://huggingface.co/city96/stable-diffusion-3.5-medium-gguf/resolve/main/sd3.5_medium-Q4_0.gguf",
        "filename": "sd3.5_medium-Q4_0.gguf",
        "size_mb": 1700, "category": "Image Generation", "type": "comfyui-unet",
    },
    {
        "id": "sd35-medium-q8", "name": "SD 3.5 Medium (Q8, higher quality)",
        "desc": "Less-quantized SD3.5 Medium. Noticeably cleaner output than Q4. ~3GB UNet.",
        "url": "https://huggingface.co/city96/stable-diffusion-3.5-medium-gguf/resolve/main/sd3.5_medium-Q8_0.gguf",
        "filename": "sd3.5_medium-Q8_0.gguf",
        "size_mb": 3000, "category": "Image Generation", "type": "comfyui-unet",
    },
    {
        "id": "sd35-large-q4", "name": "SD 3.5 Large (Q4, 24GB-class)",
        "desc": "Stability's 8B SD3.5 Large. Top-tier quality. Q4 ~5GB UNet; full stack (UNet + triple CLIP + VAE) wants 16GB+ VRAM.",
        "url": "https://huggingface.co/city96/stable-diffusion-3.5-large-gguf/resolve/main/sd3.5_large-Q4_0.gguf",
        "filename": "sd3.5_large-Q4_0.gguf",
        "size_mb": 5000, "category": "Image Generation", "type": "comfyui-unet",
    },
    {
        "id": "sd35-large-q8", "name": "SD 3.5 Large (Q8, 24GB-class)",
        "desc": "Less-quantized SD3.5 Large. Best quality this side of API. ~9GB UNet.",
        "url": "https://huggingface.co/city96/stable-diffusion-3.5-large-gguf/resolve/main/sd3.5_large-Q8_0.gguf",
        "filename": "sd3.5_large-Q8_0.gguf",
        "size_mb": 9000, "category": "Image Generation", "type": "comfyui-unet",
    },
    {
        "id": "flux2-klein-4b", "name": "Flux.2 Klein 4B base (24GB-class)",
        "desc": "Next-gen Flux base model (non-distilled). ~30 steps, guidance 2.5-4. Needs ~16GB VRAM. Uses Qwen3 text encoder.",
        "url": "https://huggingface.co/black-forest-labs/FLUX.2-klein-base-4B/resolve/main/flux-2-klein-base-4b.safetensors",
        "filename": "flux-2-klein-base-4b.safetensors",
        "size_mb": 16000, "category": "Image Generation", "type": "comfyui-unet",
    },
    # --- SDXL Full Checkpoints (→ ComfyUI/models/checkpoints/) ---
    {
        "id": "juggernaut-v9", "name": "Juggernaut XL v9 (full)",
        "desc": "Full precision photorealism. 6.7GB, needs more VRAM than GGUF.",
        "url": "https://huggingface.co/RunDiffusion/Juggernaut-XL-v9/resolve/main/Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors",
        "filename": "juggernautXL_v9.safetensors",
        "size_mb": 6700, "category": "Image Generation", "type": "comfyui-checkpoint",
    },
    {
        "id": "dreamshaper-xl", "name": "DreamShaper XL Turbo",
        "desc": "Fast versatile model. Only 6-10 steps needed. Handles illustration, photo, fantasy.",
        "url": "https://huggingface.co/Lykon/dreamshaper-xl-v2-turbo/resolve/main/DreamShaperXL_Turbo_v2_1.safetensors",
        "filename": "dreamshaper-xl-v21.safetensors",
        "size_mb": 6500, "category": "Image Generation", "type": "comfyui-checkpoint",
    },
    {
        "id": "realvis-v5-fp16", "name": "RealVisXL V5 (fp16 full)",
        "desc": "Full-precision RealVisXL V5. Best photorealism quality. ~6.5GB.",
        "url": "https://huggingface.co/SG161222/RealVisXL_V5.0/resolve/main/RealVisXL_V5.0_fp16.safetensors",
        "filename": "RealVisXL_V5.0_fp16.safetensors",
        "size_mb": 6500, "category": "Image Generation", "type": "comfyui-checkpoint",
    },
    # --- CLIP + VAE (required for GGUF models) ---
    {
        "id": "clip-l", "name": "CLIP-L (required for SDXL/Flux)",
        "desc": "Text encoder for all SDXL and Flux models. Required.",
        "url": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors",
        "filename": "clip_l.safetensors",
        "size_mb": 235, "category": "Required Components", "type": "comfyui-clip",
    },
    {
        "id": "clip-g", "name": "CLIP-G (required for SDXL GGUF)",
        "desc": "Second text encoder for SDXL GGUF models. Required.",
        "url": "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_g.safetensors",
        "filename": "clip_g.safetensors",
        "size_mb": 2600, "category": "Required Components", "type": "comfyui-clip",
    },
    {
        "id": "t5-xxl-q4", "name": "T5-XXL Q4 (required for Flux)",
        "desc": "Text encoder for Flux models. GGUF quantized for low VRAM.",
        "url": "https://huggingface.co/city96/t5-v1_1-xxl-encoder-gguf/resolve/main/t5-v1_1-xxl-encoder-Q4_K_M.gguf",
        "filename": "t5-v1_1-xxl-encoder-Q4_K_M.gguf",
        "size_mb": 2700, "category": "Required Components", "type": "comfyui-clip",
    },
    {
        "id": "sdxl-vae", "name": "SDXL VAE",
        "desc": "Image decoder for SDXL models. Required for GGUF checkpoints.",
        "url": "https://huggingface.co/stabilityai/sdxl-vae/resolve/main/sdxl_vae.safetensors",
        "filename": "sdxl_vae.safetensors",
        "size_mb": 320, "category": "Required Components", "type": "comfyui-vae",
    },
    {
        "id": "flux-vae", "name": "Flux VAE (ae.safetensors)",
        "desc": "Image decoder for Flux models. Required.",
        "url": "https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/ae.safetensors",
        "filename": "ae.safetensors",
        "size_mb": 320, "category": "Required Components", "type": "comfyui-vae",
    },
    # --- LoRAs (→ ComfyUI/models/loras/) ---
    {
        "id": "lora-pixel-art", "name": "Pixel Art XL",
        "desc": "Pixel art style for SDXL models.",
        "url": "https://huggingface.co/nerijs/pixel-art-xl/resolve/main/pixel-art-xl.safetensors",
        "filename": "pixel-art-xl.safetensors",
        "size_mb": 163, "category": "Style LoRAs", "type": "comfyui-lora",
    },
    {
        "id": "lora-sdxl-lightning-4step", "name": "SDXL Lightning 4-step LoRA",
        "desc": "ByteDance distillation LoRA. Apply to any SDXL base (Juggernaut, RealVis, etc.) to generate in 4 steps. CFG ~1-2, sampler euler, scheduler sgm_uniform.",
        "url": "https://huggingface.co/ByteDance/SDXL-Lightning/resolve/main/sdxl_lightning_4step_lora.safetensors",
        "filename": "sdxl_lightning_4step_lora.safetensors",
        "size_mb": 394, "category": "Speed LoRAs", "type": "comfyui-lora",
    },
    {
        "id": "lora-sdxl-lightning-8step", "name": "SDXL Lightning 8-step LoRA",
        "desc": "Higher-quality variant of SDXL Lightning. 8 steps, better detail than 4-step. CFG ~1-2, euler, sgm_uniform.",
        "url": "https://huggingface.co/ByteDance/SDXL-Lightning/resolve/main/sdxl_lightning_8step_lora.safetensors",
        "filename": "sdxl_lightning_8step_lora.safetensors",
        "size_mb": 394, "category": "Speed LoRAs", "type": "comfyui-lora",
    },
    # --- Improved VAE ---
    {
        "id": "sdxl-vae-fp16-fix", "name": "SDXL VAE (fp16-fix)",
        "desc": "madebyollin's fp16-safe SDXL VAE. Fixes black-square / NaN artifacts when decoding at fp16 on consumer GPUs. Drop-in replacement for sdxl_vae.",
        "url": "https://huggingface.co/madebyollin/sdxl-vae-fp16-fix/resolve/main/sdxl_vae.safetensors",
        "filename": "sdxl_vae_fp16_fix.safetensors",
        "size_mb": 335, "category": "Required Components", "type": "comfyui-vae",
    },
    # --- PixArt-Sigma (DiT, reuses T5-XXL + SDXL VAE) ---
    {
        "id": "pixart-sigma-1024", "name": "PixArt-Sigma XL 1024",
        "desc": "0.6B DiT by PixArt-alpha. Excellent prompt following at very low VRAM. Reuses existing T5-XXL + SDXL VAE. Requires ComfyUI ExtraModels / PixArt loader node.",
        "url": "https://huggingface.co/PixArt-alpha/PixArt-Sigma-XL-2-1024-MS/resolve/main/transformer/diffusion_pytorch_model.safetensors",
        "filename": "pixart_sigma_xl_1024.safetensors",
        "size_mb": 2440, "category": "Image Generation", "type": "comfyui-checkpoint",
    },
    # --- AnimateDiff Lightning (→ ComfyUI/models/animatediff_models/) ---
    {
        "id": "animatediff-lightning-4step", "name": "AnimateDiff Lightning 4-step",
        "desc": "ByteDance distilled motion module. ~4x faster video generation. Pairs with any SD 1.5 checkpoint. Use with euler + sgm_uniform, CFG ~1.",
        "url": "https://huggingface.co/ByteDance/AnimateDiff-Lightning/resolve/main/animatediff_lightning_4step_comfyui.safetensors",
        "filename": "animatediff_lightning_4step_comfyui.safetensors",
        "size_mb": 1700, "category": "Video Generation", "type": "comfyui-animatediff",
    },
    {
        "id": "animatediff-lightning-8step", "name": "AnimateDiff Lightning 8-step",
        "desc": "Higher-quality AnimateDiff Lightning. 8 steps, smoother motion than 4-step.",
        "url": "https://huggingface.co/ByteDance/AnimateDiff-Lightning/resolve/main/animatediff_lightning_8step_comfyui.safetensors",
        "filename": "animatediff_lightning_8step_comfyui.safetensors",
        "size_mb": 1700, "category": "Video Generation", "type": "comfyui-animatediff",
    },
    # --- Piper TTS Voices ---
    {
        "id": "piper-lessac", "name": "Lessac (US Male)",
        "desc": "Clear American male voice. Good default narrator.",
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
        "filename": "en_US-lessac-medium.onnx",
        "meta_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
        "size_mb": 61, "category": "TTS Voices (Piper)", "type": "piper-voice",
    },
    {
        "id": "piper-amy", "name": "Amy (US Female)",
        "desc": "American female voice.",
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx",
        "filename": "en_US-amy-medium.onnx",
        "meta_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/amy/medium/en_US-amy-medium.onnx.json",
        "size_mb": 61, "category": "TTS Voices (Piper)", "type": "piper-voice",
    },
    {
        "id": "piper-alan", "name": "Alan (UK Male)",
        "desc": "British male voice.",
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx",
        "filename": "en_GB-alan-medium.onnx",
        "meta_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/alan/medium/en_GB-alan-medium.onnx.json",
        "size_mb": 61, "category": "TTS Voices (Piper)", "type": "piper-voice",
    },
    {
        "id": "piper-jenny", "name": "Jenny (UK Female)",
        "desc": "Clear British female voice. Popular for narration.",
        "url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/jenny_dioco/medium/en_GB-jenny_dioco-medium.onnx",
        "filename": "en_GB-jenny_dioco-medium.onnx",
        "meta_url": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_GB/jenny_dioco/medium/en_GB-jenny_dioco-medium.onnx.json",
        "size_mb": 61, "category": "TTS Voices (Piper)", "type": "piper-voice",
    },
    # --- TTS Engines (pip install) ---
    {
        "id": "tts-kokoro", "name": "Kokoro TTS (82M, high quality)",
        "desc": "11 natural voices, 4x realtime on CPU. Best quality for size.",
        "pip_package": "kokoro",
        "size_mb": 300, "category": "TTS Engines", "type": "pip-package",
    },
    {
        "id": "tts-xtts", "name": "XTTS v2 (voice cloning, multi-language)",
        "desc": "Clone any voice from a 6-second sample. 17 languages. ~1x realtime on CPU.",
        "pip_package": "TTS",
        "size_mb": 1800, "category": "TTS Engines", "type": "pip-package",
    },
    {
        "id": "tts-bark", "name": "Bark (expressive, emotions, laughter)",
        "desc": "Most expressive TTS. Supports [laughs], [sighs], [music] tags. Slow on CPU.",
        "pip_package": "suno-bark",
        "size_mb": 5000, "category": "TTS Engines", "type": "pip-package",
    },
    # --- Video Generation ---
    {
        "id": "svd-xt", "name": "Stable Video Diffusion XT (img2vid)",
        "desc": "Image-to-video. Generates 25-frame clips from a still image. Needs ~16GB VRAM.",
        "url": "https://huggingface.co/stabilityai/stable-video-diffusion-img2vid-xt/resolve/main/svd_xt_1_1.safetensors",
        "filename": "svd_xt_1_1.safetensors",
        "size_mb": 9500, "category": "Video Generation", "type": "comfyui-checkpoint",
    },
    {
        "id": "wan21-t2v", "name": "Wan 2.1 T2V 1.3B (text-to-video)",
        "desc": "Lightweight text-to-video. Works on 24GB-class cards. Diffusers format.",
        "url": "https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B-Diffusers",
        "filename": "Wan2.1-T2V-1.3B",
        "size_mb": 27000, "category": "Video Generation", "type": "comfyui-checkpoint",
    },
    # --- Music Generation ---
    {
        "id": "music-audiocraft", "name": "MusicGen (text-to-music)",
        "desc": "Generate royalty-free backing tracks. With 24GB VRAM, large (3.3B) and melody variants now fit. Small/Medium also available.",
        "pip_package": "audiocraft",
        "size_mb": 3300, "category": "Music Generation", "type": "pip-package",
    },
    {
        "id": "music-musicgen-large", "name": "MusicGen Large (3.3B, 24GB-class)",
        "desc": "Largest MusicGen variant. 3.3B params, ~13GB at fp16. Auto-downloads on first use via audiocraft.",
        "pip_package": "audiocraft",
        "model_name": "facebook/musicgen-large",
        "size_mb": 13000, "category": "Music Generation", "type": "pip-package",
    },
    {
        "id": "music-musicgen-melody-large", "name": "MusicGen Melody Large (3.3B + melody conditioning)",
        "desc": "MusicGen Large with melody conditioning. Generate music matching a reference melody. ~14GB.",
        "pip_package": "audiocraft",
        "model_name": "facebook/musicgen-melody-large",
        "size_mb": 14000, "category": "Music Generation", "type": "pip-package",
    },
    # --- Ollama models ---
    {
        "id": "ollama-qwen25-14b", "name": "Qwen 2.5 14B (for OP my prompt)",
        "desc": "Best quality text model for prompt enhancement. ~9GB, runs on CPU.",
        "ollama_model": "qwen2.5:14b",
        "size_mb": 9000, "category": "LLM (Ollama)", "type": "ollama",
    },
    {
        "id": "ollama-qwen25-7b", "name": "Qwen 2.5 7B (faster OP)",
        "desc": "Lighter text model. Faster prompt enhancement. ~5GB.",
        "ollama_model": "qwen2.5:7b",
        "size_mb": 4700, "category": "LLM (Ollama)", "type": "ollama",
    },
    {
        "id": "ollama-qwen3vl-8b", "name": "Qwen3 VL 8B (vision, future scoring)",
        "desc": "Vision-language model for future image analysis features.",
        "ollama_model": "qwen3-vl:8b",
        "size_mb": 6100, "category": "LLM (Ollama)", "type": "ollama",
    },
    {
        "id": "ollama-moondream", "name": "Moondream (fast vision)",
        "desc": "Tiny vision model. Fast image analysis on CPU. ~1.7GB.",
        "ollama_model": "moondream:latest",
        "size_mb": 1700, "category": "LLM (Ollama)", "type": "ollama",
    },
]

# Trigger words per LoRA filename. Style LoRAs only fire reliably when their
# activator tokens appear in the prompt. First entry in each list is the
# canonical trigger used for auto-injection; the others are recognised as
# already-present (no injection needed) when we scan the user's prompt.
#
# Edit freely — triggers come from each LoRA's HF/Civitai page and are the
# single most common reason a style LoRA "does nothing". Leave the list empty
# for LoRAs that don't need (or don't have) a hard trigger — e.g. detailers.
LORA_TRIGGERS: dict[str, list[str]] = {
    "pixel-art-xl.safetensors":       ["pixel art", "pixel-art", "8-bit"],
    "voxel-xl.safetensors":           ["voxel art", "voxel", "voxel style"],
    "crayon-style-xl.safetensors":    ["crayon drawing", "crayon", "wax crayon"],
    "watercolor-xl.safetensors":      ["watercolor painting", "watercolor", "watercolour"],
    "sticker-style-xl.safetensors":   ["die-cut sticker", "sticker", "vinyl sticker"],
    # anime-detailer is a *detailer*, not a style LoRA — it sharpens existing
    # anime imagery. Giving it "anime" as a trigger is usually enough.
    "anime-detailer-xl.safetensors":  ["anime", "anime style"],
    # Speed/distillation LoRAs have no stylistic trigger — they affect sampling,
    # not content. Explicitly empty so auto-injection skips them.
    "sdxl_lightning_4step_lora.safetensors": [],
    "sdxl_lightning_8step_lora.safetensors": [],
}


# Map type → destination directory (relative to ComfyUI root)
DEST_MAP = {
    "comfyui-unet": "models/unet",
    "comfyui-checkpoint": "models/checkpoints",
    "comfyui-lora": "models/loras",
    "comfyui-vae": "models/vae",
    "comfyui-clip": "models/clip",
    "comfyui-animatediff": "models/animatediff_models",
    "piper-voice": None,  # handled specially → engines/voices/
    "ollama": None,  # handled via ollama pull
}
