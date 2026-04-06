"""GBA Pokemon ROM extractor — FireRed, LeafGreen, Ruby, Sapphire, Emerald.

Extracts all 386 Pokemon front/back sprites + palettes from known ROM offsets.
Uses standard GBA LZ77 decompression.
"""

from __future__ import annotations

import io
import struct

from PIL import Image

from . import AssetInfo, register

# ROM game codes → sprite table offsets
# Format: (front_sprite_table, back_sprite_table, palette_table, pokemon_count, name)
GAME_OFFSETS = {
    # Pokemon FireRed (US) Rev 1 (most common ROM in circulation)
    b"BPRE": {
        "name": "Pokemon FireRed",
        "front_sprites": 0x23511C,
        "back_sprites": 0x2365BC,
        "palettes_normal": 0x23737C,
        "palettes_shiny": 0x237374 + (386 * 8),
        "icon_sprites": 0x23BC68,
        "pokemon_count": 386,
        "names_table": 0x245F50,
    },
    # Pokemon LeafGreen (US) v1.0
    b"BPGE": {
        "name": "Pokemon LeafGreen",
        "front_sprites": 0x2350AC,
        "back_sprites": 0x2350AC + (386 * 8),
        "palettes_normal": 0x23730C,
        "palettes_shiny": 0x2383EC,
        "icon_sprites": 0x23BC68,
        "pokemon_count": 386,
        "names_table": 0x245EE0,
    },
    # Pokemon Ruby (US) v1.0
    b"AXVE": {
        "name": "Pokemon Ruby",
        "front_sprites": 0x1E8354,
        "back_sprites": 0x1E8354 + (386 * 8),
        "palettes_normal": 0x1EA5B4,
        "palettes_shiny": 0x1EB694,
        "icon_sprites": 0x1EEFAC,
        "pokemon_count": 386,
        "names_table": 0x1F7184,
    },
    # Pokemon Sapphire (US) v1.0
    b"AXPE": {
        "name": "Pokemon Sapphire",
        "front_sprites": 0x1E8354,
        "back_sprites": 0x1E8354 + (386 * 8),
        "palettes_normal": 0x1EA5B4,
        "palettes_shiny": 0x1EB694,
        "icon_sprites": 0x1EEFAC,
        "pokemon_count": 386,
        "names_table": 0x1F7184,
    },
    # Pokemon Emerald (US)
    b"BPEE": {
        "name": "Pokemon Emerald",
        "front_sprites": 0x2EB3FC,
        "back_sprites": 0x2EB3FC + (386 * 8),
        "palettes_normal": 0x2ED65C,
        "palettes_shiny": 0x2EE73C,
        "icon_sprites": 0x2F2054,
        "pokemon_count": 386,
        "names_table": 0x3185C8,
    },
}

# GBA character encoding for Pokemon names
GBA_CHARS = {
    0xBB: 'A', 0xBC: 'B', 0xBD: 'C', 0xBE: 'D', 0xBF: 'E',
    0xC0: 'F', 0xC1: 'G', 0xC2: 'H', 0xC3: 'I', 0xC4: 'J',
    0xC5: 'K', 0xC6: 'L', 0xC7: 'M', 0xC8: 'N', 0xC9: 'O',
    0xCA: 'P', 0xCB: 'Q', 0xCC: 'R', 0xCD: 'S', 0xCE: 'T',
    0xCF: 'U', 0xD0: 'V', 0xD1: 'W', 0xD2: 'X', 0xD3: 'Y',
    0xD4: 'Z', 0xD5: 'a', 0xD6: 'b', 0xD7: 'c', 0xD8: 'd',
    0xD9: 'e', 0xDA: 'f', 0xDB: 'g', 0xDC: 'h', 0xDD: 'i',
    0xDE: 'j', 0xDF: 'k', 0xE0: 'l', 0xE1: 'm', 0xE2: 'n',
    0xE3: 'o', 0xE4: 'p', 0xE5: 'q', 0xE6: 'r', 0xE7: 's',
    0xE8: 't', 0xE9: 'u', 0xEA: 'v', 0xEB: 'w', 0xEC: 'x',
    0xED: 'y', 0xEE: 'z', 0x00: ' ', 0xAB: '!', 0xAC: '?',
    0xB1: '-', 0xAD: '.', 0xB4: "'", 0x35: '2', 0xFF: '',
}


def lz77_decompress(data: bytes, offset: int) -> bytes:
    """Decompress GBA LZ77 (type 0x10) data starting at offset."""
    if data[offset] != 0x10:
        # Not LZ77 compressed — might be raw data
        # Try reading as uncompressed (some sprites aren't compressed)
        return data[offset:offset + 0x800]

    # Read decompressed size (3 bytes little-endian after the 0x10 flag)
    decomp_size = struct.unpack_from("<I", data, offset)[0] >> 8
    src = offset + 4
    dst = bytearray()

    while len(dst) < decomp_size and src < len(data):
        flags = data[src]
        src += 1

        for bit in range(7, -1, -1):
            if len(dst) >= decomp_size:
                break

            if flags & (1 << bit):
                # Compressed: reference to earlier data
                if src + 1 >= len(data):
                    break
                b1 = data[src]
                b2 = data[src + 1]
                src += 2

                length = ((b1 >> 4) & 0x0F) + 3
                disp = ((b1 & 0x0F) << 8) | b2
                disp += 1

                for _ in range(length):
                    if len(dst) >= decomp_size:
                        break
                    if disp > len(dst):
                        dst.append(0)
                    else:
                        dst.append(dst[-disp])
            else:
                # Uncompressed: literal byte
                if src >= len(data):
                    break
                dst.append(data[src])
                src += 1

    return bytes(dst)


def decode_4bpp_sprite(tile_data: bytes, width: int = 64, height: int = 64) -> list[int]:
    """Decode 4bpp (16 color) GBA tile data into pixel indices.

    GBA sprites are stored as 8x8 tiles in row-major order.
    Each tile is 32 bytes (8x8 pixels, 4 bits per pixel).
    """
    pixels = [0] * (width * height)
    tiles_wide = width // 8
    tiles_high = height // 8
    tile_idx = 0

    for ty in range(tiles_high):
        for tx in range(tiles_wide):
            tile_offset = tile_idx * 32
            if tile_offset + 32 > len(tile_data):
                tile_idx += 1
                continue

            for row in range(8):
                for col in range(0, 8, 2):
                    byte_offset = tile_offset + row * 4 + col // 2
                    if byte_offset >= len(tile_data):
                        continue
                    byte = tile_data[byte_offset]
                    px = tx * 8 + col
                    py = ty * 8 + row

                    # Low nibble = left pixel, high nibble = right pixel
                    if px < width and py < height:
                        pixels[py * width + px] = byte & 0x0F
                    if px + 1 < width and py < height:
                        pixels[py * width + px + 1] = (byte >> 4) & 0x0F

            tile_idx += 1

    return pixels


def read_gba_palette(data: bytes, offset: int, count: int = 16) -> list[tuple[int, int, int]]:
    """Read GBA 15-bit RGB palette (5 bits per channel)."""
    palette = []
    for i in range(count):
        if offset + i * 2 + 1 >= len(data):
            palette.append((0, 0, 0))
            continue
        color = struct.unpack_from("<H", data, offset + i * 2)[0]
        r = (color & 0x1F) << 3
        g = ((color >> 5) & 0x1F) << 3
        b = ((color >> 10) & 0x1F) << 3
        palette.append((r, g, b))
    return palette


def read_pokemon_name(data: bytes, names_table: int, index: int) -> str:
    """Read a Pokemon name from the names table (11 bytes per entry)."""
    offset = names_table + index * 11
    name = ""
    for i in range(11):
        if offset + i >= len(data):
            break
        byte = data[offset + i]
        if byte == 0xFF:  # string terminator
            break
        name += GBA_CHARS.get(byte, '?')
    return name.strip()


def sprite_to_png(pixels: list[int], palette: list[tuple[int, int, int]],
                  width: int, height: int) -> bytes:
    """Convert pixel indices + palette to PNG bytes."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    img_data = []
    for y in range(height):
        for x in range(width):
            idx = pixels[y * width + x]
            if idx == 0:  # transparent
                img_data.append((0, 0, 0, 0))
            elif idx < len(palette):
                r, g, b = palette[idx]
                img_data.append((r, g, b, 255))
            else:
                img_data.append((0, 0, 0, 255))
    img.putdata(img_data)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def read_pointer(data: bytes, offset: int) -> int:
    """Read a GBA ROM pointer (subtract 0x08000000 to get file offset)."""
    ptr = struct.unpack_from("<I", data, offset)[0]
    if ptr >= 0x08000000:
        return ptr - 0x08000000
    return ptr


@register
class GBAPokemonExtractor:
    console = "gba"
    description = "Game Boy Advance — Pokemon (FireRed, LeafGreen, Ruby, Sapphire, Emerald)"

    def __init__(self):
        self.game = ""
        self._offsets = None

    def detect(self, rom_data: bytes) -> bool:
        """Check if this is a supported Pokemon GBA ROM."""
        if len(rom_data) < 0xC0:
            return False
        # Game code is at offset 0xAC (4 bytes)
        game_code = rom_data[0xAC:0xB0]
        if game_code in GAME_OFFSETS:
            self._offsets = GAME_OFFSETS[game_code]
            self.game = self._offsets["name"]
            return True
        return False

    def get_categories(self) -> list[str]:
        return ["Pokemon Sprites (Front)", "Pokemon Sprites (Back)"]

    def extract_all(self, rom_data: bytes, on_progress=None) -> list[AssetInfo]:
        """Extract all Pokemon front and back sprites with palettes."""
        if not self._offsets:
            return []

        offsets = self._offsets
        count = offsets["pokemon_count"]
        assets = []

        for i in range(count):
            if on_progress and i % 20 == 0:
                pct = int((i / count) * 100)
                on_progress(pct, f"Extracting Pokemon {i + 1}/{count}")

            # Pokemon index 0 is "???" (placeholder), skip
            if i == 0:
                continue

            name = read_pokemon_name(rom_data, offsets["names_table"], i)
            if not name or name == '?':
                name = f"Pokemon #{i}"

            # Read palette
            pal_ptr_offset = offsets["palettes_normal"] + i * 8
            pal_ptr = read_pointer(rom_data, pal_ptr_offset)
            try:
                pal_data = lz77_decompress(rom_data, pal_ptr)
                palette = []
                for j in range(16):
                    if j * 2 + 1 < len(pal_data):
                        color = struct.unpack_from("<H", pal_data, j * 2)[0]
                        r = (color & 0x1F) << 3
                        g = ((color >> 5) & 0x1F) << 3
                        b = ((color >> 10) & 0x1F) << 3
                        palette.append((r, g, b))
                    else:
                        palette.append((0, 0, 0))
            except Exception:
                palette = [(0, 0, 0)] * 16

            # Front sprite
            try:
                front_ptr_offset = offsets["front_sprites"] + i * 8
                front_ptr = read_pointer(rom_data, front_ptr_offset)
                front_data = lz77_decompress(rom_data, front_ptr)
                front_pixels = decode_4bpp_sprite(front_data, 64, 64)
                front_png = sprite_to_png(front_pixels, palette, 64, 64)

                assets.append(AssetInfo(
                    id=f"pokemon_{i:03d}_front",
                    name=f"{name} (Front)",
                    category="Pokemon Sprites (Front)",
                    width=64, height=64,
                    data=front_png,
                    palette=palette,
                    meta={"dex": i, "pokemon_name": name, "view": "front"},
                ))
            except Exception:
                pass  # Skip corrupted entries

            # Back sprite
            try:
                back_ptr_offset = offsets["back_sprites"] + i * 8
                back_ptr = read_pointer(rom_data, back_ptr_offset)
                back_data = lz77_decompress(rom_data, back_ptr)
                back_pixels = decode_4bpp_sprite(back_data, 64, 64)
                back_png = sprite_to_png(back_pixels, palette, 64, 64)

                assets.append(AssetInfo(
                    id=f"pokemon_{i:03d}_back",
                    name=f"{name} (Back)",
                    category="Pokemon Sprites (Back)",
                    width=64, height=64,
                    data=back_png,
                    palette=palette,
                    meta={"dex": i, "pokemon_name": name, "view": "back"},
                ))
            except Exception:
                pass

        if on_progress:
            on_progress(100, f"Extracted {len(assets)} sprites")

        return assets
