"""Sprite tools — palette quantization, sheet composition, game format palettes.

Handles the pipeline: AI-generated 512x512 → game-ready indexed PNG.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image


# --- Game Palettes ---
# Stored as list of (R, G, B) tuples, standard 0-255 range.

# X-COM UFO Defense Battlescape palette (first 128 entries — most used)
# Full 256-color palette from PALETTES.DAT, entry 4 (battlescape).
# Original is 6-bit (0-63), pre-multiplied by 4 here.
XCOM_PALETTE = [
    (0, 0, 0), (4, 4, 4), (8, 8, 8), (16, 16, 16),
    (24, 24, 24), (32, 32, 32), (40, 40, 40), (48, 48, 48),
    (56, 56, 56), (64, 64, 64), (72, 72, 72), (80, 80, 80),
    (88, 88, 88), (96, 96, 96), (108, 108, 108), (120, 120, 120),
    # Browns/skin tones (16-31)
    (28, 16, 8), (40, 24, 12), (52, 32, 16), (64, 40, 20),
    (80, 52, 28), (96, 64, 36), (112, 80, 48), (128, 96, 60),
    (144, 112, 76), (160, 128, 92), (176, 148, 112), (192, 164, 132),
    (208, 184, 152), (224, 200, 172), (236, 216, 192), (248, 232, 212),
    # Reds (32-47)
    (40, 0, 0), (60, 0, 0), (80, 0, 0), (100, 4, 0),
    (120, 8, 0), (140, 16, 4), (160, 24, 8), (180, 36, 12),
    (200, 48, 20), (212, 64, 28), (224, 80, 40), (232, 100, 52),
    (240, 120, 68), (244, 140, 88), (248, 164, 112), (252, 188, 140),
    # Greens (48-63)
    (0, 24, 0), (0, 36, 0), (0, 48, 0), (0, 60, 4),
    (4, 76, 8), (8, 92, 16), (16, 108, 24), (24, 124, 36),
    (36, 140, 48), (48, 156, 64), (64, 168, 80), (80, 180, 100),
    (100, 192, 120), (120, 204, 140), (144, 216, 164), (168, 228, 188),
    # Blues (64-79)
    (0, 0, 40), (0, 0, 60), (0, 0, 80), (0, 4, 104),
    (0, 8, 128), (4, 16, 148), (8, 28, 168), (16, 40, 184),
    (24, 56, 200), (36, 72, 212), (52, 92, 224), (68, 112, 232),
    (88, 136, 240), (112, 160, 244), (136, 184, 248), (164, 208, 252),
    # Yellows (80-95)
    (32, 28, 0), (48, 40, 0), (64, 52, 0), (84, 68, 0),
    (104, 84, 0), (124, 100, 4), (144, 120, 8), (164, 140, 16),
    (184, 160, 28), (200, 180, 40), (216, 196, 56), (228, 212, 76),
    (240, 224, 96), (244, 232, 120), (248, 240, 148), (252, 248, 180),
    # Purples (96-111)
    (28, 0, 40), (40, 0, 60), (56, 0, 80), (72, 4, 104),
    (88, 8, 128), (108, 16, 148), (128, 28, 168), (148, 40, 184),
    (168, 56, 200), (184, 76, 212), (200, 96, 224), (216, 120, 232),
    (228, 144, 240), (236, 168, 244), (244, 192, 248), (252, 216, 252),
    # Cyans (112-127)
    (0, 24, 24), (0, 36, 36), (0, 52, 52), (0, 68, 68),
    (4, 84, 84), (8, 104, 104), (16, 124, 124), (28, 144, 144),
    (40, 160, 160), (56, 176, 176), (76, 192, 192), (96, 204, 204),
    (120, 216, 216), (144, 228, 228), (172, 240, 240), (200, 252, 252),
    # Extend with grays and mixed tones for 128-255
    *[(i, i, i) for i in range(128, 256)],
]

# NES palette — the standard 54-color NTSC palette
NES_PALETTE = [
    (124, 124, 124), (0, 0, 252), (0, 0, 188), (68, 40, 188),
    (148, 0, 132), (168, 0, 32), (168, 16, 0), (136, 20, 0),
    (80, 48, 0), (0, 120, 0), (0, 104, 0), (0, 88, 0),
    (0, 64, 88), (0, 0, 0), (0, 0, 0), (0, 0, 0),
    (188, 188, 188), (0, 120, 248), (0, 88, 248), (104, 68, 252),
    (216, 0, 204), (228, 0, 88), (248, 56, 0), (228, 92, 16),
    (172, 124, 0), (0, 184, 0), (0, 168, 0), (0, 168, 68),
    (0, 136, 136), (0, 0, 0), (0, 0, 0), (0, 0, 0),
    (248, 248, 248), (60, 188, 252), (104, 136, 252), (152, 120, 248),
    (248, 120, 248), (248, 88, 152), (248, 120, 88), (252, 160, 68),
    (248, 184, 0), (184, 248, 24), (88, 216, 84), (44, 236, 136),
    (0, 232, 216), (120, 120, 120), (0, 0, 0), (0, 0, 0),
    (252, 252, 252), (164, 228, 252), (184, 184, 248), (216, 184, 248),
    (248, 184, 248), (248, 164, 192), (240, 208, 176), (252, 224, 168),
    (248, 216, 120), (216, 248, 120), (184, 248, 184), (176, 248, 200),
    (152, 248, 240), (196, 196, 196),
]

# Game Boy — 4 shades of green
GAMEBOY_PALETTE = [
    (155, 188, 15), (139, 172, 15), (48, 98, 48), (15, 56, 15),
]

# SNES — fallback only. Real palettes should be extracted from the ROM.
SNES_DEFAULT_PALETTE = [
    (0, 0, 0), (128, 0, 0), (0, 128, 0), (128, 128, 0),
    (0, 0, 128), (128, 0, 128), (0, 128, 128), (192, 192, 192),
    (128, 128, 128), (255, 0, 0), (0, 255, 0), (255, 255, 0),
    (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255),
]

# GBA — fallback only. Real palettes should be extracted from the ROM.
GBA_DEFAULT_PALETTE = [
    (0, 0, 0), (248, 248, 248), (248, 0, 0), (0, 248, 0),
    (0, 0, 248), (248, 248, 0), (248, 0, 248), (0, 248, 248),
    (200, 200, 200), (160, 0, 0), (0, 160, 0), (0, 0, 160),
    (160, 160, 0), (160, 0, 160), (0, 160, 160), (80, 80, 80),
]

PALETTES = {
    "xcom": XCOM_PALETTE,
    "nes": NES_PALETTE,
    "gameboy": GAMEBOY_PALETTE,
    "snes": SNES_DEFAULT_PALETTE,
    "gba": GBA_DEFAULT_PALETTE,
}


# --- ROM Palette Extraction ---

def _snes_color_to_rgb(lo: int, hi: int) -> tuple[int, int, int]:
    """Convert SNES 15-bit BGR (0BBBBBGG GGGRRRRR) to 8-bit RGB."""
    val = lo | (hi << 8)
    r = (val & 0x1F) << 3
    g = ((val >> 5) & 0x1F) << 3
    b = ((val >> 10) & 0x1F) << 3
    return (r, g, b)


def _gba_color_to_rgb(lo: int, hi: int) -> tuple[int, int, int]:
    """Convert GBA 15-bit BGR (0BBBBBGG GGGRRRRR) to 8-bit RGB. Same format as SNES."""
    return _snes_color_to_rgb(lo, hi)


def extract_rom_palette(
    rom_path: str,
    offset: int,
    num_colors: int = 16,
    platform: str = "snes",
) -> list[tuple[int, int, int]]:
    """Extract a palette from a ROM file at a known byte offset.

    Args:
        rom_path: Path to the ROM file (.sfc, .smc, .gba, etc.)
        offset: Byte offset where the palette data starts.
        num_colors: Number of colors to extract (SNES: typically 16 per sub-palette).
        platform: "snes" or "gba" (both use 15-bit BGR, 2 bytes per color).

    Returns:
        List of (R, G, B) tuples in 0-255 range.
    """
    data = Path(rom_path).read_bytes()

    # .smc files have a 512-byte copier header; .sfc do not
    header_size = 0
    if rom_path.lower().endswith(".smc") and len(data) % 1024 == 512:
        header_size = 512

    actual_offset = header_size + offset
    if actual_offset + num_colors * 2 > len(data):
        raise ValueError(f"Offset 0x{offset:X} + {num_colors} colors exceeds ROM size")

    converter = _gba_color_to_rgb if platform == "gba" else _snes_color_to_rgb
    return [
        converter(data[actual_offset + i * 2], data[actual_offset + i * 2 + 1])
        for i in range(num_colors)
    ]


def scan_rom_palettes(
    rom_path: str,
    platform: str = "snes",
    min_unique: int = 6,
    max_results: int = 50,
) -> list[dict]:
    """Scan a ROM for blocks that look like valid palette data.

    Heuristic: palette blocks start with black (0,0,0), all high bytes
    have bit 7 clear (valid 15-bit color), and contain enough unique colors
    to be interesting.

    Returns:
        List of {"offset": int, "colors": [(R,G,B), ...]} sorted by
        color diversity (most unique first).
    """
    data = Path(rom_path).read_bytes()

    header_size = 0
    if rom_path.lower().endswith(".smc") and len(data) % 1024 == 512:
        header_size = 512

    block_size = 32  # 16 colors × 2 bytes
    converter = _gba_color_to_rgb if platform == "gba" else _snes_color_to_rgb
    candidates = []
    seen: set[tuple] = set()

    for pos in range(header_size, len(data) - block_size, 2):
        # First color must be black/transparent
        if data[pos] != 0 or data[pos + 1] != 0:
            continue

        # All high bytes must have bit 7 clear
        valid = True
        colors = []
        for i in range(16):
            hi = data[pos + i * 2 + 1]
            if hi & 0x80:
                valid = False
                break
            lo = data[pos + i * 2]
            colors.append(converter(lo, hi))

        if not valid:
            continue

        unique = len(set(colors))
        if unique < min_unique:
            continue

        key = tuple(colors)
        if key in seen:
            continue
        seen.add(key)

        candidates.append({
            "offset": pos - header_size,
            "colors": colors,
            "unique_count": unique,
        })

    # Sort by diversity — most unique colors first
    candidates.sort(key=lambda c: c["unique_count"], reverse=True)
    return candidates[:max_results]


def palette_to_hex(palette: list[tuple[int, int, int]]) -> list[str]:
    """Convert a palette to hex color strings."""
    return [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in palette]

# --- Preset Definitions ---

PRESETS = [
    {"id": "xcom-unit", "label": "X-COM Unit", "width": 32, "height": 40,
     "palette": "xcom", "max_colors": 256},
    {"id": "xcom-bigobs", "label": "X-COM BIGOBS", "width": 32, "height": 48,
     "palette": "xcom", "max_colors": 256},
    {"id": "xcom-ufopaedia", "label": "X-COM UFOpaedia", "width": 320, "height": 200,
     "palette": "xcom", "max_colors": 256},
    {"id": "xcom-terrain", "label": "X-COM Terrain", "width": 32, "height": 40,
     "palette": "xcom", "max_colors": 256},
    {"id": "snes-16", "label": "SNES 16x16", "width": 16, "height": 16,
     "palette": "snes", "max_colors": 16, "rom_extract": True},
    {"id": "snes-32", "label": "SNES 32x32", "width": 32, "height": 32,
     "palette": "snes", "max_colors": 16, "rom_extract": True},
    {"id": "nes-8", "label": "NES 8x8", "width": 8, "height": 8,
     "palette": "nes", "max_colors": 4},
    {"id": "gba-16", "label": "GBA 16x16", "width": 16, "height": 16,
     "palette": "gba", "max_colors": 16, "rom_extract": True},
    {"id": "gba-32", "label": "GBA 32x32", "width": 32, "height": 32,
     "palette": "gba", "max_colors": 16, "rom_extract": True},
    {"id": "gba-64", "label": "GBA 64x64", "width": 64, "height": 64,
     "palette": "gba", "max_colors": 16, "rom_extract": True},
    {"id": "custom", "label": "Custom", "width": 32, "height": 32,
     "palette": "custom", "max_colors": 256},
]


def get_palette(name: str) -> list[tuple[int, int, int]]:
    """Get a named palette."""
    return PALETTES.get(name, XCOM_PALETTE)


def get_preset(preset_id: str) -> dict | None:
    """Get a preset by ID."""
    return next((p for p in PRESETS if p["id"] == preset_id), None)


# --- Palette Quantization ---

def constrain_sprite(
    input_path: str,
    output_path: str,
    palette_name: str = "xcom",
    custom_palette: list[list[int]] | None = None,
    max_colors: int = 256,
    target_width: int = 32,
    target_height: int = 40,
    transparency_color: tuple[int, int, int] = (0, 0, 0),
    dithering: str = "none",
) -> dict:
    """Constrain an AI-generated image to game-ready indexed PNG.

    Pipeline: load → downscale (NEAREST) → detect transparency →
    quantize to palette → set index 0 transparent → save indexed PNG.
    """
    img = Image.open(input_path).convert("RGBA")

    # Step 1: Downscale to target resolution (NEAREST for pixel art)
    img_resized = img.resize((target_width, target_height), Image.NEAREST)

    # Step 2: Extract alpha for transparency detection
    alpha = np.array(img_resized)[:, :, 3]
    transparent_mask = alpha < 128

    # Step 3: Convert to RGB
    rgb = img_resized.convert("RGB")

    # Step 4: Get palette colors
    if custom_palette:
        palette = [tuple(c) for c in custom_palette]
    else:
        palette = get_palette(palette_name)

    palette = palette[:max_colors]

    # Step 5: Quantize
    if dithering == "floyd-steinberg":
        quantized = _quantize_to_palette(rgb, palette, dither=True)
    elif dithering == "ordered":
        quantized = _ordered_dither_quantize(rgb, palette)
    else:
        quantized = _quantize_to_palette(rgb, palette, dither=False)

    # Step 6: Apply transparency mask (set to index 0)
    pixels = np.array(quantized)
    pixels[transparent_mask] = 0
    result = Image.fromarray(pixels, mode="P")

    # Build the full 256-entry palette
    flat_pal = []
    for r, g, b in palette:
        flat_pal.extend([r, g, b])
    flat_pal.extend([0] * (768 - len(flat_pal)))
    result.putpalette(flat_pal)

    # Step 7: Save indexed PNG with transparency on index 0
    result.save(output_path, transparency=0)

    unique_colors = len(set(pixels.flatten()) - {0})
    return {
        "width": target_width,
        "height": target_height,
        "colors_used": unique_colors,
        "transparent_pixels": int(transparent_mask.sum()),
        "palette": palette_name,
        "dithering": dithering,
    }


def _quantize_to_palette(
    img: Image.Image,
    palette: list[tuple[int, int, int]],
    dither: bool = False,
) -> Image.Image:
    """Quantize RGB image to a fixed palette using PIL."""
    # Create a palette image for quantization
    pal_img = Image.new("P", (1, 1))
    flat = []
    for r, g, b in palette:
        flat.extend([r, g, b])
    flat.extend([0] * (768 - len(flat)))
    pal_img.putpalette(flat)

    dither_mode = Image.Dither.FLOYDSTEINBERG if dither else Image.Dither.NONE
    return img.quantize(palette=pal_img, dither=dither_mode)


def _ordered_dither_quantize(
    img: Image.Image,
    palette: list[tuple[int, int, int]],
) -> Image.Image:
    """Ordered (Bayer) dithering then snap to nearest palette color."""
    bayer_4x4 = np.array([
        [0, 8, 2, 10],
        [12, 4, 14, 6],
        [3, 11, 1, 9],
        [15, 7, 13, 5],
    ], dtype=float) / 16.0 - 0.5

    arr = np.array(img).astype(float)
    h, w, _ = arr.shape

    bayer = np.tile(bayer_4x4, (h // 4 + 1, w // 4 + 1))[:h, :w]
    spread = 32
    for c in range(3):
        arr[:, :, c] += bayer * spread
    arr = np.clip(arr, 0, 255).astype(np.uint8)

    # Snap each pixel to nearest palette color
    pal_arr = np.array(palette, dtype=np.uint8)
    flat = arr.reshape(-1, 3).astype(np.int32)
    pal_int = pal_arr.astype(np.int32)
    # Euclidean distance
    diff = flat[:, None, :] - pal_int[None, :, :]
    dist = (diff * diff).sum(axis=2)
    indices = dist.argmin(axis=1).reshape(h, w).astype(np.uint8)

    result = Image.fromarray(indices, mode="P")
    flat_pal = []
    for r, g, b in palette:
        flat_pal.extend([r, g, b])
    flat_pal.extend([0] * (768 - len(flat_pal)))
    result.putpalette(flat_pal)
    return result


# --- Sprite Sheet Composition ---

def compose_sheet(
    sprites: list[dict],
    cell_width: int,
    cell_height: int,
    columns: int = 8,
    output_path: str = "",
) -> dict:
    """Compose individual sprites into a sprite sheet.

    sprites: [{"path": str, "slot": int}, ...]
    """
    if not sprites:
        raise ValueError("No sprites to compose")

    max_slot = max(s["slot"] for s in sprites)
    rows = (max_slot // columns) + 1
    sheet_w = columns * cell_width
    sheet_h = rows * cell_height

    sheet = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))

    for s in sprites:
        img = Image.open(s["path"]).convert("RGBA")
        img = img.resize((cell_width, cell_height), Image.NEAREST)
        col = s["slot"] % columns
        row = s["slot"] // columns
        sheet.paste(img, (col * cell_width, row * cell_height))

    sheet.save(output_path)
    return {
        "width": sheet_w,
        "height": sheet_h,
        "cells": len(sprites),
        "columns": columns,
        "rows": rows,
    }


# --- Preview helpers ---

def sprite_to_data_url(path: str, scale: int = 8) -> str:
    """Load a sprite and return a base64 data URL scaled up for preview."""
    import base64

    img = Image.open(path)
    if scale > 1:
        w, h = img.size
        img = img.resize((w * scale, h * scale), Image.NEAREST)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{b64}"
