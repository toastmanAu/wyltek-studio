"""Infographic catalog — vendored from sn-infographic.

Process-lifetime singleton wrapping the JSON index and the weighted-random
sampler described in upstream's references/layout-style-selection.md
(Step 3: primary × 10, each alternative × 9, three outsiders × 1).
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Literal, TypedDict

log = logging.getLogger(__name__)

PoolKind = Literal["primary", "alternative", "outsider", "fallback"]
Kind = Literal["layouts", "styles"]


class PickLabel(TypedDict):
    layout: PoolKind
    style: PoolKind


class InfographicCatalog:
    """Loads index.json once; exposes sampling + markdown reads.

    Thread-safety: read-only after __init__. Sampler uses a fresh
    random.Random per call so concurrent FastAPI requests cannot interfere.
    """

    def __init__(self, catalog_dir: Path) -> None:
        self.dir = Path(catalog_dir)
        index_path = self.dir / "index.json"
        self.index = json.loads(index_path.read_text())

        self._data_type_map = {dt["key"]: dt for dt in self.index["data_types"]}
        self._context_map = {ctx["key"]: ctx for ctx in self.index["contexts"]}
        self._all_layouts: list[str] = list(self.index["all_layouts"])
        self._all_styles: list[str] = list(self.index["all_styles"])
        self._layout_set = set(self._all_layouts)
        self._style_set = set(self._all_styles)
        self._fallback = self.index["fallback"]
        log.info(
            "infographic_catalog loaded: %d data_types, %d contexts, %d layouts, %d styles",
            len(self._data_type_map), len(self._context_map),
            len(self._all_layouts), len(self._all_styles),
        )

    # ── Listing ─────────────────────────────────────────────────────────────

    def list_data_types(self) -> list[str]:
        return list(self._data_type_map.keys())

    def list_contexts(self) -> list[str]:
        return list(self._context_map.keys())

    def counts(self) -> dict[str, int]:
        return {"layouts": len(self._all_layouts), "styles": len(self._all_styles)}

    # ── Sampling ────────────────────────────────────────────────────────────

    def sample(
        self,
        data_type: str,
        context: str,
        *,
        seed: int | None = None,
        lock: Literal["layout", "style"] | None = None,
        current: tuple[str, str] | None = None,
    ) -> tuple[str, str]:
        (layout, style), _ = self.sample_with_label(
            data_type, context, seed=seed, lock=lock, current=current,
        )
        return layout, style

    def sample_with_label(
        self,
        data_type: str,
        context: str,
        *,
        seed: int | None = None,
        lock: Literal["layout", "style"] | None = None,
        current: tuple[str, str] | None = None,
    ) -> tuple[tuple[str, str], PickLabel]:
        rng = random.Random(seed)

        # Layout axis.
        if lock == "layout" and current is not None:
            layout, layout_label = current[0], self._classify_layout(data_type, current[0])
        else:
            layout, layout_label = self._sample_layout(data_type, rng)

        # Style axis.
        if lock == "style" and current is not None:
            style, style_label = current[1], self._classify_style(context, current[1])
        else:
            style, style_label = self._sample_style(context, rng)

        return (layout, style), {"layout": layout_label, "style": style_label}

    def _sample_layout(self, data_type: str, rng: random.Random) -> tuple[str, PoolKind]:
        entry = self._data_type_map.get(data_type)
        if entry is None:
            return self._fallback["layout"], "fallback"
        return self._weighted_pick(entry, self._all_layouts, rng)

    def _sample_style(self, context: str, rng: random.Random) -> tuple[str, PoolKind]:
        entry = self._context_map.get(context)
        if entry is None:
            return self._fallback["style"], "fallback"
        return self._weighted_pick(entry, self._all_styles, rng)

    @staticmethod
    def _weighted_pick(
        entry: dict, all_names: list[str], rng: random.Random,
    ) -> tuple[str, PoolKind]:
        """sn-infographic Step 3: primary×10, each alternative×9, three
        outsiders×1. Outsider count clamps to what's available."""
        in_category = {entry["primary"], *entry["alternatives"]}
        outsiders = [n for n in all_names if n not in in_category]
        rng.shuffle(outsiders)
        outsider_sample = outsiders[: min(3, len(outsiders))]

        pool: list[tuple[str, PoolKind]] = []
        pool.extend([(entry["primary"], "primary")] * 10)
        for alt in entry["alternatives"]:
            pool.extend([(alt, "alternative")] * 9)
        pool.extend([(o, "outsider") for o in outsider_sample])
        return rng.choice(pool)

    def _classify_layout(self, data_type: str, name: str) -> PoolKind:
        entry = self._data_type_map.get(data_type)
        if entry is None:
            return "fallback"
        if name == entry["primary"]:
            return "primary"
        if name in entry["alternatives"]:
            return "alternative"
        return "outsider"

    def _classify_style(self, context: str, name: str) -> PoolKind:
        entry = self._context_map.get(context)
        if entry is None:
            return "fallback"
        if name == entry["primary"]:
            return "primary"
        if name in entry["alternatives"]:
            return "alternative"
        return "outsider"

    # ── Markdown reads ──────────────────────────────────────────────────────

    def read_markdown(self, kind: Kind, name: str) -> str:
        if kind == "layouts":
            valid = self._layout_set
        elif kind == "styles":
            valid = self._style_set
        else:
            raise ValueError(f"unknown kind {kind!r} — expected 'layouts' or 'styles'")
        if name not in valid:
            raise KeyError(f"unknown {kind[:-1]} {name!r}")
        return (self.dir / kind / f"{name}.md").read_text()

    def expander_system_prompt(self) -> str:
        return (self.dir / "prompts-expand-system.md").read_text()
