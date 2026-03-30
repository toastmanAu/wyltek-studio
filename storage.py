"""Storage layer — project-based asset management.

All user-generated content lives under STORAGE_ROOT:
  storage/
    projects/{slug}/          ← named project folders
      project.json            ← metadata
      images/                 ← generated images + JSON sidecars
      audio/                  ← TTS output
      video/                  ← rendered video (future)
      assets/                 ← imported external files
    unsorted/{YYYY-MM-DD}/    ← quick generations not in a project
    db/                       ← SQLite databases
"""

import json
import os
import re
import shutil
from datetime import datetime, date
from pathlib import Path

STORAGE_ROOT = Path(__file__).parent / "storage"

# Asset type → subdirectory name
ASSET_DIRS = {
    "image": "images",
    "audio": "audio",
    "video": "video",
    "asset": "assets",
}


def init():
    """Create storage directory structure."""
    (STORAGE_ROOT / "projects").mkdir(parents=True, exist_ok=True)
    (STORAGE_ROOT / "unsorted").mkdir(parents=True, exist_ok=True)
    (STORAGE_ROOT / "db").mkdir(parents=True, exist_ok=True)


def db_path(name: str = "scores.db") -> Path:
    """Get path to a database file."""
    return STORAGE_ROOT / "db" / name


# --- Path resolution ---

def _slugify(name: str) -> str:
    """Convert a name to a filesystem-safe slug."""
    slug = re.sub(r'[^\w\s-]', '', name.lower().strip())
    slug = re.sub(r'[\s_]+', '-', slug)
    return slug[:80] or "unnamed"


def unsorted_dir(for_date: date = None) -> Path:
    """Get today's unsorted directory, creating it if needed."""
    d = for_date or date.today()
    path = STORAGE_ROOT / "unsorted" / d.isoformat()
    path.mkdir(parents=True, exist_ok=True)
    return path


def project_dir(project_id: str) -> Path:
    """Get a project's root directory."""
    return STORAGE_ROOT / "projects" / project_id


def asset_path(job_id: str, asset_type: str, ext: str,
               project_id: str = None) -> Path:
    """Get the full path for a new asset file.

    If project_id is given, saves into that project.
    Otherwise saves into unsorted/{today}/.
    """
    subdir = ASSET_DIRS.get(asset_type, "assets")

    if project_id:
        base = project_dir(project_id) / subdir
    else:
        base = unsorted_dir() / subdir

    base.mkdir(parents=True, exist_ok=True)
    return base / f"{job_id}{ext}"


def resolve_asset(relative_url: str) -> Path | None:
    """Resolve a URL path like /storage/images/abc123.png to a filesystem path.

    Searches: 1) all projects, 2) all unsorted date dirs.
    Returns first match or None.
    """
    filename = Path(relative_url).name

    # Search projects
    for proj in (STORAGE_ROOT / "projects").iterdir():
        if not proj.is_dir():
            continue
        for subdir in ASSET_DIRS.values():
            candidate = proj / subdir / filename
            if candidate.exists():
                return candidate

    # Search unsorted (newest first)
    unsorted = STORAGE_ROOT / "unsorted"
    if unsorted.exists():
        for date_dir in sorted(unsorted.iterdir(), reverse=True):
            if not date_dir.is_dir():
                continue
            for subdir in ASSET_DIRS.values():
                candidate = date_dir / subdir / filename
                if candidate.exists():
                    return candidate
            # Also check flat (for backwards compat during migration)
            candidate = date_dir / filename
            if candidate.exists():
                return candidate

    return None


# --- Project management ---

def create_project(name: str, description: str = "") -> dict:
    """Create a new project. Returns project metadata."""
    slug = _slugify(name)

    # Handle duplicate slugs
    base_slug = slug
    counter = 1
    while project_dir(slug).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    pdir = project_dir(slug)
    pdir.mkdir(parents=True, exist_ok=True)
    for subdir in ASSET_DIRS.values():
        (pdir / subdir).mkdir(exist_ok=True)

    meta = {
        "id": slug,
        "name": name,
        "created": datetime.now().isoformat(),
        "description": description,
        "tags": [],
    }
    with open(pdir / "project.json", "w") as f:
        json.dump(meta, f, indent=2)

    return meta


def get_project(project_id: str) -> dict | None:
    """Load project metadata."""
    meta_path = project_dir(project_id) / "project.json"
    if not meta_path.exists():
        return None
    with open(meta_path) as f:
        meta = json.load(f)
    # Count assets
    pdir = project_dir(project_id)
    meta["asset_counts"] = {}
    for asset_type, subdir in ASSET_DIRS.items():
        d = pdir / subdir
        if d.exists():
            meta["asset_counts"][asset_type] = len([
                f for f in d.iterdir()
                if f.is_file() and not f.name.endswith('.json')
            ])
        else:
            meta["asset_counts"][asset_type] = 0
    return meta


def list_projects() -> list[dict]:
    """List all projects with metadata."""
    projects = []
    proj_root = STORAGE_ROOT / "projects"
    if not proj_root.exists():
        return projects
    for pdir in sorted(proj_root.iterdir()):
        if not pdir.is_dir():
            continue
        meta = get_project(pdir.name)
        if meta:
            projects.append(meta)
    return projects


def delete_project(project_id: str) -> bool:
    """Delete a project and all its assets."""
    pdir = project_dir(project_id)
    if not pdir.exists():
        return False
    shutil.rmtree(pdir)
    return True


def update_project(project_id: str, updates: dict) -> dict | None:
    """Update project metadata fields."""
    meta_path = project_dir(project_id) / "project.json"
    if not meta_path.exists():
        return None
    with open(meta_path) as f:
        meta = json.load(f)
    for key in ("name", "description", "tags"):
        if key in updates:
            meta[key] = updates[key]
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    return meta


# --- Asset operations ---

def move_asset(filename: str, to_project: str) -> bool:
    """Move an asset from unsorted (or another project) into a project."""
    # Find the file
    source = resolve_asset(filename)
    if not source:
        return False

    # Determine asset type from parent dir name
    parent_name = source.parent.name
    asset_type = None
    for atype, dirname in ASSET_DIRS.items():
        if parent_name == dirname:
            asset_type = atype
            break

    # Default to image if we can't determine
    if not asset_type:
        ext = source.suffix.lower()
        if ext in (".wav", ".mp3", ".ogg"):
            asset_type = "audio"
        elif ext in (".mp4", ".webm"):
            asset_type = "video"
        else:
            asset_type = "image"

    dest_dir = project_dir(to_project) / ASSET_DIRS[asset_type]
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / source.name

    shutil.move(str(source), str(dest))

    # Also move JSON sidecar if it exists
    sidecar = source.with_suffix(".json")
    if sidecar.exists():
        shutil.move(str(sidecar), str(dest.with_suffix(".json")))

    return True


def list_unsorted(limit: int = 50) -> list[dict]:
    """List recent unsorted assets across all dates, newest first."""
    items = []
    unsorted = STORAGE_ROOT / "unsorted"
    if not unsorted.exists():
        return items

    for date_dir in sorted(unsorted.iterdir(), reverse=True):
        if not date_dir.is_dir():
            continue
        for subdir_name in ASSET_DIRS.values():
            subdir = date_dir / subdir_name
            if not subdir.exists():
                continue
            for f in sorted(subdir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                if f.suffix == ".json":
                    continue
                asset_type = None
                for atype, dname in ASSET_DIRS.items():
                    if subdir_name == dname:
                        asset_type = atype
                        break

                meta = {}
                sidecar = f.with_suffix(".json")
                if sidecar.exists():
                    try:
                        with open(sidecar) as mf:
                            meta = json.load(mf)
                    except Exception:
                        pass

                items.append({
                    "filename": f.name,
                    "type": asset_type or "image",
                    "date": date_dir.name,
                    "url": f"/storage/{f.name}",
                    "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                    "meta": meta,
                })
                if len(items) >= limit:
                    return items
    return items


def list_project_assets(project_id: str) -> list[dict]:
    """List all assets in a project."""
    pdir = project_dir(project_id)
    if not pdir.exists():
        return []

    items = []
    for asset_type, subdir_name in ASSET_DIRS.items():
        subdir = pdir / subdir_name
        if not subdir.exists():
            continue
        for f in sorted(subdir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
            if f.suffix == ".json":
                continue

            meta = {}
            sidecar = f.with_suffix(".json")
            if sidecar.exists():
                try:
                    with open(sidecar) as mf:
                        meta = json.load(mf)
                except Exception:
                    pass

            items.append({
                "filename": f.name,
                "type": asset_type,
                "url": f"/storage/{f.name}",
                "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                "meta": meta,
            })
    return items
