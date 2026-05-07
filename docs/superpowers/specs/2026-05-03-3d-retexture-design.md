# 3D Mesh Re-Texturing — Design Spec

**Status:** parked — to land before the agent skill so the skill ships with re-texture verbs.
**Date:** 2026-05-03

## Goal

Let users (and later, agents) take an existing 3D mesh and change its
texture **without regenerating geometry**. Two orthogonal paths:

- **Path B (texture swap)** — export the baked texture atlas → run through
  any 2D AI tool (Style Remix, image-tools, Qwen, inpaint) → write back
  into a new GLB with identical geometry/UVs.
- **Path A (TRELLIS-native re-texture)** — feed an existing TRELLIS shape
  mesh + a new reference image into the SLat-encoder → texture DiT → bake
  a fresh atlas. Higher fidelity, narrower applicability.

Ship B first; B unlocks the entire 2D toolchain for 3D meshes today.

## Why

Today the only way to change a texture is to regenerate the whole mesh,
which (a) wastes 5–30 min of GPU, (b) loses the geometry the user already
liked, and (c) introduces new floaters / non-determinism. Re-texture
decouples the cheap-to-vary part (the surface) from the expensive,
already-good part (the geometry).

## Path B — Texture Swap (simpler, universal)

### Flow

```
┌──────────┐  /api/3d/extract-texture  ┌──────────────┐
│ source   │──────────────────────────▶│ baseColor    │
│ .glb     │                           │ .png         │──┐
└──────────┘                           │ + uv.png     │  │
                                       └──────────────┘  │
                                                         ▼
                                       (any 2D AI tool — Style Remix,
                                        image-tools, Qwen, inpaint, …)
                                                         │
                                                         ▼
┌──────────┐  /api/3d/apply-texture    ┌──────────────┐
│ new .glb │◀──────────────────────────│ edited .png  │
└──────────┘                           └──────────────┘
```

### API

```
POST /api/3d/extract-texture
  body: { source_glb: "/storage/abc.glb" }
  response: {
    texture_url: "/storage/abc.texture.png",
    uv_overlay_url: "/storage/abc.uv.png",   // UV charts on white bg, for context
    width: 2048, height: 2048,
    material_index: 0,                       // which material's baseColor was extracted
  }

POST /api/3d/apply-texture
  body: {
    source_glb: "/storage/abc.glb",
    edited_texture: "/storage/abc.texture.edited.png",
    material_index: 0,
  }
  response: { new_glb_url: "/storage/abc.retex.glb" }
```

### Implementation notes

- Use `trimesh` (already a transitive dep) or `pygltflib` to read/write the
  `.glb`. Both can extract embedded `image/png` buffers and write a
  modified copy.
- `material_index` exposes multi-material meshes; default 0 covers the
  common single-material TRELLIS / Hy3D output case.
- Resize-on-apply: if the edited PNG dimensions differ from the original,
  resample to original (don't change atlas resolution). Surface a warning
  if the input dims don't match.
- UV overlay is an optional convenience render: rasterize the UV charts
  to a PNG so the user can see "this region of the atlas = this part of
  the model" before editing. Use `xatlas` output if available, else a
  `trimesh.visual` rasteriser. Cheap to compute, helps a lot for hand
  edits; ignored by Style Remix users.

### UI

In the 3D viewer panel (`static/studio/frames.html`), add two buttons
to the GLB result:
- **Edit texture** → calls `extract-texture`, opens the PNG in
  `static/studio/image-tools.html` with a "Save & re-apply" button that
  flows through `apply-texture` and replaces the GLB in-place.
- **Style Remix texture** → calls `extract-texture`, opens the PNG in
  `static/studio/remix.html`, same return path.

(Path A's "Re-texture from image" button lives next to these later.)

### Estimate

~150 LoC across `backends/` + `server.py` + `static/`. ~half a day.

### Open questions

- Should we cache the extracted atlas next to the GLB so repeated extracts
  don't re-decode? Probably yes — write `<glb>.texture.png` next to it
  and only regenerate if mtimes diverge.
- Multi-material meshes (Hy3D PBR with metallicRoughness + normals): v1
  only edits baseColor. Note in the UI that other channels are preserved.

## Path A — TRELLIS-native Re-texture (higher fidelity, narrower)

### Flow

```
existing TRELLIS shape .glb + new reference image
                ↓
        SLat-encoder (voxelise)
                ↓
        texture DiT (1024-res, 12-step default)
                ↓
        Texture decoder + bake → new .glb
```

### API

```
POST /api/3d/retexture
  body: {
    source_glb: "/storage/abc.glb",
    reference_image: "/storage/ref.png",
    texture_steps: 12,
    texture_resolution: 1024,
    texture_atlas_size: 2048,
    seed: -1,
  }
  response: { job_id: "..." }
```

Standard `/api/job/{id}` poll lifecycle.

### Implementation notes

- The wrapper already has the right nodes:
  - `Trellis2Continue_GGUF` (loads a saved pipeline state)
  - `Trellis2MeshTexturing_GGUF` (runs the texture DiT on an existing
    shape mesh)
- The blocker is **shape persistence**: TRELLIS doesn't currently save
  the SLat-encoder output. We'd need to either (a) save the voxel grid
  + encoded shape latents alongside the `.glb` at generation time, or
  (b) re-run the SLat-encoder on the loaded mesh (extra ~10s but
  avoids the persistence problem).
- Option (b) is simpler — just hand the loaded mesh to the encoder.
  Quality should be ~identical because the encoder is deterministic.
- Build a new workflow `build_trellis_retexture_workflow(...)` mirroring
  `build_trellis_workflow` but starting from a `LoadMesh_GGUF` →
  `SLatEncoder_GGUF` → `MeshTexturing_GGUF` → `ExportMesh_GGUF` chain.
- New `ComfyUIBackend.generate_trellis_retexture` method following the
  same WS-loop + heartbeat pattern shipped 2026-05-03.

### UI

Third button in the 3D viewer: **Re-texture from image** — prompts for
a new reference image, queues the job. Reuses the same progress / job
flow as a fresh TRELLIS run.

### Estimate

~250 LoC. ~1 day. Most of the work is the new workflow builder + the
backend method; UI is small.

### Open questions

- Hy3D analogue: does Hy3D have a similar "texture-only" path? Hy3D's
  `Hy3DDelightImage` + `Hy3DSampleMultiView` + `Hy3DBakeFromMultiview`
  *might* be runnable in isolation against an existing mesh. Worth a
  short investigation when picking this up. If yes, expose under the
  same `/api/3d/retexture` endpoint with `engine="hy3d"`.

## Build order when picked up

1. **Path B `extract-texture` + `apply-texture`** (~half day) — pure
   plumbing, no new GPU work, immediately useful.
2. **Path B UI** in `frames.html` viewer (~2h) — wire the two buttons,
   reuse existing image-tools / remix flows for the editor leg.
3. **Path A workflow builder** (~half day) — `build_trellis_retexture_workflow`
   stitching `LoadMesh` → `SLatEncoder` → `MeshTexturing` → `ExportMesh`
   nodes from the existing wrapper.
4. **Path A backend + endpoint** (~half day) — `generate_trellis_retexture`
   + `POST /api/3d/retexture` + job lifecycle.
5. **Path A UI** (~1h) — third viewer button.
6. **Hy3D parity for path A** (variable) — investigate first.

## Out of scope for v1

- Painting directly on the mesh in the viewer (modly doesn't do this
  either; would require either WebGL projection painting or a Three.js
  brush — large undertaking).
- KTX2 / compressed texture handling — assume PNG baseColor.
- Material editing beyond baseColor (metallicRoughness, normals, emissive)
  — preserved unchanged in v1.
- Per-region masked re-texture (e.g. "only re-texture this UV island").
  Reasonable v2; would build on `extract-texture` returning per-island
  masks alongside the atlas.

## Why this matters for the agent skill

The skill's `generate-3d` recipe currently ends at "GLB produced." Adding
re-texture means the skill can also do:

- `retexture-3d` — run path A from a new reference image
- `edit-3d-texture` — pull texture, hand it to a 2D edit verb, push it back

That's two new agent verbs that compose with everything in the 2D
toolchain for free. The skill is materially more capable with these in
place — which is why this lands before the skill, not after.

## Related context

- TRELLIS heartbeat + Q8_0 default landed 2026-05-03 — both paths inherit
  the heartbeat for free since they reuse the same WS loop.
- `feedback_gguf_kquants_slow_on_rocm.md` — re-texture jobs should
  default to Q8_0 too; do NOT use K-quants on the texture DiT.
