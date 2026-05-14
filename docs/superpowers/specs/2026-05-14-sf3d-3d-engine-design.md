# Stable Fast 3D as a Third 3D Engine

**Date:** 2026-05-14
**Status:** Design — approved, plan pending
**Authors:** Phill + Claude

## Context

Wyltek Studio currently exposes two image-to-3D engines:

- **Hunyuan3D** (`engine="hy3d"`) — modes `shape` and `pbr`. Quality has been underwhelming in practice; suspected sub-optimal config but not investigated this round.
- **TRELLIS.2-4B** (`engine="trellis"`) — modes `shape` and `textured`. Hero-asset quality, but `textured` runs ~32 minutes on a 7900 XTX (ROCm). Too slow for iteration.

There is no fast preview / game-ready slot in the lineup. **Stable Fast 3D (SF3D, Stability AI, Aug 2024)** fills it: 1B params, <1s inference (CUDA), single-image input, single-shot output of a **UV-unwrapped, low-poly, delit, PBR-textured GLB**. Output is game-engine-ready in a way TRELLIS and Hy3D's outputs are not.

## Goals

1. Add SF3D as `engine="sf3d"` — a peer to `hy3d` and `trellis`, not a replacement.
2. Match the integration shape of TRELLIS (ComfyUI custom node path, not a standalone worker).
3. Expose full output controls in the UI (per Phill's preference) — preset dropdown + per-knob fields, mirroring TRELLIS's `preset` + `tweak_*` surface.
4. Keep the diff small and additive — no refactors, no abstractions for hypothetical future engines.

## Non-Goals

- **Hunyuan3D tuning.** Tracked separately. Will be a follow-up session once SF3D gives us a fast A/B baseline.
- **Engine adapter abstraction.** With N=3 the three parallel switch arms in `server.py` and `backends/comfyui.py` are clearer than an interface. Revisit at engine #4 or #5.
- **`model_catalog.py` entry.** SF3D weights auto-download via the ComfyUI custom node; no Wyltek-managed picker.
- **Stability community-license UI consent gate.** Wyltek qualifies under the <$1M-revenue clause. Re-evaluate if/when revenue changes.
- **Batch / multi-candidate generation in v1.** SF3D supports it cheaply but the UI shape is a separate design question.

## Architecture

```
UI (3D mode + engine=sf3d + sf3d_* knobs)
  └→ POST /api/generate                                   server.py:1816
       └→ validate engine ∈ {hy3d, trellis, sf3d}
       └→ validate mode_3d   ← SKIPPED for sf3d (no shape/textured split)
       └→ build params dict (incl. sf3d_*)
       └→ resolve_3d_timeouts("sf3d", "textured") → (120s, 60s)
       └→ job_queue.submit_background → _run_job
            └→ backends/comfyui.py: build_sf3d_workflow(...) → ComfyUI API dict
                 └→ ComfyUI HTTP submit → SF3D custom node graph runs
                      └→ GLB at ComfyUI/output/3D/wyltek-sf3d_<n>.glb
                           └→ texture_io.py + mesh_export.py finalise
                                └→ storage/unsorted/<date>/meshes/
```

The flow is byte-for-byte identical to TRELLIS until the workflow-builder branch.

## Components

### Files modified

| File | Change |
|---|---|
| `server.py` | Add `sf3d` to engine whitelist; add 5 `sf3d_*` form fields; branch `mode_3d` validation to skip sf3d; append `sf3d_*` keys to `params`; map `engine=="sf3d"` to `mode_flag="textured"` for timeout lookup; add `("sf3d","textured"): (120, 60)` to `_TIMEOUT_BUDGET`. |
| `backends/comfyui.py` | Add `build_sf3d_workflow()` next to `build_trellis_workflow()` (~80 lines). Add `engine=="sf3d"` branch in the 3D job dispatcher (around line 3029). |
| `static/` (frontend) | New `sf3d_*` form group; shown when `engine=sf3d` selected; hides `mode_3d` toggle in that case. |
| `tests/test_sf3d_workflow.py` | New: workflow-builder unit tests. |
| `tests/test_3d_timeouts.py` | Extend: assert SF3D timeout entry exists and is < TRELLIS textured. |
| `tests/test_orphan_rescue.py` | Extend: SF3D output pattern is rescued same as TRELLIS. |
| `tests/test_health_actions.py` | Extend: SF3D healthcheck doesn't false-positive on first-boot missing weights. |

### Files added

- `docs/superpowers/specs/2026-05-14-sf3d-3d-engine-design.md` (this doc).
- `tests/test_sf3d_workflow.py`.

### External dependency added

A ComfyUI custom node wrapping SF3D. Specific fork to be selected in the implementation plan; candidates include `matt3o/ComfyUI-StableFast3D` and similar community wrappers. ROCm-friendliness must be verified before locking the choice; if no fork works cleanly on the 7900 XTX, we fork (precedent: `comfyui-trellis2-gguf-rocm` next to `ComfyUI-Trellis2-GGUF`).

### Parameters surfaced

| Form field | Values | Default | Notes |
|---|---|---|---|
| `sf3d_preset` | `preview` / `game-ready` / `hero` | `game-ready` | Pre-fills the other knobs when changed; explicit knob changes override. |
| `sf3d_texture_resolution` | `512` / `1024` / `2048` | `1024` | |
| `sf3d_target_vertex_count` | int 5000–50000 | `10000` | |
| `sf3d_remesh` | `none` / `triangle` / `quad` | `triangle` | |
| `sf3d_tweak_delight` | bool | `1` (on) | Off only for users who want lighting baked in. |

`auto_bg_removal` is reused unchanged (same on/off semantics as TRELLIS).

## Data Flow Specifics

- **Input image** — saved to `uploads/<job_id>_ref0.<ext>` (existing path), copied into `ComfyUI/input/`, filename passed to `build_sf3d_workflow(image_filename=...)`.
- **SF3D node graph** — placeholder shape: `LoadImage → SF3DPreProcess(remove_background=auto_bg_removal) → SF3DModel(preset_knobs) → SF3DExportGLB(file_prefix="3D/wyltek-sf3d")`. Exact node class names locked in the implementation plan after the fork is chosen.
- **Output** — single textured GLB. No second white-mesh export (SF3D is one-shot, unlike TRELLIS's shape→continue→textured sequence). `texture_io.py` + `mesh_export.py` pick it up via existing glob patterns.
- **`mode_3d` for SF3D** — ignored. Server-side: `if engine == "sf3d"`, skip the `mode_3d` whitelist check; force `mode_flag = "textured"` for the timeout-budget lookup. Asymmetric branch documented inline.
- **Timeouts** — `("sf3d", "textured"): (120, 60)`. SF3D's <1s inference is dwarfed by ComfyUI startup, image preprocessing, UV unwrap, texture bake, GLB serialise, and (first run only) ~3GB weight download. 120s outer is generous backstop; 60s inner targets steady-state.

## Error Handling

- **Engine validation** — existing 400 pattern extended: `engine must be 'hy3d', 'trellis' or 'sf3d', got <X>`.
- **Missing reference image** — existing 400 updated to mention SF3D as image-conditioned alongside Hy3D and TRELLIS.
- **ROCm incompatibility** — pattern from `backends/comfyui.py:1914-1923` (TRELLIS FP8 → BF16 fallback): if any SF3D config is determined empirically to fail on ROCm (flash-attn path, fp8 kernel, etc.), add a server-side silent fallback. Specific fallbacks identified during the implementation plan's bring-up step.
- **First-run weight download** — ~3GB auto-download via the custom node. First job appears stalled for 1–5 minutes; existing `progress_smooth.py` handles UX. Add a one-line note to the `_TIMEOUT_BUDGET` comment.
- **Texture bake failure** — if SF3D's UV unwrap or texture step fails on edge-case inputs, the node should still produce an untextured GLB. Frontend surfaces a partial-success message ("mesh OK, texture failed"). Logic mirrors TRELLIS orphan rescue (`scripts/backfill_orphan_meshes.py`).

## Testing Strategy

**Unit (pytest, per `~/.claude/rules/python-testing.md`):**

- `tests/test_sf3d_workflow.py`:
  - `build_sf3d_workflow()` returns a dict with the required node IDs.
  - Each `sf3d_preset` value maps to the documented `(texture_resolution, target_vertex_count, remesh)` tuple.
  - `auto_bg_removal=False` flips the preprocess flag.
  - Invalid `remesh` value raises `ValueError`.
- `tests/test_3d_timeouts.py`: `_TIMEOUT_BUDGET[("sf3d","textured")]` exists, outer < TRELLIS-textured outer, inner ≥ 30s.
- `tests/test_orphan_rescue.py`: SF3D output filename pattern (`wyltek-sf3d_*.glb`) recovered identically to TRELLIS.
- `tests/test_health_actions.py`: SF3D health check is `not-installed → ok` once weights present; no false-positive failure on a fresh install.

**Integration:**

- One manual end-to-end UI submit per preset (`preview` / `game-ready` / `hero`), verifying:
  - GLB lands in `storage/unsorted/<date>/meshes/`.
  - Mesh preview renders in the studio.
  - Vertex count, texture resolution, and delit-vs-lit albedo match the preset's promises.
- Documented as a checklist in the PR description. CI cannot exercise this without a 7900 XTX runner.

**Bandit:** No new secret-handling or shell-out code; `bandit -r .` should remain clean.

## Risks & Open Questions

| Risk | Mitigation |
|---|---|
| SF3D ComfyUI custom node may not work on ROCm out of the box. | Bring-up step in plan: test the chosen fork before writing the workflow builder. Fork to a `-rocm` variant if needed (precedent exists for TRELLIS). |
| SF3D weight download is large (~3GB) and silent on first run. | Document in the user-visible timeout comment; existing progress smoother absorbs the wait. |
| UV unwrap can fail on unusual inputs (very thin geometry, transparent inputs). | Partial-success path produces untextured GLB; orphan-rescue picks it up. |
| Preset values are guesses pending empirical validation. | Treat the preset table as a starting point; tune during integration test pass. |

## Rollback

All changes are additive. Rolling SF3D back to "disabled":

1. Remove `sf3d` from the engine whitelist in `server.py`.
2. Frontend selector loses the SF3D row (data-driven from `/api/3d_models`, no hardcoded UI to revert).
3. `build_sf3d_workflow()` and tests stay in place — dead code only, no production impact.

No DB migrations, no on-disk format changes, no shared-state mutations to undo.

## Future Work (Explicit Follow-Ups)

- **Hunyuan3D config audit** — separate session. Once SF3D is the fast baseline, A/B against Hy3D's various paint variants and sampler settings to determine whether Hy3D earns its slot.
- **Batch / multi-candidate generation** — SF3D's <1s inference makes "generate 8, pick 1" trivial. UI design TBD.
- **Engine adapter abstraction (Approach C)** — re-evaluate at engine #4.
