"""SNES Zelda: A Link to the Past — sprite extractor.

Extracts Link's sprites, enemy sprites, and item graphics
from the US release of ALTTP.

SNES 4bpp planar tile format:
  - 8x8 pixels per tile, 32 bytes per tile
  - Bytes 0-15: bitplanes 0+1 (interleaved row by row)
  - Bytes 16-31: bitplanes 2+3 (interleaved row by row)
"""

from __future__ import annotations

import io
import struct

from PIL import Image

from . import AssetInfo, register


# SNES ROM header detection
ZELDA_TITLE = "THE LEGEND OF ZELDA"

# Sprite sheet locations in the US ROM (no header, LoROM)
SPRITE_SHEETS = {
    "link": {
        "name": "Link",
        "offset": 0x80000,
        "length": 0x7000,  # 28KB
        "palette_offset": 0xDD308,
        "tile_width": 16,   # tiles per row in the sheet
        "description": "Link's movement, action, and item sprites",
    },
    "enemies1": {
        "name": "Enemies (Sheet 1)",
        "offset": 0xC0000,
        "length": 0x8000,
        "palette_offset": 0xDD218,
        "tile_width": 16,
        "description": "Overworld enemies and NPCs",
    },
    "enemies2": {
        "name": "Enemies (Sheet 2)",
        "offset": 0xC8000,
        "length": 0x8000,
        "palette_offset": 0xDD218,
        "tile_width": 16,
        "description": "Dungeon enemies",
    },
    "enemies3": {
        "name": "Enemies (Sheet 3)",
        "offset": 0xD0000,
        "length": 0x8000,
        "palette_offset": 0xDD218,
        "tile_width": 16,
        "description": "Bosses and special enemies",
    },
    "enemies4": {
        "name": "Enemies (Sheet 4)",
        "offset": 0xD8000,
        "length": 0x8000,
        "palette_offset": 0xDD218,
        "tile_width": 16,
        "description": "Additional enemies and effects",
    },
}

# Known Link sprite frames (16x16 = 2x2 tiles each)
# Format: (name, tile_index_top_left) — tiles are in sheet order
LINK_FRAMES = [
    ("Link Walk Down 1", 0),
    ("Link Walk Down 2", 2),
    ("Link Walk Down 3", 4),
    ("Link Walk Up 1", 32),
    ("Link Walk Up 2", 34),
    ("Link Walk Up 3", 36),
    ("Link Walk Left 1", 64),
    ("Link Walk Left 2", 66),
    ("Link Walk Left 3", 68),
    ("Link Stand Down", 6),
    ("Link Stand Up", 38),
    ("Link Stand Left", 70),
    ("Link Sword Down 1", 8),
    ("Link Sword Down 2", 10),
    ("Link Sword Up 1", 40),
    ("Link Sword Up 2", 42),
    ("Link Sword Left 1", 72),
    ("Link Sword Left 2", 74),
    ("Link Push Down", 12),
    ("Link Push Up", 44),
    ("Link Push Left", 76),
    ("Link Carry Down", 14),
    ("Link Carry Up", 46),
    ("Link Carry Left", 78),
    ("Link Fall", 96),
    ("Link Swim Down 1", 128),
    ("Link Swim Down 2", 130),
    ("Link Swim Up 1", 160),
    ("Link Swim Left 1", 192),
]


def decode_snes_4bpp_tile(data: bytes, offset: int) -> list[int]:
    """Decode a single 8x8 SNES 4bpp planar tile into pixel indices.

    SNES 4bpp planar format (32 bytes per tile):
      Bytes  0-15: rows 0-7, bitplanes 0 and 1 interleaved
      Bytes 16-31: rows 0-7, bitplanes 2 and 3 interleaved

    Returns 64 pixel indices (0-15).
    """
    pixels = [0] * 64

    for row in range(8):
        # Bitplanes 0 and 1
        bp0 = data[offset + row * 2]
        bp1 = data[offset + row * 2 + 1]
        # Bitplanes 2 and 3
        bp2 = data[offset + 16 + row * 2]
        bp3 = data[offset + 16 + row * 2 + 1]

        for col in range(8):
            bit = 7 - col
            idx = ((bp0 >> bit) & 1) | \
                  (((bp1 >> bit) & 1) << 1) | \
                  (((bp2 >> bit) & 1) << 2) | \
                  (((bp3 >> bit) & 1) << 3)
            pixels[row * 8 + col] = idx

    return pixels


def read_snes_palette(data: bytes, offset: int, count: int = 16) -> list[tuple[int, int, int]]:
    """Read SNES 15-bit BGR555 palette."""
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


def render_tile_sheet(rom_data: bytes, sheet_offset: int, sheet_length: int,
                      palette: list[tuple[int, int, int]],
                      tiles_per_row: int = 16) -> bytes:
    """Render an entire tile sheet as a PNG.

    Arranges 8x8 tiles in a grid, tiles_per_row wide.
    """
    tile_count = sheet_length // 32
    rows = (tile_count + tiles_per_row - 1) // tiles_per_row
    width = tiles_per_row * 8
    height = rows * 8

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    for t in range(tile_count):
        offset = sheet_offset + t * 32
        if offset + 32 > len(rom_data):
            break

        pixels = decode_snes_4bpp_tile(rom_data, offset)
        tx = (t % tiles_per_row) * 8
        ty = (t // tiles_per_row) * 8

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
    return buf.getvalue()


def render_16x16_sprite(rom_data: bytes, sheet_offset: int,
                        tile_index: int, tiles_per_row: int,
                        palette: list[tuple[int, int, int]]) -> bytes:
    """Render a 16x16 sprite (2x2 tiles) as a PNG.

    tile_index is the top-left tile in the sheet grid.
    """
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))

    # 2x2 tile arrangement
    for ty_off in range(2):
        for tx_off in range(2):
            t = tile_index + tx_off + ty_off * tiles_per_row
            offset = sheet_offset + t * 32
            if offset + 32 > len(rom_data):
                continue

            pixels = decode_snes_4bpp_tile(rom_data, offset)
            bx = tx_off * 8
            by = ty_off * 8

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


def alttp_decompress(src_data: bytes, src_offset: int, max_output: int = 0x2000) -> bytes:
    """ALTTP custom compression decoder.

    Ported from snesrev/zelda3 load_gfx.c Decompress().
    Commands encoded in first byte, 0xFF = end of stream.
    """
    dst = bytearray()
    pos = src_offset
    safety = 0
    while pos < len(src_data) and safety < 50000 and len(dst) < max_output:
        safety += 1
        cmd = src_data[pos]; pos += 1
        if cmd == 0xFF:
            break
        if (cmd & 0xE0) != 0xE0:
            length = (cmd & 0x1F) + 1
            cmd_type = cmd & 0xE0
        else:
            if pos >= len(src_data):
                break
            length = src_data[pos] + ((cmd & 0x03) << 8) + 1
            pos += 1
            cmd_type = (cmd << 3) & 0xE0
        if cmd_type == 0x00:
            for _ in range(length):
                if pos >= len(src_data):
                    return bytes(dst)
                dst.append(src_data[pos]); pos += 1
        elif cmd_type & 0x80:
            if pos + 1 >= len(src_data):
                break
            offs = src_data[pos] | (src_data[pos + 1] << 8); pos += 2
            for _ in range(length):
                dst.append(dst[offs] if offs < len(dst) else 0)
                offs += 1
        elif not (cmd_type & 0x40):
            if pos >= len(src_data):
                break
            v = src_data[pos]; pos += 1
            dst.extend([v] * length)
        elif not (cmd_type & 0x20):
            if pos + 1 >= len(src_data):
                break
            lo, hi = src_data[pos], src_data[pos + 1]; pos += 2
            for i in range(length):
                dst.append(lo if i % 2 == 0 else hi)
        else:
            if pos >= len(src_data):
                break
            v = src_data[pos]; pos += 1
            for _ in range(length):
                dst.append(v & 0xFF)
                v += 1
    return bytes(dst)


def find_compressed_sheets(rom_data: bytes,
                           search_start: int = 0x40000,
                           search_end: int = 0xE0000,
                           target_size: int = 0x600) -> list[tuple[int, int]]:
    """Scan ROM for compressed data that decompresses to target_size bytes.

    Returns list of (offset, non_zero_count) sorted by offset.
    """
    results = []
    last = -100
    for off in range(search_start, min(search_end, len(rom_data) - 4), 4):
        if rom_data[off] == 0xFF or rom_data[off] == 0x00:
            continue
        if off - last < 8:
            continue
        try:
            data = alttp_decompress(rom_data, off, target_size + 0x100)
            if len(data) == target_size:
                nz = sum(1 for b in data if b != 0)
                if nz > 200:
                    results.append((off, nz))
                    last = off
        except (IndexError, OverflowError):
            continue
    return results


def decode_3bpp_tile(data: bytes, offset: int) -> list[int]:
    """Decode an 8x8 3bpp tile (24 bytes) into pixel indices (0-7)."""
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


def render_3bpp_sheet(tile_data: bytes, palette: list[tuple[int, int, int]],
                      tiles_per_row: int = 16) -> bytes:
    """Render decompressed 3bpp tile data as a PNG."""
    bpt = 24
    tile_count = len(tile_data) // bpt
    rows = max(1, (tile_count + tiles_per_row - 1) // tiles_per_row)
    width = tiles_per_row * 8
    height = rows * 8

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    for t in range(tile_count):
        offset = t * bpt
        if offset + bpt > len(tile_data):
            break
        if not any(tile_data[offset:offset + bpt]):
            continue
        pixels = decode_3bpp_tile(tile_data, offset)
        tx = (t % tiles_per_row) * 8
        ty = (t // tiles_per_row) * 8
        for py in range(8):
            for px in range(8):
                idx = pixels[py * 8 + px]
                if idx == 0 or idx >= len(palette):
                    continue
                r, g, b = palette[idx]
                img.putpixel((tx + px, ty + py), (r, g, b, 255))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@register
class SNESZeldaExtractor:
    console = "snes"
    description = "Super NES — The Legend of Zelda: A Link to the Past (USA)"

    def __init__(self):
        self.game = ""

    def detect(self, rom_data: bytes) -> bool:
        """Check if this is Zelda ALTTP (US)."""
        if len(rom_data) < 0x8000:
            return False
        # LoROM title at 0x7FC0
        title = rom_data[0x7FC0:0x7FD5].decode("ascii", errors="replace").strip()
        if ZELDA_TITLE in title:
            self.game = "The Legend of Zelda: A Link to the Past"
            return True
        return False

    def get_categories(self) -> list[str]:
        return [
            "Link Sprites",
            "Link Sheet",
            "Compressed Sprites",
            "Compressed Terrain",
        ]

    def extract_all(self, rom_data: bytes, on_progress=None) -> list[AssetInfo]:
        """Extract Link's individual frames + full sprite sheets."""
        assets = []

        if on_progress:
            on_progress(5, "Reading palettes...")

        # Link's palette
        link_info = SPRITE_SHEETS["link"]
        link_palette = read_snes_palette(rom_data, link_info["palette_offset"], 16)

        if on_progress:
            on_progress(10, "Extracting Link sprites...")

        # Individual Link frames (16x16)
        for i, (name, tile_idx) in enumerate(LINK_FRAMES):
            try:
                png = render_16x16_sprite(
                    rom_data, link_info["offset"],
                    tile_idx, link_info["tile_width"],
                    link_palette,
                )
                assets.append(AssetInfo(
                    id=f"link_{i:03d}",
                    name=name,
                    category="Link Sprites",
                    width=16, height=16,
                    data=png,
                    palette=link_palette,
                    meta={"frame": i, "sprite_name": name},
                ))
            except Exception:
                pass

            if on_progress and i % 10 == 0:
                pct = 10 + int((i / len(LINK_FRAMES)) * 30)
                on_progress(pct, f"Extracting Link frame {i + 1}/{len(LINK_FRAMES)}")

        if on_progress:
            on_progress(40, "Rendering Link sheet...")

        # Full Link tile sheet (uncompressed 4bpp)
        try:
            link_info = SPRITE_SHEETS["link"]
            png = render_tile_sheet(
                rom_data, link_info["offset"], link_info["length"],
                link_palette, link_info["tile_width"],
            )
            assets.append(AssetInfo(
                id="sheet_link",
                name="Link (Full Sheet)",
                category="Link Sheet",
                width=link_info["tile_width"] * 8,
                height=((link_info["length"] // 32 + link_info["tile_width"] - 1) // link_info["tile_width"]) * 8,
                data=png,
                palette=link_palette,
                meta={"sheet": "link", "description": link_info["description"]},
            ))
        except Exception:
            pass

        if on_progress:
            on_progress(45, "Decompressing sprite sheets...")

        # All 16 sprite palette groups (8 colors each for 3bpp)
        sprite_palettes = []
        for i in range(16):
            pal_off = 0xDD218 + i * 30
            if pal_off + 16 <= len(rom_data):
                pal = read_snes_palette(rom_data, pal_off, 8)
                sprite_palettes.append((pal_off, pal))

        compressed = find_compressed_sheets(rom_data)

        for idx, (off, nz) in enumerate(compressed):
            if on_progress and idx % 10 == 0:
                pct = 45 + int((idx / max(1, len(compressed))) * 50)
                on_progress(pct, f"Decompressing sheet {idx + 1}/{len(compressed)}")

            try:
                tile_data = alttp_decompress(rom_data, off)
                fill_ratio = nz / len(tile_data)
                is_sprite = fill_ratio > 0.5
                category = "Compressed Sprites" if is_sprite else "Compressed Terrain"

                # Try all palettes, pick the one with most color variety in output
                best_png = None
                best_pal = sprite_palettes[0][1] if sprite_palettes else link_palette
                best_score = 0

                for pal_off, pal in sprite_palettes:
                    png = render_3bpp_sheet(tile_data, pal, 16)
                    # Score: larger PNG file = more distinct pixels rendered
                    # (compressed PNG size correlates with visual complexity)
                    score = len(png)
                    if score > best_score:
                        best_score = score
                        best_png = png
                        best_pal = pal

                if best_png is None:
                    best_png = render_3bpp_sheet(tile_data, link_palette[:8], 16)

                assets.append(AssetInfo(
                    id=f"compressed_{idx:03d}",
                    name=f"Sheet 0x{off:06X}",
                    category=category,
                    width=128,
                    height=max(1, (len(tile_data) // 24 + 15) // 16) * 8,
                    data=best_png,
                    palette=best_pal,
                    meta={
                        "offset": f"0x{off:06X}",
                        "compressed": True,
                        "fill_ratio": round(fill_ratio, 2),
                        "decompressed_size": len(tile_data),
                    },
                ))
            except Exception:
                pass

        if on_progress:
            on_progress(100, f"Extracted {len(assets)} sprites")

        return assets
