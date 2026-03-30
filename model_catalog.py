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
    # --- Music Generation ---
    {
        "id": "music-audiocraft", "name": "MusicGen (text-to-music)",
        "desc": "Generate royalty-free backing tracks from text descriptions. Small (300M) and Medium (1.5B) models.",
        "pip_package": "audiocraft",
        "size_mb": 3300, "category": "Music Generation", "type": "pip-package",
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

# Map type → destination directory (relative to ComfyUI root)
DEST_MAP = {
    "comfyui-unet": "models/unet",
    "comfyui-checkpoint": "models/checkpoints",
    "comfyui-lora": "models/loras",
    "comfyui-vae": "models/vae",
    "comfyui-clip": "models/clip",
    "piper-voice": None,  # handled specially → engines/voices/
    "ollama": None,  # handled via ollama pull
}
