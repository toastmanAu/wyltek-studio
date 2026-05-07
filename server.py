#!/usr/bin/env python3
"""Wyltek Studio — local-first AI creative studio."""

import asyncio
import base64
import json
import os
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path

import aiofiles
import uvicorn
import yaml
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import health_actions
import storage as store
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


# 3D job timeouts — empirically tuned per engine/mode. The OUTER timeout
# (asyncio.wait_for in JobQueue) MUST be larger than the INNER timeout
# (ComfyUI poll in backends/comfyui.py) so that on a healthy completion
# the inner finishes first and the outer never fires. 180s slack covers
# post-completion copy, sidecar write, and gallery cache invalidation.
#
# Keys: ("engine", "mode-flag")
# Values: inner ComfyUI-poll timeout in seconds (outer = inner + 180)
#
# Note: TRELLIS terminology in our code is "shape"/"textured" (mirroring
# Hy3D's "shape"/"pbr" UX). The plan that authored this table used "white"
# for TRELLIS shape-only — corrected here to match actual mode_3d values.
_3D_INNER_TIMEOUTS = {
    ("trellis", "textured"): 3000,  # ~32 min observed on 7900 XTX
    ("trellis", "shape"):     600,  # ~1–2 min observed
    ("hy3d",    "pbr"):      2100,  # ~3–5 min typical, 35 min hard cap
    ("hy3d",    "shape"):     300,  # ~30s typical
    ("worldgen", "t2s"):      540,  # ~3 min observed at 1024 panorama; bump for higher res
    ("worldgen", "i2s"):      540,
}
_3D_INNER_TIMEOUT_DEFAULT = 1800
_3D_OUTER_HANDOFF_SLACK = 180


def resolve_3d_timeouts(engine: str, mode_flag: str) -> tuple[int, int]:
    """Return (outer_job_timeout, inner_comfy_timeout) in seconds.

    `engine` is "trellis" or "hy3d". `mode_flag` is the resolved per-engine
    mode-string used by the inner backend ("textured"/"shape" for TRELLIS,
    "pbr"/"shape" for Hy3D). Outer is always inner + slack so a healthy run
    never trips the outer.
    """
    inner = _3D_INNER_TIMEOUTS.get((engine, mode_flag), _3D_INNER_TIMEOUT_DEFAULT)
    return inner + _3D_OUTER_HANDOFF_SLACK, inner


# --- Static files & SPA ---

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")
app.mount("/audio", StaticFiles(directory="outputs/audio"), name="audio")
app.mount("/data/sample-packs", StaticFiles(directory="data/sample-packs"), name="sample-packs")


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


@app.get("/studio/music")
async def music_page():
    return FileResponse("static/studio/music.html")


@app.get("/studio/video")
async def video_page():
    return FileResponse("static/studio/video.html")


@app.get("/studio/meme")
async def meme_page():
    return FileResponse("static/studio/meme.html")


@app.get("/studio/frames")
async def frames_page():
    return FileResponse("static/studio/frames.html")


@app.get("/studio/image-edit")
async def image_edit_page():
    return FileResponse("static/studio/image-edit.html")


@app.get("/studio/image-tools")
async def image_tools_legacy_redirect():
    """Back-compat alias — old bookmarks / sessionStorage 'imagetools-source'
    code paths still hit /studio/image-tools. Redirect to the new home."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/studio/image-edit", status_code=308)


@app.get("/studio/video-tools")
async def video_tools_page():
    return FileResponse("static/studio/video-tools.html")


@app.get("/studio/audio")
async def audio_page():
    return FileResponse("static/studio/audio.html")


@app.get("/studio/beats")
async def beats_page():
    return FileResponse("static/studio/beats.html")


@app.get("/studio/remix")
async def remix_page():
    return FileResponse("static/studio/remix.html")


@app.get("/studio/worldgen")
async def worldgen_page():
    return FileResponse("static/studio/worldgen.html")


@app.get("/studio/mesh-edit")
async def mesh_edit_page():
    return FileResponse("static/studio/mesh-edit.html")


@app.get("/api/worldgen/status")
async def api_worldgen_status():
    """Report whether the WorldGen subprocess backend is ready to accept jobs."""
    from pathlib import Path

    repo = Path("/home/phill/repos/WorldGen")
    smoke_log = Path("/tmp/worldgen-smoke2.log")

    if not repo.exists():
        return {"ready": False, "reason": "WorldGen repo not cloned at ~/repos/WorldGen"}

    # Check our patched modules exist
    patched_files = [
        repo / "src/worldgen/pano_gen.py",
        repo / "src/worldgen/utils/lora_utils.py",
        repo / "src/worldgen/utils/splat_utils.py",
    ]
    missing = [str(p) for p in patched_files if not p.exists()]
    if missing:
        return {"ready": False, "reason": f"WorldGen source incomplete: missing {missing}"}

    # Smoke-test status — set to true once a successful end-to-end run lands a mesh
    smoke_ok_marker = Path("/data/wyltek/worldgen/smoke_ok")
    if not smoke_ok_marker.exists():
        return {
            "ready": False,
            "reason": "End-to-end smoke test not yet verified on this machine. "
                      "Run scripts/worldgen_smoke.sh to populate /data/wyltek/worldgen/smoke_ok.",
        }

    return {
        "ready": True,
        "notes": (
            "Subprocess executor live. Typical run 3-5 min; first request after "
            "boot triggers FLUX.1-dev pipeline build (~5s + denoise time)."
        ),
    }


@app.post("/api/worldgen")
async def api_worldgen(
    prompt: str = Form(""),
    mode: str = Form("t2s"),
    resolution: int = Form(1600),
    seed: int = Form(42),
    output_format: str = Form("mesh"),
    reference_image: UploadFile | None = File(None),
):
    """Queue a Worldgen scene generation job.

    Routes through the same job_queue + _run_job pipeline as 3D Hy3D/TRELLIS
    jobs (engine="worldgen"). Output GLB lands in storage/unsorted/<date>/meshes/
    and the gallery picks it up automatically.
    """
    from pathlib import Path as _P
    from uuid import uuid4

    if mode == "t2s" and not prompt.strip():
        raise HTTPException(400, "text-to-scene mode requires a prompt")
    if mode == "i2s" and not reference_image:
        raise HTTPException(400, "image-to-scene mode requires a reference image")

    job_id = str(uuid4())
    params: dict = {
        "backend": "worldgen",
        "engine": "worldgen",
        "mode": "3d",                 # routes through is_3d branch in _run_job
        "worldgen_mode": mode,        # t2s vs i2s for the worker
        "mode_3d": mode,              # used by resolve_3d_timeouts
        "prompt": prompt,
        "resolution": resolution,
        "seed": seed,
        "output_format": output_format,
        "reference_images": [],
    }

    # Persist any uploaded reference image into a per-job staging dir, then
    # pass its path through to the worker via params["reference_images"].
    if reference_image:
        ref_dir = _P("/tmp/worldgen-refs") / job_id
        ref_dir.mkdir(parents=True, exist_ok=True)
        suffix = _P(reference_image.filename or "ref.png").suffix or ".png"
        ref_path = ref_dir / f"ref0{suffix}"
        async with aiofiles.open(ref_path, "wb") as f:
            await f.write(await reference_image.read())
        params["reference_images"] = [str(ref_path)]

    jobs[job_id] = {"status": "queued", "progress": 0, "params": params}
    outer, _inner = resolve_3d_timeouts("worldgen", mode)
    job_queue.submit_background(_run_job(job_id, params), lane="gpu",
                                job_id=job_id, timeout=outer)
    return {"job_id": job_id}


@app.post("/api/audio/extract")
async def api_audio_extract(
    video: UploadFile = File(...),
    format: str = Form("mp3"),
    quality: str = Form("192k"),
) -> JSONResponse:
    """Extract audio track from an uploaded video file using ffmpeg."""
    import storage as store

    allowed_formats = {"mp3", "wav", "flac", "ogg"}
    if format not in allowed_formats:
        return JSONResponse({"error": f"Unsupported format: {format}"}, status_code=400)

    suffix = Path(video.filename or "upload").suffix or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_in:
        tmp_in.write(await video.read())
        tmp_in_path = Path(tmp_in.name)

    out_stem = f"audio-{uuid.uuid4().hex[:8]}"
    out_path = store.unsorted_dir() / f"{out_stem}.{format}"

    # Build ffmpeg args as a list — no shell, no injection risk.
    # format is validated against an allowlist above.
    try:
        cmd = ["ffmpeg", "-y", "-i", str(tmp_in_path)]
        if format == "mp3":
            cmd += ["-q:a", "0", "-b:a", quality]
        elif format == "ogg":
            cmd += ["-c:a", "libvorbis", "-b:a", quality]
        elif format == "flac":
            cmd += ["-c:a", "flac"]
        # wav: default pcm_s16le, no extra codec flags needed
        cmd += ["-vn", str(out_path)]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            return JSONResponse(
                {"error": "ffmpeg failed", "detail": stderr.decode()[-500:]},
                status_code=500,
            )
    finally:
        tmp_in_path.unlink(missing_ok=True)

    size_kb = out_path.stat().st_size // 1024
    return JSONResponse({
        "path": str(out_path),
        "filename": out_path.name,
        "format": format,
        "size_kb": size_kb,
    })


@app.post("/api/audio/cut")
async def api_audio_cut(
    audio: UploadFile = File(...),
    start: float = Form(0.0),
    end: float = Form(...),
) -> JSONResponse:
    """Trim an audio file to the given start/end times (seconds) using ffmpeg."""
    import storage as store

    if end <= start:
        return JSONResponse({"error": "end must be after start"}, status_code=400)
    if start < 0:
        return JSONResponse({"error": "start must be >= 0"}, status_code=400)

    suffix = Path(audio.filename or "audio.mp3").suffix or ".mp3"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_in:
        tmp_in.write(await audio.read())
        tmp_in_path = Path(tmp_in.name)

    out_stem = f"cut-{uuid.uuid4().hex[:8]}"
    out_path = store.unsorted_dir() / f"{out_stem}{suffix}"

    # -ss before -i is fast stream seek; -t limits duration.
    # -c copy avoids re-encode — instant cuts for mp3/wav/flac.
    try:
        duration = end - start
        proc = await asyncio.create_subprocess_exec(
            "ffmpeg", "-y",
            "-ss", str(start),
            "-t", str(duration),
            "-i", str(tmp_in_path),
            "-c", "copy",
            str(out_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            return JSONResponse(
                {"error": "ffmpeg failed", "detail": stderr.decode()[-500:]},
                status_code=500,
            )
    finally:
        tmp_in_path.unlink(missing_ok=True)

    size_kb = out_path.stat().st_size // 1024
    return JSONResponse({
        "path": str(out_path),
        "filename": out_path.name,
        "duration": duration,
        "size_kb": size_kb,
    })


@app.get("/api/audio/serve")
async def api_audio_serve(path: str) -> FileResponse:
    """Serve a processed audio file by absolute path, restricted to storage."""
    p = Path(path).resolve()
    try:
        _assert_under_storage(p)
    except PermissionError:
        return JSONResponse({"error": "Access denied"}, status_code=403)
    if not p.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    return FileResponse(str(p))


# Whitelist of rembg session names accepted by /api/image/bg-remove. Keep in
# sync with the dropdown in static/studio/image-tools.html. New models in
# rembg's sessions_class registry (e.g. via rembg upgrade) need to be added
# here AND in the UI before they're selectable. Verify with:
#   /data/venvs/rembg/bin/python -c "from rembg.sessions import sessions_class; \
#       print(sorted(s.name() for s in sessions_class))"
_REMBG_MODELS = {
    # BiRefNet family — modern SOTA, recommended defaults
    "birefnet-general", "birefnet-general-lite", "birefnet-massive",
    "birefnet-portrait", "birefnet-dis", "birefnet-hrsod", "birefnet-cod",
    # BRIA RMBG-2.0 — non-commercial license but very strong
    "bria-rmbg",
    # ISNet family
    "isnet-general-use", "isnet-anime",
    # u2net family — older but fast
    "u2net", "u2netp", "u2net_human_seg",
    # Other fast options
    "silueta",
}

_REMBG_BIN = Path("/data/venvs/rembg/bin/rembg")


def _assert_under_storage(p: Path) -> None:
    import storage as store
    if not str(p.resolve()).startswith(str(store.STORAGE_ROOT.resolve())):
        raise PermissionError("Path outside storage root")


@app.post("/api/frame/grab")
async def api_frame_grab(request: Request):
    """Save a base64-encoded PNG frame to unsorted storage and return the path."""
    import storage as store

    data = await request.json()
    b64: str = data.get("image_b64", "")
    timestamp: float = float(data.get("timestamp", 0.0))

    if not b64:
        return JSONResponse({"error": "No image data"}, status_code=400)

    img_bytes = base64.b64decode(b64)
    ts_str = f"{timestamp:.3f}".replace(".", "s")
    filename = f"frame-{ts_str}-{uuid.uuid4().hex[:6]}.png"
    out_path = store.unsorted_dir() / filename
    out_path.write_bytes(img_bytes)

    return JSONResponse({"path": str(out_path), "filename": filename})


@app.get("/api/frame/serve")
async def api_frame_serve(path: str):
    """Serve a saved image by absolute path, restricted to the storage directory."""
    p = Path(path).resolve()
    try:
        _assert_under_storage(p)
    except PermissionError:
        return JSONResponse({"error": "Access denied"}, status_code=403)
    if not p.exists():
        return JSONResponse({"error": "Not found"}, status_code=404)
    return FileResponse(str(p))


@app.post("/api/image/bg-remove")
async def api_image_bg_remove(request: Request):
    """Remove background from an image using rembg (local, no network)."""
    import storage as store

    if not _REMBG_BIN.exists():
        return JSONResponse({"error": "rembg not installed at /data/venvs/rembg/"}, status_code=503)

    data = await request.json()
    model: str = data.get("model", "u2net")
    alpha_matting: bool = bool(data.get("alpha_matting", False))

    if model not in _REMBG_MODELS:
        return JSONResponse({"error": f"Unknown model: {model}"}, status_code=400)

    # Resolve input: server path or base64
    tmp_path: Path | None = None
    if "path" in data:
        in_path = Path(data["path"]).resolve()
        try:
            _assert_under_storage(in_path)
        except PermissionError:
            return JSONResponse({"error": "Access denied"}, status_code=403)
        if not in_path.exists():
            return JSONResponse({"error": "Source file not found"}, status_code=404)
    elif "image_b64" in data:
        img_bytes = base64.b64decode(data["image_b64"])
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.write(img_bytes)
        tmp.close()
        tmp_path = Path(tmp.name)
        in_path = tmp_path
    else:
        return JSONResponse({"error": "No image source provided"}, status_code=400)

    out_filename = f"{in_path.stem}-nobg-{uuid.uuid4().hex[:6]}.png"
    out_path = store.unsorted_dir() / out_filename

    # Build command — using exec (not shell=True) so no injection risk
    cmd = [str(_REMBG_BIN), "i", "-m", model]
    if alpha_matting:
        cmd.append("--alpha-matting")
    cmd += [str(in_path), str(out_path)]

    t0 = time.time()
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        elapsed_ms = int((time.time() - t0) * 1000)

        # rembg exits 0 even on CUDA warnings; success = output file exists
        if not out_path.exists():
            lines = stderr.decode(errors="replace").strip().splitlines()
            last = lines[-1] if lines else "rembg produced no output"
            return JSONResponse({"error": last}, status_code=500)

        result_url = f"/api/frame/serve?path={out_path}"
        return JSONResponse({
            "result_url": result_url,
            "filename": out_filename,
            "elapsed_ms": elapsed_ms,
        })
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


_IOPAINT_BIN = Path("/data/venvs/iopaint/bin/iopaint")


@app.post("/api/image/object-remove")
async def api_image_object_remove(request: Request):
    """Remove an object from an image via iopaint/LaMa.

    Body: {path, mask_b64}. The white pixels in mask_b64 are removed and
    inpainted by LaMa. Mask is auto-resized to source by iopaint.
    """
    import storage as store
    import shutil as _shutil

    if not _IOPAINT_BIN.exists():
        return JSONResponse(
            {"error": "iopaint not installed at /data/venvs/iopaint/"},
            status_code=503,
        )

    data = await request.json()
    mask_b64: str = data.get("mask_b64", "")
    if not mask_b64:
        return JSONResponse({"error": "mask_b64 required"}, status_code=400)
    # SAM2 produces pixel-tight masks; LaMa needs a few px margin to avoid
    # bleeding the object's edge back into the fill. Default 8 px is gentle
    # enough that loose brush/lasso masks aren't visibly affected. Caller
    # can pass 0 to disable.
    mask_dilate: int = int(data.get("mask_dilate", 8))

    # Resolve input: storage path or inline base64 (mirrors /api/image/bg-remove).
    upload_tmp: Path | None = None
    if "path" in data:
        in_path = Path(data["path"]).resolve()
        try:
            _assert_under_storage(in_path)
        except PermissionError:
            return JSONResponse({"error": "Access denied"}, status_code=403)
        if not in_path.exists():
            return JSONResponse({"error": "Source file not found"}, status_code=404)
    elif "image_b64" in data:
        img_bytes = base64.b64decode(data["image_b64"])
        upload_tmp = Path(tempfile.mkstemp(suffix=".png", prefix="objrm-src-")[1])
        upload_tmp.write_bytes(img_bytes)
        in_path = upload_tmp
    else:
        return JSONResponse({"error": "path or image_b64 required"}, status_code=400)

    out_filename = f"{in_path.stem}-objrm-{uuid.uuid4().hex[:6]}.png"
    out_path = store.unsorted_dir() / out_filename

    # iopaint takes file paths; stage image + mask in matched dirs.
    tmp_dir = Path(tempfile.mkdtemp(prefix="iopaint-"))
    img_dir = tmp_dir / "img"; img_dir.mkdir()
    mask_dir = tmp_dir / "mask"; mask_dir.mkdir()
    out_dir = tmp_dir / "out"; out_dir.mkdir()
    src_link = img_dir / in_path.name
    src_link.symlink_to(in_path)
    # Mask basename must match the image basename (iopaint dir-mode rule).
    mask_path = mask_dir / in_path.name
    mask_path.write_bytes(base64.b64decode(mask_b64))
    if mask_dilate > 0:
        from PIL import Image as _PIL, ImageFilter as _ImageFilter
        # MaxFilter kernel size must be odd. Convert px radius → kernel size.
        ksize = max(3, mask_dilate * 2 + 1)
        if ksize % 2 == 0:
            ksize += 1
        m = _PIL.open(mask_path).convert("L")
        m = m.filter(_ImageFilter.MaxFilter(size=ksize))
        m.save(mask_path)

    cmd = [
        str(_IOPAINT_BIN), "run",
        "--model", "lama",
        "--device", "cpu",
        "--image", str(img_dir),
        "--mask", str(mask_dir),
        "--output", str(out_dir),
    ]

    t0 = time.time()
    try:
        # Argv list, no shell — same safe pattern as /api/image/bg-remove.
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        elapsed_ms = int((time.time() - t0) * 1000)

        produced = next(out_dir.glob("*.png"), None)
        if produced is None:
            lines = stderr.decode(errors="replace").strip().splitlines()
            last = lines[-1] if lines else "iopaint produced no output"
            return JSONResponse({"error": last}, status_code=500)

        produced.rename(out_path)
        return JSONResponse({
            "result_url": f"/api/frame/serve?path={out_path}",
            "filename": out_filename,
            "output_path": str(out_path),
            "elapsed_ms": elapsed_ms,
        })
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    finally:
        _shutil.rmtree(tmp_dir, ignore_errors=True)
        if upload_tmp and upload_tmp.exists():
            upload_tmp.unlink(missing_ok=True)


_SAM_MODEL_PATH = Path.home() / "ComfyUI/models/sams/sam_vit_l_0b3195.pth"
_SAM2_CHECKPOINT = Path.home() / "ComfyUI/models/sams/sam2.1_hiera_large.pt"
_SAM2_CONFIG = "configs/sam2.1/sam2.1_hiera_l.yaml"
_sam_predictor = None  # loaded lazily, kept in memory
_sam2_predictor = None  # SAM2 predictor, lazy


def _load_sam():
    global _sam_predictor
    if _sam_predictor is not None:
        return _sam_predictor
    import torch
    from segment_anything import sam_model_registry, SamPredictor
    sam = sam_model_registry["vit_l"](checkpoint=str(_SAM_MODEL_PATH))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    sam.to(device=device)
    _sam_predictor = SamPredictor(sam)
    return _sam_predictor


def _load_sam2():
    """Load SAM2.1 hiera-large lazily; reuse across requests."""
    global _sam2_predictor
    if _sam2_predictor is not None:
        return _sam2_predictor
    import torch
    from sam2.build_sam import build_sam2
    from sam2.sam2_image_predictor import SAM2ImagePredictor
    device = "cuda" if torch.cuda.is_available() else "cpu"
    sam2_model = build_sam2(_SAM2_CONFIG, str(_SAM2_CHECKPOINT), device=device)
    _sam2_predictor = SAM2ImagePredictor(sam2_model)
    return _sam2_predictor


@app.post("/api/image/sam-segment")
async def api_image_sam_segment(request: Request):
    """Click-to-segment. Prefers SAM2.1 (hiera-large), falls back to SAM v1
    if the SAM2 checkpoint is missing. Returns a B&W mask PNG as base64."""
    import io
    import numpy as np

    use_sam2 = _SAM2_CHECKPOINT.exists()
    if not use_sam2 and not _SAM_MODEL_PATH.exists():
        return JSONResponse(
            {"error": "No SAM checkpoint found at ~/ComfyUI/models/sams/"},
            status_code=503,
        )

    data = await request.json()
    click_x: int = int(data.get("x", 0))
    click_y: int = int(data.get("y", 0))

    # Sensitivity knobs:
    #  - mask_size: 'auto' (default; pick by SAM confidence), or
    #               'small'/'medium'/'large' (pick by mask area). SAM returns
    #               3 ambiguity-aware masks per click — for a dog-fur click
    #               that's roughly (the brown patch / the leg / the whole dog).
    #  - dilate: int pixels. Positive = grow mask outward, negative = erode.
    #            Useful for tightening tight selections or feathering edges.
    mask_size = str(data.get("mask_size", "auto")).lower()
    dilate = int(data.get("dilate", 0))
    if mask_size not in ("auto", "small", "medium", "large"):
        mask_size = "auto"
    dilate = max(-30, min(30, dilate))

    # Resolve image. Three accepted forms:
    #  - path: absolute filesystem path (legacy, used by image-tools)
    #  - url: /storage/<...> URL — resolved via the shared storage helper
    #         so callers like remix.js don't need to round-trip pixels
    #         through base64 just to point SAM at a server-resident asset
    #  - image_b64: pixels embedded in the request body (any source)
    tmp_path: Path | None = None
    if "path" in data:
        in_path = Path(data["path"]).resolve()
        try:
            _assert_under_storage(in_path)
        except PermissionError:
            return JSONResponse({"error": "Access denied"}, status_code=403)
        if not in_path.exists():
            return JSONResponse({"error": "File not found"}, status_code=404)
    elif "url" in data:
        resolved = _resolve_storage_url(data["url"])
        if resolved is None:
            return JSONResponse({"error": "Image URL did not resolve"}, status_code=404)
        in_path = resolved
    elif "image_b64" in data:
        img_bytes = base64.b64decode(data["image_b64"])
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.write(img_bytes)
        tmp.close()
        tmp_path = Path(tmp.name)
        in_path = tmp_path
    else:
        return JSONResponse({"error": "No image source"}, status_code=400)

    try:
        def _run_sam() -> tuple[str, str]:
            from PIL import Image as PILImage
            img_pil = PILImage.open(in_path).convert("RGB")
            img_np = np.array(img_pil)

            if use_sam2:
                predictor = _load_sam2()
                predictor.set_image(img_np)
                masks, scores, _ = predictor.predict(
                    point_coords=np.array([[click_x, click_y]]),
                    point_labels=np.array([1]),
                    multimask_output=True,
                )
                backend = "sam2.1"
            else:
                predictor = _load_sam()
                predictor.set_image(img_np)
                masks, scores, _ = predictor.predict(
                    point_coords=np.array([[click_x, click_y]]),
                    point_labels=np.array([1]),
                    multimask_output=True,
                )
                backend = "sam_v1"

            # Pick the mask. 'auto' = SAM's highest-confidence; sized
            # selectors ('small'/'medium'/'large') sort the 3 multimasks
            # by area and pick rank 0/1/2. Lets the user dial in "the
            # brown patch" vs "the whole leg" vs "the whole animal".
            if mask_size == "auto":
                chosen = int(np.argmax(scores))
            else:
                areas = np.array([int(m.sum()) for m in masks])
                order = np.argsort(areas)  # ascending: small → large
                rank = {"small": 0, "medium": 1, "large": 2}[mask_size]
                chosen = int(order[min(rank, len(order) - 1)])
            best_mask = masks[chosen]
            mask_img = PILImage.fromarray((best_mask * 255).astype(np.uint8), mode="L")

            # Dilate/erode via PIL's morphological filters. MaxFilter grows
            # the white region; MinFilter shrinks it. Filter size is the
            # diameter, so radius=N → size=2N+1 (must be odd).
            if dilate != 0:
                from PIL import ImageFilter
                size = 2 * abs(dilate) + 1
                op = ImageFilter.MaxFilter(size) if dilate > 0 else ImageFilter.MinFilter(size)
                mask_img = mask_img.filter(op)

            buf = io.BytesIO()
            mask_img.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode(), backend

        mask_b64, backend = await asyncio.get_event_loop().run_in_executor(None, _run_sam)
        return JSONResponse({"mask_b64": mask_b64, "backend": backend})

    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


@app.get("/api/meme/templates")
async def api_meme_templates():
    """Return meme template definitions from templates.json."""
    templates_path = Path("static/images/meme-templates/templates.json")
    if templates_path.exists():
        async with aiofiles.open(templates_path) as f:
            return JSONResponse(json.loads(await f.read()))
    return JSONResponse([])


@app.post("/api/meme/generate")
async def api_meme_generate(request: Request):
    """Generate a meme image using a template with optional IP-Adapter conditioning."""
    import storage as store

    data = await request.json()
    template_id  = data.get("template_id", "")
    prompt       = data.get("prompt", "").strip()
    neg_prompt   = data.get("negative_prompt", "")
    model        = data.get("model", "")
    width        = int(data.get("width",  768))
    height       = int(data.get("height", 768))
    steps        = int(data.get("steps",  28))
    cfg          = float(data.get("cfg",  6.5))
    ip_strength  = float(data.get("ip_adapter_strength", 0.0))
    ip_wt        = data.get("ip_adapter_weight_type", "composition")
    ip_start     = float(data.get("ip_adapter_start", 0.0))
    ip_end       = float(data.get("ip_adapter_end", 0.75))
    ref_image    = data.get("reference_image", None)   # server-side static path

    if not prompt:
        return JSONResponse({"error": "prompt required"}, status_code=400)

    job_id     = str(uuid.uuid4())[:8]
    output_dir = str(Path("storage/unsorted") / datetime.now().strftime("%Y-%m-%d") / "images")

    jobs[job_id] = {
        "status": "queued", "progress": 0,
        "params": {"type": "meme_gen", "template_id": template_id, "prompt": prompt},
    }

    async def _run_meme_gen():
        jobs[job_id]["status"] = "running"
        await broadcast({"type": "job_update", "job_id": job_id,
                         "status": "running", "progress": 0})
        try:
            comfyui = registry.get_backend("comfyui")

            async def on_progress(pct, msg=""):
                jobs[job_id]["progress"] = pct
                await broadcast({"type": "job_update", "job_id": job_id,
                                 "status": "running", "progress": pct, "message": msg})

            # Resolve reference image to an absolute path ComfyUI can read
            ref_paths = []
            if ref_image:
                ref_abs = Path(ref_image.lstrip("/"))
                if ref_abs.exists():
                    ref_paths.append(str(ref_abs))

            meta = await comfyui.generate_sprites({
                "prompt":                   prompt,
                "model":                    model or "juggernautXL_v9",
                "negative_prompt":          neg_prompt,
                "batch_size":               1,
                "steps":                    steps,
                "cfg":                      cfg,
                "width":                    width,
                "height":                   height,
                "seed":                     data.get("seed", -1),
                "lora_strength":            float(data.get("lora_strength", 0.0)),
                "ip_adapter_strength":      ip_strength if ref_paths else 0.0,
                "ip_adapter_weight_type":   ip_wt,
                "ip_adapter_start":         ip_start,
                "ip_adapter_end":           ip_end,
                "reference_images":         ref_paths,
            }, output_dir, on_progress)

            import shutil
            urls = []
            for i, fpath in enumerate(meta.get("files", [])):
                dest = store.asset_path(f"{job_id}_{i}", "image", ".png")
                shutil.copy2(fpath, str(dest))
                urls.append(f"/storage/{job_id}_{i}.png")
                Path(fpath).unlink(missing_ok=True)

            output_url = urls[0] if urls else None
            jobs[job_id].update({
                "status": "complete", "progress": 100,
                "output_url": output_url, "urls": urls,
            })
            await broadcast({"type": "job_update", "job_id": job_id,
                             "status": "complete", "progress": 100,
                             "output_url": output_url, "urls": urls})
        except Exception as e:
            jobs[job_id].update({"status": "error", "error": str(e)})
            await broadcast({"type": "job_update", "job_id": job_id,
                             "status": "error", "error": str(e)})

    job_queue.submit_background(_run_meme_gen(), lane="gpu", job_id=f"meme-{job_id}")
    return {"job_id": job_id}


@app.get("/joyid-callback")
@app.get("/joyid-callback.html")
async def joyid_callback_page():
    return FileResponse("static/joyid-callback.html")



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
                    # Trigger-word lookup for auto-discovered LoRAs not in config.yaml.
                    # Distillation LoRAs (lightning, hyper) need no trigger; style LoRAs
                    # do. Discovered entries with no entry here ship trigger="".
                    _AUTO_LORA_TRIGGERS = {
                        "sdxl_lightning_4step_lora.safetensors": "",
                        "sdxl_lightning_8step_lora.safetensors": "",
                    }
                    for cat in ("ip_adapters", "upscalers", "loras"):
                        live_cat = live.get(cat, [])
                        for m in info["model_categories"].get(cat, []):
                            m["available"] = m["id"] in live_cat
                        for discovered in live_cat:
                            existing = info["model_categories"].get(cat, [])
                            if not any(m["id"] == discovered for m in existing):
                                entry = {"id": discovered, "label": discovered.rsplit(".", 1)[0], "available": True, "discovered": True}
                                if cat == "loras":
                                    entry["trigger"] = _AUTO_LORA_TRIGGERS.get(discovered, "")
                                existing.append(entry)
                # Models to hide from discovery (broken at current quantization, etc.)
                _hidden = backend_cfg.get("hidden_models", set())
                # Add GGUF unets as checkpoints too
                for unet in live.get("unets", []):
                    if unet in _hidden:
                        continue
                    if not any((m["id"] if isinstance(m, dict) else m) == unet for m in info["models"]):
                        info["models"].append({"id": unet, "label": unet.replace(".gguf", " (GGUF)").replace(".safetensors", ""), "available": True, "discovered": True, "format": "gguf" if unet.endswith(".gguf") else "safetensors"})

                # Surface 3D DiT models in their own list so the frontend's
                # 3D dropdown can be populated independently of 2D checkpoints.
                # We don't add these to `info["models"]` (the 2D list) — that's
                # exactly the bug we're fixing. Both Hy3D and TRELLIS land here;
                # the `engine` field tells the frontend which workflow to use.
                info["models_3d"] = []
                for entry in live.get("3d_models", []):
                    if entry in _hidden:
                        continue
                    if entry.startswith("trellis:"):
                        # Synthetic TRELLIS entry — auto-downloads on first use,
                        # so it's "available" without a file on disk. Quant
                        # format is picked separately via `trellis_format` form
                        # field; we surface it in the model label as a hint.
                        tname = entry.removeprefix("trellis:")
                        info["models_3d"].append({
                            "id": entry,
                            "label": f"{tname} (TRELLIS — quant configurable)",
                            "engine": "trellis",
                            "available": True,
                            "discovered": True,
                            "format": "managed",
                        })
                    else:
                        info["models_3d"].append({
                            "id": entry,
                            # Strip subfolder + extension for a readable label:
                            # "hy3dgen/hunyuan3d-dit-v2-0-fp16.safetensors"
                            # → "hunyuan3d-dit-v2-0-fp16"
                            "label": Path(entry).stem,
                            "engine": "hy3d",
                            "available": True,
                            "discovered": True,
                            "format": "safetensors" if entry.endswith(".safetensors") else "gguf",
                        })

            # Tag arch on every dict entry so the UI can ghost incompatible
            # combos in Compare mode. Additive; the generate path keeps its
            # own inline sniffs.
            from backends.arch import arch_of
            for m in info.get("models", []):
                if isinstance(m, dict) and "arch" not in m:
                    m["arch"] = arch_of(m.get("id", ""))
            for cat in ("ip_adapters", "upscalers", "loras"):
                for m in info.get("model_categories", {}).get(cat, []):
                    if isinstance(m, dict) and "arch" not in m:
                        m["arch"] = arch_of(m.get("id", ""))

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
            # 3D models — Hy3DModelLoader scans diffusion_models/ for the DiT.
            # We surface these in their OWN category so the frontend can route
            # picks to the 3D workflow instead of CheckpointLoaderSimple
            # (mismatched routing was the root cause of "Value not in list").
            #
            # Hy3DModelLoader's dropdown is the same folder as UNETLoader,
            # so it lists every diffusion_models file (Flux, Lightning, etc.) —
            # we filter to known 3D-mesh model patterns so the 3D dropdown
            # only contains things that will actually work in the Hy3D pipeline.
            hy3d = data.get("Hy3DModelLoader", {}).get("input", {}).get("required", {}).get("model", [])
            if hy3d and isinstance(hy3d[0], list):
                _3D_PATTERNS = ("hunyuan3d", "hy3d", "trellis")
                result["3d_models"] = [
                    m for m in hy3d[0]
                    if any(p in m.lower() for p in _3D_PATTERNS)
                ]
                # And subtract them from `unets` so they don't double-list as
                # 2D pickables — Hy3D files in diffusion_models/ aren't valid
                # 2D unets even though UNETLoader sees the same folder.
                if "unets" in result:
                    result["unets"] = [u for u in result["unets"] if u not in result["3d_models"]]
            else:
                result["3d_models"] = []

            # TRELLIS uses its own model_manager (auto-downloads from HuggingFace),
            # not the diffusion_models/ folder, so it doesn't surface via the
            # Hy3DModelLoader scan. Detect it by presence of its loader node and
            # synthesize a virtual entry so the UI can offer it as a 3D engine.
            trellis = data.get("Trellis2LoadModel_GGUF", {})
            if trellis:
                tr_modelnames = trellis.get("input", {}).get("required", {}).get("modelname", [])
                if tr_modelnames and isinstance(tr_modelnames[0], list):
                    for tname in tr_modelnames[0]:
                        # Use a "trellis:" prefix so the frontend can route picks
                        # to the trellis engine without separate dropdowns.
                        result["3d_models"].append(f"trellis:{tname}")
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
async def get_gallery(type: str = "image"):
    """Return list of generated assets with metadata (cached).

    Query param `type` filters by asset type: image (default — also includes
    3D meshes since they're visual outputs from the same Generate panel),
    audio, video, mesh, or all.
    """
    cache_key = f"gallery_{type}"
    now = time.monotonic()
    if _gallery_cache.get(cache_key) is not None and now - _gallery_cache["ts"] < GALLERY_TTL:
        return _gallery_cache[cache_key]

    # Type-name → set of asset types to include. The 'image' default includes
    # meshes so 3D outputs surface in the same gallery strip — they're produced
    # by the same Generate flow and the user mentally groups them together.
    type_groups = {
        "image": {"image", "mesh"},
        "visual": {"image", "mesh"},
        "mesh": {"mesh"},
        "audio": {"audio"},
        "video": {"video"},
        "all": None,  # no filter
    }
    allowed = type_groups.get(type, {type})

    import storage as store
    # Gallery pulls from unsorted (recent quick generations)
    # plus the old outputs/ dir for backwards compat during migration
    items = []
    for item in store.list_unsorted(limit=100):
        if allowed is not None and item["type"] not in allowed:
            continue
        items.append({
            "filename": item["filename"],
            "url": item["url"],
            "type": item["type"],
            "created": item["created"],
            "meta": item.get("meta", {}),
        })

    # Also check legacy outputs/ dir (images only)
    if type in ("image", "all"):
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
                    "type": "image",
                    "created": datetime.fromtimestamp(img.stat().st_mtime).isoformat(),
                    "meta": meta,
                })

    items.sort(key=lambda x: x["created"], reverse=True)
    result = items[:50]
    _gallery_cache.update({cache_key: result, "ts": now})
    return result


@app.post("/api/generate")
async def generate(
    prompt: str = Form(""),  # not required for 3D mode (image-conditioned)
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
    # 3D-mode fields. Default mode='2d' preserves the existing image
    # generation flow byte-for-byte; only mode='3d' enters a 3D engine path.
    mode: str = Form("2d"),
    mode_3d: str = Form("shape"),  # Hy3D: "shape"|"pbr"; TRELLIS: "shape"|"textured"
    engine: str = Form("hy3d"),     # "hy3d" | "trellis" — picks which 3D backend to use
    paint_model: str = Form("hunyuan3d-paint-v2-0"),  # Hy3D paint variant
    hy3d_cam_azimuths: str = Form(""),                # Hy3D advanced: camera azimuths CSV (empty = defaults)
    hy3d_cam_elevations: str = Form(""),              # Hy3D advanced: camera elevations CSV (empty = defaults)
    trellis_format: str = Form("GGUF Q4_K_M"),  # only used when engine='trellis'
    trellis_pipeline_type: str = Form("512"),    # "512" | "1024" | "1024_cascade"
    trellis_preset: str = Form("balanced"),      # quality preset bucket
    trellis_tweak_faithful: str = Form("0"),     # "1"|"0" — bump shape CFG
    trellis_tweak_fine_detail: str = Form("0"),  # "1"|"0" — bump voxel budget
    trellis_tweak_sharp_edges: str = Form("0"),  # "1"|"0" — switch to RK4 sampler
    auto_bg_removal: str = Form("1"),  # "1"|"0" — disable when uploading already-cut PNGs
    reference_images: list[UploadFile] = File(default=[]),
):
    """Start a generation job — 2D image or 3D mesh depending on `mode`."""
    job_id = str(uuid.uuid4())[:8]
    is_3d = mode == "3d"

    # Save uploaded reference images
    ref_paths = []
    for i, ref in enumerate(reference_images):
        if ref.filename and ref.size and ref.size > 0:
            ext = Path(ref.filename).suffix or ".png"
            path = Path("uploads") / f"{job_id}_ref{i}{ext}"
            async with aiofiles.open(path, "wb") as f:
                await f.write(await ref.read())
            ref_paths.append(str(path))

    # Validation diverges by mode:
    # - 2D: reference images require an IP-Adapter model (CLIP-vision conditioning).
    # - 3D: at least one reference image is REQUIRED (Hy3D is image-conditioned),
    #       and IP-Adapter doesn't apply.
    if is_3d:
        if backend != "comfyui":
            return JSONResponse(
                {"error": "3D generation only supported on the ComfyUI backend."},
                status_code=400,
            )
        if not ref_paths:
            return JSONResponse(
                {"error": "3D generation requires a reference image — Hy3D and "
                          "TRELLIS are both image-conditioned."},
                status_code=400,
            )
        if engine not in ("hy3d", "trellis"):
            return JSONResponse(
                {"error": f"engine must be 'hy3d' or 'trellis', got {engine!r}"},
                status_code=400,
            )
        # mode_3d vocabulary depends on the engine:
        # - Hy3D: shape | pbr
        # - TRELLIS: shape | textured
        valid_modes = {"hy3d": ("shape", "pbr"), "trellis": ("shape", "textured")}
        if mode_3d not in valid_modes[engine]:
            return JSONResponse(
                {"error": f"mode_3d for {engine} must be one of {valid_modes[engine]}, got {mode_3d!r}"},
                status_code=400,
            )
    elif ref_paths and backend == "comfyui" and not ip_adapter_model:
        return JSONResponse(
            {"error": "Reference images require an IP-Adapter model on the ComfyUI backend. "
                      "Pick one from the IP-Adapter Model dropdown, or remove the reference images."},
            status_code=400,
        )

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
        "mode": mode,
        "mode_3d": mode_3d,
        "engine": engine,
        "paint_model": paint_model,
        "hy3d_cam_azimuths": hy3d_cam_azimuths,
        "hy3d_cam_elevations": hy3d_cam_elevations,
        "trellis_format": trellis_format,
        "trellis_pipeline_type": trellis_pipeline_type,
        "trellis_preset": trellis_preset,
        "trellis_tweak_faithful": trellis_tweak_faithful == "1",
        "trellis_tweak_fine_detail": trellis_tweak_fine_detail == "1",
        "trellis_tweak_sharp_edges": trellis_tweak_sharp_edges == "1",
        "auto_bg_removal": auto_bg_removal == "1",
    }

    # Server-side guard: FP8 has no ROCm `addmm` kernel for Float8_e4m3fn at all.
    # We initially thought this was cascade-only, but observed failures on the
    # non-cascade `sample_shape_slat_multiview` path too (Apr 30, 21:06). The
    # wrapper's GGUF/SDNQ dequant only handles certain code paths — anywhere
    # raw FP8 weights reach a torch matmul, ROCm fails.
    # Safest stance on ROCm: silently fall back FP8 → BF16 for any TRELLIS run.
    # Once a ROCm FP8 kernel ships, this guard can be relaxed.
    if (is_3d and engine == "trellis"
            and trellis_format == "Safetensors (FP8)"):
        params["trellis_format"] = "Safetensors (BF16)"

    jobs[job_id] = {"status": "queued", "params": params, "progress": 0}
    # 2D jobs are <1min so the default 300s gpu-lane timeout is fine.
    # 3D jobs vary wildly (TRELLIS textured ~32 min, Hy3D shape ~30s),
    # so look up the per-(engine, mode) outer timeout. Outer is sized
    # so a healthy ComfyUI run finishes inside the inner timeout first;
    # the outer is just a backstop for genuine hangs. Stash the inner
    # timeout on params so backends/comfyui.py can read it without
    # re-deriving the same logic.
    if is_3d:
        if engine == "trellis":
            mode_flag = "textured" if params.get("mode_3d") in ("pbr", "textured") else "shape"
        else:
            mode_flag = params.get("mode_3d", "shape")
        outer, inner = resolve_3d_timeouts(engine, mode_flag)
        params["_inner_timeout_s"] = inner
        job_timeout = outer
    else:
        job_timeout = 0  # use lane default (300s)
    job_queue.submit_background(_run_job(job_id, params), lane="gpu",
                                job_id=job_id, timeout=job_timeout)

    return {"job_id": job_id}


@app.get("/api/queue")
async def get_queue_status():
    """Current queue status across all resource lanes."""
    return job_queue.status()


@app.get("/api/gpu-stats")
async def get_gpu_stats():
    """Proxy ComfyUI's /system_stats so the browser can surface VRAM info
    in the 3D mode UI. Direct fetch from the browser would CORS-fail
    (open-palette is on :7860, ComfyUI on :8188)."""
    comfy_url = config.get("backends", {}).get("comfyui", {}).get("url", "")
    if not comfy_url:
        return {"available": False}
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"{comfy_url.rstrip('/')}/system_stats")
            if resp.status_code != 200:
                return {"available": False}
            data = resp.json()
            dev = (data.get("devices") or [{}])[0]
            return {
                "available": True,
                "device_name": dev.get("name", "?"),
                "vram_total_gb": round((dev.get("vram_total") or 0) / (1024 ** 3), 1),
                "vram_free_gb": round((dev.get("vram_free") or 0) / (1024 ** 3), 1),
                "torch_vram_used_gb": round(((dev.get("torch_vram_total") or 0) -
                                             (dev.get("torch_vram_free") or 0)) / (1024 ** 3), 1),
            }
    except Exception:
        return {"available": False}


@app.get("/api/health/components")
async def get_health_components():
    """Component health snapshot for the floating widget.

    Returns a flat list of {name, status, tooltip} entries — one per
    component (comfyui, ollama, gpu, disk, queue). Status is one of
    green/amber/red/unknown. Tooltips carry the human-readable values.
    """
    components = await health_actions.check_components(job_queue)
    return {"components": components}


@app.post("/api/health/reset")
async def post_health_reset(request: Request):
    """Run a soft or hard reset.

    Body: {"level": "soft"} (default) or {"level": "hard"}.
    Soft = orphan-rescue + re-probe (no service restart).
    Hard = soft + restart comfyui.service.
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    level = (body.get("level") or "soft").lower()
    if level == "hard":
        result = await health_actions.hard_reset(job_queue)
    else:
        result = await health_actions.soft_reset(job_queue)
    # Invalidate gallery cache so newly-rescued meshes appear immediately.
    _gallery_cache["items"] = None
    _gallery_cache["ts"] = 0.0
    return result


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
        "ollama_error": None,
    }
    # Try to list installed Ollama models
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{result['ollama_url']}/api/tags")
            if resp.status_code == 200:
                result["installed_models"] = [m["name"] for m in resp.json().get("models", [])]
            else:
                result["ollama_error"] = f"Ollama returned HTTP {resp.status_code}"
    except httpx.TimeoutException:
        result["ollama_error"] = f"Ollama at {result['ollama_url']} timed out (service may be unresponsive)"
    except httpx.ConnectError:
        result["ollama_error"] = f"Ollama at {result['ollama_url']} unreachable (is the service running?)"
    except Exception as e:
        result["ollama_error"] = f"{type(e).__name__}: {e}"
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
    mode = data.get("mode", "image")  # "image" or "video"

    if not user_prompt:
        return JSONResponse({"error": "No prompt provided"}, status_code=400)

    ollama_url = opt_config.get("ollama_url", "http://localhost:11434")
    # Per-request override wins over the configured default so the UI can
    # A/B different OP models without mutating global config.
    ollama_model = data.get("ollama_model") or opt_config.get("model", "qwen2.5:14b")

    json_format = '{{"enhanced_prompt": "...", "negative_prompt": "...", "changes_made": "brief explanation of what you improved"}}'

    if mode == "sprite":
        system_prompt = f"""You are an expert pixel art sprite prompt engineer. The user will give you a game sprite concept. Your job is to enhance it for AI-generated pixel art.

Rules:
- Add pixel art style tokens (16-bit, retro, game asset, sprite sheet style)
- Specify the view angle (top-down, side-view, isometric, front-facing)
- Describe colors, shading, and outline style explicitly
- Keep the subject simple and centered — single character or object
- Mention transparent background for game-ready output
- Avoid complex scenes, multiple subjects, or photorealistic descriptors
- Be concise — SD 1.5 prompts work best under 75 tokens

Respond ONLY with valid JSON (no markdown, no code fences):
{json_format}"""
    elif mode == "video":
        system_prompt = f"""You are an expert AnimateDiff video prompt engineer. The user will give you a text-to-video prompt. Your job is to enhance it for maximum quality animated output.

The target model is: AnimateDiff (SD 1.5 based motion synthesis)

Rules:
- Describe the MOTION explicitly (walking, flowing, swaying, rotating, zooming)
- Add temporal cues (slow, gentle, dynamic, sweeping)
- Include scene composition and lighting that works well in motion
- Keep subjects simple — AnimateDiff works best with 1-2 focal subjects
- Avoid complex multi-character scenes or rapid scene changes
- Add style descriptors that translate well to animation (cinematic, smooth, fluid)
- Suggest a negative prompt to avoid common video artifacts (flickering, morphing, jitter)
- Be concise — SD prompts work best under 75 tokens

Respond ONLY with valid JSON (no markdown, no code fences):
{json_format}"""
    else:
        system_prompt = f"""You are an expert Stable Diffusion prompt engineer. The user will give you an image generation prompt. Your job is to enhance it for maximum quality.

The target generation model is: {target_model or 'unknown'}

Rules:
- Add specific quality descriptors (lighting, composition, detail level, style)
- Remove ambiguity — make vague descriptions concrete
- Keep the user's core intent intact
- Suggest a negative prompt to avoid common artifacts
- Be concise — SD prompts work best under 75 tokens

Respond ONLY with valid JSON (no markdown, no code fences):
{json_format}"""

    import re
    import httpx
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": ollama_model,
                    "prompt": user_prompt,
                    "system": system_prompt,
                    "stream": False,
                    # num_gpu: -1 = let Ollama auto-pick (all GPU layers that fit,
                # falling back to CPU for the rest). On a GPU-less Ollama host
                # this behaves like CPU-only but takes the normal optimized
                # path instead of the strict "num_gpu=0" fallback path, which
                # is ~3× faster in practice. See scripts/op_latency_bench.py.
                "options": {"temperature": 0.3, "num_gpu": -1},
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
        return JSONResponse({"error": "Ollama timed out (120s)"}, status_code=504)
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

    # Single source of truth for ComfyUI-backed types: ask ComfyUI itself.
    # Aggregates across all loader buckets so we don't care which dir a
    # file sits in (unet/ vs diffusion_models/ etc.). Falls back to a
    # filesystem check if ComfyUI is unreachable (offline catalog browsing).
    live = await _probe_comfyui(comfyui_url) if comfyui_url else None
    live_installed: set[str] = set()
    if live:
        for bucket in ("checkpoints", "unets", "loras", "ip_adapters", "upscalers", "clip_vision"):
            live_installed.update(live.get(bucket, []))

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
        elif item["type"] == "pip-package":
            pkg = item.get("pip_package", "")
            mod_name = pkg.replace("-", "_").split("[")[0]
            try:
                __import__(mod_name)
                entry["installed"] = True
            except ModuleNotFoundError as e:
                entry["installed"] = False
                # Package IS on disk but a transitive dep import failed — flag as broken
                # so the UI can distinguish "not installed" from "installed-but-broken".
                if e.name and e.name != mod_name:
                    entry["install_error"] = f"broken: missing '{e.name}' (transitive dep)"
            except Exception as e:
                entry["installed"] = False
                entry["install_error"] = f"broken: {type(e).__name__}: {e}"
        elif item["type"] in DEST_MAP and DEST_MAP[item["type"]]:
            if live is not None:
                entry["installed"] = item["filename"] in live_installed
            elif comfyui_root:
                dest = comfyui_root / DEST_MAP[item["type"]] / item["filename"]
                entry["installed"] = dest.exists()
            else:
                entry["installed"] = False
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
            if item["type"] == "pip-package":
                # Install via pip
                pkg = item.get("pip_package", "")
                _download_status[model_id]["progress"] = 10
                proc = await asyncio.create_subprocess_exec(
                    "pip", "install", pkg,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                _, stderr_out = await proc.communicate()
                if proc.returncode == 0:
                    _download_status[model_id] = {"status": "complete", "progress": 100}
                else:
                    _download_status[model_id] = {"status": "error", "error": stderr_out.decode()[-300:]}
                return

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
    """Move or copy an asset into a project."""
    import storage as store
    data = await request.json()
    filename = data.get("filename", "")
    if not filename:
        return JSONResponse({"error": "filename required"}, status_code=400)
    copy = data.get("copy", False)
    # Support batch: filename can be a list
    filenames = filename if isinstance(filename, list) else [filename]
    moved = 0
    for fn in filenames:
        if store.move_asset(fn, project_id, copy=copy):
            moved += 1
    if moved == 0:
        return JSONResponse({"error": "No assets found"}, status_code=404)
    return {"ok": True, "count": moved}


@app.post("/api/projects/{project_id}/upload")
async def api_upload_asset(project_id: str,
                           files: list[UploadFile] = File(...)):
    """Upload one or more files directly into a project."""
    import storage as store
    pdir = store.project_dir(project_id)
    if not pdir.exists():
        return JSONResponse({"error": "Project not found"}, status_code=404)

    uploaded = []
    for f in files:
        ext = Path(f.filename).suffix.lower()
        if ext in (".wav", ".mp3", ".ogg", ".flac"):
            asset_type = "audio"
        elif ext in (".mp4", ".webm", ".mov"):
            asset_type = "video"
        else:
            asset_type = "image"

        subdir = store.ASSET_DIRS.get(asset_type, "assets")
        dest_dir = pdir / subdir
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Use a unique name to avoid collisions
        file_id = f"{uuid.uuid4().hex[:8]}{ext}"
        dest = dest_dir / file_id

        async with aiofiles.open(str(dest), "wb") as out:
            content = await f.read()
            await out.write(content)

        # Write a minimal sidecar
        sidecar = {"original_name": f.filename, "uploaded": datetime.now().isoformat()}
        with open(dest.with_suffix(".json"), "w") as sf:
            json.dump(sidecar, sf, indent=2)

        uploaded.append({
            "filename": file_id,
            "type": asset_type,
            "url": f"/storage/{file_id}",
            "original_name": f.filename,
        })

    return {"uploaded": uploaded, "count": len(uploaded)}


@app.get("/api/projects/{project_id}/timeline")
async def api_get_timeline(project_id: str):
    """Get project timeline."""
    import storage as store
    return store.get_timeline(project_id)


@app.put("/api/projects/{project_id}/timeline")
async def api_save_timeline(project_id: str, request: Request):
    """Save project timeline."""
    import storage as store
    data = await request.json()
    if store.save_timeline(project_id, data):
        return {"ok": True}
    return JSONResponse({"error": "Project not found"}, status_code=404)


@app.post("/api/projects/{project_id}/timeline/preview")
async def api_timeline_preview(project_id: str, request: Request):
    """Render a single preview frame at the playhead position."""
    import storage as store
    from studio.video_composer import render_preview_frame

    data = await request.json()
    playhead = float(data.get("playhead", 0))
    timeline = store.get_timeline(project_id)
    pdir = store.project_dir(project_id)

    preview_path = str(pdir / "video" / "preview.png")
    (pdir / "video").mkdir(parents=True, exist_ok=True)

    result = await render_preview_frame(timeline, pdir, playhead, preview_path)
    if result:
        return {"url": f"/storage/preview.png?t={int(time.time())}"}
    return JSONResponse({"error": "No clips in timeline"}, status_code=400)


@app.post("/api/projects/{project_id}/timeline/render")
async def api_timeline_render(project_id: str):
    """Start rendering the timeline to MP4."""
    import storage as store
    from studio.video_composer import render_video

    timeline = store.get_timeline(project_id)
    if not timeline.get("clips"):
        return JSONResponse({"error": "Timeline has no clips"}, status_code=400)

    pdir = store.project_dir(project_id)
    (pdir / "video").mkdir(parents=True, exist_ok=True)

    job_id = str(uuid.uuid4())[:8]
    output_path = str(store.asset_path(job_id, "video", ".mp4", project_id=project_id))

    jobs[job_id] = {"status": "queued", "params": {"type": "video_render", "project": project_id}, "progress": 0}

    async def _run_render():
        jobs[job_id]["status"] = "running"
        await broadcast({"type": "job_update", "job_id": job_id, "status": "running", "progress": 0})

        try:
            async def on_progress(pct, msg=""):
                jobs[job_id]["progress"] = pct
                await broadcast({
                    "type": "job_update", "job_id": job_id,
                    "status": "running", "progress": pct, "message": msg,
                })

            meta = await render_video(timeline, pdir, output_path, on_progress)

            jobs[job_id].update({
                "status": "complete", "progress": 100,
                "output_url": f"/storage/{job_id}.mp4",
                **meta,
            })
            await broadcast({
                "type": "job_update", "job_id": job_id,
                "status": "complete", "progress": 100,
                "output_url": f"/storage/{job_id}.mp4",
            })
        except Exception as e:
            jobs[job_id].update({"status": "error", "error": str(e)})
            await broadcast({
                "type": "job_update", "job_id": job_id,
                "status": "error", "error": str(e),
            })

    job_queue.submit_background(_run_render(), lane="render", job_id=f"vid-{job_id}")
    return {"job_id": job_id}


@app.get("/api/unsorted")
async def api_list_unsorted():
    """List recent unsorted assets."""
    import storage as store
    return store.list_unsorted(limit=100)


@app.head("/storage/{filename:path}")
@app.get("/storage/{filename:path}")
async def serve_storage_file(filename: str):
    """Serve any file from storage by filename (searches projects + unsorted)."""
    import storage as store
    path = store.resolve_asset(filename)
    if path and path.exists():
        return FileResponse(str(path))
    return JSONResponse({"error": "File not found"}, status_code=404)


# --- Style Remix resolvers ---

def resolve_crypto_logo(slug: str) -> Path | None:
    """Resolve a crypto logo slug like 'bitcoin-btc' to storage/crypto-logos/<slug>.png.

    Rejects slugs containing path separators, '..', or empty values.
    """
    if not slug or "/" in slug or "\\" in slug or ".." in slug:
        return None
    candidate = Path("storage") / "crypto-logos" / f"{slug}.png"
    return candidate if candidate.exists() else None


def resolve_gallery_image(filename: str) -> Path | None:
    """Resolve a gallery image filename via storage.resolve_asset.

    The path-traversal guard below is defense-in-depth: `storage.resolve_asset`
    internally reduces its input to `Path(filename).name`, so traversal
    attempts are silently stripped anyway. The guard here rejects them loudly
    so misuse surfaces as a None return instead of a surprise asset hit.

    TODO(v1.1): scope this to `storage/unsorted/` only; currently delegates
    to `storage.resolve_asset` which also searches `storage/projects/`.
    """
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return None
    return store.resolve_asset(filename)


@app.get("/api/crypto-logos")
async def list_crypto_logos():
    """List all crypto logos available for Style Remix."""
    logos_dir = Path("storage") / "crypto-logos"
    if not logos_dir.exists():
        return []
    items = []
    for png in sorted(logos_dir.glob("*.png")):
        slug = png.stem
        parts = slug.rsplit("-", 1)
        if len(parts) == 2 and parts[1].isalpha():
            name = f"{parts[0].replace('-', ' ').title()} ({parts[1].upper()})"
        else:
            name = slug.replace("-", " ").title()
        items.append({"slug": slug, "name": name})
    return items


# --- Music Generation API ---

_music_engine = None


def _get_music_engine():
    global _music_engine
    if _music_engine is None:
        try:
            from studio.music_gen import MusicGenEngine
            engine = MusicGenEngine(config.get("music", {}))
            if engine.available():
                _music_engine = engine
        except Exception:
            pass
    return _music_engine


COMFYUI_URL = "http://localhost:8188"


async def _free_comfyui():
    """Ask ComfyUI to unload models and free VRAM."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"{COMFYUI_URL}/free",
                json={"unload_models": True, "free_memory": True},
            )
    except Exception:
        pass  # ComfyUI might not be running


@app.post("/api/gpu/claim-music")
async def gpu_claim_music():
    """Free ComfyUI VRAM and load MusicGen to GPU."""
    await _free_comfyui()
    engine = _get_music_engine()
    if not engine:
        return JSONResponse({"error": "MusicGen not available"}, status_code=503)
    engine.preload()
    raw_device = getattr(engine, "_device", "unknown")
    # Resolve a human-readable label. PyTorch's ROCm build keeps the "cuda"
    # API naming even on AMD GPUs, so the raw string is misleading.
    if raw_device == "cuda":
        try:
            import torch
            device_label = torch.cuda.get_device_name(0)
        except Exception:
            device_label = "GPU"
    elif raw_device == "cpu":
        device_label = "CPU"
    else:
        device_label = raw_device
    return {"ok": True, "device": device_label}


@app.post("/api/gpu/release-music")
async def gpu_release_music():
    """Unload MusicGen from GPU so other apps can use VRAM."""
    engine = _get_music_engine()
    if engine:
        engine._unload_model()
    return {"ok": True}


@app.get("/api/music/status")
async def music_status():
    """Check if music generation is available."""
    engine = _get_music_engine()
    if engine:
        return {"available": True, "models": engine.models(), "modes": engine.modes()}
    return {"available": False, "reason": "audiocraft not installed (pip install audiocraft)"}


@app.post("/api/music/generate")
async def music_generate(request: Request):
    """Generate music from a text prompt. Returns immediately with job_id; poll /api/job/{id}."""
    engine = _get_music_engine()
    if not engine:
        return JSONResponse({"error": "Music generation not available"}, status_code=503)

    data = await request.json()
    prompt = data.get("prompt", "").strip()
    mode = data.get("mode", "single")
    max_dur = 180 if mode in ("continuation", "loop") else 30
    duration = min(float(data.get("duration", 15)), max_dur)
    model_id = data.get("model", "")

    if not prompt:
        return JSONResponse({"error": "No prompt provided"}, status_code=400)

    job_id = str(uuid.uuid4())[:8]
    import storage as store
    output_path = str(store.asset_path(job_id, "audio", ".wav"))

    jobs[job_id] = {"status": "queued", "progress": 0, "type": "music"}

    async def _do():
        try:
            jobs[job_id]["status"] = "running"
            meta = await engine.generate(prompt, output_path, duration,
                                         model_id or None, mode=mode)
            jobs[job_id].update({
                "status": "complete", "progress": 100,
                "url": f"/storage/{job_id}.wav",
                "prompt": prompt,
                **meta,
            })
        except Exception as e:
            jobs[job_id].update({"status": "error", "error": str(e)})

    asyncio.create_task(_do())

    return {"job_id": job_id, "status": "queued"}


# --- Beat Builder API ---

@app.get("/api/beats/packs")
async def beats_list_packs():
    from studio import sample_packs
    return sample_packs.list_packs()


@app.get("/api/beats/packs/{pack_id}/samples")
async def beats_list_samples(pack_id: str):
    from studio import sample_packs
    return sample_packs.list_samples(pack_id)


@app.get("/api/beats/templates")
async def beats_list_templates():
    from studio import beat_builder
    return beat_builder.list_templates()


@app.post("/api/beats/preview")
async def beats_preview(request: Request):
    from studio import beat_builder
    import storage as store
    data = await request.json()
    template_id = data.get("template", "hip-hop")
    overrides = data.get("overrides", {})
    bpm = int(data.get("bpm", 0))
    job_id = str(uuid.uuid4())[:8]
    output_path = str(store.asset_path(job_id, "audio", ".wav"))
    try:
        result = beat_builder.build_track(
            template_id, overrides, bpm=bpm,
            output_path=output_path, preview_bars=8,
        )
        return {"url": f"/storage/{job_id}.wav", **result}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/beats/build")
async def beats_build(request: Request):
    from studio import beat_builder
    import storage as store
    data = await request.json()
    template_id = data.get("template", "hip-hop")
    overrides = data.get("overrides", {})
    bpm = int(data.get("bpm", 0))
    job_id = str(uuid.uuid4())[:8]
    output_path = str(store.asset_path(job_id, "audio", ".wav"))
    async def _do():
        return beat_builder.build_track(
            template_id, overrides, bpm=bpm, output_path=output_path,
        )
    try:
        result = await job_queue.submit(_do(), lane="cpu", job_id=f"beat-{job_id}")
        return {"job_id": job_id, "url": f"/storage/{job_id}.wav", **result}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/beats/enhance")
async def beats_enhance(request: Request):
    engine = _get_music_engine()
    if not engine:
        return JSONResponse({"error": "MusicGen not available"}, status_code=503)
    import storage as store
    data = await request.json()
    source_url = data.get("track_url", "")
    prompt = data.get("prompt", "").strip()
    duration = min(float(data.get("duration", 30)), 30)
    if not source_url:
        return JSONResponse({"error": "track_url required"}, status_code=400)
    if not prompt:
        return JSONResponse({"error": "prompt required"}, status_code=400)
    source_filename = source_url.split("/")[-1]
    source_path = store.resolve_asset(source_filename)
    if not source_path:
        return JSONResponse({"error": "Source track not found"}, status_code=404)
    job_id = str(uuid.uuid4())[:8]
    output_path = str(store.asset_path(job_id, "audio", ".wav"))
    async def _do():
        import torch
        import torchaudio
        model = engine._get_model("facebook/musicgen-melody")
        sr = model.sample_rate
        wav, orig_sr = torchaudio.load(str(source_path))
        if orig_sr != sr:
            wav = torchaudio.functional.resample(wav, orig_sr, sr)
        max_samples = int(duration * sr)
        wav = wav[:, :max_samples]
        model.set_generation_params(duration=duration)
        with torch.no_grad():
            result = model.generate_with_chroma(
                descriptions=[prompt],
                melody_wavs=wav.unsqueeze(0),
                melody_sample_rate=sr,
            )
        audio = result[0].cpu()
        torchaudio.save(output_path, audio, sr)
        return {
            "duration": round(audio.shape[-1] / sr, 2),
            "file_size": os.path.getsize(output_path),
        }
    try:
        result = await job_queue.submit(_do(), lane="cpu", job_id=f"enhance-{job_id}")
        return {"job_id": job_id, "url": f"/storage/{job_id}.wav", **result}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/beats/upload-sample")
async def beats_upload_sample(
    file: UploadFile = File(...),
    slot: str = Form("kick"),
):
    from studio import sample_packs
    content = await file.read()
    filename = file.filename or f"{slot}.wav"
    result = sample_packs.save_user_sample(content, filename, slot)
    return result


# --- Video Generation API ---

@app.get("/api/video/status")
async def api_video_status():
    """Check GPU availability and supported video models.

    NOTE: torch.cuda.is_available() may be False in this process because
    TTS engines set CUDA_VISIBLE_DEVICES="" at import. Video generation
    runs via ComfyUI (separate process) which has full GPU access.
    We query ComfyUI system_stats directly for GPU info.
    """
    import aiohttp

    gpu_available = False
    gpu_name = None
    vram_total = None
    vram_gb = 0

    # Query ComfyUI for actual GPU info
    comfyui_url = config.get("backends", {}).get("comfyui", {}).get("url", "http://localhost:8188")
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.get(f"{comfyui_url}/system_stats") as resp:
                if resp.status == 200:
                    stats = await resp.json()
                    devices = stats.get("devices", [])
                    for dev in devices:
                        if dev.get("type") == "cuda":
                            gpu_available = True
                            gpu_name = dev.get("name", "").split(" : ")[0].replace("cuda:0 ", "")
                            vram_bytes = dev.get("vram_total", 0)
                            vram_gb = vram_bytes / (1024**3)
                            vram_total = f"{vram_gb:.1f} GB"
                            break
    except Exception:
        pass  # ComfyUI not running — fall back to no GPU

    # Check if AnimateDiff motion model is installed (v2 preferred, v3 also works)
    ad_models_dir = Path("/data/ComfyUI/models/animatediff_models")
    animatediff_installed = (
        (ad_models_dir / "mm_sd_v15_v2.ckpt").exists()
        or (ad_models_dir / "v3_sd15_mm.ckpt").exists()
    )
    animatediff_ready = vram_gb >= 7 and animatediff_installed  # 8GB cards report ~7.6 usable

    models = [
        {"id": "animatediff", "available": animatediff_ready, "min_vram": 8,
         "installed": animatediff_installed},
        {"id": "svd", "available": False, "min_vram": 12, "installed": False},
        {"id": "cogvideox", "available": False, "min_vram": 16, "installed": False},
    ]

    return {
        "gpu_available": gpu_available,
        "gpu_name": gpu_name,
        "vram_total": vram_total,
        "models_ready": sum(1 for m in models if m["available"]),
        "models": models,
    }


@app.post("/api/video/generate")
async def api_video_generate(request: Request):
    """Generate a short video clip via AnimateDiff through ComfyUI."""
    import storage as store

    data = await request.json()
    model = data.get("model")
    prompt = data.get("prompt", "")

    if not model or not prompt:
        return JSONResponse({"error": "model and prompt required"}, status_code=400)

    if model != "animatediff":
        return JSONResponse({"error": f"{model} not yet supported"}, status_code=501)

    # Check AnimateDiff motion model is installed (any of the supported variants)
    ad_dir = Path("/data/ComfyUI/models/animatediff_models")
    motion_model = data.get("motion_model", "mm_sd_v15_v2.ckpt")
    supported_motion = {
        "mm_sd_v15_v2.ckpt",
        "v3_sd15_mm.ckpt",
        "animatediff_lightning_4step_comfyui.safetensors",
        "animatediff_lightning_8step_comfyui.safetensors",
    }
    if motion_model not in supported_motion:
        return JSONResponse({"error": f"Unsupported motion_model: {motion_model}"}, status_code=400)
    if not (ad_dir / motion_model).exists():
        return JSONResponse({"error": f"Motion model {motion_model} not installed"}, status_code=503)

    job_id = str(uuid.uuid4())[:8]
    output_path = str(store.asset_path(job_id, "video", ".mp4"))
    jobs[job_id] = {
        "status": "queued", "progress": 0,
        "params": {"type": "video_gen", "model": model, "prompt": prompt},
    }

    async def _run_video_gen():
        jobs[job_id]["status"] = "running"
        await broadcast({"type": "job_update", "job_id": job_id,
                         "status": "running", "progress": 0})
        try:
            comfyui = registry.get_backend("comfyui")

            async def on_progress(pct, msg=""):
                jobs[job_id]["progress"] = pct
                await broadcast({"type": "job_update", "job_id": job_id,
                                 "status": "running", "progress": pct, "message": msg})

            meta = await comfyui.generate_video({
                "prompt": prompt,
                "negative_prompt": data.get("negative_prompt",
                                            "low quality, blurry, distorted, watermark"),
                "width": data.get("width", 512),
                "height": data.get("height", 512),
                "duration": data.get("duration", 4),
                "steps": data.get("steps", 20),
                "cfg": data.get("cfg", 7.0),
                "seed": data.get("seed", -1),
                "fps": data.get("fps", 8),
                "motion_model": motion_model,
            }, output_path, on_progress)

            jobs[job_id].update({
                "status": "complete", "progress": 100,
                "output_url": f"/storage/{job_id}.mp4",
                **meta,
            })
            await broadcast({"type": "job_update", "job_id": job_id,
                             "status": "complete", "progress": 100,
                             "output_url": f"/storage/{job_id}.mp4"})
        except Exception as e:
            jobs[job_id].update({"status": "error", "error": str(e)})
            await broadcast({"type": "job_update", "job_id": job_id,
                             "status": "error", "error": str(e)})

    job_queue.submit_background(_run_video_gen(), lane="gpu", job_id=f"vidgen-{job_id}")
    return {"job_id": job_id}


# --- TTS API ---

async def _normalise_to_wav(src: Path, dst: Path) -> tuple[bool, str]:
    """Convert any audio/video file to mono 22050 Hz 16-bit PCM WAV.

    Returns (success, stderr_tail). Uses the same subprocess pattern as
    api_audio_extract — argument list only, no shell interpretation.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", str(src),
        "-vn",
        "-ac", "1",
        "-ar", "22050",
        "-sample_fmt", "s16",
        "-f", "wav",
        str(dst),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    return proc.returncode == 0, stderr.decode(errors="ignore")[-500:]


@app.post("/api/tts/clone-voice")
async def upload_clone_voice(voice_name: str = Form(...),
                             audio: UploadFile = File(...)):
    """Upload an audio reference for XTTS voice cloning.

    Accepts any common format (WAV, MP3, M4A, OGG, FLAC, WebM, etc.) and
    normalises to mono 22050 Hz 16-bit PCM WAV — XTTS v2's preferred input.
    """
    voices_dir = Path(__file__).parent / "engines" / "xtts_voices"
    voices_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize filename
    import re
    safe_name = re.sub(r'[^\w\s-]', '', voice_name.lower().strip())
    safe_name = re.sub(r'[\s]+', '_', safe_name)
    if not safe_name:
        return JSONResponse({"error": "Invalid voice name"}, status_code=400)

    # Keep the original extension on the temp file so ffmpeg can auto-detect format
    src_suffix = Path(audio.filename or "upload").suffix or ".bin"
    with tempfile.NamedTemporaryFile(suffix=src_suffix, delete=False) as tmp_in:
        tmp_in.write(await audio.read())
        tmp_in_path = Path(tmp_in.name)

    dest = voices_dir / f"{safe_name}.wav"

    try:
        ok, detail = await _normalise_to_wav(tmp_in_path, dest)
        if not ok:
            dest.unlink(missing_ok=True)
            return JSONResponse(
                {"error": "Audio conversion failed", "detail": detail},
                status_code=400,
            )
    finally:
        tmp_in_path.unlink(missing_ok=True)

    # Report rough duration so the UI can flag clips that are too short
    import wave
    duration = 0.0
    try:
        with wave.open(str(dest), "rb") as wf:
            frames = wf.getnframes()
            rate = wf.getframerate()
            if rate:
                duration = round(frames / rate, 2)
    except Exception:
        pass

    return {
        "ok": True,
        "voice_id": f"clone_{safe_name}",
        "name": voice_name,
        "duration": duration,
        "size_kb": dest.stat().st_size // 1024,
    }


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
    lora_model: str = Form(""),
    lora_strength: float = Form(1.0),
    lora_strength_model: float = Form(1.0),
    lora_strength_clip: float = Form(0.6),
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
            "lora_model": lora_model,
            "lora_strength": lora_strength,
            "lora_strength_model": lora_strength_model,
            "lora_strength_clip": lora_strength_clip,
            "reference_images": ref_paths,
        }
        jobs[job_id] = {"status": "queued", "params": params, "progress": 0, "comparison_id": comparison_id}
        job_queue.submit_background(_run_job(job_id, params), lane="gpu", job_id=job_id)
        job_ids.append({"job_id": job_id, "backend": entry["backend"], "model": entry.get("model", "")})

    return {"comparison_id": comparison_id, "jobs": job_ids}


# --- Style Remix API ---

_BLEND_MODE_VALUES = {"style transfer", "standard", "prompt is more important"}


@app.post("/api/remix")
async def remix(
    base_image: UploadFile | None = File(default=None),
    base_gallery_id: str = Form(""),
    style_ref: UploadFile | None = File(default=None),
    crypto_logo_id: str = Form(""),
    preserve_character: float = Form(0.45),
    style_strength: float = Form(0.75),
    ip_start: float = Form(0.0),
    ip_end: float = Form(0.8),
    blend_mode: str = Form("style transfer"),
    lora_model: str = Form(""),
    lora_strength: float = Form(0.55),
    model: str = Form("juggernautXL_v9.safetensors"),
    steps: int = Form(20),
    cfg: float = Form(6.0),
    seed: int = Form(-1),
    batch_size: int = Form(4),
    hint: str = Form(""),
):
    """Enqueue a batch of Style Remix jobs. One ComfyUI job per batch slot."""
    import random as _random
    import shutil as _shutil

    base_source_path: Path | None = None
    base_kind = ""
    base_ref = ""
    if base_image is not None and base_image.filename:
        upload_id = str(uuid.uuid4())[:8]
        ext = Path(base_image.filename).suffix or ".png"
        dest = Path("uploads") / f"remix_base_{upload_id}{ext}"
        async with aiofiles.open(dest, "wb") as f:
            await f.write(await base_image.read())
        base_source_path = dest
        base_kind = "upload"
        base_ref = dest.name
    elif base_gallery_id:
        resolved = resolve_gallery_image(base_gallery_id)
        if resolved is None:
            return JSONResponse({"error": f"Gallery image '{base_gallery_id}' not found"}, status_code=404)
        base_source_path = resolved
        base_kind = "gallery"
        base_ref = base_gallery_id
    else:
        return JSONResponse({"error": "base_image or base_gallery_id is required"}, status_code=400)

    style_source_path: Path | None = None
    style_kind = ""
    style_ref_id = ""
    if style_ref is not None and style_ref.filename:
        upload_id = str(uuid.uuid4())[:8]
        ext = Path(style_ref.filename).suffix or ".png"
        dest = Path("uploads") / f"remix_style_{upload_id}{ext}"
        async with aiofiles.open(dest, "wb") as f:
            await f.write(await style_ref.read())
        style_source_path = dest
        style_kind = "upload"
        style_ref_id = dest.name
    elif crypto_logo_id:
        resolved = resolve_crypto_logo(crypto_logo_id)
        if resolved is None:
            return JSONResponse({"error": f"Crypto logo '{crypto_logo_id}' not found"}, status_code=404)
        style_source_path = resolved
        style_kind = "crypto"
        style_ref_id = crypto_logo_id
    else:
        return JSONResponse({"error": "style_ref or crypto_logo_id is required"}, status_code=400)

    if not (0.2 <= preserve_character <= 0.9):
        return JSONResponse({"error": "preserve_character must be in [0.2, 0.9]"}, status_code=400)
    if not (1 <= batch_size <= 8):
        return JSONResponse({"error": "batch_size must be in [1, 8]"}, status_code=400)
    if blend_mode not in _BLEND_MODE_VALUES:
        return JSONResponse({"error": f"blend_mode must be one of {sorted(_BLEND_MODE_VALUES)}"}, status_code=400)

    comfy_input_dir = Path("/home/phill/ComfyUI/input")
    base_filename = f"remix_base_{uuid.uuid4().hex[:8]}{base_source_path.suffix}"
    style_filename = f"remix_style_{uuid.uuid4().hex[:8]}{style_source_path.suffix}"
    _shutil.copy2(base_source_path, comfy_input_dir / base_filename)
    _shutil.copy2(style_source_path, comfy_input_dir / style_filename)

    base_seed = _random.randint(0, 2**32 - 1 - batch_size) if seed == -1 else seed

    remix_id = str(uuid.uuid4())[:8]
    job_ids: list[dict] = []
    for i in range(batch_size):
        job_id = str(uuid.uuid4())[:8]
        slot_seed = base_seed + i
        params = {
            "remix": True,
            "backend": "comfyui",
            "base_filename": base_filename,
            "style_ref_filename": style_filename,
            "base_from_kind": base_kind,
            "base_from": base_ref,
            "style_ref_kind": style_kind,
            "style_ref": style_ref_id,
            "model": model,
            "lora_model": lora_model,
            "lora_strength": lora_strength,
            "preserve_character": preserve_character,
            "style_strength": style_strength,
            "ip_start": ip_start,
            "ip_end": ip_end,
            "blend_mode": blend_mode,
            "steps": steps,
            "cfg": cfg,
            "seed": slot_seed,
            "batch_size": batch_size,
            "slot_index": i,
            "hint": hint,
            "width": 1024,
            "height": 1024,
        }
        jobs[job_id] = {"status": "queued", "params": params, "progress": 0, "remix_id": remix_id}
        job_queue.submit_background(_run_job(job_id, params), lane="gpu", job_id=job_id)
        job_ids.append({"job_id": job_id})

    return {"remix_id": remix_id, "jobs": job_ids}


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
        # Worldgen runs as its own subprocess pipeline outside the registry —
        # see backends/worldgen.py and memory/project_worldgen_rocm.md. Skip
        # the registry lookup for it; the dispatch later in this function
        # routes worldgen-engine jobs to that module directly.
        if backend_name == "worldgen":
            backend = None
        else:
            backend = registry.get_backend(backend_name)
            if not backend:
                raise ValueError(f"Backend '{backend_name}' not available")

        import storage as store
        # Asset type and extension diverge for 3D mode — Hy3D/TRELLIS/Worldgen
        # produce .glb; 2D image gen produces .png.
        is_3d = params.get("mode") == "3d"
        if is_3d:
            output_path = store.asset_path(job_id, "mesh", ".glb")
        else:
            output_path = store.asset_path(job_id, "image", ".png")

        async def on_progress(pct: int, msg: str = ""):
            # Tolerate None for cosmetic status updates that don't move the bar.
            if pct is not None:
                jobs[job_id]["progress"] = pct
            await broadcast({
                "type": "job_update", "job_id": job_id,
                "status": "running",
                "progress": jobs[job_id].get("progress", 0),
                "message": msg,
            })

        if is_3d:
            # 3D dispatch: Hy3D vs TRELLIS vs Worldgen all share the same .glb
            # output contract, so the rest of _run_job (sidecar JSON, gallery
            # cache) treats them identically. Only the workflow + engine call
            # differs. Worldgen is the odd one out — runs as its own subprocess
            # pipeline (FLUX.1-dev + DA-2) rather than via ComfyUI.
            engine = params.get("engine")
            if engine == "worldgen":
                from backends.worldgen import generate_world
                worldgen_meta = await generate_world(
                    params, str(output_path), on_progress,
                )
                # Merge worldgen-specific metadata into params so the sidecar
                # JSON written below records what we actually produced.
                params.update({k: v for k, v in worldgen_meta.items()
                              if k not in params})
            elif engine == "trellis":
                await backend.generate_trellis(params, str(output_path), on_progress)
            else:
                await backend.generate_3d(params, str(output_path), on_progress)
        elif params.get("remix"):
            await backend.generate_remix(params, str(output_path), on_progress)
        else:
            await backend.generate(params, str(output_path), on_progress)

        # Save metadata sidecar for both 2D and 3D outputs.
        meta = {**params, "job_id": job_id, "created": datetime.now().isoformat()}
        ref_count = len(meta.pop("reference_images", []))
        meta["reference_image_count"] = ref_count
        async with aiofiles.open(output_path.with_suffix(".json"), "w") as f:
            await f.write(json.dumps(meta, indent=2))

        scores = None
        if not is_3d:
            # PNG metadata + scoring are 2D-only. Embed text chunks in the PNG
            # so prompts survive file sharing, then run the aesthetic scorer.
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

            try:
                import scoring
                scores = await scoring.score_and_save(
                    str(output_path), job_id, params.get("model", ""),
                    params.get("backend", ""), params.get("prompt", ""),
                    meta["created"],
                )
            except Exception:
                pass  # scoring is best-effort

        # Output URL: storage layer resolves via filename (.png or .glb).
        ext = ".glb" if is_3d else ".png"
        output_url = f"/storage/{job_id}{ext}"

        _gallery_cache["items"] = None  # invalidate gallery cache
        jobs[job_id].update({
            "status": "complete",
            "progress": 100,
            "output_url": output_url,
            "asset_type": "mesh" if is_3d else "image",
            "scores": scores,
        })
        await broadcast({
            "type": "job_update", "job_id": job_id,
            "status": "complete", "progress": 100,
            "output_url": output_url,
            "asset_type": "mesh" if is_3d else "image",
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


# ===== Mesh post-processing (modly tier-1 port) =====
from pydantic import BaseModel as _MeshOptModel  # local alias to avoid clobber


class _MeshOptimizeRequest(_MeshOptModel):
    job_id: str
    target_faces: int = 0  # 0 = use DEFAULT_TARGET_FACES


class _MeshSmoothRequest(_MeshOptModel):
    job_id: str
    iterations: int = 3


@app.post("/api/mesh/decimate")
async def api_mesh_decimate(req: _MeshOptimizeRequest):
    """Decimate the GLB attached to job_id, writing a sibling _decimated.glb."""
    import storage as store
    import mesh_optimize

    src = store.asset_path(req.job_id, "mesh", ".glb")
    if not src.exists():
        return {"ok": False, "error": f"no mesh for job {req.job_id}"}

    dst = src.with_name(src.stem + "_decimated.glb")
    try:
        mesh_optimize.decimate_mesh(str(src), str(dst), req.target_faces)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "output_url": f"/storage/{req.job_id}_decimated.glb",
        "target_faces": req.target_faces or mesh_optimize.DEFAULT_TARGET_FACES,
    }


@app.post("/api/mesh/smooth")
async def api_mesh_smooth(req: _MeshSmoothRequest):
    """Smooth the GLB attached to job_id, writing a sibling _smoothed.glb."""
    import storage as store
    import mesh_optimize

    src = store.asset_path(req.job_id, "mesh", ".glb")
    if not src.exists():
        return {"ok": False, "error": f"no mesh for job {req.job_id}"}

    dst = src.with_name(src.stem + "_smoothed.glb")
    try:
        mesh_optimize.smooth_mesh(str(src), str(dst), req.iterations)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    return {
        "ok": True,
        "output_url": f"/storage/{req.job_id}_smoothed.glb",
        "iterations": req.iterations,
    }


@app.get("/api/mesh/export")
async def api_mesh_export(job_id: str, fmt: str):
    """Convert the GLB attached to job_id into {glb,stl,obj,ply} on demand."""
    import storage as store
    import mesh_export
    from fastapi.responses import FileResponse

    src = store.asset_path(job_id, "mesh", ".glb")
    if not src.exists():
        return {"ok": False, "error": f"no mesh for job {job_id}"}

    dst = src.with_name(f"{src.stem}.{fmt.lower()}")
    try:
        mesh_export.export_mesh(str(src), str(dst), fmt)
    except mesh_export.UnsupportedFormatError as e:
        return {"ok": False, "error": str(e)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

    media = {
        "glb": "model/gltf-binary",
        "stl": "model/stl",
        "obj": "model/obj",
        "ply": "model/ply",
    }.get(fmt.lower(), "application/octet-stream")
    return FileResponse(str(dst), media_type=media, filename=dst.name)


# ===== Job cancellation (modly tier-1 port) =====
@app.post("/api/job/{job_id}/cancel")
async def api_job_cancel(job_id: str):
    """Cancel an in-flight or queued job.

    Cooperative: cancels the wrapping asyncio.Task, which propagates
    CancelledError into _run_job. ComfyUI itself keeps running until its
    next prompt boundary; the existing orphan-rescue path
    (backends/comfyui.py:_rescue_orphan_glb) salvages any GLB it manages
    to write before teardown.
    """
    if job_id not in jobs:
        return {"ok": False, "error": "unknown job_id"}

    cancelled = await job_queue.cancel(job_id)
    await _cancel_in_flight(job_id)

    jobs[job_id].update({"status": "cancelled"})
    await broadcast({
        "type": "job_update", "job_id": job_id,
        "status": "cancelled",
    })
    return {"ok": cancelled, "job_id": job_id, "status": "cancelled"}


async def _cancel_in_flight(job_id: str) -> None:
    """DECISION D1 = option (i): wrapper-only cancel.

    No-op here — JobQueue.cancel() already cancelled the wrapper task,
    which propagates CancelledError through asyncio.wait_for in submit().
    ComfyUI continues until its next prompt boundary; orphan-rescue picks
    up any late-arriving GLB. To switch to option (ii) graceful DELETE
    or option (iii) DELETE+kill, replace this body — see plan
    docs/superpowers/plans/2026-05-04-modly-tier1-ports.md DECISION D1.
    """
    return


if __name__ == "__main__":
    import sys
    load_config()
    # --dev flag enables hot-reload (breaks CUDA — use only for frontend work)
    use_reload = "--dev" in sys.argv
    uvicorn.run("server:app", host=config["server"]["host"],
                port=config["server"]["port"], reload=use_reload)
