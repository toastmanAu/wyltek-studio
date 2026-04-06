"""Generic SNES ROM extractor — works on any SNES game.

Scans the entire ROM for:
1. Uncompressed 4bpp tile data (spatial coherence scoring)
2. Nintendo LC_LZ2 compressed sprite sheets (decompress + validate)
3. Palette auto-detection

No game-specific knowledge needed.
"""

from __future__ import annotations

import io

from PIL import Image

from . import AssetInfo, register
from .snes_zelda import (
    alttp_decompress,
    find_compressed_sheets,
    decode_3bpp_tile,
    decode_snes_4bpp_tile,
    read_snes_palette,
    render_3bpp_sheet,
)


def square_decompress(data: bytes, offset: int, max_output: int = 0x10000) -> bytes:
    """Squaresoft LZ decompression (Chrono Trigger, Secret of Mana, FF4/5/6).

    Bit-flag header bytes control literal vs back-reference for each of 8 items.
    """
    dst = bytearray()
    pos = offset
    while pos < len(data) and len(dst) < max_output:
        flags = data[pos]; pos += 1
        for bit in range(8):
            if pos >= len(data) or len(dst) >= max_output:
                return bytes(dst)
            if flags & (0x80 >> bit):
                if pos + 1 >= len(data):
                    return bytes(dst)
                b1 = data[pos]; b2 = data[pos + 1]; pos += 2
                length = ((b1 >> 3) & 0x1F) + 3
                disp = ((b1 & 0x07) << 8) | b2
                if disp == 0:
                    return bytes(dst)
                src_pos = len(dst) - disp
                for _ in range(length):
                    dst.append(dst[src_pos] if 0 <= src_pos < len(dst) else 0)
                    src_pos += 1
            else:
                dst.append(data[pos]); pos += 1
    return bytes(dst)


def konami_decompress(data: bytes, offset: int, max_output: int = 0x10000) -> bytes:
    """Konami SNES decompression (Castlevania, Contra III, TMNT, Gradius III).

    Control byte: if bit7=0, literal run (length = byte+1).
    If bit7=1, back-reference: next byte = offset back, length = (ctrl & 0x7F) + 3.
    Stream ends when output reaches expected size or data exhausted.
    """
    dst = bytearray()
    pos = offset
    while pos < len(data) and len(dst) < max_output:
        ctrl = data[pos]; pos += 1
        if ctrl == 0:
            break  # end marker
        if ctrl & 0x80:
            # Back-reference
            length = (ctrl & 0x7F) + 3
            if pos >= len(data):
                break
            disp = data[pos]; pos += 1
            if disp == 0:
                break
            for _ in range(length):
                src = len(dst) - disp
                dst.append(dst[src] if 0 <= src < len(dst) else 0)
        else:
            # Literal run
            length = ctrl + 1
            for _ in range(length):
                if pos >= len(data):
                    return bytes(dst)
                dst.append(data[pos]); pos += 1
    return bytes(dst)


def capcom_decompress(data: bytes, offset: int, max_output: int = 0x10000) -> bytes:
    """Capcom SNES decompression (Street Fighter II, Mega Man X, Breath of Fire).

    Similar to Nintendo LC_LZ2 but with different command encoding:
    Byte 0: if top 2 bits = 00: literal run (lower 6 bits = length-1)
            if top 2 bits = 01: RLE (lower 6 bits = length-1, next byte = value)
            if top 2 bits = 10: back-ref (lower 6 bits = length-1, next 2 bytes = offset)
            if top 2 bits = 11: end marker
    """
    dst = bytearray()
    pos = offset
    while pos < len(data) and len(dst) < max_output:
        cmd = data[pos]; pos += 1
        mode = (cmd >> 6) & 0x03
        length = (cmd & 0x3F) + 1

        if mode == 3:
            break  # end
        elif mode == 0:
            # Literal
            for _ in range(length):
                if pos >= len(data):
                    return bytes(dst)
                dst.append(data[pos]); pos += 1
        elif mode == 1:
            # RLE
            if pos >= len(data):
                break
            v = data[pos]; pos += 1
            dst.extend([v] * length)
        elif mode == 2:
            # Back-reference
            if pos + 1 >= len(data):
                break
            off_lo = data[pos]; off_hi = data[pos + 1]; pos += 2
            src_off = off_lo | (off_hi << 8)
            for _ in range(length):
                dst.append(dst[src_off] if src_off < len(dst) else 0)
                src_off += 1
    return bytes(dst)


def find_generic_compressed(rom_data: bytes,
                            decompress_fn,
                            name: str,
                            search_start: int = 0x10000,
                            search_end: int = 0x300000) -> list[tuple[int, int]]:
    """Generic scan for compressed data using a given decompressor."""
    results = []
    last = -100
    end = min(search_end, len(rom_data) - 4)
    for off in range(search_start, end, 0x100):
        if rom_data[off] == 0x00 or rom_data[off] == 0xFF:
            continue
        if off - last < 0x80:
            continue
        try:
            data = decompress_fn(rom_data, off, 0x2000)
            size = len(data)
            if 0x400 <= size <= 0x1800:
                nz = sum(1 for b in data if b != 0)
                ratio = nz / size
                if 0.15 < ratio < 0.9:
                    results.append((off, size))
                    last = off
        except (IndexError, OverflowError):
            continue
    return results


def find_square_compressed(rom_data: bytes,
                           search_start: int = 0x10000,
                           search_end: int = 0x300000) -> list[tuple[int, int]]:
    """Scan ROM for Squaresoft-compressed data blocks.

    Returns list of (offset, decompressed_size) for blocks that decompress
    to reasonable tile-data sizes.
    """
    results = []
    last = -100
    end = min(search_end, len(rom_data) - 4)
    for off in range(search_start, end, 0x100):
        if rom_data[off] == 0x00 or rom_data[off] == 0xFF:
            continue
        if off - last < 0x80:
            continue
        try:
            data = square_decompress(rom_data, off, 0x2000)
            size = len(data)
            if 0x400 <= size <= 0x1800:
                nz = sum(1 for b in data if b != 0)
                ratio = nz / size
                if 0.15 < ratio < 0.9:
                    results.append((off, size))
                    last = off
        except (IndexError, OverflowError):
            continue
    return results


def find_uncompressed_4bpp(rom_data: bytes,
                           interval: int = 0x2000,
                           min_coherence: float = 18.0) -> list[tuple[int, float]]:
    """Find regions of uncompressed 4bpp tile data by spatial coherence scoring.

    Real tiles have adjacent pixels that correlate (smooth gradients, outlines).
    Random/compressed data has high entropy and low coherence.

    Returns list of (offset, coherence_score) sorted by score descending.
    """
    results = []
    for off in range(0, len(rom_data) - 0x2000, interval):
        score = 0.0
        tiles_checked = 0
        for t in range(64):  # Sample 64 tiles per page
            tile_off = off + t * 32
            if tile_off + 32 > len(rom_data):
                break
            if not any(rom_data[tile_off:tile_off + 32]):
                continue
            tiles_checked += 1
            pixels = decode_snes_4bpp_tile(rom_data, tile_off)
            # Horizontal coherence
            same_h = sum(1 for i in range(63)
                         if pixels[i] == pixels[i + 1] and pixels[i] > 0)
            # Vertical coherence
            same_v = sum(1 for y in range(7) for x in range(8)
                         if pixels[y * 8 + x] == pixels[(y + 1) * 8 + x]
                         and pixels[y * 8 + x] > 0)
            score += same_h + same_v

        if tiles_checked > 0:
            score /= tiles_checked
        if score >= min_coherence:
            results.append((off, score))

    results.sort(key=lambda x: -x[1])
    return results


def find_palettes(rom_data: bytes, max_colors: int = 16,
                  max_results: int = 30) -> list[tuple[int, list[tuple[int, int, int]]]]:
    """Find plausible 15-bit SNES palettes in the ROM.

    Scores palettes by color variety, presence of darks/lights, and saturation.
    Returns list of (offset, colors) sorted by quality.
    """
    results = []
    pal_size = max_colors * 2

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

        unique = len(set(colors))
        has_dark = any(sum(c) < 100 for c in colors)
        has_light = any(sum(c) > 500 for c in colors)
        has_color = any(max(c) - min(c) > 50 for c in colors)
        score = unique + (3 if has_dark and has_light else 0) + (2 if has_color else 0)

        if score >= 8:
            results.append((off, colors, score))

    results.sort(key=lambda x: -x[2])
    return [(off, cols) for off, cols, _ in results[:max_results]]


def render_4bpp_page(rom_data: bytes, offset: int,
                     palette: list[tuple[int, int, int]],
                     cols: int = 16, rows: int = 16) -> bytes:
    """Render a page of 4bpp tiles as PNG."""
    width = cols * 8
    height = rows * 8
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))

    for t in range(cols * rows):
        tile_off = offset + t * 32
        if tile_off + 32 > len(rom_data):
            break
        if not any(rom_data[tile_off:tile_off + 32]):
            continue
        pixels = decode_snes_4bpp_tile(rom_data, tile_off)
        tx = (t % cols) * 8
        ty = (t // cols) * 8
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
class SNESGenericExtractor:
    console = "snes"
    description = "Super NES — Generic (any SNES ROM, auto-detect tiles + decompress)"

    def __init__(self):
        self.game = ""

    def detect(self, rom_data: bytes) -> bool:
        """Detect any SNES ROM by header validation.

        Only triggers if no other SNES extractor matched first.
        Handles LoROM, HiROM, and 512-byte copier (SMC) headers.
        """
        if len(rom_data) < 0x8000:
            return False

        # Try with and without 512-byte copier header
        for hdr_off in [0, 0x200]:
            if hdr_off > 0 and len(rom_data) % 0x400 != 0x200:
                continue

            for mode, base in [("LoROM", 0x7FC0), ("HiROM", 0xFFC0)]:
                off = hdr_off + base
                if off + 0x20 > len(rom_data):
                    continue
                cs = rom_data[off + 0x1C] | (rom_data[off + 0x1D] << 8)
                csc = rom_data[off + 0x1E] | (rom_data[off + 0x1F] << 8)
                if (cs + csc) & 0xFFFF == 0xFFFF:
                    title = rom_data[off:off + 21].decode("ascii", errors="replace").strip()
                    self.game = title if title.isprintable() and len(title) > 2 else "Unknown SNES ROM"
                    self._hdr_offset = hdr_off
                    self._mapping = mode
                    return True

        return False

    def get_categories(self) -> list[str]:
        return [
            "Uncompressed Tiles (4bpp)",
            "Compressed Sprites (Nintendo)",
            "Compressed Sprites (Squaresoft)",
        ]

    def extract_all(self, rom_data: bytes, on_progress=None) -> list[AssetInfo]:
        assets = []

        # Strip copier header if present
        hdr_off = getattr(self, '_hdr_offset', 0)
        if hdr_off > 0:
            rom_data = rom_data[hdr_off:]

        if on_progress:
            on_progress(5, "Scanning for palettes...")

        # Find palettes — scan more broadly for better matches
        palettes = find_palettes(rom_data, 16, 30)
        if palettes:
            default_pal = palettes[0][1]
        else:
            default_pal = [(i * 17, i * 17, i * 17) for i in range(16)]

        if on_progress:
            on_progress(15, "Scanning for uncompressed 4bpp tiles...")

        # Find uncompressed 4bpp regions
        raw_pages = find_uncompressed_4bpp(rom_data)

        for idx, (off, score) in enumerate(raw_pages[:30]):
            if on_progress and idx % 5 == 0:
                pct = 15 + int((idx / max(1, min(30, len(raw_pages)))) * 25)
                on_progress(pct, f"Rendering raw page {idx + 1}")

            try:
                # Try each top palette, pick the one with most visible pixels
                best_png = None
                best_pal = default_pal
                best_visible = 0

                for pal_off, pal_colors in palettes[:5]:
                    png = render_4bpp_page(rom_data, off, pal_colors, 16, 16)
                    # Quick heuristic: larger PNG = more visible pixels
                    if len(png) > best_visible:
                        best_visible = len(png)
                        best_png = png
                        best_pal = pal_colors

                if best_png is None:
                    best_png = render_4bpp_page(rom_data, off, default_pal, 16, 16)

                assets.append(AssetInfo(
                    id=f"raw_4bpp_{idx:03d}",
                    name=f"Tiles 0x{off:06X} (score {score:.0f})",
                    category="Uncompressed Tiles (4bpp)",
                    width=128, height=128,
                    data=best_png,
                    palette=best_pal,
                    meta={
                        "offset": f"0x{off:06X}",
                        "coherence": round(score, 1),
                        "compressed": False,
                    },
                ))
            except Exception:
                pass

        if on_progress:
            on_progress(40, "Scanning for compressed sprite sheets...")

        # Find compressed 3bpp sprite sheets (Nintendo LC_LZ2)
        compressed = find_compressed_sheets(rom_data)

        for idx, (off, nz) in enumerate(compressed):
            if on_progress and idx % 10 == 0:
                pct = 40 + int((idx / max(1, len(compressed))) * 55)
                on_progress(pct, f"Decompressing sheet {idx + 1}/{len(compressed)}")

            try:
                tile_data = alttp_decompress(rom_data, off)
                fill_ratio = nz / len(tile_data)

                # Try all detected palettes (first 8 colors for 3bpp)
                best_png = None
                best_pal = default_pal[:8]

                for pal_off, pal_colors in palettes[:10]:
                    pal_8 = pal_colors[:8]
                    png = render_3bpp_sheet(tile_data, pal_8, 16)
                    if best_png is None or len(png) > len(best_png):
                        best_png = png
                        best_pal = pal_8

                if best_png is None:
                    best_png = render_3bpp_sheet(tile_data, default_pal[:8], 16)

                assets.append(AssetInfo(
                    id=f"compressed_{idx:03d}",
                    name=f"Sheet 0x{off:06X} ({fill_ratio:.0%} fill)",
                    category="Compressed Sprites (3bpp)",
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
            on_progress(80, "Scanning for Squaresoft-compressed data...")

        # Squaresoft LZ compressed blocks (Chrono Trigger, Secret of Mana, FF)
        square_blocks = find_square_compressed(rom_data)

        for idx, (off, size) in enumerate(square_blocks[:40]):
            if on_progress and idx % 10 == 0:
                pct = 80 + int((idx / max(1, min(40, len(square_blocks)))) * 18)
                on_progress(pct, f"Decompressing Squaresoft block {idx + 1}/{min(40, len(square_blocks))}")

            try:
                tile_data = square_decompress(rom_data, off, 0x2000)
                if len(tile_data) < 0x400:
                    continue

                # Render as 4bpp tiles
                tiles = len(tile_data) // 32
                if tiles == 0:
                    continue
                cols = 16
                rows = max(1, (tiles + cols - 1) // cols)

                best_png = None
                best_pal = default_pal

                for pal_off, pal_colors in palettes[:10]:
                    img = Image.new("RGBA", (cols * 8, rows * 8), (0, 0, 0, 0))
                    for t in range(tiles):
                        pixels = decode_snes_4bpp_tile(tile_data, t * 32)
                        tx = (t % cols) * 8
                        ty = (t // cols) * 8
                        for py in range(8):
                            for px in range(8):
                                i = pixels[py * 8 + px]
                                if i == 0 or i >= len(pal_colors):
                                    continue
                                r, g, b = pal_colors[i]
                                img.putpixel((tx + px, ty + py), (r, g, b, 255))
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    png = buf.getvalue()
                    if best_png is None or len(png) > len(best_png):
                        best_png = png
                        best_pal = pal_colors

                if best_png is None:
                    continue

                nz = sum(1 for b in tile_data if b != 0)
                assets.append(AssetInfo(
                    id=f"square_{idx:03d}",
                    name=f"Sheet 0x{off:06X}",
                    category="Compressed Sprites (Squaresoft)",
                    width=cols * 8,
                    height=rows * 8,
                    data=best_png,
                    palette=best_pal,
                    meta={
                        "offset": f"0x{off:06X}",
                        "compressed": True,
                        "compression": "squaresoft_lz",
                        "decompressed_size": len(tile_data),
                    },
                ))
            except Exception:
                pass

        if on_progress:
            on_progress(100, f"Extracted {len(assets)} assets")

        return assets
