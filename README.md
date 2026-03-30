# Open Palette

Local-first AI image generation studio. Like OpenArt, but you own the stack.

Upload reference images, describe what you want, pick your model and backend, and generate. Compare outputs across multiple backends side-by-side. Swap between local GPU inference and cloud APIs with one click.

![Python](https://img.shields.io/badge/python-3.10+-blue) ![License](https://img.shields.io/badge/license-MIT-green)

## Model Comparison

Same prompt across different backends — all generated through Open Palette:

> *"a golden retriever sitting in autumn leaves, warm sunlight, shallow depth of field, photorealistic"*

| SD 1.5 (512x512, local) | SDXL Q4 GGUF (1024x1024, local) | Juggernaut XL Q4 (1024x1024, local) |
|:---:|:---:|:---:|
| ![SD 1.5](docs/screenshots/dog-sd15.png) | ![SDXL](docs/screenshots/dog-sdxl.png) | ![Juggernaut](docs/screenshots/dog-juggernaut.png) |

| RealVisXL V4 Q4 (1024x1024, local) | Nano Banana / Gemini 2.5 Flash (cloud) |
|:---:|:---:|
| ![RealVis](docs/screenshots/dog-realvis.png) | ![Gemini](docs/screenshots/dog-gemini.png) |

> *"a medieval castle on a cliff overlooking a stormy ocean, dramatic lighting, digital painting, fantasy art"*

| SD 1.5 (local) | Juggernaut XL (local) | Nano Banana / Gemini (cloud) |
|:---:|:---:|:---:|
| ![SD 1.5](docs/screenshots/castle-sd15.png) | ![Juggernaut](docs/screenshots/castle-juggernaut.png) | ![Gemini](docs/screenshots/castle-gemini.png) |

> *"a single boat upon a calm lake"*

| SD 1.5 (local) | SDXL Q4 (local) | Juggernaut XL (local) |
|:---:|:---:|:---:|
| ![SD 1.5](docs/screenshots/boat-sd15.png) | ![SDXL](docs/screenshots/boat-sdxl.png) | ![Juggernaut](docs/screenshots/boat-juggernaut.png) |

| RealVisXL V4 (local) | Nano Banana (cloud) | Nano Banana Pro (cloud) |
|:---:|:---:|:---:|
| ![RealVis](docs/screenshots/boat-realvis.png) | ![NanoBanana](docs/screenshots/boat-nanobanaana.png) | ![NanoBananaPro](docs/screenshots/boat-nanobananapro.png) |

> *"lightning striking over water at night"*

| SD 1.5 (local) | SDXL Q4 (local) | Juggernaut XL (local) |
|:---:|:---:|:---:|
| ![SD 1.5](docs/screenshots/lightning-sd15.png) | ![SDXL](docs/screenshots/lightning-sdxl.png) | ![Juggernaut](docs/screenshots/lightning-juggernaut.png) |

| RealVisXL V4 (local) | Nano Banana Pro (cloud) |
|:---:|:---:|
| ![RealVis](docs/screenshots/lightning-realvis.png) | ![NanoBananaPro](docs/screenshots/lightning-nanobananapro.png) |

> *"A cozy Japanese ramen shop at night, steam rising from bowls, warm lantern light, rain outside, detailed interior, anime style"*

| Flux.1 Dev Q4 (local) | Flux.1 Schnell Q4 (local) | Juggernaut XL v9 (local) |
|:---:|:---:|:---:|
| ![Flux Q4](docs/screenshots/ramen-flux-q4.png) | ![Schnell](docs/screenshots/ramen-schnell.png) | ![Juggernaut](docs/screenshots/ramen-juggernaut.png) |

| DreamShaper XL Turbo (local) | RealVisXL V4 Q4 (local) | SDXL Base (local) |
|:---:|:---:|:---:|
| ![DreamShaper](docs/screenshots/ramen-dreamshaper.png) | ![RealVis](docs/screenshots/ramen-realvis-gguf.png) | ![SDXL](docs/screenshots/ramen-sdxl-base.png) |

| Juggernaut XI Q4 (local) | SDXL Lightning (local) | SD 1.5 (local, 512x512) |
|:---:|:---:|:---:|
| ![Juggernaut GGUF](docs/screenshots/ramen-juggernaut-gguf.png) | ![Lightning](docs/screenshots/ramen-lightning.png) | ![SD 1.5](docs/screenshots/ramen-sd15.png) |

All local images generated on an RTX 3060 Ti (8GB VRAM) using GGUF quantized models.

### Why Per-Model Defaults Matter

Open Palette applies optimal generation settings (sampler, scheduler, CFG scale, steps, resolution) per model automatically. Without this, compare mode sends identical parameters to every model — which can produce dramatically bad results.

**The problem:** Flux, Lightning, Schnell, and DreamShaper all need radically different settings. Sending CFG 7.0 and 25 steps to a Flux model (which needs CFG 3.5) or a 4-step distilled model produces washed-out or over-processed images.

> *Before tuning: "A Pokemon style cat" — all models received steps=25, CFG=7.0, euler_ancestral sampler*

| Flux Dev Q4 (CFG 7.0) | Flux Dev Q8 (CFG 7.0) | SDXL Lightning (25 steps, CFG 7.0) | SD3 Medium Q4 |
|:---:|:---:|:---:|:---:|
| ![Flux Q4 before](docs/screenshots/before-flux-q4-cat.png) | ![Flux Q8 before](docs/screenshots/before-flux-q8-cat.png) | ![Lightning before](docs/screenshots/before-lightning-cat.png) | ![SD3 before](docs/screenshots/before-sd3-cat.png) |
| Washed out yellow blob | Barely a silhouette | Sticker artifacts | Crosshatch/halftone (broken at Q4) |

> *After tuning: "A Pokemon style dog" — each model receives its optimal settings automatically*

| Flux Dev Q4 (CFG 3.5, euler, simple) | Flux Dev Q8 (CFG 3.5, euler, simple) | Flux Dev Q5 (CFG 3.5, euler, simple) |
|:---:|:---:|:---:|
| ![Flux Q4 after](docs/screenshots/after-flux-q4-dog.png) | ![Flux Q8 after](docs/screenshots/after-flux-q8-dog.png) | ![Flux Q5 after](docs/screenshots/after-flux-q5-dog.png) |

| Flux Schnell (4 steps, CFG 1.0) | DreamShaper XL (8 steps, CFG 2.0, dpmpp_sde) | SDXL Lightning (4 steps, CFG 1.0, sgm_uniform) |
|:---:|:---:|:---:|
| ![Schnell after](docs/screenshots/after-schnell-dog.png) | ![DreamShaper after](docs/screenshots/after-dreamshaper-dog.png) | ![Lightning after](docs/screenshots/after-lightning-dog.png) |

| Juggernaut XL v9 (dpmpp_2m, karras) | RealVisXL V4 (dpmpp_2m, karras) | Gemini 2.5 Flash (cloud) | Gemini 3 Pro (cloud) |
|:---:|:---:|:---:|:---:|
| ![Juggernaut after](docs/screenshots/after-juggernaut-dog.png) | ![RealVis after](docs/screenshots/after-realvis-dog.png) | ![Gemini Flash after](docs/screenshots/after-gemini-flash-dog.png) | ![Gemini Pro after](docs/screenshots/after-gemini-pro-dog.png) |

**Key settings that affect output quality:**

| Setting | What it does | Wrong value symptoms |
|---|---|---|
| **CFG Scale** | How closely the model follows the prompt. Higher = more literal, but overcooked above model's range | Washed out, over-saturated, or blown-out highlights |
| **Steps** | Number of denoising iterations. Distilled models (Lightning, Schnell) need very few | Over-processed, artifacts, loss of detail, wasted generation time |
| **Sampler** | The algorithm used for denoising. `dpmpp_2m` is sharp, `euler` suits Flux, `dpmpp_sde` suits turbo models | Soft/blurry output, or unstable generation |
| **Scheduler** | Controls the noise schedule curve. `karras` is sharper for SDXL, `simple` for Flux, `sgm_uniform` for Lightning | Subtle quality loss, muddy details |
| **Resolution** | Must match the model's training resolution. SD 1.5 = 512x512, SDXL/Flux = 1024x1024 | Repeated patterns, artifacts, blur (especially SD 1.5 at 1024x) |

Open Palette handles all of this automatically — just pick your model and generate.

### "OP My Prompt" — AI-Enhanced Prompts

The **OP my prompt** button uses a local LLM (via [Ollama](https://ollama.com)) to enhance your prompt before generation. It adds lighting, composition, color guidance, and a negative prompt — running entirely on CPU so your GPU stays free for image generation.

> **Human prompt:** "A Pokemon style cat"
>
> **OP'd prompt:** "A cute and detailed Pokémon-style cat character with vibrant colors, expressive eyes, and a playful pose. The background is a stylized forest scene with glowing leaves and soft lighting to emphasize the character."

| | Juggernaut XL v9 | DreamShaper XL | Juggernaut XI Q4 |
|---|:---:|:---:|:---:|
| **Human prompt** | ![before](docs/screenshots/plain-cat-juggernaut.png) | ![before](docs/screenshots/plain-dog-dreamshaper.png) | ![before](docs/screenshots/after-juggernaut-dog.png) |
| **OP'd prompt** | ![after](docs/screenshots/op-cat-juggernaut.png) | ![after](docs/screenshots/op-cat-dreamshaper.png) | ![after](docs/screenshots/op-cat-juggernaut-gguf.png) |

| | RealVisXL V4 Q4 | SDXL Lightning | Flux Schnell |
|---|:---:|:---:|:---:|
| **OP'd prompt** | ![op](docs/screenshots/op-cat-realvis-gguf.png) | ![op](docs/screenshots/op-cat-lightning.png) | ![op](docs/screenshots/op-cat-schnell.png) |

The OP adds scene context, character detail, and lighting direction that the models need but simple prompts leave ambiguous. Works with any Ollama-compatible model — configure in Settings.

### Auto Image Scoring

Every generated image is automatically scored on 8 quality metrics: sharpness, saturation, brightness, color diversity, contrast, noise, edge density, and dynamic range. Scores are stored in SQLite and aggregated into per-model profiles over time.

Click the **Scores** button on any generated image or compare card to see its metrics. Visit `/api/scores/models` to see how each model performs on average across all your generations.

## Quick Start

```bash
git clone https://github.com/toastmanAu/open-palette.git
cd open-palette
pip install -r requirements.txt
cp config.example.yaml config.yaml
python server.py
```

Open **http://localhost:7860** in your browser.

### Fastest path to generating images

**No GPU? No problem.** Enable a cloud backend:

1. Get a free API key from [Google AI Studio](https://aistudio.google.com/apikey)
2. Set it: `export GEMINI_API_KEY=your_key_here`
3. Run `python server.py` and select **gemini** backend

**Have an NVIDIA GPU?** Set up [ComfyUI](https://github.com/comfyanonymous/ComfyUI) and point Open Palette at it in `config.yaml`. Download GGUF quantized models to run SDXL-quality generation on 8GB VRAM.

### Optional: Enable "OP My Prompt"

The prompt optimizer runs entirely on CPU via [Ollama](https://ollama.com) — no GPU required.

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull a model (pick one)
ollama pull qwen2.5:14b    # Best quality, ~9GB RAM, 8-12s per enhancement
ollama pull qwen2.5:7b     # Faster, ~5GB RAM
ollama pull mistral:7b      # Alternative, good quality
```

Configure the Ollama URL and model in the Settings page, or edit `config.yaml`:

```yaml
prompt_optimizer:
  enabled: true
  ollama_url: "http://[::1]:11434"   # or http://localhost:11434
  model: "qwen2.5:14b"
```

Any Ollama-compatible model works — experiment with what you have installed. The Settings page auto-detects installed models.

## Features

- **"OP my prompt"** — AI-enhanced prompts via local Ollama LLM (runs on CPU, GPU stays free)
- **Auto image scoring** — 8 quality metrics per image, stored in SQLite, per-model profiles over time
- **Text-to-image** with up to 4 reference images (IP-Adapter support)
- **Compare mode** — run the same prompt across multiple backends/models side-by-side
- **Batch mode** — generate N variations with the same prompt/model (different seeds)
- **LoRA support** — apply style LoRAs with split model/CLIP strength controls
- **Auto-model detection** — discovers installed ComfyUI models, LoRAs, shows unavailable ones greyed out
- **Per-model optimal defaults** — sampler, scheduler, resolution, steps, CFG auto-tune per model
- **GGUF quantized model support** — run Flux.1 and SDXL on 8GB VRAM via ComfyUI-GGUF
- **Built-in tips guide** — prompt writing, CFG scale, model strengths
- **Settings page** — configure API keys, enable/disable backends, test connections from the UI
- **PNG metadata** — prompt, model, seed embedded in every generated image
- **Real-time progress** via WebSocket with polling fallback
- **Gallery** of previous generations with metadata
- **Save / download / use as reference** workflow
- **Responsive** — works on desktop and mobile

## Supported Backends

| Backend | Type | Cost | Notes |
|---------|------|------|-------|
| **ComfyUI** | Local | Free | Most flexible — supports checkpoints, GGUF, LoRA, IP-Adapter, ControlNet |
| **Fooocus** | Local | Free | Simple setup, good defaults, image prompt support |
| **A1111 WebUI** | Local | Free | Mature ecosystem with extensions |
| **Gemini** | Cloud | Free tier | Nano Banana, Nano Banana Pro, Imagen 4 models |
| **HuggingFace** | Cloud | Free credits | Community models via Inference API |
| **Pollinations** | Cloud | Token required | Flux and Turbo models |
| **Stability AI** | Cloud | Paid | SDXL, Stable Image Core |
| **OpenAI** | Cloud | Paid | DALL-E 3, GPT Image 1 |
| **Replicate** | Cloud | Paid | Flux Pro, SDXL, and many more |

## Local Models

### Checkpoints (full models)

Place in `ComfyUI/models/checkpoints/`:

| Model | Size | Resolution | Steps | CFG | Best For |
|-------|------|-----------|-------|-----|----------|
| SD 1.5 | 4.0 GB | 512x512 | 20 | 7.0 | Fast drafts, stylised art |
| SDXL 1.0 | 6.5 GB | 1024x1024 | 25 | 7.0 | All-rounder |
| Juggernaut XL v9 | 6.7 GB | 1024x1024 | 30 | 6.0 | Photorealism, people, products |
| RealVisXL V4 | 6.5 GB | 1024x1024 | 28 | 5.5 | Portraits, architecture, nature |
| DreamShaper XL Turbo | 746 MB | 1024x1024 | 8 | 2.0 | Fast iteration, versatile style |

### GGUF Quantized Models (lower VRAM)

Place in `ComfyUI/models/unet/`. Requires [ComfyUI-GGUF](https://github.com/city96/ComfyUI-GGUF) custom node.

| Model | Size | VRAM | Steps | CFG | Best For |
|-------|------|------|-------|-----|----------|
| Flux.1 Dev Q4 | ~5.5 GB | 6 GB | 20 | 3.5 | State-of-the-art quality, text rendering |
| Flux.1 Dev Q5 | ~7 GB | 8 GB | 20 | 3.5 | Higher fidelity than Q4 |
| Flux.1 Dev Q8 | ~12 GB | 12 GB+ | 20 | 3.5 | Near-lossless (CPU offload on 8GB GPU) |
| Flux.1 Schnell Q4 | ~5.5 GB | 6 GB | 4 | 1.0 | Ultra-fast drafts (4 steps!) |
| SD3 Medium Q4 | ~2 GB | 5 GB | 28 | 7.0 | Different aesthetic, good prompt adherence |
| SDXL Lightning 4-step | ~5 GB | 7 GB | 4 | 1.0 | Ultra-fast, LoRA compatible |

**Flux models also need:**
- T5-XXL encoder (GGUF): `ComfyUI/models/clip/t5-v1_1-xxl-encoder-Q4_K_M.gguf` ([download](https://huggingface.co/city96/t5-v1_1-xxl-encoder-gguf))
- CLIP-L: `ComfyUI/models/clip/clip_l.safetensors`
- Flux VAE: `ComfyUI/models/vae/ae.safetensors` ([download](https://huggingface.co/black-forest-labs/FLUX.1-dev) — requires HF login + license acceptance)

**SDXL GGUF models also need:**
- CLIP-L + CLIP-G: `ComfyUI/models/clip/clip_l.safetensors`, `clip_g.safetensors`
- SDXL VAE: `ComfyUI/models/vae/sdxl_vae.safetensors`

### LoRA Style Models

Place in `ComfyUI/models/loras/`. Work with any SDXL-based model (checkpoints or GGUF).

| LoRA | Effect | Recommended Strength |
|------|--------|---------------------|
| Pixel Art XL | Pixel art / retro game style | 0.7 - 1.0 |
| Anime Detailer XL | Anime/manga illustration | 0.6 - 0.9 |
| Flat Color / Vector | Clean flat colours, vector-like | 0.5 - 0.8 |
| Film Grain / Cinematic | 35mm film grain, cinematic look | 0.3 - 0.6 |

Select a LoRA from the Advanced Settings panel. Adjust strength to control how strongly the style is applied (0 = no effect, 1+ = strong effect).

### Installing New Models

**Checkpoints:** Download `.safetensors` files into `ComfyUI/models/checkpoints/`. Add to `config.yaml` under `backends.comfyui.models.checkpoints`. Add optimal defaults in `static/js/app.js` `MODEL_DEFAULTS` object.

**GGUF models:** Download `.gguf` files into `ComfyUI/models/unet/`. Add to `config.yaml` under `backends.comfyui.models.checkpoints` (same list — the backend detects `.gguf` extension and uses the UNet loader). Add defaults to `MODEL_DEFAULTS`.

**LoRAs:** Download `.safetensors` LoRA files into `ComfyUI/models/loras/`. Add to `config.yaml` under `backends.comfyui.models.loras`. LoRAs are compatible with SDXL checkpoints and SDXL GGUF models (not Flux or SD3).

**Cloud models:** Add model IDs to the relevant backend section in `config.yaml`. No file download needed.

After adding models, restart ComfyUI (`systemctl --user restart comfyui`) and refresh Open Palette in the browser.

## Configuration

Copy `config.example.yaml` to `config.yaml` and edit:

```yaml
backends:
  comfyui:
    enabled: true
    url: "http://127.0.0.1:8188"  # your ComfyUI instance

  gemini:
    enabled: true
    api_key: ""  # or set GEMINI_API_KEY env var
```

API keys can also be managed from the **Settings** page in the UI (`/settings`).

### Environment Variables

| Variable | Backend |
|----------|---------|
| `GEMINI_API_KEY` | Google Gemini / Imagen |
| `OPENAI_API_KEY` | OpenAI DALL-E |
| `STABILITY_API_KEY` | Stability AI |
| `HF_TOKEN` or `HUGGINGFACE_API_KEY` | HuggingFace |
| `REPLICATE_API_TOKEN` | Replicate |
| `POLLINATIONS_API_KEY` | Pollinations |

### Running as a System Service

```bash
# Create systemd user service
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/open-palette.service << 'EOF'
[Unit]
Description=Open Palette
After=network.target
[Service]
Type=simple
WorkingDirectory=/path/to/open-palette
ExecStart=/usr/bin/python3 server.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=/path/to/.env  # optional, for API keys
[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now open-palette
```

Also run ComfyUI as a service for persistent local generation:

```bash
cat > ~/.config/systemd/user/comfyui.service << 'EOF'
[Unit]
Description=ComfyUI
After=network.target
[Service]
Type=simple
WorkingDirectory=/path/to/ComfyUI
ExecStart=/usr/bin/python3 main.py --listen 0.0.0.0 --port 8188
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now comfyui
```

## Architecture

```
Browser (localhost:7860)
    |
    v
Open Palette (FastAPI + WebSocket)
    |
    +-- ComfyUI API (local GPU)
    |     +-- Checkpoints (SD 1.5, SDXL, Juggernaut, RealVis, DreamShaper)
    |     +-- GGUF models (Flux.1, SD3, SDXL Lightning)
    |     +-- LoRAs (Pixel Art, Anime, Film Grain, etc.)
    |     +-- IP-Adapter (reference image conditioning)
    |     +-- Upscalers (RealESRGAN, UltraSharp)
    |
    +-- Gemini API (cloud)
    +-- HuggingFace API (cloud)
    +-- ... other cloud APIs
```

All generation is async. The server submits jobs, tracks progress via WebSocket, and streams updates to the browser. Generated images are saved with full metadata (JSON sidecar + embedded PNG tEXt chunks).

ComfyUI handles its own job queue — multiple requests are serialized automatically, swapping models in/out of VRAM as needed.

## Requirements

- Python 3.10+
- For local generation: NVIDIA GPU with 6GB+ VRAM (8GB+ recommended)
- For cloud-only: no GPU needed

## License

MIT
