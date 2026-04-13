"""
Sample pack registry for Wyltek Studio beat builder.

Packs live in data/sample-packs/{pack-id}/ with a pack.json metadata file
and WAV sample files.
"""

import json
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / "data" / "sample-packs"

ALL_SLOTS = ["kick", "snare", "hihat", "openhat", "bass", "melody", "pad", "fx"]

USER_PACK_ID = "user"
USER_PACK_TEMPLATE = {
    "name": "User Samples",
    "description": "Custom uploaded samples.",
    "bpm_range": [60, 200],
    "genre_tags": ["custom"],
    "samples": {},
}


def _pack_dir(pack_id: str) -> Path:
    return DATA_DIR / pack_id


def _load_pack_json(pack_id: str) -> Optional[dict]:
    meta_path = _pack_dir(pack_id) / "pack.json"
    if not meta_path.exists():
        return None
    try:
        with meta_path.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _save_pack_json(pack_id: str, meta: dict) -> None:
    meta_path = _pack_dir(pack_id) / "pack.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    with meta_path.open("w") as f:
        json.dump(meta, f, indent=2)


def list_packs() -> list[dict]:
    """List all available sample packs.

    Returns a list of metadata dicts, each augmented with:
      - id: the pack directory name
      - sample_count: number of WAV files that actually exist on disk
    """
    if not DATA_DIR.exists():
        return []

    packs = []
    for entry in sorted(DATA_DIR.iterdir()):
        if not entry.is_dir():
            continue
        meta = _load_pack_json(entry.name)
        if meta is None:
            continue
        wav_count = sum(1 for f in entry.iterdir() if f.suffix.lower() == ".wav")
        packs.append({**meta, "id": entry.name, "sample_count": wav_count})
    return packs


def list_samples(pack_id: str) -> list[dict]:
    """List samples defined in a pack.

    Returns a list of dicts with keys: slot, file, type, exists, pack_id.
    Only slots present in pack.json are included.
    """
    meta = _load_pack_json(pack_id)
    if meta is None:
        return []

    samples = meta.get("samples", {})
    result = []
    pack_path = _pack_dir(pack_id)
    for slot, info in samples.items():
        file_name = info.get("file", "")
        sample_type = info.get("type", "oneshot")
        exists = (pack_path / file_name).exists() if file_name else False
        result.append(
            {
                "slot": slot,
                "file": file_name,
                "type": sample_type,
                "exists": exists,
                "pack_id": pack_id,
            }
        )
    return result


def resolve_sample(pack_id: str, slot: str) -> Optional[Path]:
    """Get the full path to a sample WAV file.

    Returns None if the pack, slot, or file does not exist.
    """
    meta = _load_pack_json(pack_id)
    if meta is None:
        return None

    samples = meta.get("samples", {})
    info = samples.get(slot)
    if not info:
        return None

    file_name = info.get("file", "")
    if not file_name:
        return None

    full_path = _pack_dir(pack_id) / file_name
    return full_path if full_path.exists() else None


def sample_type(pack_id: str, slot: str) -> str:
    """Get the type ('oneshot' or 'loop') for a slot. Defaults to 'oneshot'."""
    meta = _load_pack_json(pack_id)
    if meta is None:
        return "oneshot"
    samples = meta.get("samples", {})
    info = samples.get(slot, {})
    return info.get("type", "oneshot")


def save_user_sample(file_bytes: bytes, filename: str, slot: str) -> dict:
    """Save an uploaded sample to the user pack.

    Writes the file to data/sample-packs/user/{filename}, updates pack.json,
    and returns {slot, file, type, pack_id}.
    """
    pack_id = USER_PACK_ID
    pack_path = _pack_dir(pack_id)
    pack_path.mkdir(parents=True, exist_ok=True)

    meta = _load_pack_json(pack_id)
    if meta is None:
        meta = dict(USER_PACK_TEMPLATE)
        meta["samples"] = {}

    dest = pack_path / filename
    dest.write_bytes(file_bytes)

    sample_entry = {"file": filename, "type": "oneshot"}
    meta["samples"][slot] = sample_entry
    _save_pack_json(pack_id, meta)

    return {"slot": slot, "file": filename, "type": "oneshot", "pack_id": pack_id}
