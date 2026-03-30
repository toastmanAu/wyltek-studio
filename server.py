#!/usr/bin/env python3
"""Wyltek Studio — local-first AI creative studio."""

import asyncio
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

import aiofiles
import uvicorn
import yaml
from fastapi import FastAPI, File, Form, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backends import registry
from job_queue import JobQueue

# Global state
config = {}
jobs: dict[str, dict] = {}  # job_id -> status
ws_clients: list[WebSocket] = []
job_queue = JobQueue()
_gallery_cache: dict = {"items": None, "ts": 0.0}
GALLERY_TTL = 10  # seconds — also invalidated on job completion


def load_config():
    global config
    cfg_path = Path(__file__).parent / "config.yaml"
    if not cfg_path.exists():
        cfg_path = Path(__file__).parent / "config.example.yaml"
    with open(cfg_path) as f:
        config = yaml.safe_load(f)
    os.makedirs(config["server"]["output_dir"], exist_ok=True)
    os.makedirs("uploads", exist_ok=True)


from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app):
    load_config()
    registry.init_backends(config.get("backends", {}))
    import storage as store
    store.init()
    import scoring
    scoring.DB_PATH = store.db_path("scores.db")
    scoring.init_db()
    from studio import tts_registry
    tts_registry.init_engines(config.get("tts", {}))
    yield


app = FastAPI(title="Wyltek Studio", lifespan=lifespan)


# --- Static files & SPA ---

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")
app.mount("/audio", StaticFiles(directory="outputs/audio"), name="audio")


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/settings")
async def settings_page():
    return FileResponse("static/settings.html")


@app.get("/files")
async def files_page():
    return FileResponse("static/files.html")


@app.get("/projects")
async def projects_page():
    return FileResponse("static/projects.html")


@app.get("/studio/tts")
async def tts_page():
    return FileResponse("static/studio/tts.html")


# --- Settings API ---

ENV_KEY_MAP = {
    "pollinations": "POLLINATIONS_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "huggingface": "HF_TOKEN",
    "stability": "STABILITY_API_KEY",
    "openai": "OPENAI_API_KEY",
    "replicate": "REPLICATE_API_TOKEN",
}


@app.get("/api/settings")
async def get_settings():
    """Return backend settings (keys masked)."""
    result = {}
    for name, cfg in config.get("backends", {}).items():
        entry = {
            "enabled": cfg.get("enabled", False),
            "url": cfg.get("url", ""),
            "api_key": cfg.get("api_key", ""),
            "has_env_key": bool(os.environ.get(ENV_KEY_MAP.get(name, ""), "")),
        }
        result[name] = entry
    return result


@app.post("/api/settings")
async def save_settings(request: Request):
    """Save backend settings to config.yaml."""
    request_data = await request.json()
    if not request_data:
        return JSONResponse({"error": "No data"}, status_code=400)

    name = request_data.get("backend")
    if not name or name not in config.get("backends", {}):
        return JSONResponse({"error": "Unknown backend"}, status_code=400)

    backend_cfg = config["backends"][name]

    if "enabled" in request_data:
        backend_cfg["enabled"] = request_data["enabled"]
    if "api_key" in request_data and request_data["api_key"]:
        backend_cfg["api_key"] = request_data["api_key"]
    if "url" in request_data:
        backend_cfg["url"] = request_data["url"]

    # Save to config.yaml
    cfg_path = Path(__file__).parent / "config.yaml"
    with open(cfg_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    # Reinitialize backends
    registry.init_backends(config.get("backends", {}))

    return {"ok": True}


@app.post("/api/settings/test")
async def test_backend_key(request: Request):
    """Test an API key against a backend."""
    request_data = await request.json()
    if not request_data:
        return JSONResponse({"error": "No data"}, status_code=400)

    name = request_data.get("backend", "")
    api_key = request_data.get("api_key", "") or os.environ.get(ENV_KEY_MAP.get(name, ""), "")

    if not api_key:
        return {"ok": False, "error": "No API key provided"}

    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            if name == "gemini":
                resp = await client.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}")
                if resp.status_code == 200:
                    return {"ok": True, "message": "Gemini API key valid"}
                return {"ok": False, "error": f"HTTP {resp.status_code}"}
            elif name == "openai":
                resp = await client.get("https://api.openai.com/v1/models",
                                        headers={"Authorization": f"Bearer {api_key}"})
                if resp.status_code == 200:
                    return {"ok": True, "message": "OpenAI API key valid"}
                return {"ok": False, "error": f"HTTP {resp.status_code}"}
            elif name == "stability":
                resp = await client.get("https://api.stability.ai/v1/user/account",
                                        headers={"Authorization": f"Bearer {api_key}"})
                if resp.status_code == 200:
                    return {"ok": True, "message": "Stability AI key valid"}
                return {"ok": False, "error": f"HTTP {resp.status_code}"}
            elif name == "replicate":
                resp = await client.get("https://api.replicate.com/v1/account",
                                        headers={"Authorization": f"Bearer {api_key}"})
                if resp.status_code == 200:
                    return {"ok": True, "message": "Replicate token valid"}
                return {"ok": False, "error": f"HTTP {resp.status_code}"}
            elif name == "huggingface":
                resp = await client.get("https://huggingface.co/api/whoami-v2",
                                        headers={"Authorization": f"Bearer {api_key}"})
                if resp.status_code == 200:
                    return {"ok": True, "message": "HuggingFace token valid"}
                return {"ok": False, "error": f"HTTP {resp.status_code}"}
            elif name == "pollinations":
                resp = await client.get(f"https://image.pollinations.ai/prompt/test?key={api_key}&nologo=true&width=64&height=64")
                if resp.status_code == 200:
                    return {"ok": True, "message": "Pollinations key valid"}
                return {"ok": False, "error": f"HTTP {resp.status_code}"}
            else:
                return {"ok": False, "error": "No test available for this backend"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# --- API ---

@app.get("/api/backends")
async def get_backends():
    """Return all configured backends with live model discovery."""
    result = {}
    for name, backend_cfg in config.get("backends", {}).items():
        enabled = backend_cfg.get("enabled", False)
        info = {"models": backend_cfg.get("models", []), "type": _backend_type(name), "enabled": enabled}

        if name == "comfyui" and isinstance(info["models"], dict):
            info["model_categories"] = info["models"]
            info["models"] = info["models"].get("checkpoints", [])

        # Probe ComfyUI for actually-installed models
        if name == "comfyui":
            live = await _probe_comfyui(backend_cfg.get("url", ""))
            if live:
                info["enabled"] = True
                info["live_models"] = live
                # Mark each configured model as available or not
                all_available = set(live.get("checkpoints", []) + live.get("unets", []))
                for m in info["models"]:
                    mid = m["id"] if isinstance(m, dict) else m
                    if isinstance(m, dict):
                        m["available"] = mid in all_available
                    # Add discovered models not in config
                for discovered in live.get("checkpoints", []):
                    if not any((m["id"] if isinstance(m, dict) else m) == discovered for m in info["models"]):
                        info["models"].append({"id": discovered, "label": discovered.replace(".safetensors", "").replace(".gguf", ""), "available": True, "discovered": True})
                # Same for ip_adapters, upscalers, clip_vision
                if "model_categories" in info:
                    for cat in ("ip_adapters", "upscalers", "loras"):
                        live_cat = live.get(cat, [])
                        for m in info["model_categories"].get(cat, []):
                            m["available"] = m["id"] in live_cat
                        for discovered in live_cat:
                            existing = info["model_categories"].get(cat, [])
                            if not any(m["id"] == discovered for m in existing):
                                existing.append({"id": discovered, "label": discovered.rsplit(".", 1)[0], "available": True, "discovered": True})
                # Models to hide from discovery (broken at current quantization, etc.)
                _hidden = backend_cfg.get("hidden_models", set())
                # Add GGUF unets as checkpoints too
                for unet in live.get("unets", []):
                    if unet in _hidden:
                        continue
                    if not any((m["id"] if isinstance(m, dict) else m) == unet for m in info["models"]):
                        info["models"].append({"id": unet, "label": unet.replace(".gguf", " (GGUF)").replace(".safetensors", ""), "available": True, "discovered": True, "format": "gguf" if unet.endswith(".gguf") else "safetensors"})

        result[name] = info
    return result


_comfyui_probe_cache: dict = {"data": None, "ts": 0.0, "url": ""}
PROBE_TTL = 60  # seconds


async def _probe_comfyui(url: str) -> dict | None:
    """Query ComfyUI for installed models (cached for 60s)."""
    if not url:
        return None
    now = time.monotonic()
    if (_comfyui_probe_cache["data"] is not None
            and _comfyui_probe_cache["url"] == url
            and now - _comfyui_probe_cache["ts"] < PROBE_TTL):
        return _comfyui_probe_cache["data"]
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{url.rstrip('/')}/object_info")
            if resp.status_code != 200:
                return None
            data = resp.json()
            result = {}
            # Checkpoints
            ckpt = data.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [])
            if ckpt and isinstance(ckpt[0], list):
                result["checkpoints"] = ckpt[0]
            # UNets (for GGUF)
            unet = data.get("UNETLoader", {}).get("input", {}).get("required", {}).get("unet_name", [])
            if unet and isinstance(unet[0], list):
                result["unets"] = unet[0]
            # GGUF UNet loader
            gguf_unet = data.get("UnetLoaderGGUF", {}).get("input", {}).get("required", {}).get("unet_name", [])
            if gguf_unet and isinstance(gguf_unet[0], list):
                result["unets"] = list(set(result.get("unets", []) + gguf_unet[0]))
            # IP-Adapters
            ipa = data.get("IPAdapterModelLoader", {}).get("input", {}).get("required", {}).get("ipadapter_file", [])
            if ipa and isinstance(ipa[0], list):
                result["ip_adapters"] = ipa[0]
            # Upscalers
            up = data.get("UpscaleModelLoader", {}).get("input", {}).get("required", {}).get("model_name", [])
            if up and isinstance(up[0], list):
                result["upscalers"] = up[0]
            # CLIP vision
            clip_v = data.get("CLIPVisionLoader", {}).get("input", {}).get("required", {}).get("clip_name", [])
            if clip_v and isinstance(clip_v[0], list):
                result["clip_vision"] = clip_v[0]
            # LoRAs
            lora = data.get("LoraLoader", {}).get("input", {}).get("required", {}).get("lora_name", [])
            if lora and isinstance(lora[0], list):
                result["loras"] = lora[0]
            _comfyui_probe_cache.update({"data": result, "ts": now, "url": url})
            return result
    except Exception:
        return None


@app.get("/api/gallery")
async def get_gallery():
    """Return list of generated images with metadata (cached)."""
    now = time.monotonic()
    if _gallery_cache["items"] is not None and now - _gallery_cache["ts"] < GALLERY_TTL:
        return _gallery_cache["items"]

    import storage as store
    # Gallery pulls from unsorted (recent quick generations)
    # plus the old outputs/ dir for backwards compat during migration
    items = []
    for item in store.list_unsorted(limit=50):
        if item["type"] == "image":
            items.append({
                "filename": item["filename"],
                "url": item["url"],
                "created": item["created"],
                "meta": item.get("meta", {}),
            })

    # Also check legacy outputs/ dir
    legacy_dir = Path(config["server"]["output_dir"])
    if legacy_dir.exists():
        for img in sorted(legacy_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True):
            if any(i["filename"] == img.name for i in items):
                continue
            meta_path = img.with_suffix(".json")
            meta = {}
            if meta_path.exists():
                with open(meta_path) as f:
                    meta = json.load(f)
            items.append({
                "filename": img.name,
                "url": f"/outputs/{img.name}",
                "created": datetime.fromtimestamp(img.stat().st_mtime).isoformat(),
                "meta": meta,
            })

    items.sort(key=lambda x: x["created"], reverse=True)
    result = items[:50]
    _gallery_cache.update({"items": result, "ts": now})
    return result


@app.post("/api/generate")
async def generate(
    prompt: str = Form(...),
    negative_prompt: str = Form(""),
    backend: str = Form("comfyui"),
    model: str = Form(""),
    width: int = Form(1024),
    height: int = Form(1024),
    steps: int = Form(30),
    cfg_scale: float = Form(7.0),
    seed: int = Form(-1),
    ip_adapter_model: str = Form(""),
    ip_adapter_strength: float = Form(0.6),
    upscaler: str = Form(""),
    lora_model: str = Form(""),
    lora_strength: float = Form(0.8),
    lora_strength_model: float = Form(0.0),
    lora_strength_clip: float = Form(0.0),
    reference_images: list[UploadFile] = File(default=[]),
):
    """Start an image generation job."""
    job_id = str(uuid.uuid4())[:8]

    # Save uploaded reference images
    ref_paths = []
    for i, ref in enumerate(reference_images):
        if ref.filename and ref.size and ref.size > 0:
            ext = Path(ref.filename).suffix or ".png"
            path = Path("uploads") / f"{job_id}_ref{i}{ext}"
            async with aiofiles.open(path, "wb") as f:
                await f.write(await ref.read())
            ref_paths.append(str(path))

    params = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "backend": backend,
        "model": model,
        "width": width,
        "height": height,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "seed": seed,
        "ip_adapter_model": ip_adapter_model,
        "ip_adapter_strength": ip_adapter_strength,
        "upscaler": upscaler,
        "lora_model": lora_model,
        "lora_strength": lora_strength,
        "lora_strength_model": lora_strength_model if lora_strength_model > 0 else 0,
        "lora_strength_clip": lora_strength_clip if lora_strength_clip > 0 else 0,
        "reference_images": ref_paths,
    }

    jobs[job_id] = {"status": "queued", "params": params, "progress": 0}
    job_queue.submit_background(_run_job(job_id, params), lane="gpu", job_id=job_id)

    return {"job_id": job_id}


@app.get("/api/queue")
async def get_queue_status():
    """Current queue status across all resource lanes."""
    return job_queue.status()


@app.get("/api/job/{job_id}")
async def get_job(job_id: str):
    """Poll job status."""
    if job_id not in jobs:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    result = dict(jobs[job_id])
    # Add queue position for queued/running jobs
    pos = job_queue.position(job_id)
    if pos:
        result["queue"] = pos
    return result


# --- Scoring API (static paths first, then parameterized) ---

@app.get("/api/scores/models")
async def get_model_profiles():
    """Aggregated average scores per model."""
    import scoring
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, scoring.get_model_profiles)


@app.get("/api/scores/compare")
async def compare_scores(job_ids: str = ""):
    """Scores for multiple jobs."""
    import scoring
    ids = [j.strip() for j in job_ids.split(",") if j.strip()]
    if not ids:
        return []
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, scoring.get_scores_batch, ids)


@app.get("/api/scores/{job_id}")
async def get_image_scores(job_id: str):
    """Scores for a single image."""
    import scoring
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, scoring.get_scores, job_id)
    if not result:
        return JSONResponse({"error": "Scores not found"}, status_code=404)
    return result


# --- Prompt Optimizer API ---

@app.get("/api/op-prompt/status")
async def op_prompt_status():
    """Check if prompt optimizer is available."""
    opt_config = config.get("prompt_optimizer", {})
    if not opt_config.get("enabled", False):
        return {"available": False, "reason": "disabled in config"}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{opt_config.get('ollama_url', 'http://localhost:11434')}/api/tags")
            if resp.status_code == 200:
                models = [m["name"] for m in resp.json().get("models", [])]
                target = opt_config.get("model", "qwen2.5:14b")
                available = any(target in m for m in models)
                return {"available": available, "model": target,
                        "reason": "" if available else f"Model {target} not found in Ollama"}
    except Exception:
        pass
    return {"available": False, "reason": "Ollama not reachable"}


@app.get("/api/op-prompt/config")
async def get_op_config():
    """Return prompt optimizer config + installed Ollama models."""
    opt_config = config.get("prompt_optimizer", {})
    result = {
        "enabled": opt_config.get("enabled", False),
        "ollama_url": opt_config.get("ollama_url", ""),
        "model": opt_config.get("model", ""),
        "installed_models": [],
    }
    # Try to list installed Ollama models
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{result['ollama_url']}/api/tags")
            if resp.status_code == 200:
                result["installed_models"] = [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        pass
    return result


@app.post("/api/op-prompt/config")
async def save_op_config(request: Request):
    """Save prompt optimizer config."""
    data = await request.json()
    if "prompt_optimizer" not in config:
        config["prompt_optimizer"] = {}
    if "enabled" in data:
        config["prompt_optimizer"]["enabled"] = data["enabled"]
    if "ollama_url" in data and data["ollama_url"]:
        config["prompt_optimizer"]["ollama_url"] = data["ollama_url"]
    if "model" in data and data["model"]:
        config["prompt_optimizer"]["model"] = data["model"]

    # Save to config.yaml
    cfg_path = Path(__file__).parent / "config.yaml"
    with open(cfg_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    return {"ok": True}


@app.post("/api/op-prompt")
async def op_prompt(request: Request):
    """Enhance a prompt using local Ollama LLM."""
    opt_config = config.get("prompt_optimizer", {})
    if not opt_config.get("enabled", False):
        return JSONResponse({"error": "Prompt optimizer not enabled"}, status_code=503)

    data = await request.json()
    user_prompt = data.get("prompt", "").strip()
    target_model = data.get("model", "")

    if not user_prompt:
        return JSONResponse({"error": "No prompt provided"}, status_code=400)

    ollama_url = opt_config.get("ollama_url", "http://localhost:11434")
    ollama_model = opt_config.get("model", "qwen2.5:14b")

    system_prompt = f"""You are an expert Stable Diffusion prompt engineer. The user will give you an image generation prompt. Your job is to enhance it for maximum quality.

The target generation model is: {target_model or 'unknown'}

Rules:
- Add specific quality descriptors (lighting, composition, detail level, style)
- Remove ambiguity — make vague descriptions concrete
- Keep the user's core intent intact
- Suggest a negative prompt to avoid common artifacts
- Be concise — SD prompts work best under 75 tokens

Respond ONLY with valid JSON (no markdown, no code fences):
{{"enhanced_prompt": "...", "negative_prompt": "...", "changes_made": "brief explanation of what you improved"}}"""

    import re
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": user_prompt,
                    "system": system_prompt,
                    "stream": False,
                    "options": {"temperature": 0.3},
                },
            )
            if resp.status_code != 200:
                return JSONResponse({"error": f"Ollama error: {resp.status_code}"}, status_code=502)
            result = resp.json()
            response_text = result.get("response", "")

            # Parse JSON from response (handle potential markdown wrapping)
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                return {
                    "enhanced_prompt": parsed.get("enhanced_prompt", user_prompt),
                    "negative_prompt": parsed.get("negative_prompt", ""),
                    "changes_made": parsed.get("changes_made", ""),
                    "original_prompt": user_prompt,
                }
            return JSONResponse({"error": "Failed to parse LLM response", "raw": response_text}, status_code=500)
    except httpx.TimeoutException:
        return JSONResponse({"error": "Ollama timed out (30s)"}, status_code=504)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# --- Model Catalog / Download API ---

_download_status: dict[str, dict] = {}  # model_id -> {status, progress, error}


@app.get("/api/models/catalog")
async def get_model_catalog():
    """Return model catalog with install status."""
    from model_catalog import CATALOG, DEST_MAP
    from pathlib import Path

    comfyui_url = config.get("backends", {}).get("comfyui", {}).get("url", "")
    comfyui_root = None
    # Try to find ComfyUI root from known paths
    for candidate in [Path("/home/phill/ComfyUI"), Path.home() / "ComfyUI"]:
        if candidate.exists():
            comfyui_root = candidate
            break

    # Check installed Ollama models
    ollama_models = set()
    try:
        import httpx
        ollama_url = config.get("prompt_optimizer", {}).get("ollama_url", "http://[::1]:11434")
        resp = await asyncio.get_event_loop().run_in_executor(
            None, lambda: __import__('httpx').Client(timeout=5).get(f"{ollama_url}/api/tags"))
        if resp.status_code == 200:
            ollama_models = {m["name"] for m in resp.json().get("models", [])}
    except Exception:
        pass

    result = []
    for item in CATALOG:
        entry = dict(item)
        entry.pop("url", None)  # don't expose download URLs to frontend
        entry.pop("meta_url", None)

        # Check if installed
        if item["type"] == "ollama":
            entry["installed"] = any(item.get("ollama_model", "") in m for m in ollama_models)
        elif item["type"] == "piper-voice":
            voice_path = Path(__file__).parent / "engines" / "voices" / item["filename"]
            entry["installed"] = voice_path.exists()
        elif comfyui_root and item["type"] in DEST_MAP and DEST_MAP[item["type"]]:
            dest = comfyui_root / DEST_MAP[item["type"]] / item["filename"]
            entry["installed"] = dest.exists()
        else:
            entry["installed"] = False

        # Add download status if active
        if item["id"] in _download_status:
            entry["download"] = _download_status[item["id"]]

        result.append(entry)

    return result


@app.post("/api/models/download/{model_id}")
async def download_model(model_id: str):
    """Start downloading a model from the catalog."""
    from model_catalog import CATALOG, DEST_MAP
    from pathlib import Path

    item = next((m for m in CATALOG if m["id"] == model_id), None)
    if not item:
        return JSONResponse({"error": "Model not found in catalog"}, status_code=404)

    if model_id in _download_status and _download_status[model_id].get("status") == "downloading":
        return JSONResponse({"error": "Already downloading"}, status_code=409)

    _download_status[model_id] = {"status": "downloading", "progress": 0}

    async def _do_download():
        try:
            if item["type"] == "ollama":
                # Pull via Ollama API
                ollama_url = config.get("prompt_optimizer", {}).get("ollama_url", "http://[::1]:11434")
                import httpx
                async with httpx.AsyncClient(timeout=600) as client:
                    _download_status[model_id]["progress"] = 10
                    resp = await client.post(
                        f"{ollama_url}/api/pull",
                        json={"name": item["ollama_model"], "stream": False},
                        timeout=600,
                    )
                    if resp.status_code == 200:
                        _download_status[model_id] = {"status": "complete", "progress": 100}
                    else:
                        _download_status[model_id] = {"status": "error", "error": f"Ollama error: {resp.status_code}"}
                return

            # File download (HuggingFace)
            url = item.get("url", "")
            if not url:
                _download_status[model_id] = {"status": "error", "error": "No download URL"}
                return

            # Determine destination
            if item["type"] == "piper-voice":
                dest_dir = Path(__file__).parent / "engines" / "voices"
            else:
                comfyui_root = None
                for candidate in [Path("/home/phill/ComfyUI"), Path.home() / "ComfyUI"]:
                    if candidate.exists():
                        comfyui_root = candidate
                        break
                if not comfyui_root:
                    _download_status[model_id] = {"status": "error", "error": "ComfyUI not found"}
                    return
                dest_dir = comfyui_root / DEST_MAP[item["type"]]

            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / item["filename"]

            import httpx
            async with httpx.AsyncClient(timeout=600, follow_redirects=True) as client:
                async with client.stream("GET", url) as resp:
                    if resp.status_code != 200:
                        _download_status[model_id] = {"status": "error", "error": f"HTTP {resp.status_code}"}
                        return
                    total = int(resp.headers.get("content-length", 0))
                    downloaded = 0
                    with open(dest, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=1024 * 1024):
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total > 0:
                                _download_status[model_id]["progress"] = int(downloaded / total * 100)

            # Download metadata file for Piper voices
            if item["type"] == "piper-voice" and item.get("meta_url"):
                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                    resp = await client.get(item["meta_url"])
                    if resp.status_code == 200:
                        meta_dest = dest_dir / (item["filename"] + ".json")
                        with open(meta_dest, "wb") as f:
                            f.write(resp.content)

            _download_status[model_id] = {"status": "complete", "progress": 100}

        except Exception as e:
            _download_status[model_id] = {"status": "error", "error": str(e)}

    job_queue.submit_background(_do_download(), lane="cpu", job_id=f"dl-{model_id}")
    return {"ok": True, "model_id": model_id}


@app.get("/api/models/download/{model_id}/status")
async def download_status(model_id: str):
    """Check download progress."""
    if model_id in _download_status:
        return _download_status[model_id]
    return {"status": "idle"}


# --- Storage / File Manager API ---

@app.get("/api/projects")
async def api_list_projects():
    """List all projects."""
    import storage as store
    return store.list_projects()


@app.post("/api/projects")
async def api_create_project(request: Request):
    """Create a new project."""
    import storage as store
    data = await request.json()
    name = data.get("name", "").strip()
    if not name:
        return JSONResponse({"error": "Project name required"}, status_code=400)
    meta = store.create_project(name, data.get("description", ""))
    return meta


@app.get("/api/projects/{project_id}")
async def api_get_project(project_id: str):
    """Get project details with asset counts."""
    import storage as store
    meta = store.get_project(project_id)
    if not meta:
        return JSONResponse({"error": "Project not found"}, status_code=404)
    return meta


@app.put("/api/projects/{project_id}")
async def api_update_project(project_id: str, request: Request):
    """Update project metadata."""
    import storage as store
    data = await request.json()
    meta = store.update_project(project_id, data)
    if not meta:
        return JSONResponse({"error": "Project not found"}, status_code=404)
    return meta


@app.delete("/api/projects/{project_id}")
async def api_delete_project(project_id: str):
    """Delete a project and all its assets."""
    import storage as store
    if store.delete_project(project_id):
        return {"ok": True}
    return JSONResponse({"error": "Project not found"}, status_code=404)


@app.get("/api/projects/{project_id}/assets")
async def api_project_assets(project_id: str):
    """List all assets in a project."""
    import storage as store
    return store.list_project_assets(project_id)


@app.post("/api/projects/{project_id}/move")
async def api_move_asset(project_id: str, request: Request):
    """Move an asset into a project."""
    import storage as store
    data = await request.json()
    filename = data.get("filename", "")
    if not filename:
        return JSONResponse({"error": "filename required"}, status_code=400)
    if store.move_asset(filename, project_id):
        return {"ok": True}
    return JSONResponse({"error": "Asset not found"}, status_code=404)


@app.get("/api/unsorted")
async def api_list_unsorted():
    """List recent unsorted assets."""
    import storage as store
    return store.list_unsorted(limit=100)


@app.get("/storage/{filename:path}")
async def serve_storage_file(filename: str):
    """Serve any file from storage by filename (searches projects + unsorted)."""
    import storage as store
    path = store.resolve_asset(filename)
    if path and path.exists():
        return FileResponse(str(path))
    return JSONResponse({"error": "File not found"}, status_code=404)


# --- TTS API ---

@app.get("/api/tts/engines")
async def get_tts_engines():
    """List installed TTS engines and their voices."""
    from studio import tts_registry
    return tts_registry.list_engines()


@app.post("/api/tts/generate")
async def tts_generate(request: Request):
    """Generate speech from text. Returns audio file URL."""
    data = await request.json()
    text = data.get("text", "").strip()
    engine_name = data.get("engine", "piper")
    voice = data.get("voice", "")
    speed = float(data.get("speed", 1.0))

    if not text:
        return JSONResponse({"error": "No text provided"}, status_code=400)

    from studio import tts_registry
    engine = tts_registry.get_engine(engine_name)
    if not engine:
        return JSONResponse({"error": f"Engine '{engine_name}' not available"}, status_code=400)

    # Auto-select first voice if none specified
    if not voice:
        voices = engine.voices()
        if not voices:
            return JSONResponse({"error": "No voices installed"}, status_code=400)
        voice = voices[0]["id"]

    job_id = str(uuid.uuid4())[:8]
    import storage as store
    output_path = str(store.asset_path(job_id, "audio", ".wav"))

    async def _do_tts():
        return await engine.generate(text, voice, output_path, speed)

    try:
        meta = await job_queue.submit(_do_tts(), lane="cpu", job_id=f"tts-{job_id}")
        return {
            "job_id": job_id,
            "url": f"/storage/{job_id}.wav",
            "engine": engine_name,
            "voice": voice,
            "text": text,
            **meta,
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/tts/compare")
async def tts_compare(request: Request):
    """Generate same text across multiple voices/engines for comparison."""
    data = await request.json()
    text = data.get("text", "").strip()
    selections = data.get("selections", [])  # [{engine, voice}]

    if not text:
        return JSONResponse({"error": "No text provided"}, status_code=400)
    if not selections:
        return JSONResponse({"error": "No voices selected"}, status_code=400)

    from studio import tts_registry
    results = []

    for sel in selections:
        engine = tts_registry.get_engine(sel.get("engine", "piper"))
        if not engine:
            continue
        voice = sel.get("voice", "")
        job_id = str(uuid.uuid4())[:8]
        import storage as store
        output_path = str(store.asset_path(job_id, "audio", ".wav"))

        try:
            meta = await job_queue.submit(
                engine.generate(text, voice, output_path, float(data.get("speed", 1.0))),
                lane="cpu", job_id=f"tts-{job_id}"
            )
            results.append({
                "job_id": job_id,
                "url": f"/storage/{job_id}.wav",
                "engine": sel.get("engine"),
                "voice": voice,
                **meta,
            })
        except Exception as e:
            results.append({
                "engine": sel.get("engine"),
                "voice": voice,
                "error": str(e),
            })

    return {"text": text, "results": results}


@app.post("/api/compare")
async def compare(
    prompt: str = Form(...),
    negative_prompt: str = Form(""),
    backends_json: str = Form("[]"),
    width: int = Form(1024),
    height: int = Form(1024),
    steps: int = Form(30),
    cfg_scale: float = Form(7.0),
    seed: int = Form(-1),
    reference_images: list[UploadFile] = File(default=[]),
):
    """Launch same prompt across multiple backends for comparison."""
    import json as _json
    backend_list = _json.loads(backends_json)  # [{backend, model}, ...]

    # Save uploaded reference images once
    ref_paths = []
    for i, ref in enumerate(reference_images):
        if ref.filename and ref.size and ref.size > 0:
            ext = Path(ref.filename).suffix or ".png"
            cmp_id = str(uuid.uuid4())[:6]
            path = Path("uploads") / f"cmp_{cmp_id}_ref{i}{ext}"
            async with aiofiles.open(path, "wb") as f:
                await f.write(await ref.read())
            ref_paths.append(str(path))

    comparison_id = str(uuid.uuid4())[:8]
    job_ids = []

    for entry in backend_list:
        job_id = str(uuid.uuid4())[:8]
        params = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "backend": entry["backend"],
            "model": entry.get("model", ""),
            "width": width,
            "height": height,
            "steps": steps,
            "cfg_scale": cfg_scale,
            "seed": seed,
            "ip_adapter_model": "",
            "ip_adapter_strength": 0.6,
            "upscaler": "",
            "reference_images": ref_paths,
        }
        jobs[job_id] = {"status": "queued", "params": params, "progress": 0, "comparison_id": comparison_id}
        job_queue.submit_background(_run_job(job_id, params), lane="gpu", job_id=job_id)
        job_ids.append({"job_id": job_id, "backend": entry["backend"], "model": entry.get("model", "")})

    return {"comparison_id": comparison_id, "jobs": job_ids}


# --- WebSocket for live progress ---

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        ws_clients.remove(ws)


async def broadcast(msg: dict):
    for ws in ws_clients[:]:
        try:
            await ws.send_json(msg)
        except Exception:
            ws_clients.remove(ws)


# --- Job runner ---

MAX_FINISHED_JOBS = 200


def _evict_old_jobs():
    """Remove oldest completed/errored jobs when exceeding limit."""
    finished = [(jid, j) for jid, j in jobs.items() if j["status"] in ("complete", "error")]
    if len(finished) <= MAX_FINISHED_JOBS:
        return
    # Sort by creation (job_id order is chronological via uuid, but use insertion order)
    for jid, _ in finished[:-MAX_FINISHED_JOBS]:
        del jobs[jid]


async def _run_job(job_id: str, params: dict):
    _evict_old_jobs()
    jobs[job_id]["status"] = "running"
    await broadcast({"type": "job_update", "job_id": job_id, "status": "running", "progress": 0})

    try:
        backend_name = params["backend"]
        backend = registry.get_backend(backend_name)
        if not backend:
            raise ValueError(f"Backend '{backend_name}' not available")

        import storage as store
        output_path = store.asset_path(job_id, "image", ".png")

        async def on_progress(pct: int, msg: str = ""):
            jobs[job_id]["progress"] = pct
            await broadcast({
                "type": "job_update", "job_id": job_id,
                "status": "running", "progress": pct, "message": msg,
            })

        await backend.generate(params, str(output_path), on_progress)

        # Save metadata alongside image + embed in PNG
        meta = {**params, "job_id": job_id, "created": datetime.now().isoformat()}
        ref_count = len(meta.pop("reference_images", []))
        meta["reference_image_count"] = ref_count
        async with aiofiles.open(output_path.with_suffix(".json"), "w") as f:
            await f.write(json.dumps(meta, indent=2))

        # Embed metadata in PNG tEXt chunks (survives file sharing)
        try:
            from PIL import Image
            from PIL.PngImagePlugin import PngInfo
            img = Image.open(output_path)
            png_meta = PngInfo()
            png_meta.add_text("prompt", meta["prompt"])
            if meta.get("negative_prompt"):
                png_meta.add_text("negative_prompt", meta["negative_prompt"])
            png_meta.add_text("backend", meta.get("backend", ""))
            png_meta.add_text("model", meta.get("model", ""))
            png_meta.add_text("steps", str(meta.get("steps", "")))
            png_meta.add_text("cfg_scale", str(meta.get("cfg_scale", "")))
            png_meta.add_text("seed", str(meta.get("seed", "")))
            png_meta.add_text("size", f"{meta.get('width', '')}x{meta.get('height', '')}")
            if ref_count > 0:
                png_meta.add_text("reference_images", str(ref_count))
            png_meta.add_text("generator", "Wyltek Studio")
            img.save(output_path, pnginfo=png_meta)
        except Exception:
            pass  # metadata embedding is best-effort

        # Score the image (~50ms, runs in thread executor)
        scores = None
        try:
            import scoring
            scores = await scoring.score_and_save(
                str(output_path), job_id, params.get("model", ""),
                params.get("backend", ""), params.get("prompt", ""),
                meta["created"],
            )
        except Exception:
            pass  # scoring is best-effort

        _gallery_cache["items"] = None  # invalidate gallery cache
        jobs[job_id].update({
            "status": "complete",
            "progress": 100,
            "output_url": f"/storage/{job_id}.png",
            "scores": scores,
        })
        await broadcast({
            "type": "job_update", "job_id": job_id,
            "status": "complete", "progress": 100,
            "output_url": f"/storage/{job_id}.png",
            "scores": scores,
        })

    except Exception as e:
        jobs[job_id].update({"status": "error", "error": str(e)})
        await broadcast({
            "type": "job_update", "job_id": job_id,
            "status": "error", "error": str(e),
        })


def _backend_type(name: str) -> str:
    local = {"comfyui", "fooocus", "a1111"}
    free = {"pollinations", "huggingface"}
    if name in local:
        return "local"
    if name in free:
        return "free"
    return "paid"


if __name__ == "__main__":
    load_config()
    uvicorn.run("server:app", host=config["server"]["host"],
                port=config["server"]["port"], reload=True)
