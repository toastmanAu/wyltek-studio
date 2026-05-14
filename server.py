#!/usr/bin/env python3
"""Wyltek Studio — local-first AI creative studio."""

import asyncio
import base64
import json
import os
import re
import socket
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path

import aiofiles
import uvicorn
import yaml
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import health_actions
import storage as store
from backends import registry
from backends import sensenova as _sensenova
from backends.sensenova import ASPECT_BUCKETS as _SENSENOVA_ASPECTS
from job_queue import JobQueue
from pydantic import BaseModel, Field
from studio import worker_lifecycle as _wl

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
Path("uploads").mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
Path("templates").mkdir(parents=True, exist_ok=True)
app.mount("/templates", StaticFiles(directory="templates"), name="templates")


_DOWNLOAD_ROOTS = {
    "outputs": Path("outputs").resolve(),
    "uploads": Path("uploads").resolve(),
}


@app.get("/download")
async def force_download(path: str):
    # iOS Safari / iOS PWA navigate to bare static URLs and route binary files
    # (.glb, .zip, etc.) into Quick Look — which has no Cancel/Back button and
    # traps the user. Re-serving the same file with Content-Disposition:
    # attachment makes iOS save it to the Files app instead.
    raw = path.lstrip("/")
    head, _, rest = raw.partition("/")
    if not rest:
        raise HTTPException(status_code=404)

    if head == "storage":
        # Generated meshes/images live here — resolve_asset already reduces
        # input to basename and searches projects + unsorted, so traversal
        # is structurally impossible.
        target = store.resolve_asset(rest)
        if target is None or not target.is_file():
            raise HTTPException(status_code=404)
        return FileResponse(target, filename=target.name)

    root = _DOWNLOAD_ROOTS.get(head)
    if root is None:
        raise HTTPException(status_code=404)
    target = (root / rest).resolve()
    if root not in target.parents or not target.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(target, filename=target.name)


@app.get("/save", response_class=HTMLResponse)
async def save_page(path: str):
    # iOS standalone PWA can't trigger downloads in its in-app Safari overlay
    # for binary responses (blank page) or blob URLs from another document
    # (10% stall). Renderable HTML wrappers always paint, and the user can
    # tap the inner <a download> link or long-press → "Download Linked File"
    # to land the file in the Files app.
    name = Path(path).name or "download"
    # Light XSS hardening — the path comes from a query param and gets
    # interpolated into the HTML. Reject any name with control chars or HTML
    # metacharacters; the resolver downstream will validate the actual file.
    if any(c in name for c in '<>"\'&\n\r\t'):
        raise HTTPException(status_code=400)
    safe_path = path.replace('"', '%22')
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Save {name}</title>
<style>
  html, body {{ margin: 0; padding: 0; height: 100%; background: #0f0f10; color: #f4f4f5; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }}
  .wrap {{ min-height: 100%; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 28px 24px; box-sizing: border-box; }}
  .name {{ font-size: 17px; font-weight: 600; word-break: break-all; margin-bottom: 24px; max-width: 100%; opacity: 0.85; }}
  .btn {{ display: inline-block; padding: 18px 36px; background: #2563eb; color: #fff; text-decoration: none; border-radius: 14px; font-size: 17px; font-weight: 600; -webkit-tap-highlight-color: transparent; -webkit-touch-callout: default; touch-action: manipulation; }}
  .ios-steps {{ margin-top: 28px; padding: 16px 20px; background: rgba(255,255,255,0.06); border-radius: 12px; max-width: 340px; font-size: 14px; line-height: 1.6; }}
  .ios-steps b {{ color: #f4f4f5; }}
  .ios-steps ol {{ margin: 8px 0 0; padding-left: 20px; }}
  .ios-steps li {{ margin-bottom: 6px; opacity: 0.85; }}
  .desktop-hint {{ margin-top: 20px; font-size: 12px; opacity: 0.45; }}
</style>
</head>
<body>
<div class="wrap">
  <div class="name">{name}</div>
  <a class="btn" href="{safe_path}" download="{name}">Download</a>
  <div class="ios-steps">
    <b>On iPhone / iPad:</b>
    <ol>
      <li>Press and hold the Download button.</li>
      <li>Tap <b>Open in Browser</b>.</li>
      <li>Safari will save the file — find it in Files → Downloads.</li>
    </ol>
  </div>
  <div class="desktop-hint">On desktop, just tap Download.</div>
</div>
</body>
</html>"""


@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.get("/manifest.json")
async def pwa_manifest():
    return FileResponse("static/manifest.json", media_type="application/manifest+json")


@app.get("/sw.js")
async def pwa_service_worker():
    # Served from root so its scope covers the whole app, not just /static/*.
    return FileResponse(
        "static/sw.js",
        media_type="application/javascript",
        headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"},
    )


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


@app.get("/studio/infographic")
async def studio_infographic():
    return FileResponse("static/studio/infographic.html")


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


@app.get("/studio/sprite")
async def sprite_page():
    return FileResponse("static/studio/sprite.html")


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


@app.post("/api/video/tools/probe")
async def api_video_tools_probe(file: UploadFile = File(...)):
    """Save an uploaded video to a temp path and ffprobe it for metadata.

    Returns: { path, duration, width, height, fps, codec, size_bytes }
    Frontend uses this to populate the source preview + drive the live
    filesize estimate.
    """
    import storage as store

    if not file.filename:
        return JSONResponse({"error": "No file"}, status_code=400)
    suffix = Path(file.filename).suffix or ".mp4"
    tmp_path = store.unsorted_dir() / f"upload-{uuid.uuid4().hex[:8]}{suffix}"
    async with aiofiles.open(tmp_path, "wb") as f:
        await f.write(await file.read())

    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_streams", "-show_format", str(tmp_path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        tmp_path.unlink(missing_ok=True)
        return JSONResponse(
            {"error": "ffprobe failed", "detail": stderr.decode(errors="replace")[-300:]},
            status_code=500,
        )

    info = json.loads(stdout.decode())
    video_stream = next(
        (s for s in info.get("streams", []) if s.get("codec_type") == "video"),
        {},
    )
    fps = 0.0
    rate = video_stream.get("r_frame_rate", "0/1")
    if "/" in rate:
        n, d = rate.split("/", 1)
        try:
            fps = float(n) / float(d) if float(d) else 0.0
        except (ValueError, ZeroDivisionError):
            fps = 0.0

    raw_w = int(video_stream.get("width", 0) or 0)
    raw_h = int(video_stream.get("height", 0) or 0)

    # Detect rotation: phones record portrait clips as e.g. 1920×1080 with a
    # rotation flag, not as 1080×1920. FFmpeg's scale filter operates on the
    # auto-rotated frame, so the frontend needs *visual* dimensions to
    # compute aspect ratio correctly. Two metadata flavors:
    #   1. legacy: stream.tags.rotate = "90"/"180"/"270"
    #   2. newer:  stream.side_data_list[].side_data_type == "Display Matrix"
    #              with a `rotation` field (often negative; -90 ≡ 270).
    rotation = 0
    rot_tag = video_stream.get("tags", {}).get("rotate")
    if rot_tag:
        try:
            rotation = int(rot_tag) % 360
        except ValueError:
            rotation = 0
    if not rotation:
        for sd in video_stream.get("side_data_list", []) or []:
            if sd.get("side_data_type") == "Display Matrix" and "rotation" in sd:
                try:
                    rotation = int(round(float(sd["rotation"]))) % 360
                except (TypeError, ValueError):
                    rotation = 0
                break

    # Swap dims for ±90° rotation so width/height reported are visual.
    # 180° flip doesn't swap (still landscape), only mirrors.
    if rotation in (90, 270):
        width, height = raw_h, raw_w
    else:
        width, height = raw_w, raw_h

    return {
        "path": str(tmp_path),
        "duration": float(info.get("format", {}).get("duration", 0) or 0),
        "size_bytes": int(info.get("format", {}).get("size", 0) or 0),
        "width": width,
        "height": height,
        "fps": round(fps, 3),
        "codec": video_stream.get("codec_name", "?"),
        "rotation": rotation,
    }


@app.post("/api/video/tools/transcode")
async def api_video_tools_transcode(request: Request):
    """Transcode a previously-uploaded video with FFmpeg.

    Request body (JSON):
      path:   absolute path to source (from /probe)
      width, height: target resolution (0,0 = keep source)
      fps:    target fps (0 = keep source)
      crf:    quality (0-51, lower=better; codec dependent)
      codec:  'h264' | 'h265' | 'vp9' | 'av1'
      format: 'mp4' | 'webm' | 'mov' | 'mkv'
    """
    import storage as store

    data = await request.json()
    src = Path(data.get("path", "")).resolve()
    try:
        _assert_under_storage(src)
    except PermissionError:
        return JSONResponse({"error": "Access denied"}, status_code=403)
    if not src.exists():
        return JSONResponse({"error": "Source not found"}, status_code=404)

    width = int(data.get("width") or 0)
    height = int(data.get("height") or 0)
    fps = float(data.get("fps") or 0)
    crf = int(data.get("crf") or 23)
    codec = data.get("codec", "h264")
    fmt = data.get("format", "mp4")

    CODECS = {"h264": "libx264", "h265": "libx265", "vp9": "libvpx-vp9", "av1": "libaom-av1"}
    FORMATS = {"mp4", "webm", "mov", "mkv"}
    if codec not in CODECS:
        return JSONResponse({"error": f"codec must be one of {list(CODECS)}"}, status_code=400)
    if fmt not in FORMATS:
        return JSONResponse({"error": f"format must be one of {sorted(FORMATS)}"}, status_code=400)
    if not (0 <= crf <= 51):
        return JSONResponse({"error": "crf must be 0-51"}, status_code=400)

    tag_parts = [codec]
    if width and height:
        tag_parts.append(f"{height}p")
    tag = "-".join(tag_parts)
    out_filename = f"{src.stem}-{tag}-{uuid.uuid4().hex[:6]}.{fmt}"
    out_path = store.unsorted_dir() / out_filename

    args = ["ffmpeg", "-y", "-i", str(src)]

    vf_parts = []
    if width and height:
        vf_parts.append(f"scale={width}:{height}")
    if fps:
        vf_parts.append(f"fps={fps}")
    if vf_parts:
        args += ["-vf", ",".join(vf_parts)]

    args += ["-c:v", CODECS[codec]]
    if codec in ("h264", "h265"):
        args += ["-crf", str(crf), "-preset", "medium"]
    elif codec == "vp9":
        args += ["-crf", str(crf), "-b:v", "0"]
    elif codec == "av1":
        args += ["-crf", str(crf), "-b:v", "0", "-cpu-used", "4"]

    audio_codec = "aac" if fmt in ("mp4", "mov") else "libopus" if fmt == "webm" else "aac"
    args += ["-c:a", audio_codec, "-b:a", "192k"]

    args.append(str(out_path))

    t0 = time.time()
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    elapsed = time.time() - t0

    if proc.returncode != 0 or not out_path.exists():
        return JSONResponse(
            {"error": "ffmpeg failed", "detail": stderr.decode(errors="replace")[-500:]},
            status_code=500,
        )

    return {
        "path": str(out_path),
        "filename": out_filename,
        "url": f"/api/frame/serve?path={out_path}",
        "size_bytes": out_path.stat().st_size,
        "elapsed_s": round(elapsed, 1),
    }



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


# ----------------------------------------------------------------------------
# 3D mesh re-texture (Path B: texture swap)
# ----------------------------------------------------------------------------
# These two endpoints decouple geometry from texture: the user can extract
# the baseColor atlas of an existing GLB, run it through any 2D AI tool
# (Style Remix, image-tools, Qwen, …), then write the edited PNG back into
# a new GLB with identical geometry/UVs. See spec at
# docs/superpowers/specs/2026-05-03-3d-retexture-design.md.

def _resolve_storage_url(url_or_path: str) -> Path | None:
    """Translate a storage URL or absolute path to a filesystem Path.

    Accepts the URL conventions used across the studio:
      - shorthand `/storage/<filename>` (gallery API — basename resolved
        via `store.resolve_asset` searching projects+unsorted)
      - deep `/storage/<dir>/<dir>/<filename>` (direct relative path)
      - `/api/frame/serve?path=<abs>` (image-mutation endpoints; the real
        path lives inside the query string, not the URL path)
      - absolute `http(s)://host/...` (cache-busted asset URLs)

    Returns None on lookup failure or path-traversal attempts.
    """
    import storage as store
    from urllib.parse import urlsplit, parse_qs

    if not url_or_path:
        return None

    # Strip any absolute origin so we work with the path component.
    cleaned = url_or_path
    for prefix in ("http://", "https://"):
        if cleaned.startswith(prefix):
            slash = cleaned.find("/", len(prefix))
            cleaned = cleaned[slash:] if slash != -1 else ""
            break

    parts = urlsplit(cleaned)
    path_only = parts.path
    qs = parse_qs(parts.query)

    if path_only == "/api/frame/serve":
        # The actual filesystem path rides in the query string. _assert_under_storage
        # below stops anything outside STORAGE_ROOT regardless.
        raw = qs.get("path", [""])[0]
        if not raw:
            return None
        candidate = Path(raw)
    elif path_only.startswith("/storage/"):
        rel = path_only[len("/storage/"):]
        # Prefer the explicit deep path if it exists (avoids basename
        # collisions across project subdirs); fall back to resolve_asset
        # for shorthand `/storage/<filename>` URLs from /api/gallery.
        direct = store.STORAGE_ROOT / rel
        candidate = direct if direct.exists() else store.resolve_asset(path_only)
    else:
        candidate = Path(path_only)

    if candidate is None:
        return None
    try:
        candidate = candidate.resolve()
        _assert_under_storage(candidate)
    except (PermissionError, OSError):
        return None
    return candidate if candidate.exists() else None


@app.post("/api/3d/extract-texture")
async def api_3d_extract_texture(request: Request):
    """Extract the baseColor PNG from a GLB.

    Caches the result next to the source as `<stem>.texture.png` so
    repeat extracts (e.g. user opens the texture editor twice) skip
    the decode. Cache invalidates when the source GLB's mtime advances.
    """
    import storage as store
    from texture_io import extract_basecolor

    data = await request.json()
    source = data.get("source_glb")
    material_index = int(data.get("material_index", 0))

    glb_path = _resolve_storage_url(source)
    if glb_path is None:
        return JSONResponse({"error": "Source GLB not found"}, status_code=404)

    cache_path = glb_path.with_suffix(".texture.png")
    cache_fresh = (
        cache_path.exists()
        and cache_path.stat().st_mtime >= glb_path.stat().st_mtime
    )
    if not cache_fresh:
        try:
            png_bytes, width, height = extract_basecolor(
                glb_path, material_index=material_index
            )
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        cache_path.write_bytes(png_bytes)
    else:
        from PIL import Image as _PIL
        with _PIL.open(cache_path) as im:
            width, height = im.size

    # Return the shorthand `/storage/<basename>` URL — the gallery and
    # serve_storage_file route both resolve by basename via resolve_asset,
    # so the deep path stays an internal detail.
    return JSONResponse({
        "texture_url": f"/storage/{cache_path.name}",
        "width": width,
        "height": height,
        "material_index": material_index,
    })


@app.post("/api/3d/apply-texture")
async def api_3d_apply_texture(request: Request):
    """Swap a GLB's baseColor with an edited PNG, write a new GLB.

    Output goes next to the source as `<stem>-retex-<6chars>.glb` so
    related files stay grouped. Geometry, UVs, and other PBR channels
    (metallicRoughness, normal, occlusion, emissive) are byte-stable.
    """
    import storage as store
    from texture_io import apply_basecolor

    data = await request.json()
    source = data.get("source_glb")
    edited = data.get("edited_texture")
    material_index = int(data.get("material_index", 0))

    glb_path = _resolve_storage_url(source)
    if glb_path is None:
        return JSONResponse({"error": "Source GLB not found"}, status_code=404)
    edited_path = _resolve_storage_url(edited)
    if edited_path is None:
        return JSONResponse({"error": "Edited texture not found"}, status_code=404)

    out_filename = f"{glb_path.stem}-retex-{uuid.uuid4().hex[:6]}.glb"
    out_path = glb_path.parent / out_filename

    try:
        apply_basecolor(
            glb_path,
            edited_path.read_bytes(),
            out_path,
            material_index=material_index,
        )
    except ValueError as exc:
        return JSONResponse({"error": str(exc)}, status_code=400)

    return JSONResponse({"new_glb_url": f"/storage/{out_path.name}"})


@app.post("/api/3d/stage-texture")
async def api_3d_stage_texture(request: Request):
    """Stage a base64-encoded PNG to /storage/ so it can be referenced
    by `/api/3d/apply-texture`. Used by the mesh-edit page when the
    user uploads an edited atlas directly (vs. routing through
    image-edit / remix which already write to /storage/).
    """
    import storage as store

    data = await request.json()
    filename = (data.get("filename") or "edited").rsplit(".", 1)[0]
    safe_stem = "".join(c for c in filename if c.isalnum() or c in "-_")[:40] or "edited"
    b64 = data.get("image_b64")
    if not b64:
        return JSONResponse({"error": "image_b64 required"}, status_code=400)
    try:
        png_bytes = base64.b64decode(b64)
    except Exception as exc:
        return JSONResponse({"error": f"invalid base64: {exc}"}, status_code=400)

    out_dir = store.unsorted_dir() / "images"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_filename = f"{safe_stem}-{uuid.uuid4().hex[:6]}.png"
    out_path = out_dir / out_filename
    out_path.write_bytes(png_bytes)
    return JSONResponse({"url": f"/storage/{out_filename}"})


@app.get("/api/meme/templates")
async def api_meme_templates():
    """Return meme template definitions from templates.json."""
    templates_path = Path("static/images/meme-templates/templates.json")
    if templates_path.exists():
        async with aiofiles.open(templates_path) as f:
            return JSONResponse(json.loads(await f.read()))
    return JSONResponse([])


@app.get("/api/sprites/models")
async def api_sprite_models():
    """List sprite-generation model IDs registered in the ComfyUI backend.

    Consumed by /studio/meme and /studio/sprite. Returns a flat list of
    keys; consumers tolerate both `[name, ...]` and `{models: [...]}`.
    """
    from backends.comfyui import SPRITE_MODELS
    return JSONResponse(list(SPRITE_MODELS.keys()))


@app.get("/api/sprite/game-presets")
async def api_sprite_game_presets():
    """List retro-game palette/dimension presets from studio.sprite_tools.

    Each entry: {id, label, width, height, palette, max_colors, rom_extract?}.
    Consumed by /studio/sprite for the "Game format" dropdown.
    """
    from studio.sprite_tools import PRESETS
    return JSONResponse(PRESETS)


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


# --- Sprite sheet generation ------------------------------------------------
#
# Wraps comfyui.generate_sprites() in a per-pose loop, then composes the
# individual frames into a sheet via studio.sprite_tools.compose_sheet().
# The single-shot sprite path lives in /api/meme/generate (which reuses
# generate_sprites for IP-Adapter-conditioned single images); this
# endpoint is the multi-frame, sheet-output variant.

@app.post("/api/sprite/sheet")
async def api_sprite_sheet(request: Request):
    """Generate a sprite sheet: N frames of one character in different poses.

    Body:
        reference_image_b64 (str, required): PNG/JPEG bytes of the character
        poses (list[str], required): pose IDs (e.g. ["idle", "walk_1", "attack"])
        preset (str): "tight" (identity-lock) or "loose" (variety). Default "tight".
        model (str): SPRITE_MODELS key. Default "juggernautXL_v9".
        style_hint (str, optional): freeform style modifier appended per frame
        columns (int): grid columns. Default 4.
        cell_size (int): frame side length in the composed sheet. Default 256.
        seed (int, optional): -1 for random; same seed across frames helps consistency
        steps (int, optional): override model default
        cfg (float, optional): override preset cfg
    """
    from studio import sprite_sheet

    data = await request.json()
    ref_b64 = data.get("reference_image_b64", "")
    poses_raw = data.get("poses") or sprite_sheet.DEFAULT_POSES
    preset_id = data.get("preset", "tight")
    model = data.get("model", "juggernautXL_v9")
    style_hint = (data.get("style_hint") or "").strip()
    columns = int(data.get("columns", 4))
    cell_size = int(data.get("cell_size", 256))
    seed_in = data.get("seed", -1)
    steps_in = data.get("steps")
    cfg_in = data.get("cfg")
    # Game format: when set, each cleaned frame is run through
    # sprite_tools.constrain_sprite (downscale + palette quantize) for
    # actual game-ready output. None = keep cell_size RGBA frames.
    game_preset_id = data.get("game_preset") or None

    if not ref_b64:
        return JSONResponse({"error": "reference_image_b64 is required"}, status_code=400)

    if preset_id not in sprite_sheet.PRESETS:
        return JSONResponse(
            {"error": f"preset must be one of {list(sprite_sheet.PRESETS)}"},
            status_code=400,
        )

    if game_preset_id is not None:
        from studio.sprite_tools import get_preset as _get_game_preset
        if _get_game_preset(game_preset_id) is None:
            return JSONResponse(
                {"error": f"unknown game_preset {game_preset_id!r}"},
                status_code=400,
            )

    poses = sprite_sheet.normalise_poses(poses_raw)
    if not poses:
        return JSONResponse({"error": "at least one pose required"}, status_code=400)
    if len(poses) > 32:
        return JSONResponse({"error": "max 32 poses per sheet"}, status_code=400)

    job_id = str(uuid.uuid4())[:8]
    output_dir = Path("outputs/sprite") / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Persist the reference image so the ComfyUI backend can read it from
    # a stable path. generate_sprites copies into ComfyUI/input itself, so
    # absolute path is fine.
    try:
        ref_bytes = base64.b64decode(ref_b64)
    except Exception:
        return JSONResponse({"error": "reference_image_b64 is not valid base64"},
                            status_code=400)
    ref_path = output_dir / "reference.png"
    ref_path.write_bytes(ref_bytes)

    jobs[job_id] = {
        "status": "queued", "progress": 0,
        "params": {"type": "sprite_sheet", "poses": poses, "preset": preset_id,
                   "model": model},
    }

    async def _run_sprite_sheet():
        await _run_sprite_sheet_job(
            job_id=job_id,
            output_dir=output_dir,
            ref_path=ref_path,
            poses=poses,
            preset_id=preset_id,
            model=model,
            style_hint=style_hint,
            columns=columns,
            cell_size=cell_size,
            seed_in=int(seed_in) if seed_in is not None else -1,
            steps_override=int(steps_in) if steps_in is not None else None,
            cfg_override=float(cfg_in) if cfg_in is not None else None,
            game_preset_id=game_preset_id,
        )

    # Lane default is 300s — way too short for sprite jobs. Cold start
    # (model load + IPAdapter + CLIP-Vision) eats ~180s on its own; each
    # warm frame is ~80-120s including rembg. Budget 240s cold start +
    # 180s per pose. 4 poses → 16 min cap, 32 poses → 100 min cap.
    sprite_timeout = 240 + len(poses) * 180
    job_queue.submit_background(_run_sprite_sheet(), lane="gpu",
                                job_id=f"sprite-{job_id}",
                                timeout=sprite_timeout)
    return {"job_id": job_id}


async def _run_sprite_sheet_job(
    *,
    job_id: str,
    output_dir: Path,
    ref_path: Path,
    poses: list[str],
    preset_id: str,
    model: str,
    style_hint: str,
    columns: int,
    cell_size: int,
    seed_in: int,
    steps_override: int | None,
    cfg_override: float | None,
    game_preset_id: str | None = None,
) -> None:
    """Loop generate_sprites() per pose, optionally palette-quantize each
    frame to a retro game format, compose sheet, zip frames."""
    from studio import sprite_sheet
    from studio.sprite_tools import compose_sheet, get_preset as _get_game_preset, constrain_sprite

    preset = sprite_sheet.PRESETS[preset_id]
    game_preset = _get_game_preset(game_preset_id) if game_preset_id else None
    layout = sprite_sheet.plan_layout(
        len(poses), columns=columns,
        cell_width=cell_size, cell_height=cell_size,
    )
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    # Fix the seed across frames so character identity stays stable.
    # IP-Adapter does most of the lifting but a shared seed reduces drift.
    import random
    seed = seed_in if seed_in != -1 else random.randint(0, 2**32 - 1)

    jobs[job_id]["status"] = "running"
    await broadcast({"type": "job_update", "job_id": job_id,
                     "status": "running", "progress": 0})

    try:
        comfyui = registry.get_backend("comfyui")

        sprites_for_sheet: list[dict] = []
        total = len(poses)

        for idx, pose in enumerate(poses):
            base_pct = int(5 + (idx / total) * 85)

            async def on_progress(pct, msg="", _base=base_pct, _idx=idx, _pose=pose):
                # Map ComfyUI's 0-100 inner progress to our slice for this frame.
                frame_share = 85 / total
                overall = int(_base + (pct / 100) * frame_share)
                jobs[job_id]["progress"] = overall
                await broadcast({
                    "type": "job_update", "job_id": job_id,
                    "status": "running", "progress": overall,
                    "message": f"frame {_idx + 1}/{total} ({_pose}) — {msg}",
                })

            prompt = sprite_sheet.build_pose_prompt(pose, style_hint=style_hint)

            # Build params; omit `steps` entirely when no override so
            # generate_sprites() falls back to the model's tuned default
            # instead of trying to convert None to int (ComfyUI rejects).
            # single_frame=True asks the backend to use the isolated-subject
            # prompt grammar instead of the sheet-style one (the latter
            # otherwise produces mini-sheets inside each frame).
            gen_params: dict = {
                "prompt": prompt,
                "model": model,
                "batch_size": 1,
                "seed": seed,
                "single_frame": True,
                "cfg": cfg_override if cfg_override is not None else preset["cfg"],
                "ip_adapter_strength": preset["ip_adapter_strength"],
                "ip_adapter_weight_type": preset["ip_adapter_weight_type"],
                "ip_adapter_start": preset["ip_adapter_start"],
                "ip_adapter_end": preset["ip_adapter_end"],
                "reference_images": [str(ref_path)],
            }
            if steps_override is not None:
                gen_params["steps"] = steps_override

            meta = await comfyui.generate_sprites(
                gen_params, str(frames_dir / pose), on_progress)

            # generate_sprites writes to {output_dir}/sprite_0.png etc.; for a
            # batch-of-1 the file we want is sprite_0.png in the per-pose dir.
            src_files = meta.get("files", [])
            if not src_files:
                raise RuntimeError(f"no output for pose {pose}")
            raw = Path(src_files[0])

            # Post-process: rembg + largest-blob crop + centre on transparent
            # canvas. Solves the SDXL "row of mini-poses per frame" problem
            # that prompt-engineering alone can't fix.
            from studio import sprite_postprocess
            dest = frames_dir / f"{idx:02d}_{pose}.png"
            extract_meta = await sprite_postprocess.extract_subject(
                raw, dest,
                target_size=layout.cell_width,
                rembg_bin=_REMBG_BIN,
            )
            raw.unlink(missing_ok=True)
            # Clean up per-pose subdir (it's empty now apart from maybe debris).
            try:
                (frames_dir / pose).rmdir()
            except OSError:
                pass

            # Optional: palette-quantize to a retro game format. Replaces
            # the cleaned RGBA frame at `dest` with an indexed PNG at the
            # preset's target dimensions (e.g. X-COM Unit = 32x40). The
            # subsequent compose_sheet step's NEAREST resize will scale
            # this up to cell_size for the visible sheet, preserving the
            # pixel-art aesthetic.
            if game_preset:
                constrain_sprite(
                    input_path=str(dest),
                    output_path=str(dest),
                    palette_name=game_preset["palette"],
                    max_colors=game_preset["max_colors"],
                    target_width=game_preset["width"],
                    target_height=game_preset["height"],
                )

            sprites_for_sheet.append({
                "path": str(dest), "slot": idx,
                "blobs_found": extract_meta.blobs_found,
                "chosen_pixels": extract_meta.chosen_pixels,
            })

        # Compose the sheet.
        sheet_path = output_dir / "sheet.png"
        sheet_meta = compose_sheet(
            sprites=sprites_for_sheet,
            cell_width=layout.cell_width,
            cell_height=layout.cell_height,
            columns=layout.columns,
            output_path=str(sheet_path),
        )

        # Zip frames for one-click download.
        import zipfile
        zip_path = output_dir / "frames.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for sp in sprites_for_sheet:
                zf.write(sp["path"], arcname=Path(sp["path"]).name)

        # Sidecar.
        (output_dir / "out.json").write_text(json.dumps({
            "poses": poses,
            "preset": preset_id,
            "model": model,
            "style_hint": style_hint,
            "seed": seed,
            "columns": layout.columns,
            "rows": layout.rows,
            "cell": [layout.cell_width, layout.cell_height],
            "sheet": [layout.sheet_width, layout.sheet_height],
            "game_preset": game_preset_id,
            "game_format": (
                {"id": game_preset["id"], "width": game_preset["width"],
                 "height": game_preset["height"], "palette": game_preset["palette"],
                 "max_colors": game_preset["max_colors"]}
                if game_preset else None
            ),
            "frames": [Path(s["path"]).name for s in sprites_for_sheet],
        }, indent=2))

        sheet_url = f"/outputs/sprite/{job_id}/sheet.png"
        zip_url = f"/outputs/sprite/{job_id}/frames.zip"
        frame_urls = [
            f"/outputs/sprite/{job_id}/frames/{Path(s['path']).name}"
            for s in sprites_for_sheet
        ]

        update = {
            "status": "complete", "progress": 100,
            "output_url": sheet_url,
            "sheet_url": sheet_url,
            "zip_url": zip_url,
            "frame_urls": frame_urls,
            "sheet": sheet_meta,
        }
        jobs[job_id].update(update)
        await broadcast({"type": "job_update", "job_id": job_id, **update})
    except asyncio.CancelledError:
        # Job lane timed out (or someone called /api/cancel). CancelledError
        # is a BaseException so the broad `except Exception` below would miss
        # it, leaving the UI frozen at the last progress %. Broadcast a
        # clean error and re-raise so the cancellation still propagates.
        jobs[job_id].update({
            "status": "error",
            "error": "job timed out (try fewer poses or wait — ComfyUI cold-start "
                     "model load can eat 3 min before frame 1 even starts)",
        })
        await broadcast({"type": "job_update", "job_id": job_id,
                         "status": "error",
                         "error": jobs[job_id]["error"]})
        raise
    except Exception as exc:
        jobs[job_id].update({"status": "error", "error": str(exc)})
        await broadcast({"type": "job_update", "job_id": job_id,
                         "status": "error", "error": str(exc)})


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
_music_engine_error: str | None = None


def _get_music_engine():
    global _music_engine, _music_engine_error
    if _music_engine is None:
        try:
            from studio.music_gen import MusicGenEngine
            engine = MusicGenEngine(config.get("music", {}))
            # Force the real import so a missing transitive dep surfaces its
            # actual name instead of collapsing to a generic "not installed".
            import audiocraft  # noqa: F401
            _music_engine = engine
            _music_engine_error = None
        except ImportError as e:
            missing = getattr(e, "name", None) or "audiocraft"
            if missing == "audiocraft":
                _music_engine_error = "audiocraft not installed. Run: pip install audiocraft"
            else:
                _music_engine_error = (
                    f"audiocraft is installed but its import requires '{missing}', "
                    f"which is not installed. Run: pip install {missing}"
                )
        except Exception as e:
            _music_engine_error = f"audiocraft failed to load: {e.__class__.__name__}: {e}"
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
    return {
        "available": False,
        "reason": _music_engine_error or "audiocraft not installed (pip install audiocraft)",
    }


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

    # Music runs on the same GPU as ComfyUI/WorldGen, so it MUST go through
    # the gpu lane (Semaphore(1) - serial). A bare asyncio.create_task here
    # bypasses the lane and lets musicgen run concurrently with an active
    # worldgen / image-gen job; on a 24 GB 7900 XTX that combo blew up at
    # hipErrorLaunchFailure on 2026-05-12 and triggered an amdgpu MODE1
    # reset. 1800s timeout matches 3D mesh runs - long continuation chunks
    # (3 x 30 s) can push past the 300 s gpu default. job_id matches the
    # user-facing id so /api/job/{id}/cancel can actually find the task.
    job_queue.submit_background(
        _do(), lane="gpu", job_id=job_id, timeout=1800,
    )

    return {"job_id": job_id, "status": "queued"}


# --- SFX Generation API (AudioGen) ---
#
# Mirror of the Music API above: same audiocraft library, same GPU
# claim/release pattern, same gpu-lane serialisation. AudioGen is built
# for environmental sounds and SFX (footsteps, rain, applause, glass
# breaking) rather than music - if a user wants drum patterns or melody,
# they should use the Music page instead.

_sfx_engine = None
_sfx_engine_error: str | None = None


def _get_sfx_engine():
    global _sfx_engine, _sfx_engine_error
    if _sfx_engine is None:
        try:
            from studio.sfx_gen import SfxGenEngine
            engine = SfxGenEngine(config.get("sfx", {}))
            # Force the AudioGen import so transitive misses surface their
            # real name (audiocraft itself is shared with MusicGen).
            from audiocraft.models import AudioGen  # noqa: F401
            _sfx_engine = engine
            _sfx_engine_error = None
        except ImportError as e:
            missing = getattr(e, "name", None) or "audiocraft"
            if missing == "audiocraft":
                _sfx_engine_error = "audiocraft not installed. Run: pip install audiocraft"
            else:
                _sfx_engine_error = (
                    f"audiocraft is installed but its import requires '{missing}', "
                    f"which is not installed. Run: pip install {missing}"
                )
        except Exception as e:
            _sfx_engine_error = f"audiocraft failed to load: {e.__class__.__name__}: {e}"
    return _sfx_engine


@app.post("/api/gpu/claim-sfx")
async def gpu_claim_sfx():
    """Free ComfyUI VRAM and preload the AudioGen model on the GPU.

    Mirror of /api/gpu/claim-music. Stops ComfyUI from holding ~12 GB
    of FLUX/SDXL weights so AudioGen's ~5 GB has room.
    """
    await _free_comfyui()
    engine = _get_sfx_engine()
    if not engine:
        return JSONResponse(
            {"error": _sfx_engine_error or "AudioGen not available"},
            status_code=503)
    engine.preload()
    raw_device = getattr(engine, "_device", "unknown")
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


@app.post("/api/gpu/release-sfx")
async def gpu_release_sfx():
    """Unload AudioGen so ComfyUI / other workloads can use VRAM."""
    engine = _get_sfx_engine()
    if engine:
        engine._unload_model()
    return {"ok": True}


@app.get("/api/sfx/status")
async def sfx_status():
    """Check if SFX generation is available + what model(s) it offers."""
    engine = _get_sfx_engine()
    if engine:
        return {"available": True, "models": engine.models(),
                "max_duration": engine.MAX_DURATION}
    return {
        "available": False,
        "reason": _sfx_engine_error or "audiocraft not installed (pip install audiocraft)",
    }


@app.post("/api/sfx/generate")
async def sfx_generate(request: Request):
    """Generate an SFX clip from a text prompt.

    Returns immediately with a job_id; poll /api/job/{id} or use the WS
    broadcast like other GPU jobs. Submission goes through job_queue on
    lane="gpu" (Semaphore(1)) so it serialises against ComfyUI worldgen
    and MusicGen - the same crash this fixes on 2026-05-12.
    """
    engine = _get_sfx_engine()
    if not engine:
        return JSONResponse(
            {"error": _sfx_engine_error or "SFX generation not available"},
            status_code=503)

    data = await request.json()
    prompt = data.get("prompt", "").strip()
    duration = float(data.get("duration", 5.0))
    model_id = data.get("model", "") or None

    if not prompt:
        return JSONResponse({"error": "No prompt provided"}, status_code=400)

    job_id = str(uuid.uuid4())[:8]
    import storage as store
    output_path = str(store.asset_path(job_id, "audio", ".wav"))

    jobs[job_id] = {"status": "queued", "progress": 0, "type": "sfx"}

    async def _do():
        try:
            jobs[job_id]["status"] = "running"
            meta = await engine.generate(prompt, output_path, duration, model_id)
            jobs[job_id].update({
                "status": "complete", "progress": 100,
                "url": f"/storage/{job_id}.wav",
                "prompt": prompt,
                **meta,
            })
        except Exception as e:
            jobs[job_id].update({"status": "error", "error": str(e)})

    # gpu lane (Semaphore(1)) - serialises with worldgen / image-gen /
    # musicgen. 600s timeout covers a 10s clip with model cold-load and
    # CPU fallback if VRAM is tight. job_id matches the user-facing id so
    # /api/job/{id}/cancel can actually find the task.
    job_queue.submit_background(
        _do(), lane="gpu", job_id=job_id, timeout=600,
    )

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
    ip_adapter_model: str = Form(""),
    ip_adapter_strength: float = Form(0.6),
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

    if ref_paths and not ip_adapter_model:
        comfy_entries = [e for e in backend_list if e.get("backend") == "comfyui"]
        if comfy_entries:
            return JSONResponse(
                {"error": "Reference images require an IP-Adapter model on the ComfyUI backend. "
                          "Pick one from the IP-Adapter Model dropdown, or remove the ComfyUI "
                          "entries from the comparison."},
                status_code=400,
            )

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
            "ip_adapter_model": ip_adapter_model,
            "ip_adapter_strength": ip_adapter_strength,
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

# Valid IPAdapterBatch weight_type values in current ComfyUI_IPAdapter_plus.
# The previous set ("standard", "prompt is more important") was rejected with
# node_errors.value_not_in_list — those names were dropped upstream.
_BLEND_MODE_VALUES = {
    "strong style transfer",
    "style transfer",
    "style and composition",
    "linear",
}


@app.post("/api/remix")
async def remix(
    base_image: UploadFile | None = File(default=None),
    base_gallery_id: str = Form(""),
    style_ref: UploadFile | None = File(default=None),
    crypto_logo_id: str = Form(""),
    # Atlas-SAM re-texture path: when the caller supplies a mask, the
    # backend post-composites the generated atlas back into the base
    # using the mask (white = replace, black = preserve). Optional.
    mask_image: UploadFile | None = File(default=None),
    preserve_character: float = Form(0.45),
    style_strength: float = Form(0.75),
    ip_start: float = Form(0.0),
    ip_end: float = Form(0.8),
    blend_mode: str = Form("strong style transfer"),
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

    # Atlas-SAM mask: only persisted + threaded into params when supplied.
    # Backwards-compat — image-mode remix never sends a mask, so this
    # branch is skipped and the existing pipeline runs unchanged.
    mask_filename = ""
    if mask_image is not None and mask_image.filename:
        mask_id = str(uuid.uuid4())[:8]
        mask_ext = Path(mask_image.filename).suffix or ".png"
        mask_dest = Path("uploads") / f"remix_mask_{mask_id}{mask_ext}"
        async with aiofiles.open(mask_dest, "wb") as f:
            await f.write(await mask_image.read())
        mask_filename = f"remix_mask_{uuid.uuid4().hex[:8]}{mask_ext}"
        _shutil.copy2(mask_dest, comfy_input_dir / mask_filename)

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
            "mask_filename": mask_filename,  # empty string when not in mesh-mode
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
    local = {"comfyui", "fooocus", "a1111", "hidream", "sensenova"}
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
    """Backend-aware cancel: actually free the GPU, not just the asyncio task.

    The asyncio cancel from JobQueue.cancel() unblocks our event loop, but
    by itself does NOT preempt CUDA/ROCm kernels - those run to completion
    inside the worker process. So we also signal the relevant backend:

    * **SenseNova infographic jobs** → restart sensenova-worker.service.
      The worker holds a single GPU lock around each render; a SIGTERM is
      the only reliable way to interrupt the in-flight diffusion loop. The
      unit has Restart=on-failure so an explicit restart bounces it back
      up clean.
    * **ComfyUI image / 3D / worldgen jobs** → POST /interrupt to the
      ComfyUI HTTP API. Stops the current step boundary and clears the
      queue head; the orphan-rescue path in backends/comfyui.py still
      picks up any in-progress GLB.

    Best-effort: a failure here doesn't block the user-visible "cancelled"
    status the caller will set - the asyncio cancel already happened.
    """
    job = jobs.get(job_id) or {}
    params = job.get("params") or {}
    is_sensenova = params.get("backend") == "sensenova"

    if is_sensenova:
        try:
            await _wl.sensenova_restart()
        except Exception as exc:
            print(f"[cancel] sensenova restart failed for {job_id}: {exc}")
        return

    # ComfyUI-backed: send /interrupt. URL is read from config so a remote
    # ComfyUI is reachable too. 1.5s timeout - this is a localhost call on
    # the happy path.
    comfy_url = config.get("backends", {}).get("comfyui", {}).get("url", "")
    if not comfy_url:
        return
    try:
        import httpx
        async with httpx.AsyncClient(timeout=1.5) as client:
            await client.post(f"{comfy_url.rstrip('/')}/interrupt")
    except Exception as exc:
        print(f"[cancel] comfyui /interrupt failed for {job_id}: {exc}")


# -----------------------------------------------------------------------------
# /api/sensenova/render — freeform-prompt SenseNova render.
#
# Takes a complete prompt + explicit dimensions, runs T2I via the worker
# daemon, and broadcasts progress over the same WS the rest of the studio
# uses. Cancel-via-restart is handled by the hook above (_cancel_in_flight)
# which keys on params["backend"] == "sensenova".
# -----------------------------------------------------------------------------


class _SenseNovaRenderBody(BaseModel):
    prompt: str = Field(min_length=1)
    width: int = Field(ge=512, le=2720)
    height: int = Field(ge=512, le=2720)
    seed: int = Field(default=42, ge=0)
    cfg_scale: float = Field(default=4.0, ge=0.5, le=10.0)
    num_steps: int = Field(default=50, ge=4, le=100)
    # 2026-05-13: infographic flow can now route to HiDream-O1 instead of
    # SenseNova-U1 for text-accuracy-sensitive jobs. HiDream's pixel-DiT
    # design preserves glyphs through generation (no VAE blur), making it
    # markedly better for infographics, posters, and any image where the
    # rendered text must match the prompt exactly. Default stays sensenova
    # to preserve existing behaviour.
    backend: str = Field(default="sensenova", pattern="^(sensenova|hidream)$")
    # SCALIST prompt-rewriter — only consulted when backend == "hidream".
    # HiDream's leaderboard text-rendering scores assume the prompt has
    # been pre-processed by this rewriter (the model was trained on
    # SCALIST-shaped prompts that spell out exact glyphs, fonts, materials,
    # and positions). Default ON for HiDream renders; toggle off for A/B.
    use_prompt_agent: bool = Field(default=True)
    # Reserve N solid-magenta placeholder rectangles in the render so a
    # downstream UI can composite logos/images into them. 0 = off, keeps
    # the existing flow bit-identical. >0 appends a sentinel instruction
    # to the prompt and runs the detector after the PNG lands, writing
    # out.slots.json next to out.png.
    reserve_logo_slots: int = Field(default=0, ge=0, le=10)


@app.post("/api/sensenova/render", status_code=202)
async def sensenova_render(body: _SenseNovaRenderBody):
    """Freeform-prompt render. Returns job_id; PNG arrives over WS.

    Dispatches to the selected backend (sensenova-worker on port 9091 or
    hidream-worker on port 9092). Endpoint kept under ``/api/sensenova/``
    for backward compatibility with existing infographic UI bindings.
    """
    job_id = uuid.uuid4().hex[:12]
    params = {
        "prompt": body.prompt,
        "width": body.width,
        "height": body.height,
        "seed": body.seed,
        "cfg_scale": body.cfg_scale,
        "num_steps": body.num_steps,
        "backend": body.backend,  # consumed by the cancel hook
        "use_prompt_agent": body.use_prompt_agent,
        "reserve_logo_slots": body.reserve_logo_slots,
    }
    jobs[job_id] = {"status": "queued", "params": params, "progress": 0}
    runner = (
        _run_hidream_render_job
        if body.backend == "hidream"
        else _run_sensenova_render_job
    )
    job_queue.submit_background(
        runner(job_id, params),
        lane="gpu",
        job_id=job_id,
        # 30 min — SenseNova at 2048+ can take 5–7 min; the JobQueue's
        # default 300 s gpu-lane timeout was clipping renders mid-flight,
        # leaving the worker to finish into an orphan PNG and the UI stuck.
        # HiDream is faster (~45 s at 2048×2048) but inherits the cap.
        timeout=1800,
    )
    return {"job_id": job_id}


async def _run_sensenova_render_job(job_id: str, params: dict) -> None:
    """Background runner — bypasses the template assembler entirely."""
    from backends import sensenova_client
    from backends.sensenova_client import SenseNovaWorkerError
    from progress_smooth import SmoothProgress
    from studio.worker_lifecycle import ensure_loaded, WorkerArbitrationError

    jobs[job_id]["status"] = "running"
    await broadcast({
        "type": "job_update", "job_id": job_id,
        "status": "running", "progress": 0,
    })

    output_dir = Path("outputs/sensenova-render") / job_id
    output_dir.mkdir(parents=True, exist_ok=True)

    async def on_progress(pct: int, msg: str = ""):
        jobs[job_id]["progress"] = pct
        await broadcast({
            "type": "job_update", "job_id": job_id,
            "status": "running", "progress": pct, "message": msg,
        })

    async def on_arbitration(msg: str) -> None:
        # Surface worker-swap progress at a low pct so the SmoothProgress
        # creep (which starts at 10) keeps moving forward when the render
        # itself begins.
        await on_progress(3, msg)

    try:
        # Auto-orchestrate: stop hidream-worker if it's holding the GPU,
        # start sensenova-worker, wait for "loaded: true". Skips the
        # stop/start when sensenova is already loaded (the common case).
        try:
            await ensure_loaded("sensenova", on_status=on_arbitration)
        except WorkerArbitrationError as exc:
            raise SenseNovaWorkerError(f"worker arbitration: {exc}") from exc

        # When the caller requested logo slots, splice the sentinel
        # instruction onto the prompt so the model paints magenta
        # placeholders we can detect after the render.
        from studio.logo_slot_detector import build_sentinel_prompt, detect_and_save
        slot_count = int(params.get("reserve_logo_slots") or 0)
        effective_prompt = build_sentinel_prompt(params["prompt"], n=slot_count)

        async with SmoothProgress(on_progress, tick_seconds=2.0, max_creep=85) as sp:
            await sp.set(10, "rendering")
            png = await sensenova_client.render_t2i(
                prompt=effective_prompt,
                output_dir=output_dir,
                width=params["width"],
                height=params["height"],
                seed=params["seed"],
                cfg_scale=params["cfg_scale"],
                num_steps=params["num_steps"],
                timeout_s=1800,
            )
            await sp.set(95, "saving")

        # Canonicalise to out.png so a future history view can find it.
        canonical = output_dir / "out.png"
        if png != canonical:
            try:
                png.rename(canonical)
                png = canonical
            except OSError:
                pass

        slots_summary: dict | None = None
        if slot_count > 0:
            try:
                slots_summary = detect_and_save(png, requested=slot_count)
            except Exception as exc:  # detector failure must not kill render
                slots_summary = {"error": str(exc), "requested": slot_count,
                                 "detected": 0}

        # Sidecar with the full params (for future history/re-render features).
        try:
            (output_dir / "out.json").write_text(json.dumps({
                "prompt": params["prompt"],
                "width": params["width"],
                "height": params["height"],
                "seed": params["seed"],
                "cfg_scale": params["cfg_scale"],
                "num_steps": params["num_steps"],
                "reserve_logo_slots": slot_count,
            }, indent=2))
        except Exception:
            pass

        try:
            rel = png.relative_to(Path("outputs"))
            output_url = f"/outputs/{rel.as_posix()}"
        except ValueError:
            output_url = str(png)

        update = {"status": "complete", "progress": 100, "output_url": output_url}
        if slots_summary is not None:
            update["slots"] = slots_summary
        jobs[job_id].update(update)
        broadcast_payload = {
            "type": "job_update", "job_id": job_id,
            "status": "complete", "progress": 100, "output_url": output_url,
        }
        if slots_summary is not None:
            broadcast_payload["slots"] = slots_summary
        await broadcast(broadcast_payload)
    except SenseNovaWorkerError as exc:
        jobs[job_id].update({"status": "error", "error": str(exc)})
        await broadcast({
            "type": "job_update", "job_id": job_id,
            "status": "error", "error": str(exc),
        })
    except asyncio.CancelledError:
        # JobQueue's wait_for timeout, or an explicit /cancel, raises this.
        # CancelledError is a BaseException — without this branch the job
        # dict stayed at "running" forever and the UI got stuck at 95%.
        jobs[job_id].update({"status": "cancelled"})
        try:
            await broadcast({
                "type": "job_update", "job_id": job_id,
                "status": "cancelled",
            })
        except Exception:
            pass
        raise  # let the JobQueue see it
    except Exception as e:
        jobs[job_id].update({"status": "error", "error": str(e)})
        await broadcast({
            "type": "job_update", "job_id": job_id,
            "status": "error", "error": str(e),
        })


async def _run_hidream_render_job(job_id: str, params: dict) -> None:
    """HiDream-O1 background runner — sibling of _run_sensenova_render_job.

    Routed when ``params["backend"] == "hidream"``. HiDream's worker writes
    its output into ``output_dir/out.png`` (same convention as SenseNova),
    so the surrounding canonicalisation + WS broadcast logic is identical.

    Caveats:

    * HiDream snaps sub-2048 resolutions up internally — the ``width``/
      ``height`` from the UI may be reshaped. The worker returns the actual
      rendered dimensions in ``actual_width`` / ``actual_height``; we don't
      currently surface them to the UI, the WS message just carries the URL.
    * ``num_steps`` from the UI is ignored — HiDream's "full" model is fixed
      at 50 steps. The form value still validates server-side (4..100) but
      doesn't reach the worker.
    * ``cfg_scale`` maps to HiDream's ``guidance_scale`` (Full mode default 5.0).
    * The worker must be running. Caller responsibility — start it via
      ``POST /api/hidream/worker/start`` before submitting. A clear
      HiDreamWorkerError propagates if it's stopped.
    """
    from backends import hidream_client
    from backends.hidream_client import HiDreamWorkerError
    from progress_smooth import SmoothProgress
    from studio.worker_lifecycle import ensure_loaded, WorkerArbitrationError

    jobs[job_id]["status"] = "running"
    await broadcast({
        "type": "job_update", "job_id": job_id,
        "status": "running", "progress": 0,
    })

    # Absolute path: the hidream-worker daemon runs with WorkingDirectory=
    # /home/phill/hidream-o1-image, so a relative path here would land
    # there instead of in Wyltek's outputs/. The sensenova_client path
    # works around this by being on the same WorkingDirectory; HiDream
    # needs an explicit absolute path.
    output_dir = (Path.cwd() / "outputs/sensenova-render" / job_id).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    async def on_progress(pct: int, msg: str = ""):
        jobs[job_id]["progress"] = pct
        await broadcast({
            "type": "job_update", "job_id": job_id,
            "status": "running", "progress": pct, "message": msg,
        })

    async def on_arbitration(msg: str) -> None:
        # Worker-swap progress at a low pct; SmoothProgress takes over from 10.
        await on_progress(3, msg)

    try:
        # When the caller requested logo slots, splice the sentinel
        # instruction onto the prompt so the model paints magenta
        # placeholders we can detect after the render.
        from studio.logo_slot_detector import build_sentinel_prompt, detect_and_save
        slot_count = int(params.get("reserve_logo_slots") or 0)
        sentinel_prompt = build_sentinel_prompt(params["prompt"], n=slot_count)

        # SCALIST prompt rewrite runs FIRST, before worker arbitration.
        # Ollama loads gemma4:26b into VRAM to do the rewrite; if hidream
        # is already resident (~17 GB), the two collide on a 24 GB card.
        # By running SCALIST first with keep_alive:0, gemma4 loads,
        # runs, and unloads BEFORE ensure_loaded brings hidream up.
        # Sequential VRAM use, no contention.
        render_prompt = sentinel_prompt
        rewrite_info: dict | None = None
        layout_bboxes: list | None = None
        if params.get("use_prompt_agent", True):
            from studio.hidream_prompt_agent import rewrite_prompt as _rewrite
            await on_progress(2, "rewriting prompt with SCALIST agent")
            # Feed the sentinel-augmented prompt to SCALIST so the rewrite
            # preserves the magenta-rectangle instruction. SCALIST keeps
            # the sentinel block verbatim in practice (it's already
            # specific and well-formed), so detection still works.
            rewrite_info = await _rewrite(sentinel_prompt)
            render_prompt = rewrite_info.get("prompt", sentinel_prompt)
            # SCALIST now also produces bbox coordinates per text element;
            # HiDream's generate_image takes these as hard layout constraints,
            # freeing the autoregressive attention budget from layout-choice
            # work. Empty list (no bboxes) is a no-op — renderer falls back
            # to its own layout inference.
            bboxes = rewrite_info.get("layout_bboxes") or []
            if bboxes:
                layout_bboxes = bboxes
            # Diagnostic trail lives in out.json (scalist_rewrite field).
            # Don't reach for a module logger — server.py doesn't configure
            # one, and an accidental `log.info(...)` here would NameError
            # inside the runner and surface as the user-facing render error.

        # Auto-orchestrate: stop sensenova-worker if it's holding the GPU,
        # start hidream-worker, wait for "loaded: true". Skips the
        # stop/start when hidream is already loaded (warm case).
        try:
            await ensure_loaded("hidream", on_status=on_arbitration)
        except WorkerArbitrationError as exc:
            raise HiDreamWorkerError(f"worker arbitration: {exc}") from exc

        async with SmoothProgress(on_progress, tick_seconds=2.0, max_creep=85) as sp:
            msg = "rendering (HiDream-O1)"
            if layout_bboxes:
                msg += f" with {len(layout_bboxes)} bboxes"
            await sp.set(10, msg)
            result = await hidream_client.render_t2i(
                prompt=render_prompt,
                output_dir=output_dir,
                width=params["width"],
                height=params["height"],
                seed=params["seed"],
                model_type="full",
                guidance_scale=float(params.get("cfg_scale", 5.0)),
                layout_bboxes=layout_bboxes,
                timeout_s=1800.0,
            )
            await sp.set(95, "saving")

        png = Path(result["png_path"])
        canonical = output_dir / "out.png"
        if png != canonical:
            try:
                png.rename(canonical)
                png = canonical
            except OSError:
                pass

        slots_summary: dict | None = None
        if slot_count > 0:
            try:
                slots_summary = detect_and_save(png, requested=slot_count)
            except Exception as exc:
                slots_summary = {"error": str(exc), "requested": slot_count,
                                 "detected": 0}

        try:
            (output_dir / "out.json").write_text(json.dumps({
                "backend": "hidream",
                "prompt": params["prompt"],
                "rewritten_prompt": render_prompt if rewrite_info else None,
                "scalist_rewrite": rewrite_info,
                "layout_bboxes_used": layout_bboxes,
                "width": params["width"],
                "height": params["height"],
                "seed": params["seed"],
                "cfg_scale": params["cfg_scale"],
                "num_steps": params["num_steps"],
                "reserve_logo_slots": slot_count,
                "actual_width": result.get("actual_width"),
                "actual_height": result.get("actual_height"),
                "elapsed_s": result.get("elapsed_s"),
            }, indent=2, ensure_ascii=False))
        except Exception:
            pass

        # output_dir is absolute here (see comment above), so png is absolute
        # too. The sensenova flow uses Path("outputs") which works only when
        # CWD is the project root and png is a relative path. Resolve both
        # to absolute first so relative_to() actually finds the prefix.
        try:
            abs_outputs = (Path.cwd() / "outputs").resolve()
            rel = png.relative_to(abs_outputs)
            output_url = f"/outputs/{rel.as_posix()}"
        except ValueError:
            output_url = str(png)

        update = {"status": "complete", "progress": 100, "output_url": output_url}
        if slots_summary is not None:
            update["slots"] = slots_summary
        jobs[job_id].update(update)
        broadcast_payload = {
            "type": "job_update", "job_id": job_id,
            "status": "complete", "progress": 100, "output_url": output_url,
        }
        if slots_summary is not None:
            broadcast_payload["slots"] = slots_summary
        await broadcast(broadcast_payload)
    except HiDreamWorkerError as exc:
        jobs[job_id].update({"status": "error", "error": str(exc)})
        await broadcast({
            "type": "job_update", "job_id": job_id,
            "status": "error", "error": str(exc),
        })
    except asyncio.CancelledError:
        jobs[job_id].update({"status": "cancelled"})
        try:
            await broadcast({
                "type": "job_update", "job_id": job_id,
                "status": "cancelled",
            })
        except Exception:
            pass
        raise
    except Exception as e:
        jobs[job_id].update({"status": "error", "error": str(e)})
        await broadcast({
            "type": "job_update", "job_id": job_id,
            "status": "error", "error": str(e),
        })


# -----------------------------------------------------------------------------
# Logo gallery — backs the manual-fill page (/studio/infographic-fill).
#
# Lives at static/assets/logos/ so existing /static StaticFiles mount serves
# the images directly. The /api/logos/* endpoints are the *manifest* layer:
# they list the folder and accept new uploads (drop-from-phone workflow).
# -----------------------------------------------------------------------------

LOGO_GALLERY_DIR = Path("static/assets/logos")
LOGO_ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".webp"}
LOGO_MAX_BYTES = 8 * 1024 * 1024  # 8 MB ceiling — plenty for any logo


def _safe_logo_name(raw: str) -> str:
    """Strip path components and clamp to a filesystem-safe basename.

    Allows letters, digits, dash, underscore, dot. Everything else collapses
    to underscores. Reserves an extension whitelist (raised to the caller if
    the extension is wrong).
    """
    base = Path(raw).name  # strips any directory traversal
    if not base:
        raise HTTPException(400, "filename required")
    ext = Path(base).suffix.lower()
    if ext not in LOGO_ALLOWED_EXT:
        raise HTTPException(
            400,
            f"unsupported extension {ext!r}; allowed: {sorted(LOGO_ALLOWED_EXT)}",
        )
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(base).stem).strip("_.-")
    if not stem:
        stem = "logo"
    return f"{stem}{ext}"


def _list_logo_entries() -> list[dict]:
    """Return the gallery contents as JSON-ready dicts, alpha-sorted."""
    LOGO_GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    for p in sorted(LOGO_GALLERY_DIR.iterdir(), key=lambda p: p.name.lower()):
        if not p.is_file() or p.name.startswith("."):
            continue
        if p.suffix.lower() not in LOGO_ALLOWED_EXT:
            continue
        try:
            st = p.stat()
        except OSError:
            continue
        entries.append({
            "filename": p.name,
            "url": f"/static/assets/logos/{p.name}",
            "size_bytes": st.st_size,
            "mtime": st.st_mtime,
        })
    return entries


@app.get("/api/logos/list")
async def api_logos_list():
    """Return the current gallery contents.

    Used by the fill page to populate the sidebar and to refresh after an
    upload. No caching beyond what the browser does for /static; entries
    carry mtime so the client can bust thumbnail caches if needed.
    """
    return {"entries": _list_logo_entries()}


@app.post("/api/logos/upload", status_code=201)
async def api_logos_upload(file: UploadFile = File(...)):
    """Save an uploaded image into the gallery folder.

    Filename collision policy: append ``_2``, ``_3``... before the extension
    so phone uploads named ``IMG_0123.png`` never clobber a prior file.
    Returns the updated gallery so the client can re-render without a
    second roundtrip.
    """
    LOGO_GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    raw_name = file.filename or "logo.png"
    name = _safe_logo_name(raw_name)

    contents = await file.read()
    if len(contents) == 0:
        raise HTTPException(400, "empty file")
    if len(contents) > LOGO_MAX_BYTES:
        raise HTTPException(
            413,
            f"file too large ({len(contents)} bytes > {LOGO_MAX_BYTES})",
        )

    # PIL verify — rejects corrupt / mislabelled bytes before we land them
    # on disk where the gallery would surface a broken thumbnail.
    try:
        from PIL import Image, UnidentifiedImageError
        from io import BytesIO
        with Image.open(BytesIO(contents)) as im:
            im.verify()
    except (UnidentifiedImageError, Exception) as exc:
        raise HTTPException(400, f"not a valid image: {exc}") from exc

    target = LOGO_GALLERY_DIR / name
    if target.exists():
        stem, ext = Path(name).stem, Path(name).suffix
        n = 2
        while (alt := LOGO_GALLERY_DIR / f"{stem}_{n}{ext}").exists():
            n += 1
        target = alt
    target.write_bytes(contents)

    return {
        "saved": {
            "filename": target.name,
            "url": f"/static/assets/logos/{target.name}",
            "size_bytes": len(contents),
        },
        "entries": _list_logo_entries(),
    }


# -----------------------------------------------------------------------------
# Infographic fill — composite uploaded/gallery logos into the magenta slots
# that the sentinel detector found at render time. The fill page (a separate
# /studio/infographic-fill HTML route, served below) reads out.slots.json,
# lets the user drag logos onto slots, then POSTs the assignments here.
# -----------------------------------------------------------------------------


class _SlotAssignment(BaseModel):
    slot_id: int = Field(ge=1)
    logo_filename: str = Field(min_length=1)


class _FillCompositeBody(BaseModel):
    job_id: str = Field(pattern=r"^[A-Za-z0-9_-]{6,64}$")
    assignments: list[_SlotAssignment] = Field(min_length=1)


@app.get("/studio/infographic-fill")
async def studio_infographic_fill() -> FileResponse:
    """HTML shell for the manual logo-placement page."""
    return FileResponse("static/studio/infographic-fill.html")


@app.get("/api/infographic-fill/job/{job_id}")
async def api_infographic_fill_job(job_id: str):
    """Return everything the fill page needs to render: image URL + slot list.

    The fill page calls this once on load instead of fetching the PNG and
    sidecar separately — keeps the client simpler and surfaces missing /
    detection-failed jobs with a clean error rather than a broken image.
    """
    if not re.fullmatch(r"[A-Za-z0-9_-]{6,64}", job_id):
        raise HTTPException(400, "invalid job_id")
    job_dir = Path("outputs/sensenova-render") / job_id
    png = job_dir / "out.png"
    sidecar = job_dir / "out.slots.json"
    if not png.is_file():
        raise HTTPException(404, "render output not found")
    if not sidecar.is_file():
        raise HTTPException(404, "no slot sidecar — was reserve_logo_slots > 0?")

    slots_data = json.loads(sidecar.read_text())
    filled = job_dir / "out.filled.png"
    audit = job_dir / "out.filled.json"
    prior: dict | None = None
    if audit.is_file():
        try:
            prior = json.loads(audit.read_text())
        except Exception:
            prior = None
    return {
        "job_id": job_id,
        "image_url": f"/outputs/sensenova-render/{job_id}/out.png",
        "filled_url": (
            f"/outputs/sensenova-render/{job_id}/out.filled.png"
            if filled.is_file() else None
        ),
        "slots": slots_data,
        "prior_assignments": prior,
    }


@app.post("/api/infographic-fill/composite")
async def api_infographic_fill_composite(body: _FillCompositeBody):
    """Composite each (slot, logo) assignment into out.png → out.filled.png.

    Fit-inside semantics: the logo is scaled so neither dimension exceeds
    the slot's bbox, preserving aspect ratio, then alpha-pasted centred
    inside the slot. The original out.png is untouched — re-saving with
    different assignments simply rewrites out.filled.png.
    """
    job_dir = Path("outputs/sensenova-render") / body.job_id
    png_path = job_dir / "out.png"
    sidecar = job_dir / "out.slots.json"
    if not png_path.is_file() or not sidecar.is_file():
        raise HTTPException(404, "render output or slot sidecar missing")

    slots_data = json.loads(sidecar.read_text())
    slots_by_id = {s["id"]: s for s in slots_data.get("slots", [])}

    import numpy as np
    from PIL import Image, ImageDraw
    base = Image.open(png_path).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    base_rgb = np.asarray(base.convert("RGB"))  # for background sampling

    # Halo erase tuning. The detector's bbox covers only the *core* solid
    # magenta region; the model's soft-edge bleed extends another 10-20%
    # past it. We paint a slightly enlarged area with the sampled
    # surrounding colour before pasting the logo, so the final composite
    # looks like the logo was placed directly on the card background
    # rather than on top of a magenta block with a glow.
    HALO_EXPAND_PCT = 0.18      # how far past the bbox we erase
    SAMPLE_OFFSET_PCT = 0.30    # how far past the bbox we sample for colour
    SAMPLE_STRIP_PX = 16        # thickness of the sampling strip

    def _sample_card_background(bbox: tuple[int, int, int, int]) -> tuple[int, int, int]:
        """Median RGB sampled from four strips just outside the halo.

        Falls back to white when the slot is so close to the canvas edge
        that no usable strips exist (rare — would only happen for slots
        produced at <5% inset from the border).
        """
        x, y, w, h = bbox
        H, W = base_rgb.shape[:2]
        ox = max(8, int(w * SAMPLE_OFFSET_PCT))
        oy = max(8, int(h * SAMPLE_OFFSET_PCT))
        strips: list[np.ndarray] = []
        # above
        if y - oy - SAMPLE_STRIP_PX >= 0:
            strips.append(base_rgb[y - oy - SAMPLE_STRIP_PX:y - oy, x:x + w])
        # below
        if y + h + oy + SAMPLE_STRIP_PX <= H:
            strips.append(base_rgb[y + h + oy:y + h + oy + SAMPLE_STRIP_PX, x:x + w])
        # left
        if x - ox - SAMPLE_STRIP_PX >= 0:
            strips.append(base_rgb[y:y + h, x - ox - SAMPLE_STRIP_PX:x - ox])
        # right
        if x + w + ox + SAMPLE_STRIP_PX <= W:
            strips.append(base_rgb[y:y + h, x + w + ox:x + w + ox + SAMPLE_STRIP_PX])
        if not strips:
            return (255, 255, 255)
        pixels = np.concatenate([s.reshape(-1, 3) for s in strips], axis=0)
        # Median is robust to text glyphs or decoration lines that happen
        # to land in a sample strip — a mean would skew toward those.
        med = np.median(pixels, axis=0)
        return tuple(int(c) for c in med)

    draw_base = ImageDraw.Draw(base)

    applied: list[dict] = []
    for assign in body.assignments:
        slot = slots_by_id.get(assign.slot_id)
        if slot is None:
            raise HTTPException(
                400,
                f"slot {assign.slot_id} not present in sidecar "
                f"(detected slots: {sorted(slots_by_id)})",
            )
        logo_name = _safe_logo_name(assign.logo_filename)
        logo_path = LOGO_GALLERY_DIR / logo_name
        if not logo_path.is_file():
            raise HTTPException(404, f"logo not found: {logo_name}")

        x, y, w, h = slot["bbox"]

        # Step 1 — erase the magenta + halo with a card-coloured fill.
        bg_rgb = _sample_card_background((x, y, w, h))
        hx = max(4, int(w * HALO_EXPAND_PCT))
        hy = max(4, int(h * HALO_EXPAND_PCT))
        fx0 = max(0, x - hx)
        fy0 = max(0, y - hy)
        fx1 = min(base.width, x + w + hx)
        fy1 = min(base.height, y + h + hy)
        draw_base.rectangle((fx0, fy0, fx1, fy1), fill=(*bg_rgb, 255))

        # Step 2 — paste the logo, fit-inside with 8% inner padding so it
        # doesn't kiss the freshly-painted card edges.
        logo = Image.open(logo_path).convert("RGBA")
        pad = max(4, int(min(w, h) * 0.08))
        inner_w, inner_h = max(1, w - 2 * pad), max(1, h - 2 * pad)
        # thumbnail mutates in-place and preserves aspect; LANCZOS gives
        # the cleanest downsample for line-art logos / wordmarks.
        logo.thumbnail((inner_w, inner_h), Image.Resampling.LANCZOS)
        paste_x = x + (w - logo.width) // 2
        paste_y = y + (h - logo.height) // 2
        overlay.paste(logo, (paste_x, paste_y), logo)
        applied.append({
            "slot_id": assign.slot_id,
            "logo": logo_name,
            "background_rgb": list(bg_rgb),
            "placed_at": [paste_x, paste_y, logo.width, logo.height],
        })

    composited = Image.alpha_composite(base, overlay).convert("RGB")
    out_path = job_dir / "out.filled.png"
    composited.save(out_path, optimize=True)

    audit = {
        "job_id": body.job_id,
        "saved_at": datetime.utcnow().isoformat() + "Z",
        "assignments": applied,
    }
    (job_dir / "out.filled.json").write_text(json.dumps(audit, indent=2))

    return {
        "output_url": f"/outputs/sensenova-render/{body.job_id}/out.filled.png",
        "audit": audit,
    }


def _comfyui_running(host: str = "127.0.0.1", port: int = 8188, timeout: float = 0.5) -> bool:
    """Cheap TCP probe: is ComfyUI listening on its default port?"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# SenseNova-U1 install probes — paths match scripts/setup-sensenova.sh defaults
# and honour the same env-var overrides so a custom install reads consistently
# from precheck and from the worker daemon.
SENSENOVA_VENV_PATH = os.environ.get("SENSENOVA_VENV", "/data/venvs/sensenova-u1")
SENSENOVA_WEIGHTS_PATH = os.environ.get(
    "SENSENOVA_WEIGHTS_FINAL", "/data/sensenova-u1-weights")
SENSENOVA_INSTALL_HINT = "./scripts/setup-sensenova.sh"


# LoRA header inspector — backs /api/lora/inspect so the compare modal can
# warn about partial text-encoder binding (a known kohya-format quirk where
# ComfyUI silently drops `lora_te*` keys whose module path doesn't exactly
# match SDXLClipModel's namespace; the UNet half still applies).
LORA_DIR = Path(os.environ.get("COMFYUI_LORA_DIR", "/data/ComfyUI/models/loras"))
_LORA_INSPECT_CACHE: dict[str, tuple[float, dict]] = {}


def _read_safetensors_keys(path: Path) -> list[str]:
    """Return tensor names from a .safetensors file without loading weights.

    Format: 8-byte little-endian uint64 = header length, then that many bytes
    of UTF-8 JSON whose top-level keys are tensor names (plus an optional
    ``__metadata__``). Reads only the header — typically a few KB even for
    a 1 GB LoRA.
    """
    import struct
    with path.open("rb") as f:
        prefix = f.read(8)
        if len(prefix) != 8:
            return []
        header_len = struct.unpack("<Q", prefix)[0]
        # Sanity guard — a well-formed safetensors header is well under 100 MB.
        if header_len <= 0 or header_len > 100_000_000:
            return []
        body = f.read(header_len)
    header = json.loads(body.decode("utf-8"))
    return [k for k in header.keys() if k != "__metadata__"]


def _classify_lora_keys(keys: list[str]) -> dict:
    """Bucket LoRA tensor names by training-script convention (kohya vs
    diffusers vs unknown) and by which half of the network they patch."""
    kohya_te = [k for k in keys if k.startswith(("lora_te1_", "lora_te2_", "lora_te_"))]
    kohya_unet = [k for k in keys if k.startswith("lora_unet_")]
    diffusers_te = [k for k in keys if "text_encoder" in k or ".text_model." in k]
    diffusers_unet = [k for k in keys
                      if k.startswith(("unet.", "lora.unet."))
                      or "down_blocks" in k or "up_blocks" in k]
    fmt = "kohya" if (kohya_te or kohya_unet) else \
          "diffusers" if (diffusers_te or diffusers_unet) else \
          "unknown"
    te_keys = kohya_te if fmt == "kohya" else diffusers_te
    unet_keys = kohya_unet if fmt == "kohya" else diffusers_unet
    return {
        "format": fmt,
        "has_te_keys": bool(te_keys),
        "te_key_count": len(te_keys),
        "has_unet_keys": bool(unet_keys),
        "unet_key_count": len(unet_keys),
    }


@app.get("/api/lora/inspect")
async def inspect_lora(name: str):
    """Surface what's inside a LoRA file so the compare modal can advise the
    user about trigger words and partial text-encoder binding. Reads only the
    safetensors header, cached by (name, mtime)."""
    safe_name = Path(name).name
    if (safe_name != name
            or not safe_name.endswith(".safetensors")
            or "/" in name or "\\" in name):
        raise HTTPException(400, "invalid lora name")
    path = LORA_DIR / safe_name
    if not path.is_file():
        raise HTTPException(404, "lora not found")
    mtime = path.stat().st_mtime
    cached = _LORA_INSPECT_CACHE.get(safe_name)
    if cached and cached[0] == mtime:
        info = cached[1]
    else:
        try:
            keys = _read_safetensors_keys(path)
        except (OSError, ValueError, json.JSONDecodeError):
            keys = []
        info = _classify_lora_keys(keys)
        _LORA_INSPECT_CACHE[safe_name] = (mtime, info)
    from model_catalog import LORA_TRIGGERS
    return {**info, "name": safe_name, "triggers": LORA_TRIGGERS.get(safe_name, [])}


def _sensenova_venv_present() -> bool:
    return Path(SENSENOVA_VENV_PATH, "bin", "python").is_file()


def _sensenova_weights_present() -> bool:
    p = Path(SENSENOVA_WEIGHTS_PATH)
    if not p.is_dir():
        return False
    # Treat empty dirs as not-installed — `huggingface-cli download` creates
    # the dir before any weights land, so existence alone isn't enough.
    return any(p.iterdir())


@app.get("/api/sensenova/precheck")
async def sensenova_precheck():
    """Health probe for the SenseNova-U1 backend.

    Failure modes surfaced (in increasing order of how-actionable-from-UI):

    1. **Not installed** — venv or weights missing. Hard-block render and
       point at ``scripts/setup-sensenova.sh``.
    2. **ComfyUI holding the GPU** — installed and worker would be ready,
       but ComfyUI is up. Soft-block: UI offers a one-click Stop ComfyUI
       button (POST /api/comfyui/stop) instead of telling the user to open
       a terminal.
    3. **Worker not running** — installed, GPU free, but
       ``sensenova-worker.service`` is stopped or loading. Soft-block: UI
       offers Start/Restart, or auto-starts on page open.
    4. **Ready** — worker running AND model loaded.
    """
    venv_ok = _sensenova_venv_present()
    weights_ok = _sensenova_weights_present()
    installed = venv_ok and weights_ok

    worker = await _wl.sensenova_status()
    comfy = await _wl.comfyui_status()
    comfyui_blocking = comfy.state in ("running", "starting")

    blockers: list[str] = []
    if not venv_ok:
        blockers.append(
            f"SenseNova-U1 is not installed (venv missing at "
            f"{SENSENOVA_VENV_PATH}). Run {SENSENOVA_INSTALL_HINT} first.")
    if not weights_ok:
        blockers.append(
            f"SenseNova-U1 weights missing at {SENSENOVA_WEIGHTS_PATH}. "
            f"Run {SENSENOVA_INSTALL_HINT} to download.")
    if installed and comfyui_blocking:
        blockers.append(
            "ComfyUI is using the GPU. Click 'Stop ComfyUI' to free it for "
            "SenseNova — you can restart ComfyUI from this page when done.")
    if installed and not comfyui_blocking and worker.state == "stopped":
        blockers.append(
            "SenseNova worker is stopped. Click 'Start worker' (or wait for "
            "auto-start) — first load takes ~25s while 32 GB of BF16 weights "
            "page onto the GPU.")
    if installed and not comfyui_blocking and worker.state == "starting":
        blockers.append(
            "SenseNova worker is starting (loading model weights). This "
            "usually finishes in 20-30 seconds.")
    if installed and worker.state == "crashed":
        blockers.append(
            "SenseNova worker crashed. Click 'Restart worker' — check "
            "`journalctl --user -u sensenova-worker` if it keeps failing.")

    ready = installed and not comfyui_blocking and worker.state == "running"

    details = {
        "venv_path": SENSENOVA_VENV_PATH,
        "venv_present": venv_ok,
        "weights_path": SENSENOVA_WEIGHTS_PATH,
        "weights_present": weights_ok,
        # Legacy field — kept for any older client that still reads it.
        "comfyui_running": comfyui_blocking,
        "comfyui": comfy.to_dict(),
        "worker": worker.to_dict(),
    }
    if not installed:
        details["install_hint"] = SENSENOVA_INSTALL_HINT

    return {
        "ready": ready,
        "installed": installed,
        "blockers": blockers,
        "details": details,
    }


# ===== Worker lifecycle controls (UI-driven; no terminal access needed) =====
#
# Two services, four verbs each. All routed through systemctl --user via
# studio.worker_lifecycle (argv list, no shell). The infographic page wires
# these to buttons so users never have to drop to a terminal to free the GPU
# or restart a wedged worker.

@app.get("/api/workers/status")
async def workers_status():
    """Both worker states in one round-trip for the UI status pill."""
    return await _wl.all_statuses()


@app.get("/api/sensenova/worker/status")
async def sensenova_worker_status():
    s = await _wl.sensenova_status()
    return s.to_dict()


@app.post("/api/sensenova/worker/start")
async def sensenova_worker_start():
    return await _wl.sensenova_start()


@app.post("/api/sensenova/worker/stop")
async def sensenova_worker_stop():
    return await _wl.sensenova_stop()


@app.post("/api/sensenova/worker/restart")
async def sensenova_worker_restart():
    return await _wl.sensenova_restart()


@app.get("/api/hidream/worker/status")
async def hidream_worker_status():
    s = await _wl.hidream_status()
    return s.to_dict()


@app.post("/api/hidream/worker/start")
async def hidream_worker_start():
    return await _wl.hidream_start()


@app.post("/api/hidream/worker/stop")
async def hidream_worker_stop():
    return await _wl.hidream_stop()


@app.post("/api/hidream/worker/restart")
async def hidream_worker_restart():
    return await _wl.hidream_restart()


@app.get("/api/comfyui/status")
async def comfyui_lifecycle_status():
    s = await _wl.comfyui_status()
    return s.to_dict()


@app.post("/api/comfyui/start")
async def comfyui_lifecycle_start():
    return await _wl.comfyui_start()


@app.post("/api/comfyui/stop")
async def comfyui_lifecycle_stop():
    """Stop ComfyUI to free the GPU for the SenseNova worker.

    Mirror of the manual `systemctl --user stop comfyui.service` the
    infographic precheck used to ask for. Pair with /api/comfyui/start
    after the infographic session.
    """
    return await _wl.comfyui_stop()


@app.post("/api/comfyui/restart")
async def comfyui_lifecycle_restart():
    return await _wl.comfyui_restart()


if __name__ == "__main__":
    import sys
    load_config()
    # --dev flag enables hot-reload (breaks CUDA — use only for frontend work)
    use_reload = "--dev" in sys.argv
    uvicorn.run("server:app", host=config["server"]["host"],
                port=config["server"]["port"], reload=use_reload)
