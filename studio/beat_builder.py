"""
Beat builder template engine for Wyltek Studio.

Assembles sample packs into arranged tracks using pydub.
Templates live in data/templates/{id}.json and describe BPM, structure,
slot patterns/loops, and mix parameters.
"""

import json
import logging
import math
import os
from pathlib import Path
from typing import Optional

from pydub import AudioSegment

from studio import sample_packs

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent.parent / "data" / "templates"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def list_templates() -> list[dict]:
    """List all available beat templates.

    Loads each JSON file in TEMPLATES_DIR and injects the ``id`` field
    (the filename stem).  Returns an empty list if the directory is missing.
    """
    if not TEMPLATES_DIR.exists():
        return []

    templates = []
    for entry in sorted(TEMPLATES_DIR.iterdir()):
        if entry.suffix.lower() != ".json":
            continue
        try:
            with entry.open() as f:
                data = json.load(f)
            templates.append({**data, "id": entry.stem})
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Skipping template %s: %s", entry.name, exc)
    return templates


def load_template(template_id: str) -> dict:
    """Load a template by ID.

    Raises:
        FileNotFoundError: if the template JSON does not exist.
    """
    path = TEMPLATES_DIR / f"{template_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {template_id}")
    with path.open() as f:
        data = json.load(f)
    return {**data, "id": template_id}


def build_track(
    template_id: str,
    overrides: dict,
    bpm: int = 0,
    output_path: str = "",
    preview_bars: int = 0,
) -> dict:
    """Assemble a beat track from a template and export it as a WAV file.

    Args:
        template_id: ID of the template to use (must exist in TEMPLATES_DIR).
        overrides: Mapping of slot_name -> {"pack": pack_id, "sample": filename}
            for slots whose source sample should be swapped.
        bpm: Override the template BPM.  0 means use the template default.
        output_path: Destination path for the exported WAV.  If empty, a path
            is generated next to the templates directory.
        preview_bars: When > 0, the structure is trimmed to at most this many
            bars so a quick preview can be rendered cheaply.

    Returns:
        dict with keys: duration (seconds), file_size (bytes), bpm, sections, template.
    """
    template = load_template(template_id)
    effective_bpm = bpm if bpm > 0 else template.get("bpm", 120)

    # ---- timing ------------------------------------------------------------
    beat_ms = 60_000 / effective_bpm
    bar_ms = beat_ms * 4          # 4/4 assumed
    subdivisions = 8
    sub_ms = bar_ms / subdivisions

    # ---- structure ---------------------------------------------------------
    structure = template.get("structure", [])
    if preview_bars > 0:
        structure = _trim_structure(structure, preview_bars)

    # ---- resolve audio samples ---------------------------------------------
    default_pack = template.get("default_pack", "")
    slot_defs = template.get("slots", {})

    resolved_audio: dict[str, Optional[AudioSegment]] = {}
    for slot_name, slot_def in slot_defs.items():
        resolved_audio[slot_name] = _resolve_audio(
            slot_name, slot_def, default_pack, overrides
        )

    # ---- mix params --------------------------------------------------------
    mix = template.get("mix", {})
    master_volume: float = mix.get("master_volume", 1.0)
    fade_in_bars: int = mix.get("fade_in_bars", 0)
    fade_out_bars: int = mix.get("fade_out_bars", 0)

    # ---- build sections ----------------------------------------------------
    track = AudioSegment.silent(duration=0)
    section_names: list[str] = []

    for section_spec in structure:
        section_name = section_spec.get("section", "unknown")
        bars = section_spec.get("bars", 4)
        section_ms = int(bar_ms * bars)
        section_names.append(section_name)

        base = AudioSegment.silent(duration=section_ms)

        for slot_name, slot_def in slot_defs.items():
            audio = resolved_audio.get(slot_name)
            if audio is None:
                continue

            # Check if this slot is active for this section
            active_sections = slot_def.get("sections", [])
            if not _slot_active(section_name, active_sections):
                continue

            velocity: float = slot_def.get("velocity", 1.0)
            gain_db = _velocity_to_db(velocity)
            slot_audio = audio.apply_gain(gain_db)

            trigger = slot_def.get("trigger", "")
            pattern = slot_def.get("pattern")
            slot_type = slot_def.get("type", "oneshot")

            if trigger == "section_start":
                # Place oneshot once at position 0
                base = _overlay_at(base, slot_audio, 0)

            elif pattern is not None and len(pattern) > 0:
                # Pattern-driven oneshot placement
                base = _apply_pattern(base, slot_audio, pattern, sub_ms, bars)

            elif slot_type == "loop":
                # Loop: repeat/trim to fill the section
                looped = _loop_to_length(slot_audio, section_ms)
                base = base.overlay(looped)

        track = track + base

    # ---- master volume and fades -------------------------------------------
    if master_volume != 1.0:
        master_db = _velocity_to_db(master_volume)
        track = track.apply_gain(master_db)

    if fade_in_bars > 0:
        fade_in_ms = int(bar_ms * fade_in_bars)
        track = track.fade_in(min(fade_in_ms, len(track)))

    if fade_out_bars > 0:
        fade_out_ms = int(bar_ms * fade_out_bars)
        track = track.fade_out(min(fade_out_ms, len(track)))

    # ---- export ------------------------------------------------------------
    if not output_path:
        out_dir = TEMPLATES_DIR.parent / "outputs" / "beats"
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(out_dir / f"{template_id}.wav")

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    track.export(output_path, format="wav")

    file_size = os.path.getsize(output_path)
    duration = len(track) / 1000.0

    return {
        "duration": duration,
        "file_size": file_size,
        "bpm": effective_bpm,
        "sections": section_names,
        "template": template_id,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_audio(
    slot_name: str,
    slot_def: dict,
    default_pack: str,
    overrides: dict,
) -> Optional[AudioSegment]:
    """Resolve audio for a single slot, respecting user overrides."""
    override = overrides.get(slot_name)

    if override:
        pack_id = override.get("pack", default_pack)
        custom_file = override.get("sample", "")
        if custom_file:
            # User supplied a specific filename — resolve relative to pack dir
            pack_dir = Path(__file__).parent.parent / "data" / "sample-packs" / pack_id
            candidate = pack_dir / custom_file
            if candidate.exists():
                return _load_wav(candidate)
            logger.warning(
                "Override sample not found for slot %s: %s", slot_name, candidate
            )
        # Fall through to pack slot resolution with the overridden pack
        path = sample_packs.resolve_sample(pack_id, slot_name)
    else:
        path = sample_packs.resolve_sample(default_pack, slot_name)

    if path is None:
        logger.debug("No sample resolved for slot %s (pack=%s)", slot_name, default_pack)
        return None

    return _load_wav(path)


def _load_wav(path: Path) -> Optional[AudioSegment]:
    """Load a WAV file into an AudioSegment, returning None on failure."""
    try:
        return AudioSegment.from_wav(str(path))
    except Exception as exc:
        logger.warning("Failed to load WAV %s: %s", path, exc)
        return None


def _slot_active(section_name: str, active_sections: list) -> bool:
    """Return True if the slot should play in this section."""
    if not active_sections:
        return False
    if "all" in active_sections:
        return True
    return section_name in active_sections


def _overlay_at(base: AudioSegment, clip: AudioSegment, position_ms: int) -> AudioSegment:
    """Overlay clip onto base at position_ms, clamping to base length."""
    if position_ms >= len(base):
        return base
    return base.overlay(clip, position=position_ms)


def _apply_pattern(
    base: AudioSegment,
    hit: AudioSegment,
    pattern: list,
    sub_ms: float,
    bars: int,
) -> AudioSegment:
    """Overlay a oneshot hit at every active step in a repeating pattern.

    The pattern repeats every len(pattern) subdivisions, cycling over all bars.

    Args:
        base: The section buffer to overlay hits onto.
        hit: The oneshot sample to place at active steps.
        pattern: List of 0/1 values (1 = place hit at this subdivision).
        sub_ms: Duration of one subdivision in milliseconds.
        bars: Number of bars in this section.

    Returns:
        Updated AudioSegment with hits overlaid.
    """
    if not pattern:
        return base

    steps_per_bar = len(pattern)
    result = base
    total_bars = bars

    for bar in range(total_bars):
        for step, active in enumerate(pattern):
            if not active:
                continue
            position_ms = int((bar * steps_per_bar + step) * sub_ms)
            result = _overlay_at(result, hit, position_ms)

    return result


def _loop_to_length(audio: AudioSegment, target_ms: int) -> AudioSegment:
    """Repeat or trim an audio segment to exactly target_ms milliseconds."""
    if len(audio) == 0:
        return AudioSegment.silent(duration=target_ms)

    result = audio
    while len(result) < target_ms:
        result = result + audio

    return result[:target_ms]


def _velocity_to_db(velocity: float) -> float:
    """Convert a 0.0–1.0 velocity to a dB gain value (log scale).

    Clamps velocity to the range [0.001, 1.0] to avoid log(0).
    velocity=1.0 → 0.0 dB (no change).
    velocity=0.5 → ~-6.0 dB.
    """
    clamped = max(0.001, min(1.0, velocity))
    return 20.0 * math.log10(clamped)


def _trim_structure(structure: list[dict], max_bars: int) -> list[dict]:
    """Trim a structure list to at most max_bars total bars.

    Sections are included in order until the bar budget is exhausted.
    A section that would exceed the budget is truncated.

    Args:
        structure: List of {"section": str, "bars": int} dicts.
        max_bars: Maximum total bars to include.

    Returns:
        A new structure list (original is not modified).
    """
    result = []
    remaining = max_bars
    for spec in structure:
        if remaining <= 0:
            break
        bars = spec.get("bars", 4)
        included = min(bars, remaining)
        result.append({**spec, "bars": included})
        remaining -= included
    return result
