"""Component health checks + reset actions for Wyltek Studio.

Wired into server.py via two endpoints:
  GET  /api/health/components  -> list[ComponentStatus]
  POST /api/health/reset       -> soft or hard reset

All thresholds and external URLs live in HEALTH_POLICY at the top so the
policy can be tuned without touching the check/reset logic. Edit the
values in-place; the module reads them at call time, so changes take
effect on the next poll without a server restart.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import aiohttp


log = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Policy — tweak these to suit your hardware/workflow.
# --------------------------------------------------------------------------
#
# Status colours follow a strict ladder:
#   red    = component is unreachable / out of resources / definitely broken
#   amber  = component is reachable but degraded (low headroom, queue full)
#   green  = healthy, no operator action needed
#
# `_amber` and `_red` are thresholds. For "free space" / "free VRAM" style
# metrics the value drops as things get worse, so amber > red. For "queue
# depth" the value rises as things get worse, so amber < red.
# The classifier helpers below pick the right direction per metric.

HEALTH_POLICY: dict = {
    # External services we ping. Short timeout — these are localhost.
    "comfy_url": "http://127.0.0.1:8188",
    "ollama_url": "http://127.0.0.1:11434",
    "probe_timeout_s": 1.5,

    # systemd --user unit names used by hard reset.
    "comfy_service": "comfyui.service",

    # GPU VRAM headroom (free GB). 7900 XTX has 24 GB total; Trellis textured
    # peaks ~18 GB, so <4 GB free during idle is suspicious, <1 GB free means
    # the next 3D job will OOM.
    "vram_amber_free_gb": 4.0,
    "vram_red_free_gb": 1.0,

    # Disk free on /data (where ComfyUI models + outputs live).
    "disk_path": "/data",
    "disk_amber_free_gb": 50.0,
    "disk_red_free_gb": 10.0,

    # Queue depth: how many jobs queued+running before we flag amber/red.
    "queue_amber_depth": 2,
    "queue_red_depth": 4,

    # Where ComfyUI writes 3D outputs and where we copy them into.
    "comfy_output_dir": "/home/phill/ComfyUI/output",
    "storage_unsorted_dir": "/home/phill/open-palette/storage/unsorted",
}


# --------------------------------------------------------------------------
# Result shape returned to the UI. Kept flat + JSON-friendly.
# --------------------------------------------------------------------------

Status = Literal["green", "amber", "red", "unknown"]


@dataclass
class ComponentStatus:
    name: str
    status: Status
    tooltip: str

    def to_dict(self) -> dict:
        return {"name": self.name, "status": self.status, "tooltip": self.tooltip}


# --------------------------------------------------------------------------
# Classifiers
# --------------------------------------------------------------------------

def _classify_lower_is_worse(value: float, amber: float, red: float) -> Status:
    """Used for free-resource metrics (VRAM free, disk free)."""
    if value <= red:
        return "red"
    if value <= amber:
        return "amber"
    return "green"


def _classify_higher_is_worse(value: float, amber: float, red: float) -> Status:
    """Used for load metrics (queue depth)."""
    if value >= red:
        return "red"
    if value >= amber:
        return "amber"
    return "green"


# --------------------------------------------------------------------------
# Individual checks
# --------------------------------------------------------------------------

async def _http_alive(url: str, timeout_s: float) -> bool:
    """True if `url` responds with anything (even a 404) inside the timeout."""
    try:
        timeout = aiohttp.ClientTimeout(total=timeout_s)
        async with aiohttp.ClientSession(timeout=timeout) as s:
            async with s.get(url) as resp:
                return resp.status < 600
    except Exception:
        return False


async def check_comfyui() -> ComponentStatus:
    url = HEALTH_POLICY["comfy_url"] + "/system_stats"
    alive = await _http_alive(url, HEALTH_POLICY["probe_timeout_s"])
    if alive:
        return ComponentStatus("comfyui", "green", "ComfyUI reachable on :8188")
    return ComponentStatus(
        "comfyui", "red", "ComfyUI not responding — hard reset will restart it"
    )


async def check_ollama() -> ComponentStatus:
    url = HEALTH_POLICY["ollama_url"] + "/api/tags"
    alive = await _http_alive(url, HEALTH_POLICY["probe_timeout_s"])
    if alive:
        return ComponentStatus("ollama", "green", "Ollama reachable on :11434")
    return ComponentStatus(
        "ollama", "amber", "Ollama not responding (AI Copilot disabled)"
    )


def check_gpu_vram() -> ComponentStatus:
    """Parse `rocm-smi --json --showmeminfo vram` for free VRAM on card 0."""
    import subprocess as _sp  # localised: sole subprocess use in this module
    try:
        out = _sp.run(
            ["rocm-smi", "--json", "--showmeminfo", "vram"],
            capture_output=True, text=True, timeout=2,
        )
        data = json.loads(out.stdout)
        card = next(iter(data.values()))
        total = int(card["VRAM Total Memory (B)"])
        used = int(card["VRAM Total Used Memory (B)"])
        free_gb = (total - used) / (1024 ** 3)
    except Exception as exc:
        log.warning("rocm-smi probe failed: %s", exc)
        return ComponentStatus("gpu", "unknown", "rocm-smi unavailable")

    status = _classify_lower_is_worse(
        free_gb,
        HEALTH_POLICY["vram_amber_free_gb"],
        HEALTH_POLICY["vram_red_free_gb"],
    )
    return ComponentStatus("gpu", status, f"GPU VRAM: {free_gb:.1f} GB free")


def check_disk() -> ComponentStatus:
    path = HEALTH_POLICY["disk_path"]
    try:
        st = os.statvfs(path)
        free_gb = (st.f_bavail * st.f_frsize) / (1024 ** 3)
    except FileNotFoundError:
        return ComponentStatus("disk", "unknown", f"{path} not mounted")

    status = _classify_lower_is_worse(
        free_gb,
        HEALTH_POLICY["disk_amber_free_gb"],
        HEALTH_POLICY["disk_red_free_gb"],
    )
    return ComponentStatus("disk", status, f"{path}: {free_gb:.0f} GB free")


def check_queue(queue) -> ComponentStatus:
    """Inspect JobQueue for total active+pending jobs across all lanes."""
    s = queue.status()
    total = sum(lane["running"] + lane["queued"] for lane in s.values())
    status = _classify_higher_is_worse(
        total,
        HEALTH_POLICY["queue_amber_depth"],
        HEALTH_POLICY["queue_red_depth"],
    )
    return ComponentStatus("queue", status, f"{total} job(s) in flight")


# --------------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------------

async def check_components(queue) -> list[dict]:
    """Run all probes concurrently. Returns list[dict] in dot-strip order."""
    comfy_t = asyncio.create_task(check_comfyui())
    ollama_t = asyncio.create_task(check_ollama())
    loop = asyncio.get_running_loop()
    gpu_t = loop.run_in_executor(None, check_gpu_vram)
    disk_t = loop.run_in_executor(None, check_disk)

    components = await asyncio.gather(comfy_t, ollama_t, gpu_t, disk_t)
    components = list(components) + [check_queue(queue)]
    return [c.to_dict() for c in components]


# --------------------------------------------------------------------------
# Reset actions
# --------------------------------------------------------------------------

def _rescue_orphan_meshes() -> dict:
    """In-process port of scripts/backfill_orphan_meshes.py.

    Walks ComfyUI 3D output and copies any `.glb` not already in storage
    into `storage/unsorted/{date}/meshes/` with a `rescued: true` sidecar.
    Idempotent — uses size-match against existing storage entries to avoid
    duplicates from the same day.
    """
    comfy_3d = Path(HEALTH_POLICY["comfy_output_dir"]) / "3D"
    storage = Path(HEALTH_POLICY["storage_unsorted_dir"])

    if not comfy_3d.exists():
        return {"rescued": [], "skipped_existing": 0, "comfy_3d_missing": True}

    rescued: list[str] = []
    skipped = 0
    for src in sorted(comfy_3d.glob("wyltek-*_textured_*.glb")):
        day = datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y-%m-%d")
        target_dir = storage / day / "meshes"
        size = src.stat().st_size

        if target_dir.exists() and any(
            abs(q.stat().st_size - size) < 2 for q in target_dir.glob("*.glb")
        ):
            skipped += 1
            continue

        try:
            job_id = src.name.split("_textured_")[0].split("_")[-1][:8]
        except Exception:
            job_id = src.stem[:8]

        target_dir.mkdir(parents=True, exist_ok=True)
        target_glb = target_dir / f"{job_id}.glb"
        target_json = target_dir / f"{job_id}.json"
        shutil.copy2(src, target_glb)
        target_json.write_text(json.dumps({
            "job_id": job_id,
            "backend": "comfyui",
            "engine": "trellis" if "trellis" in src.name else "hy3d",
            "mode": "3d",
            "trellis_mode": "textured",
            "format": "glb",
            "rescued": True,
            "rescue_reason": "Surfaced by /api/health/reset (soft).",
            "source": str(src),
            "rescued_at": datetime.now().isoformat(),
        }, indent=2))
        rescued.append(str(target_glb))

    return {"rescued": rescued, "skipped_existing": skipped}


async def soft_reset(queue) -> dict:
    """Cheap, repeatable reset. No service touches.

    1. Sweep for orphan GLBs and copy them into storage.
    2. Re-probe component health so the UI gets fresh dots back immediately.

    Deliberately does NOT cancel running jobs — a real long Trellis textured
    run looks identical to a stuck one from this layer. Use hard_reset()
    if cancellation is required.
    """
    rescue_report = await asyncio.get_running_loop().run_in_executor(
        None, _rescue_orphan_meshes
    )
    components = await check_components(queue)
    return {
        "level": "soft",
        "rescue": rescue_report,
        "components": components,
    }


async def hard_reset(queue) -> dict:
    """Soft reset + restart ComfyUI service.

    Uses `systemctl --user restart` so no sudo is needed; open-palette runs
    as the same user that owns the comfyui unit. All args are static literals
    + a unit name from HEALTH_POLICY (operator-controlled), no shell.
    """
    soft_result = await soft_reset(queue)

    service = HEALTH_POLICY["comfy_service"]
    try:
        proc = await asyncio.create_subprocess_exec(
            "systemctl", "--user", "restart", service,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        restart_ok = proc.returncode == 0
        restart_err = stderr.decode().strip() if stderr else ""
    except asyncio.TimeoutError:
        restart_ok = False
        restart_err = "systemctl restart timed out after 15s"
    except FileNotFoundError:
        restart_ok = False
        restart_err = "systemctl not on PATH"

    await asyncio.sleep(2.0)
    components_after = await check_components(queue)

    return {
        **soft_result,
        "level": "hard",
        "service_restart": {
            "service": service,
            "ok": restart_ok,
            "error": restart_err,
        },
        "components": components_after,
    }
