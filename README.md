# Open Palette

Local-first AI image generation studio. Like OpenArt, but you own the stack.

Upload reference images, describe what you want, pick your model backend, and generate.
Supports local inference (ComfyUI, Fooocus, Stable Diffusion WebUI, Ollama) and
online APIs (Pollinations, Gemini, Stability AI, OpenAI, Replicate) — free or paid.

## Quick Start

```bash
# Install
pip install -r requirements.txt

# Configure backends (edit to match your setup)
cp config.example.yaml config.yaml

# Run
python server.py

# Open http://localhost:7860
```

## Features

- Text-to-image with up to 4 reference images
- Backend-agnostic: swap models/providers without changing workflow
- Per-component model selection (base model, IP-adapter, upscaler, refiner)
- Real-time generation progress via WebSocket
- Save / download / share generated images
- Gallery of previous generations
- Responsive UI — works on desktop and mobile

## Supported Backends

| Backend | Type | Cost | Notes |
|---------|------|------|-------|
| ComfyUI | Local | Free | Most flexible, node-based pipelines |
| Fooocus | Local | Free | Simplest setup, good defaults |
| A1111 WebUI | Local | Free | Mature ecosystem |
| Ollama (vision) | Local | Free | Image understanding only |
| Pollinations.ai | Online | Free | No API key needed |
| Gemini | Online | Free tier | Google API key |
| Stability AI | Online | Paid | High quality |
| OpenAI (DALL-E) | Online | Paid | Easy API |
| Replicate | Online | Paid | Access to many models |
| HuggingFace | Online | Free tier | Community models |

## Requirements

- Python 3.10+
- For local generation: NVIDIA GPU with 6GB+ VRAM (8GB+ recommended)
- For online-only: no GPU needed
