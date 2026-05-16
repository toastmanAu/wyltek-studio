"""Build the vendored infographic catalog from an upstream SenseNova-Skills
checkout.

Usage:

    python -m scripts.build_infographic_catalog \\
        /tmp/SenseNova-Skills/skills/sn-infographic/references \\
        static/studio/catalogs/

Idempotent. Run on every upstream re-pull; commit the diff alongside the
catalog files so deploys never need a build step.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

CANONICAL_FALLBACK_LAYOUT = "hub-spoke"
CANONICAL_FALLBACK_STYLE = "corporate-memphis"

TOP_LEVEL_FILES = [
    "layout-style-selection.md",
    "prompts-expand-system.md",
    "prompts-critic-system.md",
]


def build_catalog(refs_dir: Path, out_dir: Path) -> None:
    """Vendor upstream catalog into out_dir and write index.json.

    Raises ValueError if the selection-rules tables reference a layout or
    style name with no corresponding .md file in the source tree.
    """
    refs_dir = Path(refs_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for sub in ("layouts", "styles"):
        if (out_dir / sub).exists():
            shutil.rmtree(out_dir / sub)
    (out_dir / "layouts").mkdir(exist_ok=True)
    (out_dir / "styles").mkdir(exist_ok=True)

    _copy_tree(refs_dir / "layouts", out_dir / "layouts")
    _copy_tree(refs_dir / "styles", out_dir / "styles")
    for name in TOP_LEVEL_FILES:
        src = refs_dir / name
        if src.exists():
            shutil.copy2(src, out_dir / name)

    layouts = sorted(p.stem for p in (out_dir / "layouts").glob("*.md"))
    styles = sorted(p.stem for p in (out_dir / "styles").glob("*.md"))

    sel_file = out_dir / "layout-style-selection.md"
    if not sel_file.exists():
        raise FileNotFoundError(
            f"layout-style-selection.md not found in {refs_dir}. "
            "Is this the correct upstream references/ directory?"
        )
    data_types, contexts = _parse_selection_tables(sel_file.read_text())

    layout_set, style_set = set(layouts), set(styles)
    for dt in data_types:
        for name in [dt["primary"], *dt["alternatives"]]:
            if name not in layout_set:
                raise ValueError(
                    f"data_type {dt['key']!r} references unknown layout {name!r}"
                )
    for ctx in contexts:
        for name in [ctx["primary"], *ctx["alternatives"]]:
            if name not in style_set:
                raise ValueError(
                    f"context {ctx['key']!r} references unknown style {name!r}"
                )

    fallback_layout = (
        CANONICAL_FALLBACK_LAYOUT
        if CANONICAL_FALLBACK_LAYOUT in layout_set
        else data_types[0]["primary"]
    )
    fallback_style = (
        CANONICAL_FALLBACK_STYLE
        if CANONICAL_FALLBACK_STYLE in style_set
        else contexts[0]["primary"]
    )

    index = {
        "version": "1",
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "data_types": data_types,
        "contexts": contexts,
        "all_layouts": layouts,
        "all_styles": styles,
        "fallback": {"layout": fallback_layout, "style": fallback_style},
    }
    (out_dir / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n"
    )


def _copy_tree(src: Path, dst: Path) -> None:
    dst.mkdir(parents=True, exist_ok=True)
    for p in src.glob("*.md"):
        shutil.copy2(p, dst / p.name)


_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$")


def _parse_selection_tables(md_text: str) -> tuple[list[dict], list[dict]]:
    """Return (data_types, contexts) parsed from the two markdown tables."""
    data_types: list[dict] = []
    contexts: list[dict] = []
    current: list[dict] | None = None

    for line in md_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            current = None
            continue
        if set(stripped.replace("|", "").strip()) <= set("- :"):
            continue  # separator row
        m = _ROW_RE.match(stripped)
        if not m:
            continue
        col1, col2, col3 = (s.strip() for s in m.groups())
        col1_lower = col1.lower()
        # Upstream wraps layout / style names in markdown inline-code
        # backticks (e.g. `linear-progression`). Strip them so cross-ref
        # validation against the .md filename set works.
        # col2 is a single backticked token; col3 is a comma-separated list of them.
        col2 = col2.strip("`").strip()
        col3 = col3.replace("`", "")
        if "data_type" in col1_lower or "data type" in col1_lower:
            current = data_types
            continue
        if "context" in col1_lower:
            current = contexts
            continue
        if current is None:
            continue
        alternatives = [a.strip() for a in col3.split(",") if a.strip()]
        current.append({"key": col1, "primary": col2, "alternatives": alternatives})

    if not data_types or not contexts:
        raise ValueError(
            "selection-rules markdown did not yield both data_type and context tables"
        )
    return data_types, contexts


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__, file=sys.stderr)
        return 2
    build_catalog(Path(argv[1]), Path(argv[2]))
    print(f"[build_infographic_catalog] wrote {argv[2]}/index.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
