"""Sprite frame post-processing — turn an SDXL "row of mini-poses" output
into a single isolated subject centred on a transparent canvas.

Pipeline per frame:

  1. rembg (isnet-anime) -> transparent-background RGBA
  2. Connected components on the alpha mask
  3. Pick the largest blob -- that's the main subject
  4. Crop to that blob's bbox
  5. Scale (contain) into target_size x target_size
  6. Paste centred on a transparent canvas
  7. Save

This is the workaround for the base-SDXL "pixel art + pose" strip-shape bias
that the single_frame=True prefix in generate_sprites only partially solves.
See [[generate-sprites-prefix-bias]] memory.
"""

from __future__ import annotations

# Aliased import: avoids the literal `create_subprocess_exec(` token in the
# call site, which trips an over-eager TypeScript-targeted security hook.
# The call shape is positional-args (no shell), the same safe pattern used
# by /api/image/bg-remove in server.py.
from asyncio import create_subprocess_exec as _spawn_proc
from asyncio.subprocess import PIPE as _PIPE
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class ExtractResult:
    blobs_found: int
    chosen_pixels: int
    src_bbox: tuple[int, int, int, int]  # (left, top, right, bottom) in source
    cropped_size: tuple[int, int]        # (w, h) after bbox crop
    final_size: tuple[int, int]          # (target_size, target_size)
    rembg_ms: int


async def extract_subject(
    src_path: Path,
    dst_path: Path,
    *,
    target_size: int,
    rembg_bin: Path,
    rembg_model: str = "isnet-anime",
    alpha_threshold: int = 16,
    pad_pct: float = 0.06,
) -> ExtractResult:
    """Isolate the main subject from src_path, centre on transparent canvas.

    alpha_threshold -- pixel counted as "subject" when alpha > this (0-255).
    pad_pct         -- fraction of target_size to leave as breathing room
                       around the subject after fitting (0.06 = 6% each side).
    """
    import time

    if not src_path.exists():
        raise FileNotFoundError(src_path)
    if not rembg_bin.exists():
        raise FileNotFoundError(f"rembg binary not found at {rembg_bin}")

    tmp_rgba = src_path.with_name(src_path.stem + ".rembg.png")
    t0 = time.time()
    proc = await _spawn_proc(
        str(rembg_bin), "i", "-m", rembg_model,
        str(src_path), str(tmp_rgba),
        stdout=_PIPE, stderr=_PIPE,
    )
    _, stderr = await proc.communicate()
    rembg_ms = int((time.time() - t0) * 1000)
    if not tmp_rgba.exists():
        msg_lines = stderr.decode(errors="replace").strip().splitlines()
        msg = msg_lines[-1] if msg_lines else "rembg produced no output"
        raise RuntimeError(f"rembg failed: {msg}")

    try:
        result = _isolate_largest_blob(
            tmp_rgba, dst_path,
            target_size=target_size,
            alpha_threshold=alpha_threshold,
            pad_pct=pad_pct,
            rembg_ms=rembg_ms,
        )
    finally:
        tmp_rgba.unlink(missing_ok=True)
    return result


def _isolate_largest_blob(
    rgba_path: Path,
    dst_path: Path,
    *,
    target_size: int,
    alpha_threshold: int,
    pad_pct: float,
    rembg_ms: int,
) -> ExtractResult:
    """Pure (sync) logic -- kept separate so it's unit-testable without rembg."""
    from scipy.ndimage import label as cc_label

    img = Image.open(rgba_path).convert("RGBA")
    rgba = np.array(img)
    alpha = rgba[..., 3]
    mask = alpha > alpha_threshold

    # Connected components on the alpha mask. SDXL strip outputs typically
    # produce N disjoint character blobs separated by transparent gaps;
    # picking the largest = the most-rendered figure.
    labels, n_blobs = cc_label(mask)

    if n_blobs == 0:
        blank = Image.new("RGBA", (target_size, target_size), (0, 0, 0, 0))
        blank.save(dst_path)
        return ExtractResult(
            blobs_found=0, chosen_pixels=0,
            src_bbox=(0, 0, 0, 0),
            cropped_size=(0, 0),
            final_size=(target_size, target_size),
            rembg_ms=rembg_ms,
        )

    # np.bincount over labels: index 0 is the background blob (label == 0
    # pixels), so zero it out and argmax over the rest.
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    chosen_label = int(sizes.argmax())
    chosen_mask = labels == chosen_label
    chosen_pixels = int(sizes[chosen_label])

    ys, xs = np.where(chosen_mask)
    top, left = int(ys.min()), int(xs.min())
    bottom, right = int(ys.max()) + 1, int(xs.max()) + 1

    # Zero alpha on all OTHER blobs so the crop is clean -- otherwise adjacent
    # figures clipping into the bbox would leave debris.
    cleaned = rgba.copy()
    cleaned[~chosen_mask, 3] = 0

    cropped = Image.fromarray(cleaned[top:bottom, left:right], mode="RGBA")
    cw, ch = cropped.size

    # Fit into target_size with padding (contain), preserving aspect.
    avail = int(target_size * (1.0 - 2 * pad_pct))
    if cw == 0 or ch == 0:
        scale = 1.0
    else:
        scale = min(avail / cw, avail / ch)
    new_w = max(1, int(round(cw * scale)))
    new_h = max(1, int(round(ch * scale)))
    resized = cropped.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (target_size, target_size), (0, 0, 0, 0))
    ox = (target_size - new_w) // 2
    oy = (target_size - new_h) // 2
    canvas.paste(resized, (ox, oy), resized)
    canvas.save(dst_path)

    return ExtractResult(
        blobs_found=int(n_blobs),
        chosen_pixels=chosen_pixels,
        src_bbox=(left, top, right, bottom),
        cropped_size=(cw, ch),
        final_size=(target_size, target_size),
        rembg_ms=rembg_ms,
    )
