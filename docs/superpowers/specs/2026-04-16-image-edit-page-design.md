# Image Edit Page — Design

**Date:** 2026-04-16
**Status:** Approved (pending user review of this document)

## Summary

Add an image editing page to Wyltek Studio at `/studio/image-edit.html`. Users send images from the Generate page's viewer (or any gallery thumbnail) to the editor, optionally paint a mask, write a text instruction, pick a model, and produce an edited image. Results land in `outputs/edits/` and support iterative re-editing via a "Use as Source" action. Direct upload is supported so arbitrary images (not just Wyltek-generated ones) can be edited.

## Scope

### In scope (v1)

- New page at `/studio/image-edit.html` with source canvas + mask overlay, prompt input, model selector, parameter controls, gallery strip.
- Two local editing models wired through the existing ComfyUI backend:
  - **FLUX.1 Kontext [dev]** — instruction-driven identity-preserving edits.
  - **Qwen-Image-Edit** — instruction-driven stylistic edits.
- Mask painting (brush, clear, undo, toggle). Mask is optional; omitted mask means whole-image edit.
- Handoff from Generate page: URL param `?asset=<filename>`, no file copy.
- Direct upload via drag/drop and file picker.
- Edit results saved to `outputs/edits/` and surfaced in a gallery strip.
- Gallery actions: Save, Copy URL, Send to Project, Use as Source (iterative chain).
- "Send to Editor" button on Generate page main viewer AND each gallery thumbnail.

### Out of scope (v1)

- OmniGen2 (added in a follow-up if results from Kontext/Qwen disappoint).
- Secondary reference images (multi-image conditioning).
- Pulling source images from project files (C-scope inputs).
- Region-selection beyond freehand brush (no polygon/rectangle/magic-wand).
- Edit history beyond the session gallery strip (no persistent edit-chain state).

## Architecture

One new backend route, two new workflow-builder methods on the existing ComfyUI backend, two new workflow JSON templates, one new HTML page, one new JS module, and modest edits to three existing files. No new backend module, no new job queue, no new storage system.

```
Generate page (index.html)
   │
   │  "Send to Editor" (new button)
   ▼
/studio/image-edit.html?asset=<filename>
   │
   │  POST /api/edit  (multipart)
   ▼
server.py   ───►   backends/comfyui.py.run_edit()
                        │
                        ├─ kontext_edit.json   (template + substitution)
                        └─ qwen_image_edit.json
                        │
                        ▼
                 ComfyUI  →  result PNG
                        │
                        ▼
               outputs/edits/<uuid>.png
```

## Components

### New files

| Path | Purpose |
|------|---------|
| `static/studio/image-edit.html` | Editor page. Left: source canvas + mask overlay + brush tools. Right: model selector, prompt textarea, Edit button, collapsible params. Bottom: edit gallery strip. |
| `static/studio/js/image-edit.js` | Page controller. Handles `?asset=` param, direct upload, mask canvas state, `/api/edit` call, gallery rendering, action button wiring. |
| `workflows/edits/kontext_edit.json` | ComfyUI workflow template for FLUX.1 Kontext [dev]. |
| `workflows/edits/qwen_image_edit.json` | ComfyUI workflow template for Qwen-Image-Edit. |
| `tests/test_image_edit.py` | Pytest unit + integration tests for the backend edit path. |
| `tests/e2e/image-edit.spec.ts` | Playwright E2E for the full flow. |

### Modified files

| Path | Change |
|------|--------|
| `server.py` | Add `POST /api/edit` route (multipart: `source_filename` or uploaded file, `mask` optional, `prompt`, `model`, `steps`, `cfg`, `seed`). |
| `backends/comfyui.py` | Add `build_kontext_edit_workflow(...)`, `build_qwen_edit_workflow(...)`, and a dispatch method `run_edit(model, source_bytes, mask_bytes, prompt, params)`. |
| `model_catalog.py` | Register Kontext + Qwen-Image-Edit with an `"edit"` capability tag so the frontend can populate the model selector. |
| `static/index.html` | Add "Send to Editor" button to `.result-actions` and gallery thumbnails. |
| `static/js/app.js` | Wire "Send to Editor" buttons → `window.location = '/studio/image-edit.html?asset=' + encodeURIComponent(filename)`. |
| `static/js/nav.js` | Add nav entry for "Edit" under Studio. |

### Reused unchanged

- `ProjectPicker` (for "Send to Project" on edit gallery items).
- `/outputs/*` static mount.
- Toast system.
- Existing ComfyUI client plumbing and job queue.

## Data flow

### Handoff (Generate → Edit)

1. User clicks "Send to Editor" on `/` (main viewer or gallery thumbnail).
2. Browser navigates to `/studio/image-edit.html?asset=<filename>`.
3. On load, `image-edit.js` reads `?asset`, sets `<img src="/outputs/<filename>">` as the source canvas background, and initialises the mask overlay at matching dimensions.

### Direct upload

1. User drops file onto drop zone or picks via file input.
2. File uploaded via existing `/api/upload` (verify during implementation; add if missing).
3. Returned filename becomes the source.

### Edit request

1. User picks model, writes prompt, optionally paints mask.
2. Mask canvas is exported to PNG (transparent = no edit, opaque = edit region). Skip entirely if untouched.
3. `POST /api/edit` multipart: `source_filename`, `mask` (optional blob), `prompt`, `model`, `steps`, `cfg`, `seed`.
4. `server.py` reads source from `outputs/` (or staged upload), calls `ComfyUIBackend.run_edit(...)`.
5. Backend loads the appropriate workflow JSON, substitutes source image, mask (if present), prompt, and params. Submits to ComfyUI, polls for completion, returns result bytes.
6. Server writes result to `outputs/edits/<uuid>.png`, returns `{filename, url}`.

### Result handling

1. Gallery strip prepends the new edit thumbnail.
2. Thumbnail actions: Save, Copy URL, Send to Project, Use as Source.
3. "Use as Source" swaps the edit into the source slot for iterative chaining. Mask is reset.

## Error handling

### Frontend (`image-edit.js`)

| Condition | Behaviour |
|-----------|-----------|
| Missing/invalid `?asset` | Show drop zone, no error toast (fresh session). |
| Source image fails to load | Error toast: "Couldn't load `<filename>` — it may have been deleted. Upload a new image." |
| Upload rejected (non-image / >20MB) | Toast with reason, no network call. |
| `/api/edit` non-2xx | Toast the server error message, keep prompt intact. |
| `/api/edit` timeout (>5 min) | Toast: "Edit timed out, check ComfyUI". No silent swallow. |
| Model not loaded in ComfyUI | Server returns 424 → toast: "Kontext not installed — see /settings". |

### Backend (`server.py` + `comfyui.py`)

| Condition | Response |
|-----------|----------|
| Source file missing from `outputs/` | 404 with clear message. |
| Mask dimensions mismatch source | 400 with expected dimensions. |
| ComfyUI unreachable | 503 "ComfyUI backend not running". |
| ComfyUI execution error | Bubble up the node error from the ComfyUI websocket, not a generic 500. |
| `outputs/edits/` not writable | 500 with path in the error (surfaces disk/permission issues fast). |
| Selected model fails | Error — no silent fallback to another model. |

All backend errors log full stack + request context. Frontend sees a clean message.

## Testing

### Backend (pytest — `tests/test_image_edit.py`)

- **Unit:** `build_kontext_edit_workflow` / `build_qwen_edit_workflow` — substitute placeholders into workflow JSON, assert nodes have correct inputs (source path, mask path, prompt, seed). No ComfyUI call.
- **Unit:** `/api/edit` validation — missing source → 404, bad model → 400, mask dimension mismatch → 400. Mock the backend.
- **Integration** (marked `@pytest.mark.integration`, skip if `COMFYUI_URL` unset): real round-trip to ComfyUI with a tiny test image for each model. Slow, local-only, not in CI.

### Frontend (Playwright — `tests/e2e/image-edit.spec.ts`)

- **Handoff:** visit `/`, mock `/api/generate`, click "Send to Editor", assert URL and source image loaded.
- **Direct upload:** drop file on edit page, assert source populated.
- **Mask canvas:** paint strokes, assert PNG export is non-transparent in painted region.
- **Edit submit:** mock `/api/edit`, click Edit, assert gallery thumb prepended, actions present.
- **Iterative chain:** click "Use as Source" on a gallery edit, assert source slot updated and mask reset.

### Manual verification (required, not automated)

- Run each model against a real source image (e.g., `~/Downloads/cs_finalists/6ec17ebd.png` with instruction "flatten, remove gradient, solid colors"). Confirm visual quality before claiming done.
- UI feature-correctness can't be test-proven — run the dev server and use it in a browser before marking complete.

### Coverage target

- 80% on new Python code in `backends/comfyui.py` edit paths and the new route.
- Frontend coverage tracked via Playwright assertion count, not line %.

## Model installation (operational note)

Neither model is installed today on the ComfyUI used by Wyltek Studio. Implementation plan will include a setup step:

- **FLUX.1 Kontext [dev]**: ~24 GB bf16; Q6/fp8 quant acceptable. Non-commercial license.
- **Qwen-Image-Edit**: Apache 2.0. ~20B class.

Both fit comfortably in the 7900 XTX 24 GB VRAM budget. Model presence is a frontend capability check (surfaced by `model_catalog.py`) and a backend error path (424) — not a silent fallback.

## Decisions log

| # | Decision | Alternative considered | Rationale |
|---|----------|------------------------|-----------|
| Q1 | Two models on day one: Kontext + Qwen-Image-Edit. | One model, three models, zero models. | Covers instruction-edit + stylistic-edit use cases without multi-image complexity. |
| Q2 | Text + source image + optional mask. | Text-only; text + mask + reference image. | Source-image identity preservation + mask gives region control without multi-image model complexity. |
| Q3 | URL-param handoff, no staging copy. | Staging dir with redirect; mirror ProjectPicker exactly. | Outputs are already persistent and URL-addressable; staging buys nothing. |
| Q4 | Generate handoff + direct upload. | Generate-only; + pull from project files. | Direct upload covers the cs_finalists-style workflow; project-files can come later. |
| Q5 | Edits to `outputs/edits/`, gallery strip with full actions, "Send to Editor" on all gallery thumbnails. | Mixed outputs dir; main-viewer-only handoff. | Separation keeps edits organized; all-thumbnail handoff means older generations are editable too. |
| A1 | Extend existing `backends/comfyui.py` with edit workflow builders. | New `backends/comfyui_edit.py` module. | Edit workflows are close enough to gen workflows that a single backend remains coherent. |
