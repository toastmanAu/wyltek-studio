---
title: Infographic Builder — Wyltek Studio
date: 2026-05-05
status: draft (brainstorm output)
engine: SenseNova-U1-8B-MoT (interleave mode)
route: /studio/infographic
related:
  - wyltek-infographic-log.md
  - ~/.claude/projects/-home-phill-open-palette/memory/project_sensenova_u1_rocm.md
---

# Infographic Builder

A template-driven page in Wyltek Studio for producing publication-quality
infographics from structured prompts plus optional reference images, powered
by SenseNova-U1-8B-MoT in `interleave` mode. Includes an inline post-edit
canvas (V1-canvas scope) for repairing the ~5% of generation that AI gets
wrong without leaving the page.

## Motivation

SenseNova-U1 produces text-in-image quality that beats every other
locally-runnable model we have tested (see `wyltek-infographic-log.md`
runs 001–003). Its weakness is the same as every diffusion model: small
glyph fidelity, brand-precise colors, and exact iconography degrade.
Hand-built TFT/UI artwork has long taught Phill that **95% correct +
inline repair** beats either pure regeneration or starting from scratch
in another tool.

The page exists because:

1. Free-form prompting an infographic is a prompt-engineering
   discipline most users will never master. Templates make the
   common shapes one-click.
2. Numbered image references (`Image 1`, `Image 2` …) remove the
   "the photo I uploaded" ambiguity and map directly onto SenseNova's
   positional `<image>` placeholder protocol.
3. Inline post-edit closes the loop without an export-to-GIMP detour
   for repairs the user can do faster in-browser.

## Goals (v1)

- Eight built-in templates: hub-and-spoke, comparison, timeline,
  stat-showcase, quadrant, list, geographic-map, hierarchical.
- Optional image references (0..N) per render, labeled by number.
- Two render tiers: **Draft** (8-step ~73s) and **Final** (50-step
  ~5min) selected per render.
- Custom templates via dropping JSON into `templates/infographics/`.
- Inline post-edit canvas: PNG drag-drop overlay, corner-drag resize,
  paste-image-from-clipboard, save composite as a new render.
- Self-hostable: documented venv install with platform detection
  (ROCm / CUDA / MPS), no service dependencies on Phill's machine.

## Non-goals (v1)

- Region-select → system-clipboard → GIMP round-trip (deferred to v1.5;
  covered by the manual full-image export the user can already do).
- In-app template authoring UI (file-based authoring is the v1
  power-user path).
- A3B-MoT smaller-variant support (evaluation deferred; ship 8B-MoT
  first as the proven path).
- True interleaved-output mode (text+images output). v1 returns one PNG.
- Auth, rate limiting, multi-user queues (out of scope: this is a
  self-host-first feature; one user, one GPU, FIFO is the existing
  job_queue contract).

## Architecture

Five subsystems, kept independent so each can be tested and replaced
without touching the others.

### 1. Template engine

**Location:** `templates/infographics/{name}.json` + `studio/infographics.py`

Each template is a JSON file declaring slots and an assembly template:

```json
{
  "id": "hub_and_spoke",
  "name": "Hub & Spoke",
  "description": "Central concept with N radiating spokes. Best for feature overviews.",
  "preview": "templates/infographics/_previews/hub_and_spoke.png",
  "slots": [
    {"id": "title",     "type": "text",  "label": "Title",        "max_len": 60,  "required": true},
    {"id": "hub_desc",  "type": "text",  "label": "Hub concept",  "max_len": 140, "required": true},
    {"id": "hub_image", "type": "image_ref", "label": "Hub image (optional)", "required": false},
    {"id": "spokes",    "type": "list",  "label": "Spokes",       "min": 4, "max": 8,
     "item_slots": [
        {"id": "label",   "type": "text",      "max_len": 24, "required": true},
        {"id": "tagline", "type": "text",      "max_len": 60, "required": false},
        {"id": "color",   "type": "color",     "required": false},
        {"id": "image",   "type": "image_ref", "required": false}
     ]}
  ],
  "prompt_template": "...mustache-style template, see below..."
}
```

Slot types: `text`, `image_ref`, `color`, `list` (composite),
`enum` (closed-set choices, e.g., aspect ratio buckets).

`prompt_template` uses Mustache-style `{{slot}}` and `{{#list}}…{{/list}}`.
Image references render as `[Image N]` tokens at template-assembly time;
the backend rewrites these to SenseNova `<image>` placeholders and
collects the corresponding paths in order.

**Custom templates:** drop a JSON conforming to `studio/infographics_schema.json`
into `templates/infographics/`. Hot-reload on page refresh — no server restart.

### 2. Builder UI

**Location:** `static/studio/infographic.html` + `static/studio/js/infographic.js`

Three-pane desktop layout (collapses to single column on mobile):

```
┌──────────────────┬──────────────────────────┬──────────────────┐
│ TEMPLATE PANE    │   PREVIEW + CANVAS PANE  │   HISTORY PANE   │
│                  │                          │                  │
│ Template ▼       │   [generated PNG]        │   [thumb] 003    │
│                  │                          │   [thumb] 002    │
│ Slot fields      │                          │   [thumb] 001    │
│ ...              │                          │                  │
│                  │   ─── Post-edit ───      │                  │
│ Image refs:      │   [tools]                │                  │
│ + Add image      │                          │                  │
│ ▣ Image 1: …     │   [Render Draft]         │                  │
│ ▣ Image 2: …     │   [Render Final]         │                  │
└──────────────────┴──────────────────────────┴──────────────────┘
```

Slot fields render based on the active template's slot list. Image-ref
slots get a thumbnail tile labeled "Image N" with a remove button.
Free-text slots that contain an image-ref slot get a chip-insert button
("Insert Image 2") to avoid typos.

**No-template mode** is just a synthetic template with one big text slot
plus the image-ref system; same code path.

### 3. SenseNova backend

**Location:** `backends/sensenova.py` (~150 lines, mirrors `worldgen.py` shape)

Subprocess pattern (same as iopaint/worldgen — venv-isolated):

```
backend.generate(prompt, image_paths, draft=False, aspect=None)
  └── writes /tmp/sensenova-{job_id}.jsonl
        {"prompt": "...", "image": [...], "width": W, "height": H, "seed": ..., "think_mode": false}
  └── popen([VENV/bin/python, REPO/examples/interleave/inference.py,
              "--model_path", WEIGHTS_50STEP if not draft else WEIGHTS_8STEP,
              "--jsonl", JSONL_PATH,
              "--output_dir", OUT_DIR,
              "--no-think_mode"])
  └── streams stdout to job heartbeat (ETA estimator pattern from Trellis)
  └── on success: returns OUT_DIR/{stem}.png
  └── on failure: structured error to job log
```

Hooks into existing `submit_background` job queue with per-job timeout
override (recently shipped) — Draft default 180s, Final default 600s.
Cancel + orphan-rescue path applies as-is.

**Concurrency:** strictly serial. SenseNova at BF16 with CPU offload
already saturates the 7900 XTX; concurrent renders OOM. The job queue
already serializes; no extra lock needed.

**VRAM tenancy:** documented requirement to stop ComfyUI before
launching SenseNova on driveThree-class hardware. The backend exposes
a `/api/sensenova/precheck` endpoint that the UI calls before
submitting; if ComfyUI is running and SenseNova is the requested
backend, return 409 with a message and a "stop ComfyUI" affordance.
On Mac unified-memory hardware this precheck is a no-op (different
service topology).

### 4. Render history

**Location:** `storage.py` (existing) + history pane component

Each render persisted as `outputs/infographic/{timestamp}-{template_id}.png`
plus a sidecar `.json` with the slot values, image refs, prompt, seed,
and tier. Click a thumbnail in the history pane to load all slot
values back into the form (round-trip), and the PNG into the canvas.

History is per-installation (single-user); no auth model.

### 5. Post-edit canvas (V1-canvas scope)

**Location:** `static/studio/js/canvas-edit.js`

Renders on top of the preview PNG using HTML5 Canvas. Tools:

| Tool | Behavior |
|---|---|
| **Drop PNG** | Drag a PNG from desktop onto canvas → adds as a movable layer |
| **Paste from clipboard** | `Ctrl+V` with image in clipboard → adds as a layer |
| **Move layer** | Click + drag a layer to reposition |
| **Resize layer** | Corner handles, hold Shift to constrain aspect |
| **Delete layer** | Select + Delete key |
| **Save composite** | "Save as new render" → flattens canvas to PNG, persists via storage with link back to the original render |

Layer model: simple z-ordered list of `{type: "png", x, y, w, h, src}`
records; no rotation, no filters, no blend modes in v1. The composite
save is a `<canvas>.toDataURL("image/png")` → POST to backend → store.

**Out of scope for V1-canvas:**
- Region selection + clipboard export (V1.5)
- Layer rotation, opacity, blend modes
- Vector overlays / text editing
- Undo/redo stack beyond a single-step undo

## Multi-image conditioning protocol

Verified against `examples/interleave/inference.py` and `run.sh`:

1. Image references positionally bind to `<image>` placeholders in
   prompt, in declaration order.
2. JSONL batch mode: `{"image": [...], ...}` with relative paths
   resolved against `--image_root`.
3. **Output resolution follows Image 1 via `smart_resize`** when
   any image is supplied. The aspect picker UI is disabled in this
   case and the actual output size is shown as "auto (matches Image 1)".
4. Text-only renders use the trained-resolution buckets
   (1:1 / 16:9 / 9:16 / 3:2 / 2:3 / 4:3 / 3:4 / 1:2 / 2:1 / 1:3 / 3:1).
   The aspect picker is a dropdown of these named buckets only —
   free-form W×H is intentionally not exposed (anything outside the
   bucket set degrades quality and the model itself prints a warning).

## Templates v1 — list

| ID | Name | Slot summary |
|---|---|---|
| `hub_and_spoke` | Hub & Spoke | title, hub_desc, hub_image?, spokes[4..8] |
| `comparison` | Comparison / vs. | title, left{heading,bullets[3..5],image?}, right{...} |
| `timeline` | Timeline / Process | title, steps[3..7]{label,description,image?} |
| `stats` | Stat Showcase | title, cells[3..6]{value,label,image?} |
| `quadrant` | Quadrant / 2×2 | title, x_axis{low,high}, y_axis{low,high}, quadrants[4]{label} |
| `list` | List / N-Things | title, intro?, rows[3..7]{label,description,image?} |
| `map` | Geographic Map | title, region (enum: world/continent/country), overlays[]{location,label,value?,image?} |
| `hierarchy` | Hierarchical | title, root, levels[2..4]{nodes[]{label,parent_ref}} |

A small preview PNG ships with each template (rendered once and committed)
so the dropdown can show thumbnails.

## Hardware story

**Primary tier: 8B-MoT** (50-step + 8-step-preview weights). This is
the verified path on driveThree (RX 7900 XTX, ROCm 7.2). Shipped as
the default.

**Install:** `scripts/setup-sensenova.sh` (new) detects platform:

| Platform | Path |
|---|---|
| Linux + ROCm 7.2+ | `pip install torch==2.11.0+rocm7.2 --index-url …`, install repo deps, download weights |
| Linux + CUDA | `pip install torch --index-url cu121`, etc |
| macOS (Apple Silicon) | torch with MPS backend, weights download |
| Other / CPU | refuse with a clear "minimum spec" message |

Weights are downloaded by the install script via `huggingface-cli` with
mirror selection (HF + ModelScope).

**A3B-MoT (3B-active MoE)** evaluation tracked as a follow-up issue, not
part of v1. If it lands, the model selector gets a third tier
("Lightweight") and the hardware matrix gets a "16GB GPU / 32GB Mac"
recommendation.

## API surface

New routes:

| Method | Path | Purpose |
|---|---|---|
| GET  | `/api/infographic/templates` | List templates (id, name, schema) |
| POST | `/api/infographic/render`    | Submit job. Body: `{template_id, slots, image_refs[], tier: "draft"\|"final", aspect?: "1:1"\|"16:9"\|...}` → 202 + `{job_id}` |
| GET  | `/api/infographic/jobs/{id}` | Poll status (existing job-queue pattern) |
| POST | `/api/infographic/composite` | Save post-edit composite. Body: `{base_render_id, png_data_url}` |
| GET  | `/api/sensenova/precheck`    | Returns `{ready: bool, blockers: [...]}` |

Notes on the render body:
- `aspect` is only honored when `image_refs` is empty; with refs, output
  size is derived from Image 1.
- `tier="draft"` routes to the 8-step weights, `tier="final"` to 50-step.
- The backend always uses `examples/interleave/inference.py` (one code
  path covers text-only and text+image) — the previously-used
  `examples/t2i/inference.py` is only kept around as the
  `scripts/sensenova-smoke-test.sh` reference path.

Image uploads reuse the existing `/api/upload` endpoint; image-ref
slots store the returned URL.

## Testing plan

- **Unit:** template assembly (slot → prompt rendering), `[Image N]` →
  `<image>` rewriting, slot validation.
- **Integration:** mock SenseNova subprocess; verify jsonl payload shape,
  job lifecycle, history persistence, composite save round-trip.
- **End-to-end (manual / opt-in):** real SenseNova render under
  `tests/manual/test_infographic_e2e.py`, gated on `SENSENOVA_E2E=1`,
  same pattern as the existing testnet smoke tests.
- **Visual regression:** golden-PNG hash for each of the 8 templates'
  preview tiles (committed once); no AI-output diffing — that's not
  reproducible across runs at the bit level.

Coverage target: 80%+ on the template engine, backend wrapper, and
canvas serialization. The model itself is exempt (it's a black box
behind a subprocess).

## Risks & known unknowns

| Risk | Mitigation |
|---|---|
| Multi-image renders blow up VRAM headroom | Cap `image_refs` to 4 in v1; surface a clear UI message when exceeded |
| `smart_resize` picks an awkward output size for stretched ref images | Show the predicted output size in the form before render; warn if outside trained buckets |
| Custom template JSON is malformed | Validate against `infographics_schema.json` at load; show errors in dropdown rather than crashing |
| Mac MPS path unverified | Phase 1 ships with a "tested on Linux ROCm" badge; macOS is best-effort, real verification is a community contribution gate |
| Post-edit canvas compositing on huge PNGs (2592×864) is sluggish | Downscale-while-editing / re-resolve on save (standard canvas pattern) |
| Template prompt drift across SenseNova version updates | Pin the model version in `setup-sensenova.sh`; templates declare their tested model in frontmatter; UI warns on mismatch |

Open questions deferred to implementation phase:

- Stem naming for output PNGs — encode template+seed for traceability?
- Should the no-template mode also support saving as a custom template
  (one-click promote)?
- Does the post-edit canvas need a "fit to viewport" toggle or always
  fit?

## Future work (out of scope for v1)

- **V1.5 — region-select clipboard round-trip** (the GIMP loop)
- **V1.5 — A3B-MoT smaller variant** (Mac/16GB GPU tier)
- **V1.5 — In-app template authoring UI** (move custom templates from
  files-only to first-class)
- **V2 — Interleaved output mode** (text + image steps in one render)
- **V2 — Animated infographic export** (Lottie/GIF/MP4 from layered
  composites)
- **V2 — Style-locked series mode** (lock palette + composition across
  multiple renders for a brand series)

## File map (new)

```
backends/
  sensenova.py
docs/superpowers/specs/
  2026-05-05-infographic-builder-design.md   # this file
scripts/
  setup-sensenova.sh
static/studio/
  infographic.html
  js/
    infographic.js
    canvas-edit.js
studio/
  infographics.py            # template loader + prompt assembler
  infographics_schema.json
templates/infographics/
  hub_and_spoke.json
  comparison.json
  timeline.json
  stats.json
  quadrant.json
  list.json
  map.json
  hierarchy.json
  _previews/
    *.png
tests/
  test_infographics_templates.py
  test_sensenova_backend.py
  test_canvas_composite.py
  manual/
    test_infographic_e2e.py
```
