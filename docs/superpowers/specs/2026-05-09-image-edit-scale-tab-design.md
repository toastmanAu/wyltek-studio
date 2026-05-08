# Scale tab — image-edit page

**Date:** 2026-05-09
**Page:** `static/studio/image-edit.html`
**Scope:** Client-side only. No backend changes, no new dependencies.

## Goal

Let users drop an image and see it rendered at multiple target sizes simultaneously, at real pixel size on screen. Primary use cases: checking logo legibility at small sizes (favicon, app-icon), evaluating game-asset sprites at mip ladder sizes (16/32/64/128/256/512). Supports both smooth (bilinear) and pixel-art (nearest-neighbor) downscaling, and aspect-ratio overrides.

## Tab placement

3rd position in the tab bar. Order: `Remove Background · Remove Object · Scale · Add / Replace (soon)`. Tab id `scale`, panel id `tab-scale`.

The "Apply to Mesh" handoff (page-level button shown when the page is opened from mesh-edit with `?source=...`) does not participate with this tab — Scale produces N outputs, not one. The handoff button hides when `#tab-scale` is active, mirroring how the existing `tab-obj-add` "soon" panel does not surface a result.

## UI

```
┌─ Source ────────────────────────────────────┐
│  [drop / click to upload]   thumb · 1024×1024 · logo.png
└─────────────────────────────────────────────┘

[ Smooth · Pixel-art ]    Mode
[ Native · 1:1 · 16:9 · 4:3 · 3:4 · 9:16 ]    Ratio
[ Cover · Contain · Stretch ]    Fit (disabled when Ratio = Native)
Sizes: [ 16, 32, 64, 128, 256, 512 ] [Reset]

┌─ Sample sheet ──────────────────────────────┐
│  ▢ 16×16     ▢ 32×32      ▢ 64×64           │
│  144 B       287 B        612 B             │
│  [↓]         [↓]          [↓]               │
│  ▢ 128×128   ▢ 256×256    ▢ 512×512         │
│  ...                                         │
└─────────────────────────────────────────────┘

[ Download All ]
```

Each tile renders the resized image at its **real pixel size** — no CSS upscaling. A 16px tile is a literal 16px image on screen. Tiles never grow beyond their natural size; the grid just wraps.

## Resize algorithm (per tile)

1. **Target dims.** `sizeLabel` = longer edge.
   - Ratio = Native: shorter edge = `round(sizeLabel × min(srcW,srcH) / max(srcW,srcH))`.
   - Ratio forced (e.g. 16:9): derive shorter edge from ratio. `targetH = sizeLabel`, `targetW = round(targetH × ratioW / ratioH)` (or vice versa, whichever way longer-edge falls).
2. **Source rect.** Computed by Fit mode:
   - **Cover:** crop source to target aspect, centred. `sx, sy` chosen to centre.
   - **Contain:** full source rect; canvas filled transparent first, then `drawImage` into letterboxed target rect.
   - **Stretch:** full source → full target (no crop, no bars).
3. **Render.** `ctx.imageSmoothingEnabled = mode === 'smooth'` then `ctx.drawImage(src, sx, sy, sw, sh, dx, dy, dw, dh)`.

## Output format

Match source MIME: PNG source → PNG output, JPEG source → JPEG (quality 0.92), WebP → WebP. Detected from the uploaded `File.type`. Filenames: `{sourceBaseName}_{w}x{h}.{ext}`.

## Download

- **Per-tile:** `canvas.toBlob(mime, quality)` → object URL → click anchor with `download` attr.
- **Download All:** sequential per-tile downloads triggered with ~50ms spacing. Browser shows one "allow multiple downloads" permission prompt; subsequent downloads land in the user's default folder. No zip dependency.

## State and re-render

Single in-memory state object: `{ srcImage, srcMime, srcName, mode, ratio, fit, sizes }`. Any control change calls `_renderScaleSheet()` which clears and re-builds the tile grid synchronously. Resize work is sub-millisecond per tile in modern browsers; no debouncing needed for ≤16 tiles.

## File footprint

- `static/studio/image-edit.html`: ~30 lines new HTML (tab button, tab panel, controls, empty grid container) + ~30 lines new CSS for the controls bar and tile grid (mostly reusing existing `--surface-*` / `--accent` tokens).
- Inline `<script>` block: ~150 lines for `setupScaleTab()`, `_renderScaleSheet()`, `_resizeOne()`, `_downloadTile()`, `_downloadAll()`, plus tab-switch wiring.

## Out of scope (deferred)

- Upscaling beyond source size (different problem — the existing upscaler covers 2D upscale).
- Custom crop region (pan/zoom of the source before scaling). User can pre-crop elsewhere.
- Format conversion (e.g. PNG → WebP). Match-source covers the common case.
- Single-target export form (rejected during brainstorming — sample sheet is the goal).

## Open questions

None. Defaults all settled:
- Mode: Smooth
- Ratio: Native
- Fit: Cover (only relevant when Ratio ≠ Native)
- Sizes: 16, 32, 64, 128, 256, 512

## Cache invalidation

This change touches `image-edit.html` (which is *not* in `static/sw.js` precache list — page is fetched on navigation, served network-first per existing SW logic). No `CACHE_VERSION` bump needed unless the change extends to shared CSS/JS in the precache list, which it does not.
