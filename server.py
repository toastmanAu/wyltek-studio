#!/usr/bin/env python3
"""Open Palette — local-first AI image generation studio."""

import asyncio
import json
import os
import uuid
from datetime import datetime
from pathlib import Path

import aiofiles
import uvicorn
import yaml
from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backends import registry

# Global state
config = {}
jobs: dict[str, dict] = {}  # job_id -> status
ws_clients: list[WebSocket] = []


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
    yield


app = FastAPI(title="Open Palette", lifespan=lifespan)


# --- Static files & SPA ---

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")


@app.get("/")
async def index():
    return FileResponse("static/index.html")


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
                for m in info["models"]:
                    mid = m["id"] if isinstance(m, dict) else m
                    if isinstance(m, dict):
                        m["available"] = mid in live.get("checkpoints", [])
                    # Add discovered models not in config
                for discovered in live.get("checkpoints", []):
                    if not any((m["id"] if isinstance(m, dict) else m) == discovered for m in info["models"]):
                        info["models"].append({"id": discovered, "label": discovered.replace(".safetensors", "").replace(".gguf", ""), "available": True, "discovered": True})
                # Same for ip_adapters, upscalers, clip_vision
                if "model_categories" in info:
                    for cat in ("ip_adapters", "upscalers"):
                        live_cat = live.get(cat, [])
                        for m in info["model_categories"].get(cat, []):
                            m["available"] = m["id"] in live_cat
                        for discovered in live_cat:
                            existing = info["model_categories"].get(cat, [])
                            if not any(m["id"] == discovered for m in existing):
                                existing.append({"id": discovered, "label": discovered.rsplit(".", 1)[0], "available": True, "discovered": True})
                # Add GGUF unets as checkpoints too
                for unet in live.get("unets", []):
                    if not any((m["id"] if isinstance(m, dict) else m) == unet for m in info["models"]):
                        info["models"].append({"id": unet, "label": unet.replace(".gguf", " (GGUF)").replace(".safetensors", ""), "available": True, "discovered": True, "format": "gguf" if unet.endswith(".gguf") else "safetensors"})

        result[name] = info
    return result


async def _probe_comfyui(url: str) -> dict | None:
    """Query ComfyUI for installed models."""
    if not url:
        return None
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
            return result
    except Exception:
        return None


@app.get("/api/gallery")
async def get_gallery():
    """Return list of generated images with metadata."""
    output_dir = Path(config["server"]["output_dir"])
    items = []
    for img in sorted(output_dir.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True):
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
    return items[:50]


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
        "reference_images": ref_paths,
    }

    jobs[job_id] = {"status": "queued", "params": params, "progress": 0}
    asyncio.create_task(_run_job(job_id, params))

    return {"job_id": job_id}


@app.get("/api/job/{job_id}")
async def get_job(job_id: str):
    """Poll job status."""
    if job_id not in jobs:
        return JSONResponse({"error": "Job not found"}, status_code=404)
    return jobs[job_id]


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
        asyncio.create_task(_run_job(job_id, params))
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

async def _run_job(job_id: str, params: dict):
    jobs[job_id]["status"] = "running"
    await broadcast({"type": "job_update", "job_id": job_id, "status": "running", "progress": 0})

    try:
        backend_name = params["backend"]
        backend = registry.get_backend(backend_name)
        if not backend:
            raise ValueError(f"Backend '{backend_name}' not available")

        output_path = Path(config["server"]["output_dir"]) / f"{job_id}.png"

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
            png_meta.add_text("generator", "Open Palette")
            img.save(output_path, pnginfo=png_meta)
        except Exception:
            pass  # metadata embedding is best-effort

        jobs[job_id].update({
            "status": "complete",
            "progress": 100,
            "output_url": f"/outputs/{job_id}.png",
        })
        await broadcast({
            "type": "job_update", "job_id": job_id,
            "status": "complete", "progress": 100,
            "output_url": f"/outputs/{job_id}.png",
        })

    except Exception as e:
        jobs[job_id].update({"status": "error", "error": str(e)})
        await broadcast({
            "type": "job_update", "job_id": job_id,
            "status": "error", "error": str(e),
        })


def _backend_type(name: str) -> str:
    local = {"comfyui", "fooocus", "a1111", "ollama"}
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
