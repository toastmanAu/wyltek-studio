"""Detect sentinel #FF00FF rectangles in a rendered infographic.

The infographic render path can append a sentinel instruction to the
prompt asking SenseNova/HiDream to paint N solid magenta rectangles where
logos belong. After the PNG is written, this module scans for those
regions and writes an ``out.slots.json`` sidecar describing each slot's
bounding box and centre, ordered for the manual-fill UI.

Magenta is used because it virtually never appears in natural infographic
artwork — false positives are confined to anti-aliasing halos around the
real placeholders, which are stripped by ``area > MIN_AREA_PX`` plus the
"take top N by area" rule. See ``detect_slots`` for the full pipeline.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import label, find_objects


# Threshold tuned against an 8-step SenseNova-U1 draft render — generous
# enough to catch glow halos at the rectangle edges (where the model
# softens toward the background) but tight enough that no natural
# infographic palette colour lands inside it.
_RED_MIN, _GREEN_MAX, _BLUE_MIN = 180, 80, 180

# A slot smaller than this is anti-aliasing noise, not a real placeholder.
# 64x64 = 4096 px; smallest reasonable logo slot at 1536x2048 is much larger.
_MIN_AREA_PX = 4_000


@dataclass(frozen=True)
class Slot:
    id: int
    bbox: tuple[int, int, int, int]  # x, y, w, h
    center: tuple[int, int]
    area_px: int


def _bbox_from_slice(sl: tuple[slice, slice]) -> tuple[int, int, int, int]:
    ys, xs = sl
    return (int(xs.start), int(ys.start),
            int(xs.stop - xs.start), int(ys.stop - ys.start))


def detect_slots(png_path: Path, *, requested: int) -> list[Slot]:
    """Find the top ``requested`` magenta slots in the rendered PNG.

    Returns slots sorted in reading order (top-to-bottom, left-to-right
    after a row-bucketing pass), so slot id 1 is always the topmost-
    leftmost regardless of which connected component happened to be
    labelled first by scipy.
    """
    arr = np.asarray(Image.open(png_path).convert("RGB"))
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    mask = (r > _RED_MIN) & (g < _GREEN_MAX) & (b > _BLUE_MIN)

    labels, _n_components = label(mask)
    slices = find_objects(labels)

    candidates: list[Slot] = []
    for i, sl in enumerate(slices, start=1):
        if sl is None:
            continue
        area = int((labels[sl] == i).sum())
        if area < _MIN_AREA_PX:
            continue
        x, y, w, h = _bbox_from_slice(sl)
        candidates.append(Slot(
            id=0,  # assigned after sort
            bbox=(x, y, w, h),
            center=(x + w // 2, y + h // 2),
            area_px=area,
        ))

    candidates.sort(key=lambda s: -s.area_px)
    candidates = candidates[:requested]

    # Row-bucket → reading order. Rows are determined by clustering
    # centre-y values that fall within half the median slot height.
    if candidates:
        median_h = int(np.median([s.bbox[3] for s in candidates]))
        row_tol = max(1, median_h // 2)
        candidates.sort(key=lambda s: s.center[1])
        rows: list[list[Slot]] = [[candidates[0]]]
        for s in candidates[1:]:
            if abs(s.center[1] - rows[-1][-1].center[1]) <= row_tol:
                rows[-1].append(s)
            else:
                rows.append([s])
        for row in rows:
            row.sort(key=lambda s: s.center[0])
        ordered = [s for row in rows for s in row]
    else:
        ordered = []

    return [Slot(id=i, bbox=s.bbox, center=s.center, area_px=s.area_px)
            for i, s in enumerate(ordered, start=1)]


def write_sidecar(png_path: Path, *, requested: int,
                  slots: list[Slot]) -> Path:
    """Write ``<png_stem>.slots.json`` next to the rendered image."""
    canvas = Image.open(png_path).size  # (w, h)
    sidecar = png_path.with_suffix(".slots.json")
    sidecar.write_text(json.dumps({
        "canvas": list(canvas),
        "requested": requested,
        "detected": len(slots),
        "slots": [asdict(s) for s in slots],
    }, indent=2))
    return sidecar


def detect_and_save(png_path: Path, *, requested: int) -> dict:
    """Convenience wrapper: detect + write sidecar, return summary."""
    slots = detect_slots(png_path, requested=requested)
    sidecar = write_sidecar(png_path, requested=requested, slots=slots)
    return {
        "sidecar": str(sidecar),
        "requested": requested,
        "detected": len(slots),
        "slots": [asdict(s) for s in slots],
    }


SENTINEL_INSTRUCTION_TEMPLATE = (
    " Include {n} clearly separated, solid magenta #FF00FF rectangles, "
    "distributed across the layout where logos or images will later be "
    "placed. The magenta rectangles must be FULLY OPAQUE, perfectly "
    "rectangular, and use the EXACT colour #FF00FF (pure magenta — no "
    "gradients, no patterns, no overlaid text). Treat them as deliberate "
    "design placeholders, not decorative elements."
)


def build_sentinel_prompt(prompt: str, *, n: int) -> str:
    """Append the sentinel instruction to a user-supplied prompt.

    No-op when ``n <= 0`` so callers can pass the toggle value blindly.
    """
    if n <= 0:
        return prompt
    return prompt.rstrip() + SENTINEL_INSTRUCTION_TEMPLATE.format(n=n)
