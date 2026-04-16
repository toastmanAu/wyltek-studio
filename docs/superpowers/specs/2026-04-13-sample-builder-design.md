# Sample Builder — Design Spec

**Date:** 2026-04-13
**Status:** Approved
**Page:** `/studio/beats`

## Purpose

A sample-based beat/track builder that complements the existing MusicGen text-to-music studio. Users pick a genre template, swap samples in and out from royalty-free starter packs or their own uploads, and build full arranged tracks. An optional AI enhance mode runs the assembled mix through MusicGen's `generate_with_chroma` for a more organic result.

## Core Flow

1. Pick a genre template (hip hop, lo-fi, trap, house, etc.)
2. Review pre-filled sample slots — each slot loaded from the template's default pack
3. Swap any slot: pick from other packs or upload a custom sample
4. Adjust BPM, track duration, arrangement structure
5. Preview (quick 8-bar mix) or Build (full track)
6. Optionally AI Enhance — MusicGen chroma-conditions on the assembled mix with a text prompt
7. Output: WAV file, playback, Send to Project button

## Design Principles

- **Always produces a track** — empty slots auto-fill from the default pack, so the user always gets a cohesive result even with minimal input.
- **Template-driven** — genre templates define everything: BPM, structure, patterns, mix levels. Adding a new genre is adding a JSON file.
- **Two modes** — deterministic template assembly (fast, predictable) and AI-enhanced (slower, more organic). Both available on every build.

## Sample Packs

### Structure

```
data/sample-packs/
  hip-hop-kit/
    pack.json          # metadata: name, description, bpm range, genre tags
    kick.wav
    snare.wav
    hihat.wav
    openhat.wav
    bass.wav
    melody.wav
    pad.wav
    fx.wav
  lo-fi-kit/
    ...
  electronic-kit/
    ...
  user/               # user-uploaded samples
    ...
```

### Starter Packs

Ship 2-3 royalty-free packs sourced from freesound.org CC0 or equivalent:

| Pack | BPM Range | Style |
|------|-----------|-------|
| hip-hop-kit | 80-100 | Boom bap, trap-lite |
| lo-fi-kit | 70-90 | Chill, jazzy, vinyl |
| electronic-kit | 120-140 | House, techno, synth |

Each pack contains 8 normalised WAV samples: kick, snare, hihat, openhat, bass, melody, pad, fx.

### pack.json Format

```json
{
  "name": "Hip Hop Kit",
  "description": "Boom bap drums, deep bass, soulful melody",
  "bpm_range": [80, 100],
  "genre_tags": ["hip-hop", "boom-bap", "rap"],
  "samples": {
    "kick": { "file": "kick.wav", "type": "oneshot" },
    "snare": { "file": "snare.wav", "type": "oneshot" },
    "hihat": { "file": "hihat.wav", "type": "oneshot" },
    "openhat": { "file": "openhat.wav", "type": "oneshot" },
    "bass": { "file": "bass.wav", "type": "loop" },
    "melody": { "file": "melody.wav", "type": "loop" },
    "pad": { "file": "pad.wav", "type": "loop" },
    "fx": { "file": "fx.wav", "type": "oneshot" }
  }
}
```

## Genre Templates

### Structure

```
data/templates/
  hip-hop.json
  lo-fi.json
  trap.json
  house.json
```

### Template Format

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
    "kick": {
      "pattern": [1, 0, 0, 0, 1, 0, 0, 0],
      "velocity": 1.0,
      "sections": ["all"]
    },
    "snare": {
      "pattern": [0, 0, 1, 0, 0, 0, 1, 0],
      "velocity": 0.9,
      "sections": ["all"]
    },
    "hihat": {
      "pattern": [1, 1, 1, 1, 1, 1, 1, 1],
      "velocity": 0.6,
      "sections": ["all"]
    },
    "openhat": {
      "pattern": [0, 0, 0, 0, 0, 0, 0, 1],
      "velocity": 0.5,
      "sections": ["chorus"]
    },
    "bass": {
      "type": "loop",
      "velocity": 0.8,
      "sections": ["verse", "chorus"]
    },
    "melody": {
      "type": "loop",
      "velocity": 0.5,
      "sections": ["verse", "chorus"]
    },
    "pad": {
      "type": "loop",
      "velocity": 0.3,
      "sections": ["chorus", "outro"]
    },
    "fx": {
      "type": "oneshot",
      "trigger": "section_start",
      "velocity": 0.4,
      "sections": ["chorus"]
    }
  },
  "mix": {
    "master_volume": 0.85,
    "fade_in_bars": 2,
    "fade_out_bars": 2
  }
}
```

### Pattern field

For oneshot samples (kick, snare, hihat): an array of 0s and 1s representing hits per beat subdivision within a bar. `[1,0,0,0, 1,0,0,0]` = hit on beats 1 and 3 of a 4/4 bar with 8th-note resolution.

### Loop samples

Bass, melody, pad: played as continuous loops during their assigned sections. Tempo-stretched to match the template BPM if the sample's native BPM differs.

### Sections field

Which arrangement sections the slot plays in. `["all"]` means every section. Specific section names (intro, verse, chorus, outro) for selective layering — this is how templates create dynamic builds and drops.

## Backend

### New modules

| Module | Purpose |
|--------|---------|
| `studio/beat_builder.py` | Template engine — assembles samples into a mixed track using pydub |
| `studio/sample_packs.py` | Pack registry — lists packs, resolves sample paths, validates uploads |

### beat_builder.py

Core function: `build_track(template, slot_overrides, bpm, duration, output_path) -> dict`

Pipeline:
1. Load template JSON
2. Resolve each slot's sample: user override > template default pack
3. For each section in the arrangement structure:
   - Pattern slots: generate audio by placing oneshot samples at beat positions
   - Loop slots: time-stretch loop to match BPM, trim/repeat to section length
   - Only include slots assigned to this section
4. Layer all slot audio for each section
5. Concatenate sections in order
6. Apply master volume, fade in/out
7. Export as WAV

Uses `pydub` for all audio manipulation: overlay (layering), concatenation, volume adjustment, fade effects. pydub delegates encoding to FFmpeg.

### sample_packs.py

- `list_packs() -> list[dict]` — all available packs with metadata
- `list_samples(pack_id) -> list[dict]` — samples in a pack with type info
- `resolve_sample(pack_id, slot_name) -> Path` — full path to sample file
- `save_user_sample(file, slot_name) -> dict` — save uploaded sample to user pack

### AI Enhance

`enhance_track(assembled_wav_path, prompt, duration, output_path) -> dict`

1. Load the assembled track as audio tensor
2. Extract chroma features via `generate_with_chroma`
3. MusicGen generates a new track conditioned on the chroma + text prompt
4. Output alongside the raw mix — user picks which they prefer

### API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/beats/packs` | List packs with sample inventories |
| GET | `/api/beats/templates` | List genre templates |
| POST | `/api/beats/preview` | Quick 8-bar preview mix |
| POST | `/api/beats/build` | Full track assembly |
| POST | `/api/beats/enhance` | AI polish via MusicGen chroma |
| POST | `/api/beats/upload-sample` | Upload sample to user pack |

### Build request body

```json
{
  "template": "hip-hop",
  "bpm": 92,
  "duration": 120,
  "overrides": {
    "kick": { "pack": "user", "sample": "my-kick.wav" },
    "melody": { "pack": "lo-fi-kit", "sample": "melody.wav" }
  }
}
```

Slots not in `overrides` auto-fill from the template's `default_pack`.

### Enhance request body

```json
{
  "track_path": "/storage/abc123.wav",
  "prompt": "chill lo-fi hip hop with vinyl crackle",
  "duration": 30
}
```

## Frontend — `/studio/beats`

### Layout

```
+---------------------------------------------+
| Beat Builder                                 |
+---------------------------------------------+
| [Hip Hop] [Lo-Fi] [Trap] [House]   template  |
|                                    cards     |
+---------------------------------------------+
| Sample Slots                                 |
| +--------+ +--------+ +--------+ +--------+ |
| | Kick   | | Snare  | | HiHat  | | O.Hat  | |
| | [play] | | [play] | | [play] | | [play] | |
| | [swap] | | [swap] | | [swap] | | [swap] | |
| +--------+ +--------+ +--------+ +--------+ |
| +--------+ +--------+ +--------+ +--------+ |
| | Bass   | | Melody | | Pad    | | FX     | |
| | [play] | | [play] | | [play] | | [play] | |
| | [swap] | | [swap] | | [swap] | | [swap] | |
| +--------+ +--------+ +--------+ +--------+ |
+---------------------------------------------+
| BPM: [===92===]  Duration: [2:00]            |
| Structure: intro(4) verse(16) chorus(8) ...  |
+---------------------------------------------+
| [Preview]  [Build Track]  [AI Enhance]       |
+---------------------------------------------+
| Result:                                      |
| [audio player]  [Send to Project]            |
+---------------------------------------------+
```

### Interactions

- **Template cards**: click to select genre, populates all slots from default pack
- **Sample slots**: click play to audition, click swap to open a picker (choose from any pack or upload)
- **BPM slider**: adjustable, template provides default
- **Structure**: read-only display of arrangement sections (editable in future)
- **Preview**: quick server render of 8 bars, instant feedback
- **Build Track**: full render via job queue, progress bar
- **AI Enhance**: takes built track + optional text prompt, runs MusicGen chroma conditioning
- **Result**: audio player with download and Send to Project

### Swap picker

Modal with tabs: one tab per pack + "Upload" tab. Shows all samples in the selected pack with play buttons. Click to select, closes modal and updates the slot.

## Dependencies

| Dependency | Status | Purpose |
|------------|--------|---------|
| pydub | needs install | Sample manipulation, layering, mixing |
| FFmpeg | installed | Audio encoding (used by pydub) |
| audiocraft / MusicGen | installed | AI enhance via `generate_with_chroma` |

Install: `pip install pydub`

## File Structure

```
open-palette/
  studio/
    beat_builder.py        # template engine, track assembly
    sample_packs.py        # pack registry
  data/
    sample-packs/
      hip-hop-kit/
        pack.json
        kick.wav, snare.wav, ...
      lo-fi-kit/
        ...
      electronic-kit/
        ...
      user/
    templates/
      hip-hop.json
      lo-fi.json
      trap.json
      house.json
  static/
    studio/
      beats.html           # beat builder page
```

## Out of Scope (for now)

- Per-slot pattern editing (custom drum patterns) — use template defaults
- Effects chain (reverb, delay, compression) — pydub can do basic EQ/filters later
- MIDI import/export
- Multi-track timeline (that's the project workspace)
- Real-time browser-side playback/sequencing — all rendering is server-side
