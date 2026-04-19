# Style Remix — Design

**Date:** 2026-04-19
**Status:** Approved (pending user review of this document)

## Summary

Revive the Sprite Forge page as a slimmer, single-purpose **Style Remix** page at `/studio/remix`. The workflow: pick an already-generated character image from the gallery (or upload one), pick a style reference (user-uploaded image or a crypto logo from the existing catalogue), and produce a batch of remixes that preserve the character's pose/silhouette while re-skinning it in the style of the reference. No text prompt is required — the base image IS the character. An optional one-line style hint is available for nudges.

The page replaces the existing `/studio/sprites` page. All ROM-ripping, palette-constraining, sprite-sheet, and pixel-editor tabs are removed. If any of those are wanted later, they can move to Image Tools.

## Scope

### In scope (v1)

- New page at `/studio/remix` served from `static/studio/remix.html`.
- Replaces `static/studio/sprites.html`. Old page deleted.
- One-tab UI (no tab bar):
  - Base Character slot (gallery picker modal + drag-drop + file upload).
  - Style Reference (upload slot OR crypto logo dropdown — pick one).
  - Controls: Preserve Character slider (range 0.2-0.9, default 0.45), Style Intensity slider (range 0.0-1.5, default 0.75), Style Window (start/end) dual slider (each 0.0-1.0, default 0.0/0.8), Blend Mode select, LoRA picker + strength, Model picker (ComfyUI checkpoints only), Batch Size (2-8, default 4), Steps, CFG, Seed.
  - Optional one-line Style Hint field.
  - Generate button, progress bar, result grid with "Use as new base" on each result.
- New backend endpoint `POST /api/remix`.
- New method `ComfyUIBackend.generate_remix()` on top of a new `BASIC_IMG2IMG` workflow template.
- Reuses existing `ComfyUIBackend._add_ip_adapter()` for the style reference path.
- Results saved through the existing job queue / WS broadcast / storage pipeline.
- Metadata sidecar records `base_from` (source gallery id) and `style_ref` (crypto logo id OR upload filename).
- Sidebar: Remix link in the Create section, between Generate and Image Tools.

### Out of scope (v1)

- ROM extraction / Mod Builder.
- Palette-constrain, Sprite Sheet assembly, Pixel Editor tabs.
- Multi-style-ref blending (one style ref at a time).
- Video / animation remix.
- Non-ComfyUI backends for remix (A1111, Replicate, etc. not supported in v1).
- Batch picker for multiple base characters in one submit.

## Architecture

One new HTML page, one new JS controller, one new backend endpoint, one new ComfyUI workflow method + template, and small edits to the nav + AI copilot map. The old sprites page and its JS/CSS scaffolding are deleted.

```
Generate / Gallery
        │
        │  (user finds a character they like)
        ▼
/studio/remix   (new page)
        │
        │  POST /api/remix  (multipart)
        ▼
server.py   ─────►   backends/comfyui.py.generate_remix()
                            │
                            ├─ BASIC_IMG2IMG template
                            │       LoadImage → VAEEncode → KSampler(denoise)
                            │       + LoraLoader (if lora_model)
                            │       + IPAdapterUnifiedLoader + IPAdapterBatch (style ref)
                            │
                            ▼
                     ComfyUI → batch of result PNGs
                            │
                            ▼
                storage/<uuid>.png + <uuid>.json sidecar
```

## Components

### New files

| Path | Purpose |
|------|---------|
| `static/studio/remix.html` | Single-tab page. Base-character slot, style-ref inputs, controls row, submit, progress, result grid. |
| `static/studio/js/remix.js` | Page controller. Handles gallery-picker modal, file drops, `/api/remix` call, progress bar via WS, result grid rendering, "Use as new base" iteration. |
| `tests/test_remix.py` | Pytest: workflow-builder unit tests (including IPAdapterBatch required-key regression guard) + integration test for end-to-end remix. |

### Modified files

| Path | Change |
|------|--------|
| `server.py` | Add `POST /api/remix` route. Form fields: `base_image` (file) OR `base_gallery_id` (string); `style_ref` (file) OR `crypto_logo_id` (string); `preserve_character` (float, 0.2-0.9), `style_strength` (float), `ip_start` (float), `ip_end` (float), `blend_mode` (string), `lora_model` (string), `lora_strength` (float), `model` (string), `steps` (int), `cfg` (float), `seed` (int), `batch_size` (int, 2-8), `hint` (string, optional). |
| `backends/comfyui.py` | Add `BASIC_IMG2IMG` workflow template and `generate_remix(params, output_paths, on_progress)` method. Reuses `_add_ip_adapter()` and the existing LoRA injection code path. |
| `static/js/nav.js` | Add `{ href: '/studio/remix', icon: '&#127912;', label: 'Style Remix', id: 'remix' }` to NAV_ITEMS under Create. Add `/studio/remix` to the activeId detection. |
| `static/js/ai-copilot.js` | Update the page description map: `/studio/remix` → description, and remove `/studio/sprites`. |

### Deleted files

| Path | Reason |
|------|--------|
| `static/studio/sprites.html` | Replaced by `remix.html`. Old feature set (ROM extraction, palette constrain, sprite-sheet assembly, pixel editor) explicitly dropped. |

## Data flow

1. User loads `/studio/remix`.
2. Clicks **Base Character** tile → gallery picker modal fetches `/api/gallery`, grid of thumbnails, most recent first. User clicks one; modal closes; tile shows thumbnail; `base_gallery_id` is set to the image filename (e.g. `abc12345.png`).
   - Alternate: user drops a file onto the tile. Tile shows thumbnail; `base_image` field carries the upload, `base_gallery_id` is empty.
3. User picks **Style Reference**: either drops a file on the upload slot OR picks from the crypto logo dropdown (which sets `crypto_logo_id` to a filename like `/static/images/crypto-logos/ETH.png`).
4. User adjusts controls (or accepts defaults), clicks **Generate Remix**.
5. Frontend POSTs multipart to `/api/remix`. Backend:
   - If `base_gallery_id` present: resolves to `storage/<id>.png`; copies to ComfyUI input dir.
   - If `base_image` uploaded: writes to `uploads/remix_<id>.png`; copies to ComfyUI input dir.
   - Same two-path resolution for the style ref (gallery/logo path OR upload).
   - Submits one ComfyUI job per batch slot (batch_size jobs). Seed resolution: if `seed == -1`, backend picks a single random base seed for this remix; each slot gets `base_seed + index`. If `seed >= 0`, backend uses `seed + index` for each slot. This makes batches reproducible from the recorded seed while still giving each slot a distinct result.
   - Returns `{ remix_id, jobs: [{ job_id }, ...] }`.
6. Frontend renders `batch_size` placeholder tiles, subscribes to WS progress updates, and fills tiles as each job completes.
7. Each completed tile shows the result, a **Use as new base** button (sets that tile's output as the new Base Character and scrolls to the top), and the standard save/send-to-project actions.
8. Each result's `<uuid>.json` sidecar records:
   - `base_from_kind`: `"gallery" | "upload"`
   - `base_from`: gallery id if kind is gallery, upload filename if kind is upload
   - `style_ref_kind`: `"upload" | "crypto"`
   - `style_ref`: upload filename OR crypto logo id (e.g. `ETH`)
   - `preserve_character`, `style_strength`, `ip_start`, `ip_end`, `blend_mode`, `model`, `lora_model`, `lora_strength`, `seed` (the slot's specific seed, not `-1`), `steps`, `cfg`, `hint`
   - Plus the standard metadata already written by `_run_job`.

## Workflow template

`BASIC_IMG2IMG` in `backends/comfyui.py`:

```
1  LoadImage (base character)
2  VAEEncode (samples: [1,0], vae: [4,2])
3  KSampler (latent_image: [2,0], denoise: 1 - preserve_character, ...)
4  CheckpointLoaderSimple
5  (unused; kept for slot parity with BASIC_TXT2IMG)
6  CLIPTextEncode (positive) — fed the hint string (or empty)
7  CLIPTextEncode (negative) — fed the existing default negative prompt
8  VAEDecode
9  SaveImage
```

When a LoRA is set, the existing LoRA injection path (node 20) rewires 3/6/7 exactly as in txt2img.

When a style ref is set, `_add_ip_adapter()` injects nodes 10 (LoadImage for ref), 11 (IPAdapterUnifiedLoader), 13 (IPAdapterBatch) and rewires `workflow["3"]["inputs"]["model"] = ["13", 0]`. No changes to `_add_ip_adapter` are required — it already handles the LoRA→IPAdapter chain correctly, as verified during the comparison-bug fix. The frontend's `style_strength` maps to `ip_adapter_strength`, `ip_start`/`ip_end` map to `ip_adapter_start`/`ip_adapter_end`, and `blend_mode` maps to `ip_adapter_weight_type` (allowed values: `"style transfer"`, `"standard"`, `"prompt is more important"`).

## Error handling & validation

- Reject submit (400) if neither `base_image` nor `base_gallery_id` is present.
- Reject submit (400) if neither `style_ref` nor `crypto_logo_id` is present.
- Reject `preserve_character` outside `[0.2, 0.9]` with a clear error — not silently clamped, since extremes almost always indicate a UI bug. The UI slider uses the same range.
- Clamp `batch_size` to `[1, 8]`.
- If the resolved base gallery id points to a missing file, 404.
- If the resolved crypto logo id doesn't exist in `static/images/crypto-logos/`, 404.
- ComfyUI workflow validation errors propagate as usual: job status goes to `error`, the error string is stored on the job record, and the WS toast surfaces it. The "Required input is missing" diagnostic recipe (saved in memory from the Sprite Forge IPAdapterBatch fix) applies here too.

## Testing

Per `~/.claude/rules/testing.md`:

- **Unit (`tests/test_remix.py`):**
  - `BASIC_IMG2IMG` template has the expected node structure (LoadImage → VAEEncode → KSampler with `denoise` wired correctly).
  - `generate_remix` builds a workflow that includes `embeds_scaling` and `encode_batch_size` on the IPAdapterBatch node (regression guard).
  - `generate_remix` correctly wires LoRA node 20 between the checkpoint and IPAdapter, preserving the chain.
  - Invalid inputs (missing base, missing style ref, out-of-range preserve_character, out-of-range batch_size) raise the expected errors from `server.py`.
- **Integration (`tests/test_remix.py`):**
  - Fixture: a known gallery image + a fixture crypto logo. POST `/api/remix`, poll jobs, assert all complete with status `complete`, file size > 0, and metadata sidecars contain the expected lineage fields.
- **E2E (optional follow-up, not required for v1):** Playwright test driving the page through a real remix.

## YAGNI / deferred

- No "compare across backends" for remix (comfyui only).
- No batch-pick of multiple base characters in one submit.
- No on-page pixel-level editing. Use `/studio/image-tools` afterwards if needed.
- No persistent remix history beyond the standard gallery + `base_from` sidecar breadcrumb.
- No dual-IP-Adapter (style + composition) split. One style reference, one strength, one window.

## Open questions resolved during brainstorming

- **Character preservation mechanism:** img2img with partial denoise (option B), not IP-Adapter-as-character-ref (option A). User confirmed.
- **Page scope:** Revive Sprite Forge at its old route, trimmed to just the Generate workflow (option A). User confirmed.
- **Tab structure:** Single tab, no tabs bar (option A). User confirmed — "keep it clean".
- **Page name:** "Style Remix" by default. User can request keeping "Sprite Forge" — not raised as a concern.

## Risk & rollback

- Removing `sprites.html` is destructive if anyone else is hitting `/studio/sprites`. Nav already doesn't link to it, and the page isn't referenced externally. Risk: low.
- If remix quality is poor at the default `preserve_character=0.45`, tuning is a slider change, not a code change. The defaults in this spec are the starting point based on what typically works for SDXL + IPAdapter-plus style transfer.
- If users ask for the removed tabs back, each tab's code is preserved in git history (last commit before the delete). Follow-up can lift Palette/Sheet into Image Tools.
