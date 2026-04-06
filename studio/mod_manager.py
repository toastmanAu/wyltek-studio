"""Mod project manager — create, populate, and export game mod projects.

Each mod is a folder under storage/mods/{slug}/ with:
  mod.json    — metadata + slot definitions
  sprites/    — assigned sprite PNGs
  export/     — generated mod files (YAML, zips)
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

MODS_DIR = Path(__file__).parent.parent / "storage" / "mods"


# --- Mod Templates ---
# Each template defines the sprite slots a mod needs populated.

XCOM_ALIENS = [
    ("sectoid_soldier", "Sectoid Soldier", "unit", 32, 40, 8),
    ("sectoid_leader", "Sectoid Leader", "unit", 32, 40, 8),
    ("floater_soldier", "Floater Soldier", "unit", 32, 40, 8),
    ("snakeman_soldier", "Snakeman Soldier", "unit", 32, 40, 8),
    ("muton_soldier", "Muton Soldier", "unit", 32, 40, 8),
    ("ethereal_leader", "Ethereal Leader", "unit", 32, 40, 8),
    ("chryssalid", "Chryssalid", "unit", 32, 40, 8),
    ("celatid", "Celatid", "unit", 32, 40, 8),
    ("silacoid", "Silacoid", "unit", 32, 40, 8),
    ("cyberdisc", "Cyberdisc", "unit", 32, 40, 8),
    ("sectopod", "Sectopod", "unit", 32, 40, 8),
]

XCOM_UFOS = [
    ("ufo_small_scout", "Small Scout", "ufo", 80, 80, 1),
    ("ufo_medium_scout", "Medium Scout", "ufo", 80, 80, 1),
    ("ufo_large_scout", "Large Scout", "ufo", 80, 80, 1),
    ("ufo_harvester", "Harvester", "ufo", 80, 80, 1),
    ("ufo_abductor", "Abductor", "ufo", 80, 80, 1),
    ("ufo_terror_ship", "Terror Ship", "ufo", 80, 80, 1),
    ("ufo_battleship", "Battleship", "ufo", 80, 80, 1),
    ("ufo_supply_ship", "Supply Ship", "ufo", 80, 80, 1),
]

XCOM_UFOPAEDIA = [
    ("ufopedia_sectoid", "Sectoid Article", "ufopaedia", 320, 200, 1),
    ("ufopedia_floater", "Floater Article", "ufopaedia", 320, 200, 1),
    ("ufopedia_snakeman", "Snakeman Article", "ufopaedia", 320, 200, 1),
    ("ufopedia_muton", "Muton Article", "ufopaedia", 320, 200, 1),
    ("ufopedia_ethereal", "Ethereal Article", "ufopaedia", 320, 200, 1),
    ("ufopedia_chryssalid", "Chryssalid Article", "ufopaedia", 320, 200, 1),
]

XCOM_ITEMS = [
    ("corpse_sectoid", "Sectoid Corpse", "bigobs", 32, 48, 1),
    ("corpse_floater", "Floater Corpse", "bigobs", 32, 48, 1),
    ("corpse_snakeman", "Snakeman Corpse", "bigobs", 32, 48, 1),
    ("corpse_muton", "Muton Corpse", "bigobs", 32, 48, 1),
    ("corpse_ethereal", "Ethereal Corpse", "bigobs", 32, 48, 1),
]

# Pokemon Gen III: front + back for each
POKEMON_STARTERS = [
    ("bulbasaur", "Bulbasaur", 1), ("ivysaur", "Ivysaur", 2), ("venusaur", "Venusaur", 3),
    ("charmander", "Charmander", 4), ("charmeleon", "Charmeleon", 5), ("charizard", "Charizard", 6),
    ("squirtle", "Squirtle", 7), ("wartortle", "Wartortle", 8), ("blastoise", "Blastoise", 9),
    ("pikachu", "Pikachu", 25), ("eevee", "Eevee", 133),
    ("jigglypuff", "Jigglypuff", 39), ("mewtwo", "Mewtwo", 150), ("mew", "Mew", 151),
    ("chikorita", "Chikorita", 152), ("cyndaquil", "Cyndaquil", 155), ("totodile", "Totodile", 158),
    ("treecko", "Treecko", 252), ("torchic", "Torchic", 255), ("mudkip", "Mudkip", 258),
    ("rayquaza", "Rayquaza", 384), ("groudon", "Groudon", 383), ("kyogre", "Kyogre", 382),
    ("deoxys", "Deoxys", 386),
]


def _build_xcom_slots() -> list[dict]:
    """Build all sprite slots for an X-COM total conversion."""
    slots = []
    for sid, name, stype, w, h, frames in XCOM_ALIENS:
        slots.append({
            "id": sid, "name": name, "category": "Aliens",
            "type": stype, "width": w, "height": h, "frames": frames,
            "sprite": None, "status": "empty",
        })
    for sid, name, stype, w, h, frames in XCOM_UFOS:
        slots.append({
            "id": sid, "name": name, "category": "UFOs",
            "type": stype, "width": w, "height": h, "frames": frames,
            "sprite": None, "status": "empty",
        })
    for sid, name, stype, w, h, frames in XCOM_UFOPAEDIA:
        slots.append({
            "id": sid, "name": name, "category": "UFOpaedia",
            "type": stype, "width": w, "height": h, "frames": frames,
            "sprite": None, "status": "empty",
        })
    for sid, name, stype, w, h, frames in XCOM_ITEMS:
        slots.append({
            "id": sid, "name": name, "category": "Items",
            "type": stype, "width": w, "height": h, "frames": frames,
            "sprite": None, "status": "empty",
        })
    return slots


def _build_pokemon_slots() -> list[dict]:
    """Build sprite slots for Pokemon GBA mod (front + back per mon)."""
    slots = []
    for sid, name, dex_num in POKEMON_STARTERS:
        slots.append({
            "id": f"{sid}_front", "name": f"{name} (Front)", "category": "Pokemon",
            "type": "pokemon_front", "width": 64, "height": 64, "frames": 1,
            "dex": dex_num, "sprite": None, "status": "empty",
        })
        slots.append({
            "id": f"{sid}_back", "name": f"{name} (Back)", "category": "Pokemon",
            "type": "pokemon_back", "width": 64, "height": 64, "frames": 1,
            "dex": dex_num, "sprite": None, "status": "empty",
        })
    return slots


TEMPLATES = {
    "xcom": {
        "name": "X-COM: Crypto Defense",
        "game": "OpenXCOM (UFO Defense)",
        "description": "Total conversion — replace all aliens and UFOs with crypto-themed monsters",
        "build_slots": _build_xcom_slots,
    },
    "pokemon-gba": {
        "name": "CryptoMon GBA",
        "game": "Pokemon (GBA, Gen III)",
        "description": "Replace Pokemon sprites with crypto monster designs",
        "build_slots": _build_pokemon_slots,
    },
}


# --- Mod CRUD ---

def create_mod(template_id: str, name: str = "", author: str = "",
               description: str = "") -> dict:
    """Create a new mod project from a template."""
    template = TEMPLATES.get(template_id)
    if not template:
        raise ValueError(f"Unknown template: {template_id}")

    slug = re.sub(r'[^\w-]', '', (name or template["name"]).lower().replace(' ', '-'))
    slug = slug or f"mod-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    mod_dir = MODS_DIR / slug
    if mod_dir.exists():
        # Append timestamp to avoid collision
        slug = f"{slug}-{datetime.now().strftime('%H%M%S')}"
        mod_dir = MODS_DIR / slug

    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / "sprites").mkdir(exist_ok=True)
    (mod_dir / "export").mkdir(exist_ok=True)

    slots = template["build_slots"]()

    mod = {
        "id": slug,
        "template": template_id,
        "name": name or template["name"],
        "game": template["game"],
        "author": author or "Wyltek Industries",
        "description": description or template["description"],
        "created": datetime.now().isoformat(),
        "slots": slots,
        "slot_count": len(slots),
        "filled_count": 0,
    }

    with open(mod_dir / "mod.json", "w") as f:
        json.dump(mod, f, indent=2)

    return mod


def list_mods() -> list[dict]:
    """List all mod projects (summary only, no slots)."""
    MODS_DIR.mkdir(parents=True, exist_ok=True)
    mods = []
    for p in sorted(MODS_DIR.iterdir()):
        manifest = p / "mod.json"
        if manifest.exists():
            with open(manifest) as f:
                mod = json.load(f)
            mods.append({
                "id": mod["id"],
                "name": mod["name"],
                "game": mod["game"],
                "template": mod["template"],
                "author": mod.get("author", ""),
                "slot_count": mod.get("slot_count", len(mod.get("slots", []))),
                "filled_count": sum(1 for s in mod.get("slots", []) if s.get("sprite")),
                "created": mod.get("created", ""),
            })
    return mods


def get_mod(mod_id: str) -> dict | None:
    """Get full mod project including all slots."""
    manifest = MODS_DIR / mod_id / "mod.json"
    if not manifest.exists():
        return None
    with open(manifest) as f:
        mod = json.load(f)
    mod["filled_count"] = sum(1 for s in mod.get("slots", []) if s.get("sprite"))
    return mod


def assign_sprite(mod_id: str, slot_id: str, sprite_url: str) -> dict | None:
    """Assign a sprite image to a mod slot. Copies the file into the mod."""
    mod = get_mod(mod_id)
    if not mod:
        return None

    slot = next((s for s in mod["slots"] if s["id"] == slot_id), None)
    if not slot:
        return None

    # Resolve and copy sprite into mod folder
    from storage import resolve_asset
    filename = sprite_url.split("/storage/")[-1] if "/storage/" in sprite_url else sprite_url
    src = resolve_asset(filename)
    if not src or not src.exists():
        return None

    dest_dir = MODS_DIR / mod_id / "sprites"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{slot_id}.png"
    shutil.copy2(src, dest)

    slot["sprite"] = f"/storage/mods/{mod_id}/sprites/{slot_id}.png"
    slot["status"] = "filled"

    # Save updated manifest
    mod["filled_count"] = sum(1 for s in mod["slots"] if s.get("sprite"))
    with open(MODS_DIR / mod_id / "mod.json", "w") as f:
        json.dump(mod, f, indent=2)

    return slot


def delete_mod(mod_id: str) -> bool:
    """Delete a mod project."""
    mod_dir = MODS_DIR / mod_id
    if mod_dir.exists():
        shutil.rmtree(mod_dir)
        return True
    return False


def generate_xcom_yaml(mod: dict) -> str:
    """Generate OpenXCOM YAML ruleset from mod slots."""
    lines = [f"# {mod['name']} — OpenXCOM Mod", f"# Author: {mod['author']}", ""]

    lines.append("extraStrings:")
    lines.append("  - type: en-US")
    lines.append("    strings:")
    for slot in mod["slots"]:
        str_id = f"STR_{slot['id'].upper()}"
        lines.append(f"      {str_id}: \"{slot['name']}\"")
    lines.append("")

    lines.append("extraSprites:")
    for slot in mod["slots"]:
        if slot.get("sprite"):
            pck_name = f"{slot['id'].upper()}.PCK"
            lines.append(f"  - type: {pck_name}")
            lines.append(f"    width: {slot['width']}")
            lines.append(f"    height: {slot['height']}")
            lines.append(f"    files:")
            for i in range(slot.get("frames", 1)):
                lines.append(f"      {i}: Resources/{mod['id']}/{slot['id']}_{i}.png")
    lines.append("")

    return "\n".join(lines)
