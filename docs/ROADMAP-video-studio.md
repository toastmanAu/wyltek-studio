# Open Palette Video Studio — Roadmap

## Vision

Extend Open Palette from an image generation tool into a full local-first creative studio. Generate images, compose them into videos with transitions, text overlays, AI narration, and music — all from one interface, all running locally.

## Architecture

```
Open Palette (existing)
  └─ /studio (new page)
       ├─ Timeline editor (drag images, audio, text onto tracks)
       ├─ TTS engine selector (Piper, Kokoro, XTTS, Bark, F5-TTS)
       ├─ Transition library (fade, slide, zoom, dissolve, etc.)
       ├─ Text overlay editor (titles, captions, lower-thirds)
       ├─ Audio mixer (narration + music + SFX tracks)
       └─ Export pipeline (ffmpeg → MP4/WebM)
```

### Core dependency: FFmpeg
All video composition runs through FFmpeg. No GPU needed for basic composition — CPU handles image sequencing, transitions, audio mixing, and encoding at reasonable speed. FFmpeg is the only hard requirement.

### TTS engines (all CPU-capable, install as needed)

| Engine | Size | Speed (CPU) | Strengths | Install |
|---|---|---|---|---|
| **Piper** | ~60MB/voice | 30x realtime | Fast, many voices, lightweight | Binary + ONNX voice model |
| **Kokoro** | ~300MB | 10x realtime | Great quality for size, new | pip install kokoro |
| **Coqui XTTS v2** | ~1.8GB | 1x realtime | Voice cloning, multi-language | pip install TTS |
| **Bark** (Suno) | ~5GB | 0.3x realtime | Most expressive, emotions, music | pip install suno-bark |
| **F5-TTS** | ~1.2GB | 2x realtime (GPU) | High quality, voice cloning | pip install f5-tts |

Strategy: Install Piper first (instant, lightweight), add others as optional backends. Same pattern as image generation backends — registry, configurable, user picks what they have installed.

---

## Phases

### Phase 1: TTS Playground (standalone, quick win)
**Goal:** Get all TTS engines running, compare voices side-by-side.

**New page:** `/studio/tts` — text input, engine/voice selector, generate button, audio player.

- [ ] Install Piper binary + 2-3 voice models (en_US, en_GB)
- [ ] Install Kokoro via pip
- [ ] Create `tts/` backend module with registry pattern (like image backends)
- [ ] `POST /api/tts/generate` — text, engine, voice → WAV file
- [ ] `GET /api/tts/engines` — list installed engines + available voices
- [ ] Frontend: text input, engine picker, voice picker, generate + play
- [ ] Compare mode: same text across multiple voices/engines
- [ ] Save generated audio to `outputs/audio/`

**Dependencies:** None beyond what's installed. Piper is a standalone binary.

### Phase 2: Image-to-Video Compositor
**Goal:** Arrange Open Palette images on a timeline, add transitions, export video.

**New page:** `/studio/video`

- [ ] Install FFmpeg (likely already installed, check)
- [ ] Timeline UI: horizontal track, drag images from gallery
- [ ] Per-image controls: duration (2-10s), transition type, ken burns (pan/zoom)
- [ ] Transition library: fade, dissolve, slide-left/right/up/down, zoom, wipe
- [ ] Preview: show current frame at playhead position (server-rendered frame)
- [ ] Export: `POST /api/video/render` → FFmpeg pipeline → MP4
- [ ] Progress tracking via WebSocket (same pattern as image generation)
- [ ] Output to `outputs/video/`

**Backend:** Python subprocess calling FFmpeg with filter_complex for transitions. Each transition is a parameterized FFmpeg filter template.

**Key FFmpeg filters:**
- `xfade` — crossfade, dissolve, wipe, slide transitions between images
- `zoompan` — ken burns effect (slow pan/zoom on still images)
- `overlay` — text overlays, watermarks
- `concat` — join segments
- `amix` — mix audio tracks

### Phase 3: Text Overlays & Captions
**Goal:** Add titles, captions, and lower-thirds to the video timeline.

- [ ] Text track on timeline (alongside image track)
- [ ] Text editor: font, size, color, position, animation (fade in/out, typewriter)
- [ ] Pre-built templates: title card, lower-third, caption bar, chapter heading
- [ ] SRT/VTT subtitle import for caption sync
- [ ] Auto-caption from TTS (generate speech → extract timing → overlay text)
- [ ] Render via FFmpeg `drawtext` filter

### Phase 4: Audio Integration
**Goal:** Layer narration, music, and sound effects.

- [ ] Audio tracks on timeline (narration, music, SFX — up to 3 tracks)
- [ ] Import external audio files (MP3, WAV, OGG)
- [ ] TTS integration: generate narration directly into timeline from text
- [ ] Volume envelope: per-track volume, duck music under narration
- [ ] Fade in/out per audio clip
- [ ] Royalty-free music library (link to freepd.com, pixabay audio, etc.)
- [ ] Export audio mix via FFmpeg `amix` / `amerge`

### Phase 5: External Media & Polish
**Goal:** Import external images/video, final polish features.

- [ ] Import external images (drag from desktop, URL paste)
- [ ] Import short video clips (as timeline elements)
- [ ] Aspect ratio presets: 16:9 (YouTube), 9:16 (Shorts/TikTok), 1:1 (Instagram)
- [ ] Resolution presets: 720p, 1080p, 4K
- [ ] Project save/load (JSON project file)
- [ ] Thumbnail generator (pick frame, add text overlay)
- [ ] YouTube metadata export (title, description, tags)

### Phase 6: Animation (Future — GPU required)
**Goal:** Animate between images, generate video sequences.

- [ ] AnimateDiff / SVD (Stable Video Diffusion) integration via ComfyUI
- [ ] Image-to-video: animate a single Open Palette image (2-4s clips)
- [ ] Interpolation: generate transition frames between two images
- [ ] Deforum-style camera movements
- [ ] Requires GPU upgrade (16GB+ VRAM recommended)

---

## Video Composition Engine Decision

**Chosen: `ffmpeg-python`** (Python FFmpeg filter graph builder)

Evaluated 2026-03-30. Alternatives considered:
- MoviePy: active (v2.2.1) but 20x slower, no built-in transitions/Ken Burns
- editly: feature-complete but unmaintained (3 years, Node.js)
- FFCreator: Node.js, Chinese docs, decent but adds runtime dependency
- Remotion: React-based, massive overkill for image→video composition
- vidpy: alpha status, requires MLT framework

**Why ffmpeg-python:**
- Python-native (fits FastAPI stack, no Node.js needed)
- Full FFmpeg filter graph access: xfade (30+ transitions), zoompan (Ken Burns), drawtext, amix
- Thin wrapper = fast (no Python-layer overhead for rendering)
- Active maintenance
- FFmpeg 4.4.2 already installed with xfade + zoompan support confirmed

**Integration:** `pip install ffmpeg-python`, build filter graphs in Python, execute via subprocess. Timeline JSON spec → ffmpeg-python filter graph → MP4/WebM output.

**Fallback for text:** If FFmpeg's drawtext filter is insufficient for complex text layouts, add MoviePy's TextClip as a secondary dependency. Start with drawtext only.

## Technical Notes

### Timeline data model
```json
{
  "project": "my-video",
  "resolution": [1920, 1080],
  "fps": 30,
  "tracks": {
    "images": [
      {"src": "/outputs/abc123.png", "start": 0, "duration": 4, "transition": "fade", "kenburns": "zoom-in"},
      {"src": "/outputs/def456.png", "start": 3.5, "duration": 5, "transition": "slide-left"}
    ],
    "text": [
      {"text": "Chapter 1", "start": 0, "duration": 3, "style": "title-card", "animation": "fade-in"}
    ],
    "narration": [
      {"src": "/outputs/audio/nar1.wav", "start": 0.5, "duration": null}
    ],
    "music": [
      {"src": "/uploads/bgm.mp3", "start": 0, "volume": 0.3, "duck_under": "narration"}
    ]
  }
}
```

### FFmpeg transition example
```bash
# Crossfade between two images (4s each, 1s transition)
ffmpeg -loop 1 -t 4 -i img1.png -loop 1 -t 4 -i img2.png \
  -filter_complex "[0:v][1:v]xfade=transition=fade:duration=1:offset=3,format=yuv420p" \
  -c:v libx264 -pix_fmt yuv420p output.mp4
```

### File structure
```
open-palette/
  studio/
    __init__.py
    tts_registry.py       # TTS backend registry (same pattern as image backends)
    tts_piper.py           # Piper backend
    tts_kokoro.py          # Kokoro backend
    tts_xtts.py            # XTTS backend
    tts_bark.py            # Bark backend
    video_composer.py      # FFmpeg wrapper for timeline → video
    video_transitions.py   # Transition filter templates
  static/
    studio/
      tts.html             # TTS playground page
      video.html           # Video editor page
      js/
        timeline.js        # Timeline UI component
        tts.js             # TTS page logic
        video.js           # Video editor logic
      css/
        studio.css         # Studio-specific styles
```

### Resource estimates
| Component | Disk | RAM (runtime) | GPU |
|---|---|---|---|
| Piper (3 voices) | ~200MB | ~100MB | None |
| Kokoro | ~300MB | ~500MB | None |
| XTTS v2 | ~1.8GB | ~2GB | Optional |
| Bark | ~5GB | ~4GB | Recommended |
| F5-TTS | ~1.2GB | ~1.5GB | Recommended |
| FFmpeg | ~100MB | ~200MB per render | None |
| **Total (all engines)** | **~8.5GB** | **Peak ~4GB** | **Optional** |

---

## Priority order
1. **Phase 1** (TTS) — quick win, immediately useful for YouTube content
2. **Phase 2** (compositor) — the core video builder
3. **Phase 4** (audio) — layer TTS into videos
4. **Phase 3** (text) — titles and captions
5. **Phase 5** (external media) — polish and flexibility
6. **Phase 6** (animation) — future, hardware-dependent
