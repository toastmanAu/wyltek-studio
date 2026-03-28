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
    """Return all configured backends and their models."""
    result = {}
    for name, backend_cfg in config.get("backends", {}).items():
        if not backend_cfg.get("enabled", False):
            continue
        info = {"models": backend_cfg.get("models", []), "type": _backend_type(name)}
        # For comfyui, flatten model categories
        if name == "comfyui" and isinstance(info["models"], dict):
            info["model_categories"] = info["models"]
            info["models"] = info["models"].get("checkpoints", [])
        result[name] = info
    return result


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

        # Save metadata alongside image
        meta = {**params, "job_id": job_id, "created": datetime.now().isoformat()}
        meta.pop("reference_images", None)  # don't store temp paths
        async with aiofiles.open(output_path.with_suffix(".json"), "w") as f:
            await f.write(json.dumps(meta, indent=2))

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
