"""Sprite sheet orchestration helpers — pure logic.

Per-frame I/O and ComfyUI dispatch live in `server.py` (`_run_sprite_sheet_job`).
This module owns the pieces that benefit from being unit-testable and
easy to tweak without restarting the server:

  * Tight / Loose presets that translate to IP-Adapter strengths
  * The default pose list shown as UI chips
  * Per-frame prompt construction (TODO for user to refine)
  * Frame-index → grid-slot mapping
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


# --- Identity-lock presets --------------------------------------------------
#
# `tight`  → reference image dominates; character matches across all frames.
# `loose`  → prompt dominates; more variety but identity may drift between
#            frames.
#
# Numbers picked to land well above / below the ComfyUI default IP-Adapter
# strength (0.75) so the difference is visibly meaningful. The CFG bump on
# `loose` keeps prompt influence high once image weight drops.

PRESETS: dict[str, dict[str, float]] = {
    "tight": {
        "ip_adapter_strength": 0.95,
        "ip_adapter_weight_type": "style transfer",
        "ip_adapter_start": 0.0,
        "ip_adapter_end": 1.0,
        "cfg": 5.5,
    },
    "loose": {
        "ip_adapter_strength": 0.45,
        "ip_adapter_weight_type": "style transfer",
        "ip_adapter_start": 0.0,
        "ip_adapter_end": 0.7,
        "cfg": 7.0,
    },
}


# --- Pose-set presets -------------------------------------------------------
#
# Each preset is a named list of pose IDs. The UI exposes them via a "Pose
# set" dropdown; selecting one replaces the active chip list. Users can
# still toggle individual chips off and add custom poses on top.
#
# Naming convention: pose IDs are snake_case, descriptive but short, and
# match the verbs a prompt will key off (see `build_pose_prompt`). Adding
# a "_N" suffix denotes a frame number inside an animation cycle.

POSE_PRESETS: list[dict] = [
    {
        "id": "platformer",
        "label": "Platformer / Action (8)",
        "description": "Side-scroller staple set — idle, walk cycle, run, jump, attack, hurt, victory.",
        "poses": [
            "idle", "walk_1", "walk_2", "run",
            "jump", "attack", "hurt", "victory",
        ],
    },
    {
        "id": "jrpg-four-dir",
        "label": "JRPG four-direction (8)",
        "description": "Top-down 2-frame walk cycle in each of the four cardinal directions — Pokémon-style.",
        "poses": [
            "walk_down_1", "walk_down_2",
            "walk_up_1", "walk_up_2",
            "walk_left_1", "walk_left_2",
            "walk_right_1", "walk_right_2",
        ],
    },
    {
        "id": "walk-cycle-8",
        "label": "Smooth walk cycle (8)",
        "description": "Eight-frame side-view walk — contact, recoil, passing, high-point × 2 sides.",
        "poses": [
            "walk_1", "walk_2", "walk_3", "walk_4",
            "walk_5", "walk_6", "walk_7", "walk_8",
        ],
    },
    {
        "id": "fighter",
        "label": "Fighter (8)",
        "description": "Brawler / fighting-game move set — neutral stance through KO.",
        "poses": [
            "stance", "jab", "hook", "uppercut",
            "kick_low", "kick_high", "block", "ko",
        ],
    },
    {
        "id": "combat-npc",
        "label": "Combat NPC (8)",
        "description": "Enemy / NPC behaviour cycle — idle, alert, attack variants, hurt, knockdown, dead.",
        "poses": [
            "idle", "alert", "attack_swing", "attack_thrust",
            "block", "hurt", "knockdown", "dead",
        ],
    },
    {
        "id": "emotes",
        "label": "Emotes / social (8)",
        "description": "Non-combat character expressions — wave, point, sit, sleep, dance, etc.",
        "poses": [
            "wave", "point", "sit", "sleep",
            "cheer", "dance", "laugh", "cry",
        ],
    },
    {
        "id": "facing-quad",
        "label": "Facing quad (4)",
        "description": "Minimum set for a static NPC sprite — same idle from four cardinal angles.",
        "poses": [
            "idle_front", "idle_left", "idle_right", "idle_back",
        ],
    },
]


def get_pose_preset(preset_id: str) -> dict | None:
    """Look up a pose-set preset by id. Returns None if unknown."""
    return next((p for p in POSE_PRESETS if p["id"] == preset_id), None)


# Back-compat alias — the original DEFAULT_POSES is the platformer preset.
DEFAULT_POSES: list[str] = POSE_PRESETS[0]["poses"]


# --- Per-frame prompt -------------------------------------------------------

def build_pose_prompt(pose: str, *, style_hint: str = "") -> str:
    """Compose the per-frame prompt sent to ComfyUI alongside the reference.

    `generate_sprites()` already prefixes "pixel art sprite, …, game asset,
    clean lines, transparent background, 16-bit style" so we only need the
    *subject + action* clause here. The reference image carries identity;
    this prompt carries the pose.

    Args:
        pose:       pose id from UI (e.g. "idle", "walk_1", "attack")
        style_hint: optional user modifier (e.g. "side-scroller, 16-bit")

    Returns: the prompt body for ComfyUI. Keep terse — long prompts hurt
    SDXL pose adherence more than they help.
    """
    # TODO(phill): edit this. Identity-lock instructions ("same character as
    # reference", "preserve outfit and palette") help when the model drifts;
    # pose verbs ("running forward", "mid-leap") beat noun forms
    # ("running pose"). Style_hint is appended raw — keep it short.
    pose_clean = pose.replace("_", " ")
    parts = [f"same character as reference, {pose_clean} pose, full body, side view"]
    if style_hint:
        parts.append(style_hint)
    return ", ".join(parts)


# --- Sheet layout -----------------------------------------------------------

@dataclass(frozen=True)
class SheetLayout:
    columns: int
    rows: int
    cell_width: int
    cell_height: int

    @property
    def sheet_width(self) -> int:
        return self.columns * self.cell_width

    @property
    def sheet_height(self) -> int:
        return self.rows * self.cell_height


def plan_layout(
    n_frames: int,
    *,
    columns: int = 4,
    cell_width: int = 256,
    cell_height: int = 256,
) -> SheetLayout:
    """Compute the grid dimensions for `n_frames` frames.

    Default 4 columns gives a balanced rectangle for 4 / 8 / 12 pose sets.
    Rows round up; trailing cells stay transparent if frame count isn't
    a clean multiple of `columns`.
    """
    if n_frames < 1:
        raise ValueError("n_frames must be >= 1")
    rows = (n_frames + columns - 1) // columns
    return SheetLayout(
        columns=columns,
        rows=rows,
        cell_width=cell_width,
        cell_height=cell_height,
    )


def slot_for_frame(idx: int, layout: SheetLayout) -> tuple[int, int]:
    """Map a 0-based frame index to its (col, row) on the sheet."""
    return idx % layout.columns, idx // layout.columns


# --- Pose ID validation -----------------------------------------------------

def normalise_poses(raw: Iterable[str]) -> list[str]:
    """Strip whitespace, dedupe (preserving order), drop empties.

    Pose IDs are user-controlled; they end up in filenames and the sidecar
    JSON. Keep them filesystem-safe by replacing spaces with underscores.
    """
    seen: set[str] = set()
    out: list[str] = []
    for p in raw:
        if not p:
            continue
        clean = p.strip().lower().replace(" ", "_")
        if not clean or clean in seen:
            continue
        seen.add(clean)
        out.append(clean)
    return out
