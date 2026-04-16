# Sample Builder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a sample-based beat builder at `/studio/beats` — users pick genre templates, swap samples, and build arranged tracks with optional MusicGen AI enhancement.

**Architecture:** Two backend modules (`sample_packs.py` for registry, `beat_builder.py` for assembly), six API endpoints in `server.py`, one frontend page. Sample packs and templates stored as JSON + WAV files under `data/`. Track assembly uses pydub for layering/mixing, MusicGen `generate_with_chroma` for optional AI polish.

**Tech Stack:** Python/FastAPI (existing), pydub (new dep), audiocraft/MusicGen (existing), vanilla JS frontend (matches existing studio pages).

---

### Task 1: Install pydub and create data directories

**Files:**
- Modify: `requirements.txt`
- Create: `data/sample-packs/.gitkeep`
- Create: `data/templates/.gitkeep`

- [ ] **Step 1: Install pydub**

```bash
pip install pydub
```

- [ ] **Step 2: Verify pydub works with FFmpeg**

```bash
python3 -c "from pydub import AudioSegment; print('pydub OK')"
```

Expected: `pydub OK`

- [ ] **Step 3: Add pydub to requirements.txt**

Add `pydub` to the existing requirements.txt file.

- [ ] **Step 4: Create data directories**

```bash
mkdir -p data/sample-packs data/templates
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt data/
git commit -m "chore: add pydub dependency and data directories for sample builder"
```

---

### Task 2: Create starter sample packs

**Files:**
- Create: `scripts/fetch-sample-packs.py`
- Create: `data/sample-packs/hip-hop-kit/pack.json`
- Create: `data/sample-packs/lo-fi-kit/pack.json`
- Create: `data/sample-packs/electronic-kit/pack.json`

Each pack needs 8 normalised WAV samples. Since we can't download from freesound.org programmatically without an API key, we'll generate placeholder packs using pydub's tone generators and document how to replace them with real CC0 samples later.

- [ ] **Step 1: Create the sample pack generator script**

```python
"""Generate placeholder sample packs with synthesized sounds.

Replace individual WAV files with real CC0 samples from freesound.org
for production use. This script creates usable placeholder packs so
the beat builder can be developed and tested immediately.
"""

from pathlib import Path
from pydub import AudioSegment
from pydub.generators import Sine, Square, Sawtooth, WhiteNoise
import json
import struct
import math

DATA_DIR = Path(__file__).parent.parent / "data" / "sample-packs"


def make_kick(duration_ms: int = 200) -> AudioSegment:
    """Synthesize a kick drum — sine sweep from 150Hz to 40Hz."""
    sample_rate = 44100
    samples = int(sample_rate * duration_ms / 1000)
    raw = []
    for i in range(samples):
        t = i / sample_rate
        progress = i / samples
        freq = 150 * (1 - progress) + 40 * progress
        amplitude = (1 - progress) ** 2  # exponential decay
        sample = amplitude * math.sin(2 * math.pi * freq * t)
        raw.append(int(sample * 32767))
    data = struct.pack(f"<{len(raw)}h", *raw)
    return AudioSegment(data=data, sample_width=2, frame_rate=sample_rate, channels=1)


def make_snare(duration_ms: int = 150) -> AudioSegment:
    """Synthesize a snare — noise burst + pitched tone."""
    noise = WhiteNoise().to_audio_segment(duration=duration_ms)
    tone = Sine(200).to_audio_segment(duration=duration_ms)
    mix = noise.overlay(tone - 6)  # tone quieter
    return mix.fade_out(int(duration_ms * 0.8))


def make_hihat(duration_ms: int = 80) -> AudioSegment:
    """Synthesize a closed hi-hat — short noise burst."""
    noise = WhiteNoise().to_audio_segment(duration=duration_ms)
    return noise.fade_out(60) - 6  # quieter


def make_openhat(duration_ms: int = 300) -> AudioSegment:
    """Synthesize an open hi-hat — longer noise."""
    noise = WhiteNoise().to_audio_segment(duration=duration_ms)
    return noise.fade_out(200) - 6


def make_bass_loop(bpm: int, bars: int = 2) -> AudioSegment:
    """Synthesize a bass loop — simple sub pattern."""
    beat_ms = int(60000 / bpm)
    bar_ms = beat_ms * 4
    total_ms = bar_ms * bars
    silence = AudioSegment.silent(duration=total_ms)
    note = Sine(55).to_audio_segment(duration=beat_ms).fade_out(int(beat_ms * 0.7)) - 3
    # Play on beats 1 and 3
    result = silence.overlay(note, position=0)
    result = result.overlay(note, position=beat_ms * 2)
    if bars > 1:
        result = result.overlay(note, position=bar_ms)
        result = result.overlay(note, position=bar_ms + beat_ms * 2)
    return result


def make_melody_loop(bpm: int, freq: float, bars: int = 2) -> AudioSegment:
    """Synthesize a simple melody loop."""
    beat_ms = int(60000 / bpm)
    bar_ms = beat_ms * 4
    total_ms = bar_ms * bars
    silence = AudioSegment.silent(duration=total_ms)
    notes = [freq, freq * 1.25, freq * 1.5, freq * 1.25]
    for i, f in enumerate(notes):
        note = Sine(f).to_audio_segment(duration=beat_ms).fade_in(20).fade_out(80) - 8
        silence = silence.overlay(note, position=i * beat_ms)
    return silence


def make_pad_loop(bpm: int, freq: float, bars: int = 4) -> AudioSegment:
    """Synthesize a pad — sustained tone with slow attack."""
    bar_ms = int(60000 / bpm) * 4
    total_ms = bar_ms * bars
    pad = Sine(freq).to_audio_segment(duration=total_ms).fade_in(500).fade_out(500) - 12
    return pad


def make_fx(duration_ms: int = 500) -> AudioSegment:
    """Synthesize a riser FX — ascending sweep."""
    sample_rate = 44100
    samples = int(sample_rate * duration_ms / 1000)
    raw = []
    for i in range(samples):
        t = i / sample_rate
        progress = i / samples
        freq = 200 + 2000 * progress
        amplitude = progress * 0.5
        sample = amplitude * math.sin(2 * math.pi * freq * t)
        raw.append(int(sample * 32767))
    data = struct.pack(f"<{len(raw)}h", *raw)
    return AudioSegment(data=data, sample_width=2, frame_rate=sample_rate, channels=1)


def normalise(seg: AudioSegment, target_dbfs: float = -14.0) -> AudioSegment:
    """Normalise audio to target loudness."""
    change = target_dbfs - seg.dBFS
    return seg.apply_gain(change)


def write_pack(name: str, meta: dict, samples: dict[str, AudioSegment]):
    """Write a sample pack to disk."""
    pack_dir = DATA_DIR / name
    pack_dir.mkdir(parents=True, exist_ok=True)

    pack_json = {
        "name": meta["name"],
        "description": meta["description"],
        "bpm_range": meta["bpm_range"],
        "genre_tags": meta["genre_tags"],
        "samples": {},
    }

    for slot, audio in samples.items():
        filename = f"{slot}.wav"
        normalise(audio).export(str(pack_dir / filename), format="wav")
        sample_type = "loop" if slot in ("bass", "melody", "pad") else "oneshot"
        pack_json["samples"][slot] = {"file": filename, "type": sample_type}

    with open(pack_dir / "pack.json", "w") as f:
        json.dump(pack_json, f, indent=2)
    print(f"  Written: {pack_dir}")


def main():
    print("Generating sample packs...")

    # Hip Hop Kit (90 BPM)
    write_pack("hip-hop-kit", {
        "name": "Hip Hop Kit",
        "description": "Boom bap drums, deep bass, soulful melody",
        "bpm_range": [80, 100],
        "genre_tags": ["hip-hop", "boom-bap", "rap"],
    }, {
        "kick": make_kick(200),
        "snare": make_snare(150),
        "hihat": make_hihat(80),
        "openhat": make_openhat(300),
        "bass": make_bass_loop(90),
        "melody": make_melody_loop(90, 330),  # E4
        "pad": make_pad_loop(90, 165),         # E3
        "fx": make_fx(500),
    })

    # Lo-Fi Kit (80 BPM)
    write_pack("lo-fi-kit", {
        "name": "Lo-Fi Kit",
        "description": "Dusty drums, warm bass, jazzy chords",
        "bpm_range": [70, 90],
        "genre_tags": ["lo-fi", "chill", "jazzy"],
    }, {
        "kick": make_kick(250),  # longer, softer kick
        "snare": make_snare(180),
        "hihat": make_hihat(60),
        "openhat": make_openhat(250),
        "bass": make_bass_loop(80),
        "melody": make_melody_loop(80, 294),  # D4
        "pad": make_pad_loop(80, 147),         # D3
        "fx": make_fx(600),
    })

    # Electronic Kit (128 BPM)
    write_pack("electronic-kit", {
        "name": "Electronic Kit",
        "description": "Punchy drums, synth bass, arp melody",
        "bpm_range": [120, 140],
        "genre_tags": ["house", "techno", "electronic"],
    }, {
        "kick": make_kick(150),  # shorter, punchier
        "snare": make_snare(100),
        "hihat": make_hihat(50),
        "openhat": make_openhat(200),
        "bass": make_bass_loop(128),
        "melody": make_melody_loop(128, 440),  # A4
        "pad": make_pad_loop(128, 220),         # A3
        "fx": make_fx(400),
    })

    # Create empty user pack
    user_dir = DATA_DIR / "user"
    user_dir.mkdir(parents=True, exist_ok=True)
    with open(user_dir / "pack.json", "w") as f:
        json.dump({
            "name": "My Samples",
            "description": "Your uploaded samples",
            "bpm_range": [60, 200],
            "genre_tags": ["custom"],
            "samples": {},
        }, f, indent=2)
    print(f"  Written: {user_dir}")

    print("Done.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the generator**

```bash
cd /home/phill/open-palette && python3 scripts/fetch-sample-packs.py
```

Expected: Three pack directories created with WAV files and pack.json each, plus empty user pack.

- [ ] **Step 3: Verify packs**

```bash
ls data/sample-packs/hip-hop-kit/
```

Expected: `bass.wav fx.wav hihat.wav kick.wav melody.wav openhat.wav pack.json pad.wav snare.wav`

- [ ] **Step 4: Commit**

```bash
git add scripts/fetch-sample-packs.py data/sample-packs/
git commit -m "feat: add synthesized starter sample packs for beat builder"
```

---

### Task 3: Create genre templates

**Files:**
- Create: `data/templates/hip-hop.json`
- Create: `data/templates/lo-fi.json`
- Create: `data/templates/trap.json`
- Create: `data/templates/house.json`

- [ ] **Step 1: Write hip-hop template**

Create `data/templates/hip-hop.json`:

```json
{
  "name": "Hip Hop",
  "bpm": 90,
  "time_sig": "4/4",
  "default_pack": "hip-hop-kit",
  "structure": [
    { "section": "intro", "bars": 4 },
    { "section": "verse", "bars": 16 },
    { "section": "chorus", "bars": 8 },
    { "section": "verse", "bars": 16 },
    { "section": "chorus", "bars": 8 },
    { "section": "outro", "bars": 4 }
  ],
  "slots": {
    "kick": { "pattern": [1,0,0,0, 1,0,0,0], "velocity": 1.0, "sections": ["all"] },
    "snare": { "pattern": [0,0,1,0, 0,0,1,0], "velocity": 0.9, "sections": ["all"] },
    "hihat": { "pattern": [1,1,1,1, 1,1,1,1], "velocity": 0.6, "sections": ["all"] },
    "openhat": { "pattern": [0,0,0,0, 0,0,0,1], "velocity": 0.5, "sections": ["chorus"] },
    "bass": { "type": "loop", "velocity": 0.8, "sections": ["verse", "chorus"] },
    "melody": { "type": "loop", "velocity": 0.5, "sections": ["verse", "chorus"] },
    "pad": { "type": "loop", "velocity": 0.3, "sections": ["chorus", "outro"] },
    "fx": { "type": "oneshot", "trigger": "section_start", "velocity": 0.4, "sections": ["chorus"] }
  },
  "mix": { "master_volume": 0.85, "fade_in_bars": 2, "fade_out_bars": 2 }
}
```

- [ ] **Step 2: Write lo-fi template**

Create `data/templates/lo-fi.json`:

```json
{
  "name": "Lo-Fi",
  "bpm": 80,
  "time_sig": "4/4",
  "default_pack": "lo-fi-kit",
  "structure": [
    { "section": "intro", "bars": 4 },
    { "section": "verse", "bars": 16 },
    { "section": "chorus", "bars": 8 },
    { "section": "verse", "bars": 16 },
    { "section": "outro", "bars": 4 }
  ],
  "slots": {
    "kick": { "pattern": [1,0,0,0, 0,0,1,0], "velocity": 0.9, "sections": ["all"] },
    "snare": { "pattern": [0,0,1,0, 0,0,0,1], "velocity": 0.8, "sections": ["all"] },
    "hihat": { "pattern": [1,0,1,0, 1,0,1,0], "velocity": 0.5, "sections": ["verse", "chorus"] },
    "openhat": { "pattern": [0,0,0,0, 0,0,0,0], "velocity": 0.4, "sections": [] },
    "bass": { "type": "loop", "velocity": 0.7, "sections": ["verse", "chorus"] },
    "melody": { "type": "loop", "velocity": 0.6, "sections": ["all"] },
    "pad": { "type": "loop", "velocity": 0.4, "sections": ["all"] },
    "fx": { "type": "oneshot", "trigger": "section_start", "velocity": 0.3, "sections": ["intro"] }
  },
  "mix": { "master_volume": 0.8, "fade_in_bars": 4, "fade_out_bars": 4 }
}
```

- [ ] **Step 3: Write trap template**

Create `data/templates/trap.json`:

```json
{
  "name": "Trap",
  "bpm": 140,
  "time_sig": "4/4",
  "default_pack": "electronic-kit",
  "structure": [
    { "section": "intro", "bars": 4 },
    { "section": "verse", "bars": 8 },
    { "section": "chorus", "bars": 8 },
    { "section": "verse", "bars": 8 },
    { "section": "chorus", "bars": 8 },
    { "section": "outro", "bars": 4 }
  ],
  "slots": {
    "kick": { "pattern": [1,0,0,1, 0,0,1,0], "velocity": 1.0, "sections": ["all"] },
    "snare": { "pattern": [0,0,0,0, 1,0,0,0], "velocity": 1.0, "sections": ["all"] },
    "hihat": { "pattern": [1,1,1,1, 1,1,1,1], "velocity": 0.7, "sections": ["all"] },
    "openhat": { "pattern": [0,0,0,0, 0,0,1,0], "velocity": 0.5, "sections": ["chorus"] },
    "bass": { "type": "loop", "velocity": 0.9, "sections": ["verse", "chorus"] },
    "melody": { "type": "loop", "velocity": 0.4, "sections": ["chorus"] },
    "pad": { "type": "loop", "velocity": 0.2, "sections": ["intro", "outro"] },
    "fx": { "type": "oneshot", "trigger": "section_start", "velocity": 0.5, "sections": ["chorus"] }
  },
  "mix": { "master_volume": 0.9, "fade_in_bars": 1, "fade_out_bars": 2 }
}
```

- [ ] **Step 4: Write house template**

Create `data/templates/house.json`:

```json
{
  "name": "House",
  "bpm": 124,
  "time_sig": "4/4",
  "default_pack": "electronic-kit",
  "structure": [
    { "section": "intro", "bars": 8 },
    { "section": "verse", "bars": 16 },
    { "section": "chorus", "bars": 16 },
    { "section": "verse", "bars": 16 },
    { "section": "chorus", "bars": 16 },
    { "section": "outro", "bars": 8 }
  ],
  "slots": {
    "kick": { "pattern": [1,0,0,0, 1,0,0,0], "velocity": 1.0, "sections": ["all"] },
    "snare": { "pattern": [0,0,0,0, 1,0,0,0], "velocity": 0.8, "sections": ["verse", "chorus"] },
    "hihat": { "pattern": [0,1,0,1, 0,1,0,1], "velocity": 0.6, "sections": ["all"] },
    "openhat": { "pattern": [0,0,1,0, 0,0,1,0], "velocity": 0.5, "sections": ["chorus"] },
    "bass": { "type": "loop", "velocity": 0.8, "sections": ["verse", "chorus"] },
    "melody": { "type": "loop", "velocity": 0.5, "sections": ["chorus"] },
    "pad": { "type": "loop", "velocity": 0.4, "sections": ["all"] },
    "fx": { "type": "oneshot", "trigger": "section_start", "velocity": 0.4, "sections": ["chorus"] }
  },
  "mix": { "master_volume": 0.85, "fade_in_bars": 4, "fade_out_bars": 4 }
}
```

- [ ] **Step 5: Commit**

```bash
git add data/templates/
git commit -m "feat: add genre templates for beat builder (hip-hop, lo-fi, trap, house)"
```

---

### Task 4: Build sample_packs.py registry

**Files:**
- Create: `studio/sample_packs.py`

- [ ] **Step 1: Write sample_packs.py**

```python
"""Sample pack registry — lists packs, resolves sample paths, handles uploads."""

import json
import shutil
from pathlib import Path
from typing import Optional

DATA_DIR = Path(__file__).parent.parent / "data" / "sample-packs"

ALL_SLOTS = ["kick", "snare", "hihat", "openhat", "bass", "melody", "pad", "fx"]


def list_packs() -> list[dict]:
    """List all available sample packs with metadata."""
    packs = []
    if not DATA_DIR.exists():
        return packs
    for pack_dir in sorted(DATA_DIR.iterdir()):
        if not pack_dir.is_dir():
            continue
        meta_path = pack_dir / "pack.json"
        if not meta_path.exists():
            continue
        with open(meta_path) as f:
            meta = json.load(f)
        meta["id"] = pack_dir.name
        # Count actual WAV files present
        meta["sample_count"] = sum(
            1 for s in meta.get("samples", {}).values()
            if (pack_dir / s["file"]).exists()
        )
        packs.append(meta)
    return packs


def list_samples(pack_id: str) -> list[dict]:
    """List all samples in a pack with slot and type info."""
    pack_dir = DATA_DIR / pack_id
    meta_path = pack_dir / "pack.json"
    if not meta_path.exists():
        return []
    with open(meta_path) as f:
        meta = json.load(f)
    samples = []
    for slot, info in meta.get("samples", {}).items():
        filepath = pack_dir / info["file"]
        samples.append({
            "slot": slot,
            "file": info["file"],
            "type": info.get("type", "oneshot"),
            "exists": filepath.exists(),
            "pack_id": pack_id,
        })
    return samples


def resolve_sample(pack_id: str, slot: str) -> Optional[Path]:
    """Get the full path to a sample WAV file."""
    pack_dir = DATA_DIR / pack_id
    meta_path = pack_dir / "pack.json"
    if not meta_path.exists():
        return None
    with open(meta_path) as f:
        meta = json.load(f)
    info = meta.get("samples", {}).get(slot)
    if not info:
        return None
    filepath = pack_dir / info["file"]
    return filepath if filepath.exists() else None


def sample_type(pack_id: str, slot: str) -> str:
    """Get the type (oneshot or loop) for a sample slot."""
    pack_dir = DATA_DIR / pack_id
    meta_path = pack_dir / "pack.json"
    if not meta_path.exists():
        return "oneshot"
    with open(meta_path) as f:
        meta = json.load(f)
    info = meta.get("samples", {}).get(slot)
    return info.get("type", "oneshot") if info else "oneshot"


def save_user_sample(file_bytes: bytes, filename: str, slot: str) -> dict:
    """Save an uploaded sample to the user pack."""
    user_dir = DATA_DIR / "user"
    user_dir.mkdir(parents=True, exist_ok=True)

    # Save the WAV file
    dest = user_dir / filename
    with open(dest, "wb") as f:
        f.write(file_bytes)

    # Update pack.json
    meta_path = user_dir / "pack.json"
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)
    else:
        meta = {
            "name": "My Samples",
            "description": "Your uploaded samples",
            "bpm_range": [60, 200],
            "genre_tags": ["custom"],
            "samples": {},
        }

    # Determine type from slot name
    stype = "loop" if slot in ("bass", "melody", "pad") else "oneshot"
    meta["samples"][slot] = {"file": filename, "type": stype}

    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    return {"slot": slot, "file": filename, "type": stype, "pack_id": "user"}
```

- [ ] **Step 2: Quick smoke test**

```bash
python3 -c "
from studio.sample_packs import list_packs, resolve_sample
packs = list_packs()
print(f'Packs: {len(packs)}')
for p in packs:
    print(f'  {p[\"id\"]}: {p[\"name\"]} ({p[\"sample_count\"]} samples)')
kick = resolve_sample('hip-hop-kit', 'kick')
print(f'Hip-hop kick: {kick}')
"
```

Expected: 4 packs listed (hip-hop-kit, lo-fi-kit, electronic-kit, user), kick path resolved.

- [ ] **Step 3: Commit**

```bash
git add studio/sample_packs.py
git commit -m "feat: add sample pack registry module"
```

---

### Task 5: Build beat_builder.py — template engine

**Files:**
- Create: `studio/beat_builder.py`

- [ ] **Step 1: Write beat_builder.py**

```python
"""Beat builder — assembles samples into arranged tracks using pydub."""

import json
import os
from pathlib import Path
from typing import Optional

from pydub import AudioSegment

from studio import sample_packs

TEMPLATES_DIR = Path(__file__).parent.parent / "data" / "templates"


def list_templates() -> list[dict]:
    """List all available genre templates."""
    templates = []
    if not TEMPLATES_DIR.exists():
        return templates
    for tpl_file in sorted(TEMPLATES_DIR.glob("*.json")):
        with open(tpl_file) as f:
            tpl = json.load(f)
        tpl["id"] = tpl_file.stem
        templates.append(tpl)
    return templates


def load_template(template_id: str) -> dict:
    """Load a template by ID."""
    tpl_path = TEMPLATES_DIR / f"{template_id}.json"
    if not tpl_path.exists():
        raise FileNotFoundError(f"Template not found: {template_id}")
    with open(tpl_path) as f:
        return json.load(f)


def build_track(template_id: str, overrides: dict, bpm: int = 0,
                output_path: str = "", preview_bars: int = 0) -> dict:
    """Build a track from a template with optional sample overrides.

    Args:
        template_id: Genre template to use.
        overrides: Dict of slot -> {"pack": pack_id, "sample": filename}
                   for slots the user has swapped.
        bpm: Override BPM (0 = use template default).
        output_path: Where to write the WAV file.
        preview_bars: If > 0, only render this many bars (for quick preview).

    Returns:
        Dict with duration, file_size, sections info.
    """
    tpl = load_template(template_id)
    bpm = bpm or tpl["bpm"]
    default_pack = tpl["default_pack"]

    beat_ms = 60000 / bpm        # ms per beat
    bar_ms = beat_ms * 4          # ms per bar (4/4 time)
    subdivisions = 8              # 8th-note resolution (pattern length)
    sub_ms = bar_ms / subdivisions

    # Resolve samples for each slot
    slot_audio: dict[str, AudioSegment] = {}
    slot_types: dict[str, str] = {}

    for slot_name in sample_packs.ALL_SLOTS:
        if slot_name not in tpl.get("slots", {}):
            continue

        # User override or default pack
        if slot_name in overrides:
            ov = overrides[slot_name]
            sample_path = sample_packs.resolve_sample(ov["pack"], slot_name)
            stype = sample_packs.sample_type(ov["pack"], slot_name)
        else:
            sample_path = sample_packs.resolve_sample(default_pack, slot_name)
            stype = sample_packs.sample_type(default_pack, slot_name)

        if sample_path and sample_path.exists():
            slot_audio[slot_name] = AudioSegment.from_file(str(sample_path))
            slot_types[slot_name] = stype

    # Build arrangement
    structure = tpl["structure"]
    if preview_bars > 0:
        # Trim structure for preview
        structure = _trim_structure(structure, preview_bars)

    sections_audio: list[AudioSegment] = []
    section_info: list[dict] = []

    for sec in structure:
        sec_name = sec["section"]
        sec_bars = sec["bars"]
        sec_ms = int(bar_ms * sec_bars)
        section_mix = AudioSegment.silent(duration=sec_ms)

        for slot_name, slot_cfg in tpl["slots"].items():
            if slot_name not in slot_audio:
                continue

            # Check if this slot plays in this section
            slot_sections = slot_cfg.get("sections", ["all"])
            if "all" not in slot_sections and sec_name not in slot_sections:
                continue

            velocity = slot_cfg.get("velocity", 1.0)
            volume_db = _velocity_to_db(velocity)
            audio = slot_audio[slot_name]

            if slot_cfg.get("pattern"):
                # Pattern-based (oneshot): place hits according to pattern
                section_mix = _apply_pattern(
                    section_mix, audio + volume_db,
                    slot_cfg["pattern"], sub_ms, sec_bars
                )
            elif slot_cfg.get("type") == "loop":
                # Loop: repeat/trim to fill section
                looped = _loop_to_length(audio + volume_db, sec_ms)
                section_mix = section_mix.overlay(looped)
            elif slot_cfg.get("trigger") == "section_start":
                # Oneshot at section start
                section_mix = section_mix.overlay(audio + volume_db, position=0)

        sections_audio.append(section_mix)
        section_info.append({"section": sec_name, "bars": sec_bars,
                             "duration_ms": sec_ms})

    # Concatenate all sections
    full_track = sections_audio[0]
    for sec_audio in sections_audio[1:]:
        full_track = full_track + sec_audio

    # Apply master mix
    mix_cfg = tpl.get("mix", {})
    master_vol = mix_cfg.get("master_volume", 0.85)
    full_track = full_track + _velocity_to_db(master_vol)

    # Fade in/out
    fade_in_bars = mix_cfg.get("fade_in_bars", 0)
    fade_out_bars = mix_cfg.get("fade_out_bars", 0)
    if fade_in_bars > 0:
        full_track = full_track.fade_in(int(bar_ms * fade_in_bars))
    if fade_out_bars > 0:
        full_track = full_track.fade_out(int(bar_ms * fade_out_bars))

    # Export
    full_track.export(output_path, format="wav")

    return {
        "duration": round(len(full_track) / 1000, 2),
        "file_size": os.path.getsize(output_path),
        "bpm": bpm,
        "sections": section_info,
        "template": template_id,
    }


def _apply_pattern(base: AudioSegment, hit: AudioSegment,
                   pattern: list[int], sub_ms: float,
                   bars: int) -> AudioSegment:
    """Place oneshot hits according to a rhythmic pattern, repeated per bar."""
    steps_per_bar = len(pattern)
    for bar in range(bars):
        bar_offset = bar * steps_per_bar * sub_ms
        for step, active in enumerate(pattern):
            if active:
                pos = int(bar_offset + step * sub_ms)
                base = base.overlay(hit, position=pos)
    return base


def _loop_to_length(audio: AudioSegment, target_ms: int) -> AudioSegment:
    """Repeat (or trim) an audio loop to fill the target duration."""
    if len(audio) == 0:
        return AudioSegment.silent(duration=target_ms)
    if len(audio) >= target_ms:
        return audio[:target_ms]
    repeats = (target_ms // len(audio)) + 1
    return (audio * repeats)[:target_ms]


def _velocity_to_db(velocity: float) -> float:
    """Convert 0.0-1.0 velocity to dB gain adjustment."""
    if velocity <= 0:
        return -60
    # 1.0 = 0 dB, 0.5 = -6 dB, 0.25 = -12 dB (logarithmic)
    import math
    return 20 * math.log10(velocity)


def _trim_structure(structure: list[dict], max_bars: int) -> list[dict]:
    """Trim arrangement structure to a maximum number of bars."""
    result = []
    remaining = max_bars
    for sec in structure:
        if remaining <= 0:
            break
        bars = min(sec["bars"], remaining)
        result.append({"section": sec["section"], "bars": bars})
        remaining -= bars
    return result
```

- [ ] **Step 2: Smoke test — build a preview**

```bash
python3 -c "
from studio.beat_builder import build_track
result = build_track('hip-hop', {}, output_path='/tmp/test-beat.wav', preview_bars=8)
print(result)
import os; print(f'File size: {os.path.getsize(\"/tmp/test-beat.wav\") / 1024:.0f} KB')
"
```

Expected: WAV file created, result dict with duration ~21s (8 bars at 90 BPM).

- [ ] **Step 3: Smoke test — full build with override**

```bash
python3 -c "
from studio.beat_builder import build_track
result = build_track('lo-fi', {'kick': {'pack': 'electronic-kit', 'sample': 'kick.wav'}},
                     output_path='/tmp/test-lofi.wav')
print(result)
"
```

Expected: Full lo-fi track with electronic kick swapped in.

- [ ] **Step 4: Commit**

```bash
git add studio/beat_builder.py
git commit -m "feat: add beat builder template engine with pydub assembly"
```

---

### Task 6: Add API endpoints in server.py

**Files:**
- Modify: `server.py` — add route for `/studio/beats` and six API endpoints
- Modify: `static/js/nav.js` — add Beat Builder nav entry

- [ ] **Step 1: Add page route and API endpoints to server.py**

Add after the existing `/studio/audio` route (around line 123):

```python
@app.get("/studio/beats")
async def beats_page():
    return FileResponse("static/studio/beats.html")
```

Add a new API section after the music generation endpoints (after line ~1590):

```python
# --- Beat Builder API ---

@app.get("/api/beats/packs")
async def beats_list_packs():
    """List available sample packs."""
    from studio import sample_packs
    return sample_packs.list_packs()


@app.get("/api/beats/packs/{pack_id}/samples")
async def beats_list_samples(pack_id: str):
    """List samples in a pack."""
    from studio import sample_packs
    return sample_packs.list_samples(pack_id)


@app.get("/api/beats/templates")
async def beats_list_templates():
    """List available genre templates."""
    from studio import beat_builder
    return beat_builder.list_templates()


@app.post("/api/beats/preview")
async def beats_preview(request: Request):
    """Build an 8-bar preview mix."""
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
        return {
            "url": f"/storage/{job_id}.wav",
            **result,
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/beats/build")
async def beats_build(request: Request):
    """Build a full arranged track."""
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
            template_id, overrides, bpm=bpm,
            output_path=output_path,
        )

    try:
        result = await job_queue.submit(_do(), lane="cpu", job_id=f"beat-{job_id}")
        return {
            "job_id": job_id,
            "url": f"/storage/{job_id}.wav",
            **result,
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/beats/enhance")
async def beats_enhance(request: Request):
    """AI-enhance a built track via MusicGen chroma conditioning."""
    engine = _get_music_engine()
    if not engine:
        return JSONResponse(
            {"error": "MusicGen not available — needed for AI enhance"},
            status_code=503,
        )

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

        model = engine._get_model()
        sr = model.sample_rate

        # Load source track and extract chroma
        wav, orig_sr = torchaudio.load(str(source_path))
        if orig_sr != sr:
            wav = torchaudio.functional.resample(wav, orig_sr, sr)

        # Trim to requested duration
        max_samples = int(duration * sr)
        wav = wav[:, :max_samples]

        # Generate with chroma conditioning
        model.set_generation_params(duration=duration)
        with torch.no_grad():
            result = model.generate_with_chroma(
                descriptions=[prompt],
                melody_wavs=wav.unsqueeze(0),
                melody_sample_rate=sr,
            )

        # Save output
        audio = result[0].cpu()
        torchaudio.save(output_path, audio, sr)

        return {
            "duration": round(audio.shape[-1] / sr, 2),
            "file_size": os.path.getsize(output_path),
        }

    try:
        result = await job_queue.submit(_do(), lane="cpu", job_id=f"enhance-{job_id}")
        return {
            "job_id": job_id,
            "url": f"/storage/{job_id}.wav",
            **result,
        }
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/api/beats/upload-sample")
async def beats_upload_sample(
    file: UploadFile = File(...),
    slot: str = Form("kick"),
):
    """Upload a sample to the user pack."""
    from studio import sample_packs

    content = await file.read()
    filename = file.filename or f"{slot}.wav"
    result = sample_packs.save_user_sample(content, filename, slot)
    return result
```

- [ ] **Step 2: Add Beat Builder to nav**

In `static/js/nav.js`, add after the Music Studio entry (line 8):

```javascript
    { href: '/studio/beats', icon: '&#127928;', label: 'Beat Builder', id: 'beats' },
```

And add the path check after the music check (around line 29):

```javascript
  else if (path.startsWith('/studio/beats')) activeId = 'beats';
```

- [ ] **Step 3: Verify server starts**

```bash
python3 -c "import ast; ast.parse(open('server.py').read()); print('OK')"
```

- [ ] **Step 4: Commit**

```bash
git add server.py static/js/nav.js
git commit -m "feat: add beat builder API endpoints and nav entry"
```

---

### Task 7: Build the frontend — `/studio/beats`

**Files:**
- Create: `static/studio/beats.html`

- [ ] **Step 1: Create beats.html**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Wyltek Studio — Beat Builder</title>
  <link rel="stylesheet" href="/static/css/style.css">
  <link rel="stylesheet" href="/static/css/nav.css">
  <script src="/static/js/nav.js"></script>
  <script src="/static/js/project-picker.js"></script>
  <style>
    .studio-page { max-width: 900px; margin: 0 auto; padding: 32px 24px; }
    .studio-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
    .studio-header h2 { margin: 0; }

    /* Template cards */
    .template-cards {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 10px; margin-bottom: 24px;
    }
    .template-card {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 8px; padding: 14px; cursor: pointer;
      transition: border-color 0.15s; text-align: center;
    }
    .template-card:hover { border-color: var(--accent); }
    .template-card.selected { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
    .template-card h4 { margin: 0 0 4px 0; font-size: 14px; }
    .template-card .tpl-bpm { font-size: 12px; color: var(--text-dim); }

    /* Sample slots */
    .slots-section { margin-bottom: 20px; }
    .slots-section h3 { font-size: 14px; color: var(--text-dim); margin-bottom: 12px; }
    .slot-grid {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 10px;
    }
    .slot-card {
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 8px; padding: 12px;
    }
    .slot-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
    .slot-name { font-size: 13px; font-weight: 600; text-transform: capitalize; }
    .slot-source { font-size: 10px; color: var(--text-dim); }
    .slot-actions { display: flex; gap: 6px; }
    .slot-btn {
      padding: 4px 10px; font-size: 11px; border-radius: 4px; cursor: pointer;
      border: 1px solid var(--border); background: var(--surface-2); color: var(--text);
    }
    .slot-btn:hover { border-color: var(--accent); color: var(--accent); }
    .slot-btn.playing { border-color: var(--success); color: var(--success); }

    /* Controls */
    .controls {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
      gap: 12px; margin-bottom: 20px;
    }
    .controls label { display: block; font-size: 11px; color: var(--text-dim); text-transform: uppercase; margin-bottom: 4px; }
    .controls input, .controls select {
      width: 100%; padding: 8px; background: var(--surface); border: 1px solid var(--border);
      border-radius: 6px; color: var(--text); font-size: 13px;
    }

    /* Structure display */
    .structure-bar {
      display: flex; gap: 2px; margin-bottom: 20px; height: 28px; border-radius: 6px; overflow: hidden;
    }
    .structure-section {
      display: flex; align-items: center; justify-content: center;
      font-size: 9px; font-weight: 600; text-transform: uppercase; color: #fff;
    }
    .structure-section.intro { background: #6366f1; }
    .structure-section.verse { background: #8b5cf6; }
    .structure-section.chorus { background: #ec4899; }
    .structure-section.outro { background: #6366f1; opacity: 0.7; }

    /* Action buttons */
    .btn-row { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }
    .btn-action {
      padding: 10px 24px; font-size: 13px; font-weight: 600;
      border: none; border-radius: 8px; cursor: pointer;
    }
    .btn-preview { background: var(--surface-2); color: var(--accent); border: 1px solid var(--accent); }
    .btn-preview:hover { background: var(--accent-dim); }
    .btn-build { background: var(--accent); color: #fff; }
    .btn-build:hover { background: var(--accent-hover); }
    .btn-enhance { background: var(--surface-2); color: var(--success); border: 1px solid var(--success); }
    .btn-enhance:hover { background: rgba(52,211,153,0.1); }
    .btn-action:disabled { opacity: 0.5; cursor: not-allowed; }

    /* Enhance prompt */
    .enhance-area { display: none; margin-bottom: 16px; }
    .enhance-area.active { display: block; }
    .enhance-area textarea {
      width: 100%; padding: 10px; background: var(--surface); border: 1px solid var(--border);
      border-radius: 6px; color: var(--text); font-size: 13px; resize: vertical; min-height: 60px;
    }

    /* Result */
    .result-area { display: none; margin-top: 16px; }
    .result-area.active { display: block; }
    .result-area audio { width: 100%; margin: 8px 0; }
    .result-meta { font-size: 12px; color: var(--text-dim); display: flex; gap: 16px; flex-wrap: wrap; }
    .result-actions { display: flex; gap: 8px; margin-top: 8px; }

    /* Swap modal */
    .swap-overlay {
      display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.6);
      z-index: 1000; align-items: center; justify-content: center;
    }
    .swap-overlay.active { display: flex; }
    .swap-modal {
      background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
      width: 90vw; max-width: 500px; max-height: 70vh; display: flex; flex-direction: column;
    }
    .swap-header {
      padding: 14px 18px; border-bottom: 1px solid var(--border);
      display: flex; justify-content: space-between; align-items: center;
    }
    .swap-header h3 { margin: 0; font-size: 15px; }
    .swap-close { background: none; border: none; color: var(--text-dim); font-size: 18px; cursor: pointer; }
    .swap-body { padding: 12px 18px; overflow-y: auto; flex: 1; }
    .swap-pack-label { font-size: 11px; color: var(--text-dim); text-transform: uppercase; margin: 12px 0 6px; }
    .swap-pack-label:first-child { margin-top: 0; }
    .swap-item {
      display: flex; align-items: center; justify-content: space-between;
      padding: 8px 10px; border-radius: 6px; cursor: pointer; margin-bottom: 4px;
    }
    .swap-item:hover { background: var(--accent-dim); }
    .swap-item-name { font-size: 13px; }
    .swap-item-play {
      padding: 2px 8px; font-size: 10px; border-radius: 4px;
      background: var(--surface-2); border: 1px solid var(--border); color: var(--text); cursor: pointer;
    }
    .swap-upload { margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border); text-align: center; }
    .swap-upload label {
      display: inline-block; padding: 6px 14px; font-size: 12px; border-radius: 6px;
      background: var(--surface-2); border: 1px solid var(--border); color: var(--text); cursor: pointer;
    }
    .swap-upload label:hover { border-color: var(--accent); }

    .saved-msg {
      position: fixed; bottom: 24px; right: 24px;
      background: var(--surface); border: 1px solid var(--accent);
      border-radius: 8px; padding: 10px 20px; font-size: 13px;
      opacity: 0; transform: translateY(10px);
      transition: opacity 0.3s, transform 0.3s; pointer-events: none; z-index: 1000;
    }
    .saved-msg.show { opacity: 1; transform: translateY(0); }

    @media (max-width: 768px) {
      .studio-page { padding: 16px 12px; }
      .template-cards { grid-template-columns: repeat(2, 1fr); }
      .slot-grid { grid-template-columns: repeat(2, 1fr); }
    }
  </style>
</head>
<body>
  <div class="studio-page">
    <div class="studio-header">
      <h2>Beat Builder</h2>
    </div>

    <h3 style="font-size:14px;color:var(--text-dim);margin-bottom:12px">Genre Template</h3>
    <div class="template-cards" id="template-cards"></div>

    <div class="slots-section">
      <h3>Sample Slots</h3>
      <div class="slot-grid" id="slot-grid"></div>
    </div>

    <div class="structure-bar" id="structure-bar"></div>

    <div class="controls">
      <div>
        <label>BPM</label>
        <input type="number" id="bpm" min="60" max="200" value="90">
      </div>
    </div>

    <div class="btn-row">
      <button class="btn-action btn-preview" id="btn-preview" onclick="doPreview()">Preview (8 bars)</button>
      <button class="btn-action btn-build" id="btn-build" onclick="doBuild()">Build Full Track</button>
      <button class="btn-action btn-enhance" id="btn-enhance" onclick="toggleEnhance()">AI Enhance</button>
    </div>

    <div class="enhance-area" id="enhance-area">
      <textarea id="enhance-prompt" placeholder="Describe the style — e.g. 'chill lo-fi hip hop with vinyl warmth'"></textarea>
      <div style="margin-top:8px">
        <button class="btn-action btn-enhance" onclick="doEnhance()">Generate AI Version</button>
      </div>
    </div>

    <div class="result-area" id="result-area">
      <strong id="result-label">Result</strong>
      <audio id="result-audio" controls></audio>
      <div class="result-meta" id="result-meta"></div>
      <div class="result-actions">
        <button class="slot-btn" id="btn-send-beat" onclick="sendBeatToProject()">Send to Project</button>
      </div>
    </div>
  </div>

  <!-- Swap modal -->
  <div class="swap-overlay" id="swap-overlay">
    <div class="swap-modal">
      <div class="swap-header">
        <h3 id="swap-title">Swap Sample</h3>
        <button class="swap-close" onclick="closeSwap()">&times;</button>
      </div>
      <div class="swap-body" id="swap-body"></div>
    </div>
  </div>

  <div class="saved-msg" id="toast-msg"></div>

  <script>
    let templates = [];
    let packs = [];
    let selectedTemplate = null;
    let slotOverrides = {};
    let currentAudioUrl = null;
    let previewPlayer = null;

    function toast(msg) {
      const el = document.getElementById('toast-msg');
      el.textContent = msg;
      el.classList.add('show');
      setTimeout(() => el.classList.remove('show'), 3000);
    }

    // --- Init ---
    async function init() {
      templates = await (await fetch('/api/beats/templates')).json();
      packs = await (await fetch('/api/beats/packs')).json();
      renderTemplates();
      if (templates.length > 0) selectTemplate(templates[0].id);
    }

    // --- Templates ---
    function renderTemplates() {
      const container = document.getElementById('template-cards');
      container.textContent = '';
      templates.forEach(tpl => {
        const card = document.createElement('div');
        card.className = 'template-card' + (selectedTemplate === tpl.id ? ' selected' : '');
        const h4 = document.createElement('h4');
        h4.textContent = tpl.name;
        const bpm = document.createElement('div');
        bpm.className = 'tpl-bpm';
        bpm.textContent = tpl.bpm + ' BPM';
        card.appendChild(h4);
        card.appendChild(bpm);
        card.onclick = () => selectTemplate(tpl.id);
        container.appendChild(card);
      });
    }

    function selectTemplate(id) {
      selectedTemplate = id;
      slotOverrides = {};
      const tpl = templates.find(t => t.id === id);
      if (tpl) document.getElementById('bpm').value = tpl.bpm;
      renderTemplates();
      renderSlots();
      renderStructure();
    }

    // --- Slots ---
    function renderSlots() {
      const grid = document.getElementById('slot-grid');
      grid.textContent = '';
      const tpl = templates.find(t => t.id === selectedTemplate);
      if (!tpl) return;

      Object.keys(tpl.slots).forEach(slot => {
        const card = document.createElement('div');
        card.className = 'slot-card';

        const header = document.createElement('div');
        header.className = 'slot-header';
        const name = document.createElement('span');
        name.className = 'slot-name';
        name.textContent = slot;
        const source = document.createElement('span');
        source.className = 'slot-source';
        source.textContent = slotOverrides[slot] ? slotOverrides[slot].pack : tpl.default_pack;
        header.appendChild(name);
        header.appendChild(source);

        const actions = document.createElement('div');
        actions.className = 'slot-actions';

        const playBtn = document.createElement('button');
        playBtn.className = 'slot-btn';
        playBtn.textContent = 'Play';
        playBtn.onclick = () => auditionSlot(slot, tpl.default_pack);
        actions.appendChild(playBtn);

        const swapBtn = document.createElement('button');
        swapBtn.className = 'slot-btn';
        swapBtn.textContent = 'Swap';
        swapBtn.onclick = () => openSwap(slot);
        actions.appendChild(swapBtn);

        card.appendChild(header);
        card.appendChild(actions);
        grid.appendChild(card);
      });
    }

    function auditionSlot(slot, defaultPack) {
      const packId = slotOverrides[slot] ? slotOverrides[slot].pack : defaultPack;
      // Construct URL to sample file
      const url = '/data/sample-packs/' + packId + '/' + slot + '.wav?t=' + Date.now();
      if (previewPlayer) previewPlayer.pause();
      previewPlayer = new Audio(url);
      previewPlayer.play().catch(() => toast('Could not play sample'));
    }

    // --- Structure visualiser ---
    function renderStructure() {
      const bar = document.getElementById('structure-bar');
      bar.textContent = '';
      const tpl = templates.find(t => t.id === selectedTemplate);
      if (!tpl) return;
      const totalBars = tpl.structure.reduce((sum, s) => sum + s.bars, 0);
      tpl.structure.forEach(sec => {
        const el = document.createElement('div');
        el.className = 'structure-section ' + sec.section;
        el.style.flex = sec.bars;
        el.textContent = sec.section + ' (' + sec.bars + ')';
        bar.appendChild(el);
      });
    }

    // --- Swap modal ---
    function openSwap(slot) {
      document.getElementById('swap-title').textContent = 'Swap: ' + slot;
      document.getElementById('swap-overlay').classList.add('active');
      const body = document.getElementById('swap-body');
      body.textContent = '';

      packs.forEach(pack => {
        if (pack.id === 'user' && Object.keys(pack.samples || {}).length === 0) return;
        const label = document.createElement('div');
        label.className = 'swap-pack-label';
        label.textContent = pack.name;
        body.appendChild(label);

        const samples = pack.samples || {};
        if (samples[slot]) {
          const item = document.createElement('div');
          item.className = 'swap-item';
          const nameEl = document.createElement('span');
          nameEl.className = 'swap-item-name';
          nameEl.textContent = samples[slot].file;
          item.appendChild(nameEl);

          const playEl = document.createElement('button');
          playEl.className = 'swap-item-play';
          playEl.textContent = 'Play';
          playEl.onclick = (e) => {
            e.stopPropagation();
            if (previewPlayer) previewPlayer.pause();
            previewPlayer = new Audio('/data/sample-packs/' + pack.id + '/' + samples[slot].file);
            previewPlayer.play().catch(() => {});
          };
          item.appendChild(playEl);

          item.onclick = () => {
            slotOverrides[slot] = { pack: pack.id, sample: samples[slot].file };
            closeSwap();
            renderSlots();
            toast('Swapped ' + slot + ' → ' + pack.name);
          };
          body.appendChild(item);
        }
      });

      // Upload option
      const upload = document.createElement('div');
      upload.className = 'swap-upload';
      const lbl = document.createElement('label');
      lbl.textContent = 'Upload your own';
      const inp = document.createElement('input');
      inp.type = 'file';
      inp.accept = 'audio/*';
      inp.style.display = 'none';
      inp.onchange = (e) => uploadSample(e.target.files[0], slot);
      lbl.appendChild(inp);
      upload.appendChild(lbl);
      body.appendChild(upload);
    }

    function closeSwap() {
      document.getElementById('swap-overlay').classList.remove('active');
    }

    document.getElementById('swap-overlay').addEventListener('click', function(e) {
      if (e.target === e.currentTarget) closeSwap();
    });

    async function uploadSample(file, slot) {
      if (!file) return;
      const form = new FormData();
      form.append('file', file);
      form.append('slot', slot);
      try {
        const resp = await fetch('/api/beats/upload-sample', { method: 'POST', body: form });
        const data = await resp.json();
        if (data.error) throw new Error(data.error);
        slotOverrides[slot] = { pack: 'user', sample: data.file };
        // Refresh packs to get updated user pack
        packs = await (await fetch('/api/beats/packs')).json();
        closeSwap();
        renderSlots();
        toast('Uploaded ' + file.name + ' as ' + slot);
      } catch (e) {
        toast('Upload failed: ' + e.message);
      }
    }

    // --- Build / Preview ---
    async function doPreview() {
      await buildRequest('/api/beats/preview', 'Preview');
    }

    async function doBuild() {
      await buildRequest('/api/beats/build', 'Full Track');
    }

    async function buildRequest(endpoint, label) {
      const btn = endpoint.includes('preview') ?
        document.getElementById('btn-preview') : document.getElementById('btn-build');
      btn.disabled = true;
      btn.textContent = 'Building...';

      try {
        const resp = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            template: selectedTemplate,
            overrides: slotOverrides,
            bpm: parseInt(document.getElementById('bpm').value),
          }),
        });
        const data = await resp.json();
        if (data.error) throw new Error(data.error);

        currentAudioUrl = data.url;
        const area = document.getElementById('result-area');
        area.classList.add('active');
        document.getElementById('result-label').textContent = label;
        const audio = document.getElementById('result-audio');
        audio.src = data.url + '?t=' + Date.now();
        audio.dataset.filename = data.url.split('/').pop();

        const meta = document.getElementById('result-meta');
        meta.textContent = '';
        const items = [
          'Duration: ' + data.duration + 's',
          'BPM: ' + data.bpm,
          'Size: ' + (data.file_size / 1024).toFixed(0) + ' KB',
          'Template: ' + data.template,
        ];
        items.forEach(text => {
          const span = document.createElement('span');
          span.textContent = text;
          meta.appendChild(span);
        });

        toast(label + ' complete!');
      } catch (e) {
        toast('Build failed: ' + e.message);
      } finally {
        btn.disabled = false;
        btn.textContent = endpoint.includes('preview') ? 'Preview (8 bars)' : 'Build Full Track';
      }
    }

    // --- AI Enhance ---
    function toggleEnhance() {
      document.getElementById('enhance-area').classList.toggle('active');
    }

    async function doEnhance() {
      if (!currentAudioUrl) { toast('Build a track first'); return; }
      const prompt = document.getElementById('enhance-prompt').value.trim();
      if (!prompt) { toast('Enter a style description'); return; }

      const btn = document.querySelectorAll('.btn-enhance')[1];
      btn.disabled = true;
      btn.textContent = 'Enhancing...';

      try {
        const resp = await fetch('/api/beats/enhance', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            track_url: currentAudioUrl,
            prompt: prompt,
            duration: 30,
          }),
        });
        const data = await resp.json();
        if (data.error) throw new Error(data.error);

        currentAudioUrl = data.url;
        const area = document.getElementById('result-area');
        area.classList.add('active');
        document.getElementById('result-label').textContent = 'AI Enhanced';
        const audio = document.getElementById('result-audio');
        audio.src = data.url + '?t=' + Date.now();
        audio.dataset.filename = data.url.split('/').pop();

        const meta = document.getElementById('result-meta');
        meta.textContent = '';
        const items = [
          'Duration: ' + data.duration + 's',
          'Size: ' + (data.file_size / 1024).toFixed(0) + ' KB',
        ];
        items.forEach(text => {
          const span = document.createElement('span');
          span.textContent = text;
          meta.appendChild(span);
        });

        toast('AI enhancement complete!');
      } catch (e) {
        toast('Enhance failed: ' + e.message);
      } finally {
        btn.disabled = false;
        btn.textContent = 'Generate AI Version';
      }
    }

    // --- Send to Project ---
    function sendBeatToProject() {
      const audio = document.getElementById('result-audio');
      const filename = audio.dataset.filename;
      if (!filename) { toast('Build a track first'); return; }
      ProjectPicker.init(toast);
      ProjectPicker.show(filename);
    }

    init();
  </script>
</body>
</html>
```

- [ ] **Step 2: Add static file route for sample pack audio**

The audition feature needs to serve WAV files from `data/sample-packs/`. Add to `server.py` after the existing static mounts:

```python
from starlette.staticfiles import StaticFiles

# Add near other static mounts:
app.mount("/data/sample-packs", StaticFiles(directory="data/sample-packs"), name="sample-packs")
```

Check if a StaticFiles mount already exists and add alongside it.

- [ ] **Step 3: Verify the page loads**

Start the server and navigate to `http://localhost:7860/studio/beats`.
Expected: Template cards, sample slot grid, BPM control, action buttons.

- [ ] **Step 4: Commit**

```bash
git add static/studio/beats.html server.py
git commit -m "feat: add beat builder frontend page with template selection, slot swapping, and build/preview/enhance"
```

---

### Task 8: Integration test — end-to-end build and enhance

**Files:** None (manual testing)

- [ ] **Step 1: Start server**

```bash
cd /home/phill/open-palette && python3 server.py
```

- [ ] **Step 2: Test template selection**

Open `http://localhost:7860/studio/beats`. Click each template card. Verify slots update and BPM changes.

- [ ] **Step 3: Test preview**

Click "Preview (8 bars)". Verify audio player appears with ~21s clip (8 bars at 90 BPM).

- [ ] **Step 4: Test full build**

Click "Build Full Track". Verify full arranged track plays with sections.

- [ ] **Step 5: Test slot swap**

Click "Swap" on any slot. Pick a sample from a different pack. Build again. Verify the swapped sample is audible.

- [ ] **Step 6: Test AI Enhance**

Click "AI Enhance", enter a prompt, click "Generate AI Version". Verify MusicGen produces a chroma-conditioned track.

- [ ] **Step 7: Test Send to Project**

Click "Send to Project". Select a project. Verify the track appears in the project's asset pool.

- [ ] **Step 8: Test upload**

Click "Swap" on a slot, click "Upload your own", upload a WAV file. Verify it appears in the user pack and can be used.

---

Plan complete and saved to `docs/superpowers/plans/2026-04-13-sample-builder.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session, batch execution with checkpoints

Which approach?