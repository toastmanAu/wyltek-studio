# Image-Tools Editing Capabilities — Buildout Plan

**Author:** Claude Code (paired w/ Phill)
**Date:** 2026-05-01
**Status:** Draft

---

## TL;DR

Two stub tabs (`Remove Object`, `Add / Replace`) in `static/studio/image-tools.html` need real backends, plus add capabilities for recolor-with-integrity and instruction-driven editing.

Plan: **4 phases**, each independently shippable. Phase 1 (object removal) is the smallest and highest-impact win — uses no big model downloads. Phase 3 (instruction edit / FLUX Kontext) is **promoted to primary editing UI** based on UX feedback — it's the headliner tab, with Phase 2's mask-mode as a secondary path. Phase 4 is mostly UI work over existing infra. Pose / limb editing (formerly "Phase 5") is **deferred** — not worth the effort at current local model quality.

**Pre-Phase 3 spike**: A short OmniGen2 vs FLUX Kontext head-to-head comparison decides which model (or both) backs the instruction-edit UI before we commit Phase 3's UI work to Kontext exclusively.

**Qwen-Image is dropped from scope** — Kontext fills that role and has materially broader ROCm community testing.

---

## Background — current state

`static/studio/image-tools.html` has three tabs:

| Tab | Status |
|---|---|
| `Remove Background` | ✅ Shipped — 14-model rembg dropdown, BiRefNet default, validated against the modelHouse test set |
| `Remove Object` | 🟡 UI shell only (line 110 button, panel at line 180) |
| `Add / Replace` | 🟡 UI shell only (line 111 button, panel at line 225) |

No backend endpoints, no model wiring for the latter two.

### What's already installed (assets we can leverage)

**Diffusion models on disk:**
- FLUX.1 dev (Q4 + Q8 GGUF) — strong base
- FLUX.1 schnell (Q4 GGUF) — 4-step fast
- FLUX 2 klein 4B (fp8 + base)
- SD 3.5 Large (Q8 GGUF)
- SDXL family (Juggernaut, RealVis, Dreamshaper, etc.)

**Editing-relevant models:**
- `sam_vit_l_0b3195.pth` (1.2 GB) — SAM v1 large
- `instantid/` (ControlNet + IP-Adapter for face-ID preservation)
- `pulid/pulid_flux2_klein_v2.safetensors` — face ID lock for Flux 2
- `ipadapter/` (IP-Adapter plus, faceid-plus v2)
- `controlnet/xinsir-controlnet-canny-sdxl.safetensors` — for ControlNet edge-guided edits (SDXL only)
- `controlnet/xinsir-controlnet-tile-sdxl.safetensors`

**Custom nodes installed:**
- ComfyUI-PuLID-Flux2 — face ID
- ComfyUI_IPAdapter_plus — style/composition transfer
- ComfyUI-Impact-Pack + Subpack — segmentation, masking, FaceDetailer
- ComfyUI-RMBG — bg removal
- ComfyUI-GGUF — quantized model loading

### Gaps to fill (per phase, detailed below)

- `iopaint` Python lib + LaMa model weights (Phase 1)
- SAM2 + ComfyUI-segment-anything-2 custom node (Phase 1)
- FLUX.1 Fill dev (Phase 2) — ~12 GB Q8 GGUF
- FLUX.1 Kontext dev (Phase 3) — ~12 GB Q8 GGUF
- ControlNet canny **for FLUX** (Phase 4) — ~3 GB

---

## Phased buildout

### Phase 1 — `Remove Object` tab (object removal via iopaint + SAM2)

**Goal:** Click on an object in an image, get a clean removal with no halo, no fill artifacts.

**Why iopaint + LaMa, not Flux Fill:** LaMa is 200 MB, runs fast on CPU even (sub-second per edit), and is empirically the best-known model for "remove this object, fill the gap with plausible background." Flux Fill is a sledgehammer for this nail — slower, more VRAM, no quality benefit for vanilla removal.

**Why SAM2 for masking, not SAM v1:** v1 is what's on disk but its segmentation quality on common objects is noticeably worse than SAM2. SAM2 is the right click-to-mask backend for any modern editor. v1 stays for fallback.

**Components:**

| Piece | Source | Size | Effort |
|---|---|---|---|
| `iopaint` Python lib | `pip install iopaint` | ~50 MB deps | 5 min |
| LaMa model weights | auto-downloaded by iopaint | ~200 MB | bundled |
| SAM2 model | `facebook/sam2-hiera-large` from HF | ~600 MB | 15 min download |
| `ComfyUI-segment-anything-2` custom node | `kijai/ComfyUI-segment-anything-2` | small | 10 min |

**Backend:**

```
POST /api/image/object-remove
  body: {
    path: "<storage path>",
    mask_b64: "<base64 PNG of the user-painted mask>",  // OR
    sam2_clicks: [{x, y, label: "fg"|"bg"}, ...],         // SAM2 generates the mask
  }
  response: {
    output_path: "<storage path of the result>",
    duration_ms: <int>
  }
```

Two paths because:
- **Click-to-mask via SAM2** is the modern UX (point at the object, mask is computed). Server runs SAM2 with the click coordinates → mask → LaMa → output.
- **Manual brush mask** is the fallback (existing pixel painting tools generate the mask client-side). Server skips SAM2, goes straight to LaMa.

**UI:**

```
[ Source image ]                 [ Result image ]
  ↓ user clicks an object
  ↓ SAM2 mask appears as overlay (auto)
  ↓ user can refine: add/remove brush
  ↓ "Remove" button
                                  ↓ LaMa runs, result shown
```

Mask refinement UI uses an HTML5 canvas overlay. Two brush modes: "include in mask" / "exclude from mask." Match the bg-remove tab's existing visual language.

**Success criteria:**
- Removes a discrete object from the modelHouse test set (e.g., a window pane) with no visible artifact at 1024×1024
- End-to-end (click → result) under 5 seconds on the 7900 XTX
- Manual brush mode works as fallback when SAM2 returns a poor mask

**Estimated effort:** 4–6 hours (split: 2h backend + iopaint integration, 2h SAM2 wiring, 1–2h frontend canvas overlay)

---

### Phase 2 — `Add / Replace` tab (mask + prompt → Flux Fill)

**Goal:** User masks a region, types "a sleeping cat", and the masked area fills with that prompt-driven content seamlessly integrated.

**Components:**

| Piece | Source | Size | Effort |
|---|---|---|---|
| FLUX.1 Fill dev | `black-forest-labs/FLUX.1-Fill-dev` from HF (or GGUF Q8 from quanters) | ~12 GB Q8 / ~24 GB fp16 | 30 min download |
| FLUX.1 Fill T5 + CLIP encoders | If not already on disk for FLUX dev | ~5 GB | 15 min |
| ComfyUI Flux Fill workflow node | Built into ComfyUI core (vanilla nodes) | n/a | n/a |

**Backend:**

```
POST /api/image/inpaint
  body: {
    path: "<source image storage path>",
    mask_b64: "<base64 PNG mask>",
    prompt: "a sleeping cat",
    negative_prompt: "...",
    cfg: <float, default 3.5>,
    steps: <int, default 20>,
    seed: <int, -1 for random>,
  }
  response: {
    output_path: ...,
    duration_ms: ...
  }
```

Routes to ComfyUI via the existing `_run_job` infrastructure in `server.py`. Workflow is single-node-ish: load image, load mask, load Flux Fill, sample, save.

**UI:**

Reuses the canvas overlay from Phase 1 for mask painting. Adds a prompt input box, CFG/steps controls (collapsed under "Advanced" by default), seed control with random/lock toggle. Two-step UX:

1. Paint mask
2. Type what to put there → "Generate" button

Show a 2x2 grid of variations on click (4 different seeds) so user picks the best — this is critical for inpaint UX since first-shot quality is variable.

**Success criteria:**
- Replace a window with a tree on the modelHouse — looks plausible at 1024×1024
- Replace a person's shirt color while preserving the shirt's wrinkles and pose (note: this is a *partial mask* over the shirt, not a full shirt rebuild)
- 4-variation grid renders in under 60 s on 7900 XTX with Flux Fill Q8

**Estimated effort:** 6–8 hours (2h Flux Fill download + node verification, 2h backend, 2h UI variations grid + prompt inputs, 2h quality testing)

---

### Phase 2.5 — Spike: OmniGen2 vs FLUX Kontext head-to-head

**Goal:** Before Phase 3 commits to a single instruction-edit model, run a focused comparison on the same 5–8 test edits across both candidates. Decide: ship Kontext only, OmniGen2 only, or both as alternatives in the dropdown.

**Why both are credible:**
- **FLUX Kontext dev** — Black Forest Labs, ~12B params, instruction-tuned for editing. Strong AMD ROCm community presence, vanilla ComfyUI nodes.
- **OmniGen2** (`Shitao/OmniGen2`) — VectorSpaceLab, ~7B params, *multi-input* compositional editing ("put the cat from img A into scene B"). Lighter, sometimes better at compositional intent. Less ROCm validation.

The compositional ability of OmniGen2 (accepts multiple input images) is a meaningful capability that Kontext doesn't have. Worth a few hours to know whether we want it before locking the UI.

**Spike deliverables:**

1. Download both models (Q8 GGUF where available, otherwise fp16 with offload). ~24 GB total.
2. Build minimal ComfyUI workflows for each — no UI integration, just confirm both run on ROCm.
3. Run the same 5–8 test prompts on the same 5 source images:
   - "Change the wall to blue" — recolor preservation
   - "Remove the chimney" — object removal via instruction
   - "Add a moon in the sky" — addition with realistic placement
   - "Make it sunset" — global lighting/tone change
   - "Put a hat on the person" — placement of NEW object
   - "Replace the dog with a cat" — substitution preserving pose/scale
   - "Compose: this person + this background" — *only OmniGen2 attempts this*
   - "Add the text 'WANTED' on the poster" — text rendering
4. Tabulate: success rate, quality, speed per model per task category.
5. Decision: which to wire as the primary backend, whether to expose the second as a "try other model" toggle.

**Estimated effort:** 4–6 hours (2h downloads + workflow setup, 2h running tests, 1–2h analysis + decision write-up)

**Output:** decision document appended to this spec, plus the 8-edit comparison gallery saved to `storage/spike/2026-05-XX-omnigen2-vs-kontext/`.

---

### Phase 3 — `Edit` tab, instruction mode (PROMOTED to primary)

**Goal:** Headline editing experience. User types "make the sky stormy" or "remove the person on the left" — model figures out where and how. No mask needed. This is now the most prominent editing tab in image-tools, immediately after `Remove Background`.

**UI placement change** (vs. original spec): Phase 3 was originally "second mode under Add / Replace." It's now its own tab named simply `Edit`, positioned as the second tab after `Remove Background`. The mask-based path (Phase 2) becomes the secondary tab `Mask & Fill` — same backend, separate UI for users who want spatial precision.

**Tab order after Phase 3 ships:**

```
[ Remove Background ] [ Edit ★ headliner ] [ Mask & Fill ] [ Remove Object ] [ Recolor ]
                                                              (Phase 1)        (Phase 4)
```

**Components:** depends on Phase 2.5 spike outcome. Default plan assumes FLUX Kontext, but workflow factory is built so swapping/multiplexing is trivial.

| Piece | Source | Size | Effort |
|---|---|---|---|
| FLUX.1 Kontext dev | `black-forest-labs/FLUX.1-Kontext-dev` | ~12 GB Q8 / ~24 GB fp16 | already downloaded in spike |
| OmniGen2 (optional, if dual-model) | `Shitao/OmniGen2` | ~12 GB | already downloaded in spike |

**Backend:**

```
POST /api/image/instruct-edit
  body: {
    path: "<source image>",
    instruction: "make the sky stormy",
    model: "kontext" | "omnigen2",     // optional, default per spike outcome
    extra_paths: ["<storage path>", ...] // optional, OmniGen2 multi-input
    cfg: <float>,
    steps: <int>,
    seed: <int>,
  }
  response: {
    output_path: ...,
    duration_ms: ...,
    model_used: ...,
  }
```

Same `_run_job` route. Workflow chosen at runtime based on `model` field.

**UI:**

```
[ Source image ]                       [ 2x2 variation grid ]

Just describe what to change:
[ "make the sky stormy"             ] [ Generate ]

  ⚙ Advanced     [ Model: Kontext ▾ ]
                 ☐ Add reference image (OmniGen2 only)
                 [ CFG: 2.5 ] [ Steps: 28 ] [ Seed: random ]
```

Defaults to whichever model wins the Phase 2.5 spike. Model dropdown only appears under Advanced — most users never touch it.

**Success criteria:**
- "Change the wall colour to blue" preserves all other detail at 1024×1024
- "Remove the chimney" produces a roof with no chimney and plausible roofline
- "Add a moon in the sky" gets a moon in a sensible place
- "Add the text 'WANTED' on the poster" — readable text in plausible location
- All 4 variation grid renders in under 90 s on Q8 GGUF
- (If OmniGen2 wired) "Put the cat from img A into img B" produces a coherent compose

**Estimated effort:** 4–6 hours after Phase 2.5 (1h backend dispatch + workflow factory, 2h UI as headliner tab + reference-image picker if OmniGen2 wired, 1h tab reordering + landing-page polish, 1h quality testing across edit categories)

---

### Phase 4 — Recolor pipeline (ControlNet canny + prompt change)

**Goal:** "Make this red car blue" while every line, shadow, and reflection stays exactly where it was.

**Components:**

| Piece | Source | Size | Effort |
|---|---|---|---|
| FLUX ControlNet canny | `XLabs-AI/flux-controlnet-canny-v3` or InstantX's variant | ~3 GB | 15 min |
| Existing FLUX dev model | Already on disk | — | — |

**Why a separate phase from Phase 3:** Kontext can recolor, but ControlNet canny gives **pixel-perfect line preservation** — necessary when the user wants the recolor to be invisible-except-for-the-color-change. Kontext is more impressionistic; ControlNet is surgical.

Could be exposed as a tab variant or a "preserve structure exactly" toggle within Phase 3's UI.

**UI option A — separate tab `Recolor / Restyle`:**

```
[ Source image ]
  ↓
[ "Change to: ___" ] (free text or preset chips: "blue", "sunset", "watercolour")
[ Strength slider (canny weight) ]
  ↓
"Apply"
```

**UI option B — toggle inside `Add / Replace` (Phase 3):**

```
☑ Preserve original structure exactly (slower, more faithful)
```

Recommend **B** initially (less UI surface, instruction-driven), then split if usage warrants.

**Success criteria:**
- Recolor every red panel of the modelHouse to green; chimney brick, roof shingles, windows untouched
- Wall texture and shadows unchanged after recolor
- Faster than Phase 3's Kontext path (~30 s for a single output)

**Estimated effort:** 3–4 hours (1h ControlNet download + node verify, 1h backend, 1h UI integration, 1h validation)

---

### Phase 5 — Pose / limb repositioning — DEFERRED

**Decision (2026-05-01):** Skipped. Local-model quality at the photoreal end is research-grade (~30–50% success on identity preservation), not worth the UI investment now. Game-asset workflows already have an alternative path (TRELLIS multi-view from concept poses). Reassess if later Flux/OmniGen versions improve identity-preserving repose.

**Components stub** (kept for future reference):
- OpenPose ControlNet for FLUX (~3 GB)
- PuLID-Flux2 (already on disk)
- Pose editor UI (drag stick figure joints) — significant frontend work

---

## Cross-cutting concerns

### Storage & history

All edits go through `storage/unsorted/{date}/edits/` (new subdir alongside `meshes/`, `images/`, etc.). Each edit produces:
- The output image
- A sidecar JSON: source_path, model_used, prompt, mask_hash (for cache identification), duration, etc.
- A backlink to the source image so the gallery can show "edit history" if user clicks on an edit and asks "where did this come from?"

### Mask interchange format

All mask-using endpoints accept either:
- `mask_b64`: base64-encoded PNG, alpha channel = mask (white = mask region)
- `sam2_clicks`: list of `{x, y, label}` — server runs SAM2 to derive mask

Internal convention: white pixel = "edit this region." Standardize across Phases 1, 2, 4. Avoids "is white the mask or the keep area" confusion that bites half of inpainting tools.

### Variation grid pattern

Phases 2, 3, 4 all benefit from "show me 4 alternatives at different seeds." Build this once as a reusable frontend component:

```html
<variation-grid
  on-generate="..."
  count="4"
  prompt-bound-to="#prompt-input">
</variation-grid>
```

JS component takes a generation function, calls it 4× with different seeds, displays a 2×2 grid with click-to-select, click-to-regenerate-just-this-cell, click-to-save-to-photos.

Ship this as part of Phase 2 since that's where it first matters; reuse in 3 and 4.

### Job queue + timeouts

Reuse existing `JobQueue` + `_run_job` infrastructure. New 3D timeout table from the prior fork-and-PR spec applies pattern: per-mode timeouts. Add entries:

```python
_2D_EDIT_TIMEOUTS = {
    "object_remove": 30,         # iopaint + LaMa is fast
    "inpaint": 90,                # Flux Fill at 20 steps
    "instruct": 120,              # Flux Kontext, slightly slower
    "recolor": 60,                # ControlNet canny + Flux dev
}
```

### Auth / rate limit (if remote-accessed)

Open-palette is already authenticated and not internet-exposed by default. No new surface needed unless user wants to expose these endpoints publicly (separate decision).

---

## Total scope estimate

| Phase | Effort | Disk | New deps |
|---|---|---|---|
| 1: Remove Object | 4–6 h | ~1.5 GB (SAM2 + LaMa) | iopaint, ComfyUI-segment-anything-2 |
| 2: Mask & Fill | 6–8 h | ~12 GB (Flux Fill Q8) | none new |
| 2.5: OmniGen2 vs Kontext spike | 4–6 h | ~24 GB (both models, persisted) | none new |
| 3: Edit (instruction, headliner) | 4–6 h | already downloaded in 2.5 | depends on spike outcome |
| 4: Recolor | 3–4 h | ~3 GB (Flux ControlNet canny) | none new |
| 5: Pose | DEFERRED | n/a | n/a |
| **Total Phases 1–4 + spike** | **21–30 hours** | **~40 GB** | **2 packages** |

Spread across 4–5 sessions of focused work.

---

## Recommended ordering

**Session A** (~6 h): Phase 1 end-to-end. Quick win, no big downloads, validates click-to-mask UX before committing to 24 GB downloads.

**Session B** (~6 h): Phase 2.5 spike — OmniGen2 vs Kontext head-to-head. Decide which model (or both) backs the headliner Edit tab. ~24 GB downloads happen here so they're ready for Sessions C and D.

**Session C** (~8 h): Phase 2 (Mask & Fill) — masked inpainting using the Flux Fill weights downloaded in B. Build the reusable variation-grid component.

**Session D** (~6 h): Phase 3 (Edit headliner) — reuse downloaded model + variation grid. After this you have BOTH editing modes; image-tools is feature-complete for 80% of edit needs. Tab reorder so `Edit` is positioned right after `Remove Background`.

**Session E** (~4 h): Phase 4 (recolor).

**Total: 5 sessions, ~30 working hours.** Sessions A, B can swap order if you'd rather lock in the model choice first; Sessions C, D, E should follow B.

---

## Integration with the fork-and-PR spec

Phase 1 (Remove Object) has **no dependency** on the fork plan — iopaint + SAM2 stack is independent of the TRELLIS/Hy3D wrapper bugs we're forking around.

Phases 2–4 use FLUX models loaded via vanilla ComfyUI nodes, not the kijai/Aero-Ex wrappers. So **also no fork dependency**.

These two work tracks can proceed in parallel. The fork work fixes 3D pipeline reliability; the image-tools work delivers the 2D editing capabilities. Different repos, different code paths, different model families.

---

## Risk assessment

| Risk | Likelihood | Mitigation |
|---|---|---|
| Flux Fill / Kontext have ROCm-specific issues like Qwen-Image did | Medium | Use vanilla ComfyUI nodes (well-tested on AMD), Q8 GGUF (avoids fp8 ROCm gap). Test before committing UI work. |
| SAM2 segmentation quality is hit-or-miss on certain object classes | Medium | Always offer manual brush as fallback. Show both auto-mask and "refine" controls. |
| Variation grid takes too long (4× single-gen time) for satisfying UX | Medium | Cap at Q4 GGUF for variation grid; full Q8 only for "regenerate this one at higher quality." |
| LaMa fails on large object removal (>30% of image) | Low | Document limit; recommend Flux Fill for big regions. Fallback path. |
| User wants edits on outputs from prior edits → cascading quality loss | Medium | Always operate on the current visible image, not the original. Provide "undo to source" affordance. |

---

## Open questions for Phill

### Decisions captured 2026-05-01

3. **"Just describe" as primary editing UI** — ✅ **YES**. Promoted to headliner tab `Edit`. `Mask & Fill` becomes secondary tab.
4. **Phase 5 (pose) — skip for now** ✅. Deferred section above kept as future-reference stub.
5. **OmniGen2 vs Kontext** — ✅ **Spike both before locking Phase 3**. New Phase 2.5 added between Phase 2 and Phase 3.
6. **Qwen-Image** — ✅ **Drop from scope.** Kontext replaces it. Removed from spec.

### Remaining

1. **Phase 1 SAM2 model size** — `sam2-hiera-large` (~600 MB, best quality) vs `sam2-hiera-base-plus` (~150 MB, ~95% as good)? Default to large for quality unless Phill prefers the smaller.

2. **Variation count for Phases 2–4** — 4 (2×2 grid, current proposal) vs 6 (3×2 grid)? More options vs faster turnaround. Default 4.

---

## Next concrete action when ready

Phill confirms direction, then we:
1. Start Session A (Phase 1) — iopaint + SAM2 + Remove Object tab. ~6 h, results visible same session.
2. Or: pivot to fork work first if that's higher priority for ROCm stability.

Both tracks are independent, so we can sequence them per Phill's preference.
