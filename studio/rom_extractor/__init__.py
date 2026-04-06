"""ROM asset extractor — modular per-console architecture.

Each console gets its own module implementing the ExtractorBase interface.
The router auto-detects ROM type from header and dispatches to the right extractor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class AssetInfo:
    """Single extracted asset."""
    __slots__ = ("id", "name", "category", "width", "height", "data", "palette", "meta")

    def __init__(self, id: str, name: str, category: str,
                 width: int, height: int, data: bytes,
                 palette: list[tuple[int, int, int]] | None = None,
                 meta: dict | None = None):
        self.id = id
        self.name = name
        self.category = category
        self.width = width
        self.height = height
        self.data = data  # raw PNG bytes
        self.palette = palette
        self.meta = meta or {}


class ExtractorBase(Protocol):
    """Interface all console extractors implement."""

    console: str  # "gba", "nes", "snes"
    game: str     # detected game name

    def detect(self, rom_data: bytes) -> bool:
        """Return True if this extractor handles this ROM."""
        ...

    def extract_all(self, rom_data: bytes, on_progress=None) -> list[AssetInfo]:
        """Extract all moddable assets from the ROM."""
        ...

    def get_categories(self) -> list[str]:
        """Return asset category names (e.g. ['Pokemon Sprites', 'Trainer Sprites', 'Maps'])."""
        ...


# Registry of extractors — order matters (first match wins)
_extractors: list[type] = []


def register(cls: type):
    """Register an extractor class."""
    _extractors.append(cls)
    return cls


def _auto_import():
    """Import all extractor modules to trigger @register decorators."""
    from studio.rom_extractor import gba_pokemon  # noqa: F401
    from studio.rom_extractor import snes_zelda  # noqa: F401
    from studio.rom_extractor import snes_generic  # noqa: F401
    # Future: import nes, gbc modules here
    # Note: snes_generic MUST be after snes_zelda — first match wins,
    # game-specific extractors take priority over generic.


_auto_import()


def detect_rom(rom_data: bytes) -> ExtractorBase | None:
    """Auto-detect ROM type and return the appropriate extractor."""
    for cls in _extractors:
        ext = cls()
        if ext.detect(rom_data):
            return ext
    return None


def list_supported() -> list[dict]:
    """List all registered extractors."""
    result = []
    for cls in _extractors:
        ext = cls()
        result.append({
            "console": ext.console,
            "description": getattr(ext, "description", ext.console),
        })
    return result
