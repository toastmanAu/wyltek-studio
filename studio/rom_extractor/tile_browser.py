"""Generic ROM Tile Browser — scan any ROM for tile graphics.

Renders raw tile data at configurable bit depths (2bpp, 3bpp, 4bpp, 8bpp)
across the entire ROM. User browses pages, selects regions, assigns palettes,
and exports sprites.

This is the general-purpose solution: no game-specific knowledge needed.
"""

from __future__ import annotations

import io
from PIL import Image


# Tile decode functions for each bit depth

def decode_2bpp_tile(data: bytes, offset: int) -> list[int]:
    """Decode an 8x8 2bpp tile (16 bytes). NES/GB/SNES BG format.
    2 colors per pixel, 4 possible values (0-3).
    Bitplane 0 and 1 interleaved row by row.
    """
    pixels = [0] * 64
    for row in range(8):
        bp0 = data[offset + row * 2] if offset + row * 2 < len(data) else 0
        bp1 = data[offset + row * 2 + 1] if offset + row * 2 + 1 < len(data) else 0
        for col in range(8):
            bit = 7 - col
            pixels[row * 8 + col] = ((bp0 >> bit) & 1) | (((bp1 >> bit) & 1) << 1)
    return pixels


def decode_3bpp_tile(data: bytes, offset: int) -> list[int]:
    """Decode an 8x8 3bpp tile (24 bytes). SNES Mode 7 format.
    Bitplanes 0+1 interleaved (16 bytes), then bitplane 2 (8 bytes).
    """
    pixels = [0] * 64
    for row in range(8):
        bp0 = data[offset + row * 2] if offset + row * 2 < len(data) else 0
        bp1 = data[offset + row * 2 + 1] if offset + row * 2 + 1 < len(data) else 0
        bp2 = data[offset + 16 + row] if offset + 16 + row < len(data) else 0
        for col in range(8):
            bit = 7 - col
            pixels[row * 8 + col] = (
                ((bp0 >> bit) & 1) |
                (((bp1 >> bit) & 1) << 1) |
                (((bp2 >> bit) & 1) << 2)
            )
    return pixels


def decode_4bpp_tile(data: bytes, offset: int) -> list[int]:
    """Decode an 8x8 4bpp tile (32 bytes). SNES sprite format.
    Bitplanes 0+1 interleaved (16 bytes), bitplanes 2+3 interleaved (16 bytes).
    """
    pixels = [0] * 64
    for row in range(8):
        bp0 = data[offset + row * 2] if offset + row * 2 < len(data) else 0
        bp1 = data[offset + row * 2 + 1] if offset + row * 2 + 1 < len(data) else 0
        bp2 = data[offset + 16 + row * 2] if offset + 16 + row * 2 < len(data) else 0
        bp3 = data[offset + 16 + row * 2 + 1] if offset + 16 + row * 2 + 1 < len(data) else 0
        for col in range(8):
            bit = 7 - col
            pixels[row * 8 + col] = (
                ((bp0 >> bit) & 1) |
                (((bp1 >> bit) & 1) << 1) |
                (((bp2 >> bit) & 1) << 2) |
                (((bp3 >> bit) & 1) << 3)
            )
    return pixels


def decode_8bpp_tile(data: bytes, offset: int) -> list[int]:
    """Decode an 8x8 8bpp tile (64 bytes). Linear byte-per-pixel."""
    pixels = [0] * 64
    for i in range(64):
        if offset + i < len(data):
            pixels[i] = data[offset + i]
    return pixels


def decode_4bpp_linear_tile(data: bytes, offset: int) -> list[int]:
    """Decode an 8x8 4bpp linear tile (32 bytes). GBA format.
    Each byte = 2 pixels. Low nibble first.
    """
    pixels = [0] * 64
    for i in range(32):
        if offset + i >= len(data):
            break
        byte = data[offset + i]
        pixels[i * 2] = byte & 0x0F
        pixels[i * 2 + 1] = (byte >> 4) & 0x0F
    return pixels


DECODERS = {
    "2bpp": (decode_2bpp_tile, 16, 4),      # func, bytes_per_tile, max_colors
    "3bpp": (decode_3bpp_tile, 24, 8),
    "4bpp": (decode_4bpp_tile, 32, 16),
    "4bpp_linear": (decode_4bpp_linear_tile, 32, 16),
    "8bpp": (decode_8bpp_tile, 64, 256),
}


def generate_default_palette(max_colors: int) -> list[tuple[int, int, int]]:
    """Generate a greyscale palette for preview when no palette is specified."""
    step = 255 // max(1, max_colors - 1)
    return [(i * step, i * step, i * step) for i in range(max_colors)]


def read_snes_palette(data: bytes, offset: int, count: int = 16) -> list[tuple[int, int, int]]:
    """Read SNES/GBA 15-bit BGR555 palette."""
    palette = []
    for i in range(count):
        if offset + i * 2 + 1 >= len(data):
            palette.append((0, 0, 0))
            continue
        color = data[offset + i * 2] | (data[offset + i * 2 + 1] << 8)
        r = (color & 0x1F) << 3
        g = ((color >> 5) & 0x1F) << 3
        b = ((color >> 10) & 0x1F) << 3
        palette.append((r, g, b))
    return palette


def scan_palettes(rom_data: bytes, max_colors: int = 16) -> list[dict]:
    """Scan ROM for plausible palette locations.

    Returns list of {offset, colors, score} sorted by score descending.
    A good palette has varied colors, no out-of-range values (>0x7FFF for 15-bit).
    """
    results = []
    pal_size = max_colors * 2  # 15-bit = 2 bytes per color

    for off in range(0, len(rom_data) - pal_size, 2):
        colors = []
        valid = True
        for i in range(max_colors):
            c = rom_data[off + i * 2] | (rom_data[off + i * 2 + 1] << 8)
            if c > 0x7FFF:
                valid = False
                break
            r = (c & 0x1F) << 3
            g = ((c >> 5) & 0x1F) << 3
            b = ((c >> 10) & 0x1F) << 3
            colors.append((r, g, b))

        if not valid or len(colors) < max_colors:
            continue

        # Score: prefer palettes with color variety
        unique = len(set(colors))
        has_dark = any(sum(c) < 100 for c in colors)
        has_light = any(sum(c) > 500 for c in colors)
        has_color = any(max(c) - min(c) > 50 for c in colors)

        score = unique
        if has_dark and has_light:
            score += 3
        if has_color:
            score += 2

        if score >= 6:  # Only keep promising palettes
            results.append({
                "offset": off,
                "colors": colors,
                "score": score,
            })

    results.sort(key=lambda p: p["score"], reverse=True)
    return results[:200]  # Top 200 candidates


def render_tile_page(
    rom_data: bytes,
    start_offset: int,
    bpp: str = "4bpp",
    cols: int = 16,
    rows: int = 16,
    palette: list[tuple[int, int, int]] | None = None,
) -> tuple[bytes, dict]:
    """Render a page of tiles from a ROM at the given offset.

    Returns (png_bytes, info_dict).
    """
    decoder, bytes_per_tile, max_colors = DECODERS[bpp]
    tile_count = cols * rows

    if palette is None:
        palette = generate_default_palette(max_colors)

    width = cols * 8
    height = rows * 8
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    non_empty = 0
    for t in range(tile_count):
        offset = start_offset + t * bytes_per_tile
        if offset + bytes_per_tile > len(rom_data):
            break

        # Skip empty tiles
        tile_data = rom_data[offset:offset + bytes_per_tile]
        if not any(tile_data):
            continue

        non_empty += 1
        pixels = decoder(rom_data, offset)
        tx = (t % cols) * 8
        ty = (t // cols) * 8

        for py in range(8):
            for px in range(8):
                idx = pixels[py * 8 + px]
                if idx == 0:
                    continue  # transparent
                if idx < len(palette):
                    r, g, b = palette[idx]
                    img.putpixel((tx + px, ty + py), (r, g, b, 255))

    buf = io.BytesIO()
    img.save(buf, format="PNG")

    return buf.getvalue(), {
        "offset": start_offset,
        "bpp": bpp,
        "tiles": tile_count,
        "non_empty": non_empty,
        "bytes_per_tile": bytes_per_tile,
        "page_bytes": tile_count * bytes_per_tile,
        "width": width,
        "height": height,
    }


def extract_region(
    rom_data: bytes,
    start_offset: int,
    tile_x: int,
    tile_y: int,
    width_tiles: int,
    height_tiles: int,
    cols: int,
    bpp: str = "4bpp",
    palette: list[tuple[int, int, int]] | None = None,
) -> bytes:
    """Extract a rectangular region of tiles as a PNG.

    tile_x, tile_y: top-left tile position in the page grid
    width_tiles, height_tiles: size of selection in tiles
    cols: tiles per row in the page
    """
    decoder, bytes_per_tile, max_colors = DECODERS[bpp]

    if palette is None:
        palette = generate_default_palette(max_colors)

    width = width_tiles * 8
    height = height_tiles * 8
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    for ty in range(height_tiles):
        for tx in range(width_tiles):
            # Map grid position to tile index in the page
            page_tile = (tile_y + ty) * cols + (tile_x + tx)
            offset = start_offset + page_tile * bytes_per_tile
            if offset + bytes_per_tile > len(rom_data):
                continue

            pixels = decoder(rom_data, offset)
            bx = tx * 8
            by = ty * 8

            for py in range(8):
                for px in range(8):
                    idx = pixels[py * 8 + px]
                    if idx == 0:
                        continue
                    if idx < len(palette):
                        r, g, b = palette[idx]
                        img.putpixel((bx + px, by + py), (r, g, b, 255))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def survey_rom(rom_data: bytes, bpp: str = "4bpp", sample_interval: int = 0x4000) -> list[dict]:
    """Quick survey of the ROM — sample tile pages at regular intervals.

    Returns list of {offset, non_empty_ratio, preview_available} for pages
    with meaningful tile data.
    """
    _, bytes_per_tile, _ = DECODERS[bpp]
    tiles_per_page = 256  # 16x16 grid
    page_bytes = tiles_per_page * bytes_per_tile

    results = []
    for off in range(0, len(rom_data) - page_bytes, sample_interval):
        non_empty = 0
        for t in range(tiles_per_page):
            tile_off = off + t * bytes_per_tile
            if any(rom_data[tile_off:tile_off + bytes_per_tile]):
                non_empty += 1

        ratio = non_empty / tiles_per_page
        if ratio > 0.1:  # At least 10% non-empty
            results.append({
                "offset": off,
                "hex_offset": f"0x{off:06X}",
                "non_empty": non_empty,
                "ratio": round(ratio, 2),
            })

    return results
