#!/usr/bin/env python3
"""One-shot: find ComfyUI 3D outputs not present in open-palette storage
and copy them in with rescued=true sidecars.

Idempotent — re-running is safe. Dry-run by default; pass --apply to copy.

Background: this addresses orphans that predate the in-process orphan
rescue helper (backends/comfyui.py:_rescue_orphan_glb). Anything in
/home/phill/ComfyUI/output/3D/ matching wyltek-*_textured_*.glb that
isn't already in storage/unsorted/{any-date}/meshes/ is a past orphan.
"""

from datetime import datetime
import json
from pathlib import Path
import shutil
import sys

COMFY_3D = Path("/home/phill/ComfyUI/output/3D")
STORAGE = Path("/home/phill/open-palette/storage/unsorted")


def existing_glb_basenames() -> set[str]:
    """Set of all .glb filenames currently in any unsorted/{date}/meshes/."""
    return {p.name for p in STORAGE.glob("*/meshes/*.glb")}


def find_orphans() -> list[Path]:
    """ComfyUI .glb files that don't appear to have been copied to storage.

    Conservative size match: if any storage .glb on the same day matches
    the source's byte size within ±1 byte, assume it's already in-storage.
    Avoids duplicates while tolerating the rescue path's mtime preservation.
    """
    orphans = []
    for p in sorted(COMFY_3D.glob("wyltek-*_textured_*.glb")):
        day = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")
        target_dir = STORAGE / day / "meshes"
        if not target_dir.exists():
            orphans.append(p)
            continue
        already = any(
            abs(q.stat().st_size - p.stat().st_size) < 2
            for q in target_dir.glob("*.glb")
        )
        if not already:
            orphans.append(p)
    return orphans


def rescue(p: Path, dry_run: bool = True) -> Path:
    """Copy a single orphan into storage with a rescue sidecar."""
    day = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d")
    target_dir = STORAGE / day / "meshes"
    # Job ID: take the slice between "trellis_" / "3d_" and "_textured".
    # Fall back to the file stem's first 8 chars on a parse failure.
    try:
        job_id = p.name.split("_textured_")[0].split("_")[-1][:8]
    except Exception:
        job_id = p.stem[:8]
    target_glb = target_dir / f"{job_id}.glb"
    target_json = target_dir / f"{job_id}.json"
    if dry_run:
        print(f"DRY: {p}  ->  {target_glb}")
        return target_glb
    target_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(p, target_glb)
    target_json.write_text(json.dumps({
        "job_id": job_id,
        "backend": "comfyui",
        "engine": "trellis" if "trellis" in p.name else "hy3d",
        "mode": "3d",
        "trellis_mode": "textured",
        "format": "glb",
        "rescued": True,
        "rescue_reason": "Backfill from /home/phill/ComfyUI/output/3D/",
        "source": str(p),
        "rescued_at": datetime.now().isoformat(),
    }, indent=2))
    return target_glb


if __name__ == "__main__":
    dry = "--apply" not in sys.argv
    orphans = find_orphans()
    print(f"Found {len(orphans)} orphan(s).")
    for p in orphans:
        rescue(p, dry_run=dry)
    if dry and orphans:
        print("\nRe-run with --apply to actually copy.")
