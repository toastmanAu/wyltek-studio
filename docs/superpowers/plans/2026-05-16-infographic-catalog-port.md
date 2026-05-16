# Infographic Catalog Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the freeform-only flow on `/studio/infographic` with a catalog-driven flow that ports sn-infographic's 87 layouts × 66 styles + weighted-random sampler, preserves the current gallery/freeform flow as a tab, and adds an Ollama-based prompt expander with deterministic template fallback.

**Architecture:** Three new server-side Python modules (`studio/infographic_catalog.py`, `studio/infographic_expander.py`, `scripts/build_infographic_catalog.py`), three new endpoints in `server.py`, a vendored catalog under `static/studio/catalogs/`, and a frontend module split (`static/studio/js/infographic.js` becomes a tab dispatcher; current gallery code lifts to `static/studio/js/infographic/freeform-mode.js`; new `catalog-mode.js`). The Ollama expander posts to the local server's OpenAI-compatible endpoint; on any failure (network, timeout, missing model, malformed response) a deterministic regex-based template fallback runs and the UI shows an amber "Ollama unavailable" chip — render proceeds regardless.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, httpx (already a top-level dep), pytest, vanilla ES modules (no bundler), Ollama OpenAI-compatible API, existing SenseNova/HiDream JobQueue path.

**Spec reference:** `docs/superpowers/specs/2026-05-16-infographic-catalog-port-design.md` (commit 61bffdf).

**Convention deviations from spec:**

- Spec said `structlog` for server-side logging; actual `server.py` convention is `print(f"[component] ...")` (verified at server.py:4358). Use the latter. The two new modules (`infographic_catalog.py`, `infographic_expander.py`) use stdlib `logging.getLogger(__name__)` — matches `studio/sensenova_worker.py:45`.
- Tests live flat under `tests/`, not nested under `tests/studio/`. The existing `test_sensenova_*.py`, `test_remix_*.py` files set the pattern.
- The current `static/studio/infographic.html` is a gallery → editor flow, not a bare textarea. Spec text "Replace the freeform-textarea" is imprecise — what we preserve as "Freeform" is the entire current gallery + editor flow.

---

## File Structure

**New files:**

```
docs/superpowers/plans/2026-05-16-infographic-catalog-port.md  (this file)
scripts/build_infographic_catalog.py                          # one-shot vendor builder
studio/infographic_catalog.py                                 # InfographicCatalog class
studio/infographic_expander.py                                # Ollama HTTP + template fallback
static/studio/catalogs/                                       # vendored — committed
    layouts/*.md                                              # 87 files (verbatim upstream)
    styles/*.md                                               # 66 files (verbatim upstream)
    layout-style-selection.md                                 # selection-rules doc
    prompts-expand-system.md                                  # expander system prompt
    prompts-critic-system.md                                  # critic system prompt (vendored for future Move #2)
    index.json                                                # built by scripts/build_infographic_catalog.py
static/studio/js/infographic/
    catalog-mode.js                                           # new Catalog tab
    freeform-mode.js                                          # lifted from current infographic.js
tests/test_infographic_catalog.py
tests/test_infographic_expander.py
tests/test_api_infographic_endpoints.py
```

**Modified files:**

```
server.py                          # +3 endpoints, +catalog singleton init
static/studio/infographic.html     # +tab strip, +catalog panel, +script imports
static/studio/js/infographic.js    # becomes tab dispatcher (~80 LOC)
README.md                          # +one-liner about `ollama pull gpt-oss:20b` setup
```

**Singleton initialisation in `server.py`:** the `InfographicCatalog` is loaded once at module import (top of server.py near existing module-level singletons). If `static/studio/catalogs/index.json` is missing, log a loud warning but do not crash — the page still renders the Freeform tab; Catalog tab shows a "catalog not built" banner. This keeps dev-on-a-fresh-clone painless.

---

## Task 1: Vendor the upstream catalog corpus + build script (TDD)

**Why first:** Every later task depends on having an `index.json` to load. We build the script TDD-style, then run it against a re-cloned upstream and commit the output.

**Files:**

- Create: `scripts/build_infographic_catalog.py`
- Create: `tests/test_build_infographic_catalog.py`

### Task 1a: Re-clone the upstream skills repo

- [ ] **Step 1: Clone SenseNova-Skills into /tmp**

```bash
rm -rf /tmp/SenseNova-Skills
git clone --depth 1 https://github.com/OpenSenseNova/SenseNova-Skills.git /tmp/SenseNova-Skills
```

Expected: clone succeeds; `/tmp/SenseNova-Skills/skills/sn-infographic/references/` contains `layouts/`, `styles/`, `layout-style-selection.md`, `prompts-expand-system.md`, `prompts-critic-system.md`.

- [ ] **Step 2: Sanity-check counts**

```bash
ls /tmp/SenseNova-Skills/skills/sn-infographic/references/layouts/ | wc -l
ls /tmp/SenseNova-Skills/skills/sn-infographic/references/styles/ | wc -l
```

Expected: `87` and `66`. If counts differ from 87/66 the upstream has moved — investigate before continuing (do not silently absorb a count change; the spec's sampler weights assume these exact pool sizes).

### Task 1b: Test scaffold for build script

- [ ] **Step 3: Create the test file with a fixture upstream tree**

Create `tests/test_build_infographic_catalog.py`:

```python
"""Tests for scripts/build_infographic_catalog.py.

The build script is the single source of truth for the vendored catalog.
These tests use a *miniature* fixture upstream tree (3 layouts, 2 styles,
3 data_types, 2 contexts) so a regression in table parsing or cross-ref
validation fails loud here rather than during the real build.
"""

from __future__ import annotations

import json
from pathlib import Path
from textwrap import dedent

import pytest

from scripts.build_infographic_catalog import build_catalog


@pytest.fixture
def upstream(tmp_path: Path) -> Path:
    """A 3-layout × 2-style miniature of the real upstream tree."""
    refs = tmp_path / "references"
    (refs / "layouts").mkdir(parents=True)
    (refs / "styles").mkdir(parents=True)

    # Three layouts — names match what we put in the table below.
    for name, body in [
        ("hub-spoke",   "# Hub-and-spoke\nCenter node radiates outward.\n"),
        ("bento-grid",  "# Bento grid\nRectangular modular cells.\n"),
        ("timeline",    "# Timeline\nLeft-to-right sequence.\n"),
    ]:
        (refs / "layouts" / f"{name}.md").write_text(body)

    # Two styles.
    for name, body in [
        ("corporate-memphis", "# Corporate Memphis\nFlat geometric.\n"),
        ("swiss-style",       "# Swiss Style\nGrid-based, sans-serif.\n"),
    ]:
        (refs / "styles" / f"{name}.md").write_text(body)

    # Selection-rules doc — two markdown tables matching the upstream shape.
    (refs / "layout-style-selection.md").write_text(dedent("""\
        # Layout & Style Selection

        ## Data type → layout

        | data_type           | primary    | alternatives           |
        |---------------------|------------|------------------------|
        | overview / summary  | bento-grid | hub-spoke, timeline    |
        | timeline / history  | timeline   | bento-grid             |
        | process / tutorial  | hub-spoke  | timeline, bento-grid   |

        ## Context → style

        | context                 | primary            | alternatives        |
        |-------------------------|--------------------|---------------------|
        | Professional / Business | corporate-memphis  | swiss-style         |
        | Technical / Engineering | swiss-style        | corporate-memphis   |
    """))

    (refs / "prompts-expand-system.md").write_text("You are a prompt expander.\n")
    (refs / "prompts-critic-system.md").write_text("You are a critic.\n")
    return refs


def test_build_catalog_copies_all_files(upstream, tmp_path):
    out = tmp_path / "out"
    build_catalog(upstream, out)
    assert (out / "layouts" / "hub-spoke.md").exists()
    assert (out / "styles" / "swiss-style.md").exists()
    assert (out / "layout-style-selection.md").exists()
    assert (out / "prompts-expand-system.md").exists()
    assert (out / "prompts-critic-system.md").exists()


def test_build_catalog_writes_index_json(upstream, tmp_path):
    out = tmp_path / "out"
    build_catalog(upstream, out)
    index = json.loads((out / "index.json").read_text())
    assert index["version"] == "1"
    assert sorted(index["all_layouts"]) == ["bento-grid", "hub-spoke", "timeline"]
    assert sorted(index["all_styles"]) == ["corporate-memphis", "swiss-style"]
    assert len(index["data_types"]) == 3
    assert len(index["contexts"]) == 2
    overview = next(dt for dt in index["data_types"] if dt["key"] == "overview / summary")
    assert overview["primary"] == "bento-grid"
    assert overview["alternatives"] == ["hub-spoke", "timeline"]


def test_build_catalog_fails_on_unknown_layout_in_table(upstream, tmp_path):
    """A typo in the table that names a layout with no corresponding .md
    must fail the build — not silently propagate to runtime."""
    sel = upstream / "layout-style-selection.md"
    sel.write_text(sel.read_text().replace("bento-grid", "bento-typo"))
    with pytest.raises(ValueError, match="bento-typo"):
        build_catalog(upstream, tmp_path / "out")


def test_build_catalog_fails_on_unknown_style_in_table(upstream, tmp_path):
    sel = upstream / "layout-style-selection.md"
    sel.write_text(sel.read_text().replace("swiss-style", "swiss-typo"))
    with pytest.raises(ValueError, match="swiss-typo"):
        build_catalog(upstream, tmp_path / "out")


def test_build_catalog_idempotent(upstream, tmp_path):
    """Running the build twice produces byte-identical index.json (modulo
    built_at timestamp)."""
    out = tmp_path / "out"
    build_catalog(upstream, out)
    idx1 = json.loads((out / "index.json").read_text())
    build_catalog(upstream, out)
    idx2 = json.loads((out / "index.json").read_text())
    idx1.pop("built_at"); idx2.pop("built_at")
    assert idx1 == idx2


def test_build_catalog_fallback_uses_first_data_type_primary(upstream, tmp_path):
    """`fallback` defaults to sn-infographic's hub-spoke/corporate-memphis if
    both names exist; otherwise falls back to the first row's primaries."""
    out = tmp_path / "out"
    build_catalog(upstream, out)
    index = json.loads((out / "index.json").read_text())
    # Our fixture has hub-spoke + corporate-memphis, so the canonical defaults apply.
    assert index["fallback"] == {"layout": "hub-spoke", "style": "corporate-memphis"}
```

- [ ] **Step 4: Run the test — it must fail**

```bash
pytest tests/test_build_infographic_catalog.py -v
```

Expected: `ImportError` / `ModuleNotFoundError` on `scripts.build_infographic_catalog`. This proves the test would catch a missing implementation.

### Task 1c: Implement the build script

- [ ] **Step 5: Create scripts/build_infographic_catalog.py**

```python
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

# Files copied verbatim from upstream references/ → out/
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
    (out_dir / "layouts").mkdir(exist_ok=True)
    (out_dir / "styles").mkdir(exist_ok=True)

    # Copy md trees + top-level docs.
    _copy_tree(refs_dir / "layouts", out_dir / "layouts")
    _copy_tree(refs_dir / "styles", out_dir / "styles")
    for name in TOP_LEVEL_FILES:
        src = refs_dir / name
        if src.exists():
            shutil.copy2(src, out_dir / name)

    layouts = sorted(p.stem for p in (out_dir / "layouts").glob("*.md"))
    styles = sorted(p.stem for p in (out_dir / "styles").glob("*.md"))

    data_types, contexts = _parse_selection_tables(
        (out_dir / "layout-style-selection.md").read_text()
    )

    # Cross-ref validation — every primary/alternative must resolve to a file.
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


# Markdown-table row: `| key | primary | a, b, c |` — we tolerate extra spaces.
_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*$")


def _parse_selection_tables(md_text: str) -> tuple[list[dict], list[dict]]:
    """Return (data_types, contexts) parsed from the two markdown tables.

    A table is recognised by its header row containing 'data_type' or
    'context' (case-insensitive). Separator rows (`|---|---|---|`) and
    section headings are skipped.
    """
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
```

- [ ] **Step 6: Run tests — they must pass**

```bash
pytest tests/test_build_infographic_catalog.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 7: Run the build against real upstream**

```bash
python -m scripts.build_infographic_catalog \
    /tmp/SenseNova-Skills/skills/sn-infographic/references \
    static/studio/catalogs/
```

Expected: prints `[build_infographic_catalog] wrote static/studio/catalogs/index.json`. If you see `ValueError: data_type ... references unknown layout ...` the upstream tables have a name that doesn't match a `.md` file — open the offending md and either fix the table or add the missing file before continuing.

- [ ] **Step 8: Sanity-check the vendored output**

```bash
ls static/studio/catalogs/layouts/ | wc -l       # expect 87
ls static/studio/catalogs/styles/ | wc -l        # expect 66
python -c "import json; d=json.load(open('static/studio/catalogs/index.json')); print(len(d['data_types']), len(d['contexts']))"
# expect: 21 21  (real upstream — the test fixture had 3/2)
```

- [ ] **Step 9: Commit script + tests + vendored catalog**

```bash
git add scripts/build_infographic_catalog.py \
        tests/test_build_infographic_catalog.py \
        static/studio/catalogs/
git commit -m "feat: vendor sn-infographic catalog (87 layouts × 66 styles) + build script"
```

---

## Task 2: `InfographicCatalog` class (TDD)

Process-lifetime singleton; loads `index.json` once; exposes `list_data_types`, `list_contexts`, `sample`, `read_markdown`.

**Files:**

- Create: `studio/infographic_catalog.py`
- Create: `tests/test_infographic_catalog.py`

### Task 2a: Write the tests

- [ ] **Step 1: Create tests/test_infographic_catalog.py**

```python
"""Tests for studio.infographic_catalog.InfographicCatalog.

Uses a small synthetic catalog under tmp_path so failures point at logic,
not data drift in the real vendored corpus.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import pytest

from studio.infographic_catalog import InfographicCatalog, PoolKind


@pytest.fixture
def catalog_dir(tmp_path: Path) -> Path:
    """A 4-layout × 3-style synthetic catalog.

    Pool composition under sn-infographic rules (primary×10 + each
    alternative×9 + 3 outsiders×1):
      - data_type "overview" → primary=bento (10), alt=hub (9), outsiders
        from {timeline} (only 1 outsider available, so up to 1 added).
    """
    (tmp_path / "layouts").mkdir()
    (tmp_path / "styles").mkdir()
    for name in ("bento", "hub", "timeline", "asymmetry"):
        (tmp_path / "layouts" / f"{name}.md").write_text(
            f"# {name}\n\nFirst paragraph for {name}.\n\nSecond paragraph.\n"
        )
    for name in ("memphis", "swiss", "art-deco"):
        (tmp_path / "styles" / f"{name}.md").write_text(
            f"# {name}\n\nFirst paragraph for {name}.\n"
        )
    index = {
        "version": "1",
        "built_at": "2026-05-16T00:00:00+00:00",
        "data_types": [
            {"key": "overview", "primary": "bento", "alternatives": ["hub"]},
            {"key": "timeline", "primary": "timeline", "alternatives": ["bento"]},
        ],
        "contexts": [
            {"key": "Business",  "primary": "memphis", "alternatives": ["swiss"]},
            {"key": "Technical", "primary": "swiss",   "alternatives": ["memphis"]},
        ],
        "all_layouts": ["asymmetry", "bento", "hub", "timeline"],
        "all_styles":  ["art-deco", "memphis", "swiss"],
        "fallback": {"layout": "hub", "style": "memphis"},
    }
    (tmp_path / "index.json").write_text(json.dumps(index))
    (tmp_path / "prompts-expand-system.md").write_text("expander system prompt")
    return tmp_path


def test_loads_index(catalog_dir):
    cat = InfographicCatalog(catalog_dir)
    assert cat.list_data_types() == ["overview", "timeline"]
    assert cat.list_contexts() == ["Business", "Technical"]


def test_counts(catalog_dir):
    cat = InfographicCatalog(catalog_dir)
    assert cat.counts() == {"layouts": 4, "styles": 3}


def test_sample_seeded_is_deterministic(catalog_dir):
    cat = InfographicCatalog(catalog_dir)
    a = cat.sample("overview", "Business", seed=12345)
    b = cat.sample("overview", "Business", seed=12345)
    assert a == b


def test_sample_pool_weights(catalog_dir):
    """Across 5000 seeded samples, primary should be ≥ 35% of picks
    (theoretical: 10 / (10+9+up-to-1) ≈ 50%). Alternative should be ≥ 35%
    (theoretical: 9 / 20 ≈ 45%). Outsiders ≤ 25% (theoretical: 1/20 ≈ 5%
    when only one outsider exists, higher cap left for the larger fixtures
    in test_sample_pool_weights_larger below)."""
    cat = InfographicCatalog(catalog_dir)
    layouts = Counter()
    for seed in range(5000):
        layout, _ = cat.sample("overview", "Business", seed=seed)
        layouts[layout] += 1
    primary = layouts["bento"] / 5000
    alt = layouts["hub"] / 5000
    outsiders = (layouts["timeline"] + layouts["asymmetry"]) / 5000
    assert primary >= 0.35, f"primary share {primary:.2%} < 35%"
    assert alt >= 0.35, f"alt share {alt:.2%} < 35%"
    assert outsiders <= 0.25, f"outsider share {outsiders:.2%} > 25%"


def test_sample_returns_from_pool_label(catalog_dir):
    cat = InfographicCatalog(catalog_dir)
    seen: set[PoolKind] = set()
    for seed in range(2000):
        (_, _), label = cat.sample_with_label("overview", "Business", seed=seed)
        seen.add(label["layout"])
    # Primary and alternative should both appear; outsider may appear; fallback should not.
    assert "primary" in seen
    assert "alternative" in seen
    assert "fallback" not in seen


def test_sample_unknown_data_type_uses_fallback_layout(catalog_dir):
    cat = InfographicCatalog(catalog_dir)
    (layout, _), label = cat.sample_with_label("bogus", "Business", seed=0)
    assert layout == "hub"
    assert label["layout"] == "fallback"


def test_sample_unknown_context_uses_fallback_style(catalog_dir):
    cat = InfographicCatalog(catalog_dir)
    (_, style), label = cat.sample_with_label("overview", "bogus", seed=0)
    assert style == "memphis"
    assert label["style"] == "fallback"


def test_sample_with_lock_layout(catalog_dir):
    """When lock='layout', only the style is resampled."""
    cat = InfographicCatalog(catalog_dir)
    for seed in range(100):
        layout, style = cat.sample(
            "overview", "Business", seed=seed,
            lock="layout", current=("bento", "memphis"),
        )
        assert layout == "bento", f"seed={seed} broke lock"


def test_sample_with_lock_style(catalog_dir):
    cat = InfographicCatalog(catalog_dir)
    for seed in range(100):
        layout, style = cat.sample(
            "overview", "Business", seed=seed,
            lock="style", current=("bento", "memphis"),
        )
        assert style == "memphis", f"seed={seed} broke lock"


def test_read_markdown_layouts(catalog_dir):
    cat = InfographicCatalog(catalog_dir)
    body = cat.read_markdown("layouts", "bento")
    assert body.startswith("# bento")


def test_read_markdown_styles(catalog_dir):
    cat = InfographicCatalog(catalog_dir)
    body = cat.read_markdown("styles", "memphis")
    assert "memphis" in body


def test_read_markdown_rejects_unknown_name(catalog_dir):
    cat = InfographicCatalog(catalog_dir)
    with pytest.raises(KeyError, match="unknown"):
        cat.read_markdown("layouts", "does-not-exist")


def test_read_markdown_rejects_path_traversal(catalog_dir):
    """Names containing path separators or .. must never reach the filesystem."""
    cat = InfographicCatalog(catalog_dir)
    with pytest.raises(KeyError):
        cat.read_markdown("layouts", "../../etc/passwd")
    with pytest.raises(KeyError):
        cat.read_markdown("layouts", "subdir/bento")


def test_read_markdown_rejects_unknown_kind(catalog_dir):
    cat = InfographicCatalog(catalog_dir)
    with pytest.raises(ValueError, match="kind"):
        cat.read_markdown("colours", "memphis")


def test_expander_system_prompt(catalog_dir):
    cat = InfographicCatalog(catalog_dir)
    assert cat.expander_system_prompt() == "expander system prompt"
```

- [ ] **Step 2: Run the tests — they must fail**

```bash
pytest tests/test_infographic_catalog.py -v
```

Expected: `ModuleNotFoundError: studio.infographic_catalog`.

### Task 2b: Implement the catalog class

- [ ] **Step 3: Create studio/infographic_catalog.py**

```python
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
        rng.shuffle(outsiders)  # so different seeds pick different outsiders
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
```

- [ ] **Step 4: Run tests — they must pass**

```bash
pytest tests/test_infographic_catalog.py -v
```

Expected: all 14 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add studio/infographic_catalog.py tests/test_infographic_catalog.py
git commit -m "feat: add InfographicCatalog class + weighted sampler"
```

---

## Task 3: `InfographicExpander` (TDD with mocked Ollama)

The expander posts to Ollama; on any failure, runs a deterministic regex template fallback. Tests cover the success path, three failure modes, and the fallback's determinism.

**Files:**

- Create: `studio/infographic_expander.py`
- Create: `tests/test_infographic_expander.py`

### Task 3a: Write the tests

- [ ] **Step 1: Create tests/test_infographic_expander.py**

```python
"""Tests for studio.infographic_expander.

Ollama is mocked via httpx.MockTransport — we never reach the network.
The template fallback path is exercised by simulating Connect/Timeout/bad-
response failures.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from studio.infographic_catalog import InfographicCatalog
from studio.infographic_expander import (
    ExpansionResult,
    expand,
    template_fallback,
)


@pytest.fixture
def catalog(tmp_path: Path) -> InfographicCatalog:
    (tmp_path / "layouts").mkdir()
    (tmp_path / "styles").mkdir()
    (tmp_path / "layouts" / "bento.md").write_text(
        "# Bento\n\n## Structure\nGrid of rectangular cells with one hero cell.\n\n"
        "## Visual Elements\nThick borders, drop shadows, varied cell sizes.\n\n"
        "## Text Placement\nLabel inside each cell, hero cell holds title.\n"
    )
    (tmp_path / "styles" / "memphis.md").write_text(
        "# Memphis\n\n## Color Palette\nPastels with one accent (#FF6B6B).\n\n"
        "## Visual Elements\nSquiggles, dots, geometric shapes.\n"
    )
    index = {
        "version": "1",
        "data_types": [{"key": "overview", "primary": "bento", "alternatives": []}],
        "contexts": [{"key": "Business", "primary": "memphis", "alternatives": []}],
        "all_layouts": ["bento"],
        "all_styles": ["memphis"],
        "fallback": {"layout": "bento", "style": "memphis"},
    }
    (tmp_path / "index.json").write_text(json.dumps(index))
    (tmp_path / "prompts-expand-system.md").write_text(
        "You expand user prompts into infographic descriptions."
    )
    return InfographicCatalog(tmp_path)


def _mock_ollama_ok(response_text: str) -> httpx.MockTransport:
    """Mock transport that returns a successful OpenAI-shaped response."""
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["model"]  # sanity
        return httpx.Response(200, json={
            "choices": [{"message": {"content": response_text}}],
            "model": body["model"],
        })
    return httpx.MockTransport(handler)


def test_expand_builds_request_with_layout_and_style_bodies(catalog):
    captured = {}
    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
    with patch("studio.infographic_expander._build_client",
               return_value=httpx.Client(transport=httpx.MockTransport(handler))):
        expand("Q4 results", "bento", "memphis", catalog=catalog)
    msgs = captured["body"]["messages"]
    assert msgs[0]["role"] == "system"
    assert "expand" in msgs[0]["content"].lower()
    assert "Q4 results" in msgs[1]["content"]
    assert "Bento" in msgs[1]["content"]  # layout md was embedded
    assert "Memphis" in msgs[1]["content"]  # style md was embedded


def test_expand_uses_env_model(catalog, monkeypatch):
    monkeypatch.setenv("INFOGRAPHIC_EXPANDER_MODEL", "qwen3:14b")
    captured = {}
    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
    with patch("studio.infographic_expander._build_client",
               return_value=httpx.Client(transport=httpx.MockTransport(handler))):
        expand("p", "bento", "memphis", catalog=catalog)
    assert captured["body"]["model"] == "qwen3:14b"


def test_expand_returns_ollama_response_on_success(catalog):
    transport = _mock_ollama_ok("An expanded bento-grid prompt with Memphis flair.")
    with patch("studio.infographic_expander._build_client",
               return_value=httpx.Client(transport=transport)):
        result = expand("Q4", "bento", "memphis", catalog=catalog)
    assert isinstance(result, ExpansionResult)
    assert "expanded bento-grid" in result.prompt
    assert result.fallback_used is False
    assert result.elapsed_s >= 0.0
    assert result.model  # whatever the env said


def test_expand_falls_back_on_connect_error(catalog):
    def handler(_request):
        raise httpx.ConnectError("no route to host")
    transport = httpx.MockTransport(handler)
    with patch("studio.infographic_expander._build_client",
               return_value=httpx.Client(transport=transport)):
        result = expand("Q4", "bento", "memphis", catalog=catalog)
    assert result.fallback_used is True
    assert result.prompt  # template fallback returned something


def test_expand_falls_back_on_timeout(catalog):
    def handler(_request):
        raise httpx.ReadTimeout("read timeout")
    transport = httpx.MockTransport(handler)
    with patch("studio.infographic_expander._build_client",
               return_value=httpx.Client(transport=transport)):
        result = expand("Q4", "bento", "memphis", catalog=catalog)
    assert result.fallback_used is True


def test_expand_falls_back_on_bad_response_shape(catalog):
    def handler(_request):
        return httpx.Response(200, json={"unexpected": "shape"})
    transport = httpx.MockTransport(handler)
    with patch("studio.infographic_expander._build_client",
               return_value=httpx.Client(transport=transport)):
        result = expand("Q4", "bento", "memphis", catalog=catalog)
    assert result.fallback_used is True


def test_expand_falls_back_on_http_404_model_missing(catalog):
    """Ollama returns 404 when the model isn't pulled — must fall back."""
    def handler(_request):
        return httpx.Response(404, json={"error": "model 'foo' not found"})
    transport = httpx.MockTransport(handler)
    with patch("studio.infographic_expander._build_client",
               return_value=httpx.Client(transport=transport)):
        result = expand("Q4", "bento", "memphis", catalog=catalog)
    assert result.fallback_used is True


def test_template_fallback_is_deterministic(catalog):
    layout_md = catalog.read_markdown("layouts", "bento")
    style_md = catalog.read_markdown("styles", "memphis")
    a = template_fallback("Q4", "bento", "memphis", layout_md, style_md)
    b = template_fallback("Q4", "bento", "memphis", layout_md, style_md)
    assert a == b


def test_template_fallback_includes_layout_structure(catalog):
    layout_md = catalog.read_markdown("layouts", "bento")
    style_md = catalog.read_markdown("styles", "memphis")
    out = template_fallback("Q4 results", "bento", "memphis", layout_md, style_md)
    assert "Q4 results" in out
    assert "Grid of rectangular cells" in out  # from layout's ## Structure


def test_template_fallback_includes_style_palette(catalog):
    layout_md = catalog.read_markdown("layouts", "bento")
    style_md = catalog.read_markdown("styles", "memphis")
    out = template_fallback("p", "bento", "memphis", layout_md, style_md)
    assert "Pastels with one accent" in out  # from style's ## Color Palette


def test_template_fallback_tolerates_missing_sections(catalog, tmp_path):
    """If a layout md has no `## Structure` heading, fallback still returns
    a usable string (uses whatever paragraphs are present)."""
    bare_layout = "# Sparse layout\n\nJust one paragraph, no headers.\n"
    bare_style = "# Sparse style\n\nOne paragraph.\n"
    out = template_fallback("p", "sparse", "sparse", bare_layout, bare_style)
    assert "p" in out
    assert len(out) > 50  # not empty
```

- [ ] **Step 2: Run tests — they must fail**

```bash
pytest tests/test_infographic_expander.py -v
```

Expected: `ModuleNotFoundError: studio.infographic_expander`.

### Task 3b: Implement the expander

- [ ] **Step 3: Create studio/infographic_expander.py**

```python
"""Ollama-backed prompt expander with deterministic template fallback.

Posts to Ollama's OpenAI-compatible /v1/chat/completions. On any failure
(connect, timeout, HTTP error, malformed JSON, missing model) falls back
to a regex-based template that always returns a usable prompt string so
the render path never blocks on the LLM.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass

import httpx

from studio.infographic_catalog import InfographicCatalog

log = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-oss:20b"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_TIMEOUT_S = 30.0


@dataclass(frozen=True)
class ExpansionResult:
    prompt: str
    fallback_used: bool
    elapsed_s: float
    model: str


def expand(
    user_prompt: str,
    layout: str,
    style: str,
    *,
    catalog: InfographicCatalog,
    model: str | None = None,
    ollama_url: str | None = None,
    timeout_s: float | None = None,
) -> ExpansionResult:
    """Expand user_prompt into a full infographic prompt.

    Reads layout/style markdown bodies from the catalog and embeds them in
    the user message. Returns ExpansionResult either way — callers should
    surface fallback_used so the UI can chip "Ollama unavailable".
    """
    model = model or os.environ.get("INFOGRAPHIC_EXPANDER_MODEL", DEFAULT_MODEL)
    ollama_url = ollama_url or os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL)
    timeout_s = timeout_s or float(os.environ.get("INFOGRAPHIC_EXPANDER_TIMEOUT_S",
                                                   DEFAULT_TIMEOUT_S))

    layout_md = catalog.read_markdown("layouts", layout)
    style_md = catalog.read_markdown("styles", style)
    system = catalog.expander_system_prompt()
    user = _build_user_message(user_prompt, layout, style, layout_md, style_md)

    start = time.monotonic()
    try:
        with _build_client(ollama_url, timeout_s) as client:
            r = client.post(
                "/v1/chat/completions",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "temperature": 0.7,
                },
            )
        if r.status_code != 200:
            raise RuntimeError(f"ollama HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        prompt = data["choices"][0]["message"]["content"].strip()
        if not prompt:
            raise RuntimeError("ollama returned empty content")
        elapsed = time.monotonic() - start
        log.info("infographic_expand model=%s elapsed_s=%.2f chars=%d",
                 model, elapsed, len(prompt))
        return ExpansionResult(prompt=prompt, fallback_used=False,
                                elapsed_s=elapsed, model=model)
    except Exception as exc:
        elapsed = time.monotonic() - start
        log.warning("infographic_expand fallback=template model=%s elapsed_s=%.2f reason=%r",
                    model, elapsed, exc)
        fallback_prompt = template_fallback(user_prompt, layout, style, layout_md, style_md)
        return ExpansionResult(prompt=fallback_prompt, fallback_used=True,
                                elapsed_s=elapsed, model=model)


def _build_client(ollama_url: str, timeout_s: float) -> httpx.Client:
    """Seam for tests to inject a MockTransport."""
    return httpx.Client(base_url=ollama_url, timeout=timeout_s)


def _build_user_message(
    user_prompt: str, layout: str, style: str, layout_md: str, style_md: str,
) -> str:
    return (
        f"## User prompt\n{user_prompt}\n\n"
        f"## Layout reference: {layout}\n{layout_md}\n\n"
        f"## Style reference: {style}\n{style_md}\n"
    )


# ── Template fallback ──────────────────────────────────────────────────────
#
# Deterministic — same inputs always produce the same output. Extracts the
# Structure/Visual Elements/Text Placement sections from the layout md and
# the Color Palette/Visual Elements sections from the style md. Concatenates
# into a single descriptive prompt that always passes through to the model.

_SECTION_RE = re.compile(r"^##\s+(.+?)$\n(.*?)(?=^##\s+|\Z)", re.MULTILINE | re.DOTALL)


def template_fallback(
    user_prompt: str, layout: str, style: str, layout_md: str, style_md: str,
) -> str:
    layout_sections = _extract_sections(layout_md)
    style_sections = _extract_sections(style_md)

    parts: list[str] = [f"Infographic about: {user_prompt}."]

    structure = layout_sections.get("Structure") or _first_paragraph(layout_md)
    if structure:
        parts.append(f"Layout ({layout}): {structure}")

    elements = layout_sections.get("Visual Elements")
    if elements:
        parts.append(f"Layout elements: {elements}")

    placement = layout_sections.get("Text Placement")
    if placement:
        parts.append(f"Text placement: {placement}")

    palette = style_sections.get("Color Palette") or _first_paragraph(style_md)
    if palette:
        parts.append(f"Style palette ({style}): {palette}")

    style_elements = style_sections.get("Visual Elements")
    if style_elements:
        parts.append(f"Style elements: {style_elements}")

    return " ".join(p.strip() for p in parts if p)


def _extract_sections(md: str) -> dict[str, str]:
    """Return a {heading: body-text} map for top-level `## Heading` sections."""
    out: dict[str, str] = {}
    for m in _SECTION_RE.finditer(md):
        heading = m.group(1).strip()
        body = m.group(2).strip().replace("\n", " ")
        out[heading] = body
    return out


def _first_paragraph(md: str) -> str:
    for block in md.split("\n\n"):
        block = block.strip()
        if not block or block.startswith("#"):
            continue
        return block.replace("\n", " ")
    return ""
```

- [ ] **Step 4: Run tests — they must pass**

```bash
pytest tests/test_infographic_expander.py -v
```

Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add studio/infographic_expander.py tests/test_infographic_expander.py
git commit -m "feat: add InfographicExpander with Ollama + template fallback"
```

---

## Task 4: Server endpoints — `/api/infographic/catalog` + `/api/infographic/pick` (TDD)

Two read-only endpoints plus the singleton wiring. The render endpoint comes in Task 5 (depends on JobQueue plumbing).

**Files:**

- Modify: `server.py` (+singleton init, +2 endpoint handlers)
- Create: `tests/test_api_infographic_endpoints.py`

### Task 4a: Write the integration tests

- [ ] **Step 1: Inspect existing TestClient setup in tests/**

```bash
grep -l "TestClient" tests/*.py
```

Look at how existing tests construct the FastAPI client (`tests/test_api_sensenova_precheck.py` is the closest precedent). The shared pattern is to import `server.app` and wrap in `fastapi.testclient.TestClient` directly — no async fixtures needed.

- [ ] **Step 2: Create tests/test_api_infographic_endpoints.py with catalog + pick tests**

```python
"""Integration tests for /api/infographic/catalog and /pick.

Render endpoint tests are in Task 5 — they need JobQueue mocking.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_catalog_dir(tmp_path: Path, monkeypatch) -> Path:
    """Build a synthetic catalog in tmp_path and point server.py at it."""
    (tmp_path / "layouts").mkdir()
    (tmp_path / "styles").mkdir()
    for name in ("bento", "hub", "timeline"):
        (tmp_path / "layouts" / f"{name}.md").write_text(f"# {name}\n\nBody for {name}.\n")
    for name in ("memphis", "swiss"):
        (tmp_path / "styles" / f"{name}.md").write_text(f"# {name}\n\nBody for {name}.\n")
    index = {
        "version": "1",
        "data_types": [
            {"key": "overview", "primary": "bento", "alternatives": ["hub"]},
            {"key": "timeline", "primary": "timeline", "alternatives": ["bento"]},
        ],
        "contexts": [
            {"key": "Business",  "primary": "memphis", "alternatives": ["swiss"]},
            {"key": "Technical", "primary": "swiss",   "alternatives": ["memphis"]},
        ],
        "all_layouts": ["bento", "hub", "timeline"],
        "all_styles":  ["memphis", "swiss"],
        "fallback": {"layout": "hub", "style": "memphis"},
    }
    (tmp_path / "index.json").write_text(json.dumps(index))
    (tmp_path / "prompts-expand-system.md").write_text("expander")
    monkeypatch.setenv("INFOGRAPHIC_CATALOG_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def client(test_catalog_dir) -> TestClient:
    """Force-reload server.py so the catalog singleton picks up the env var."""
    import importlib
    import server
    importlib.reload(server)
    return TestClient(server.app)


def test_get_catalog_returns_expected_shape(client):
    r = client.get("/api/infographic/catalog")
    assert r.status_code == 200
    data = r.json()
    assert data["version"] == "1"
    assert sorted(data["data_types"]) == ["overview", "timeline"]
    assert sorted(data["contexts"]) == ["Business", "Technical"]
    assert data["counts"] == {"layouts": 3, "styles": 2}


def test_post_pick_happy_path(client):
    r = client.post("/api/infographic/pick", json={
        "data_type": "overview",
        "tone": "Business",
        "seed": 42,
    })
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["layout"] in {"bento", "hub", "timeline"}
    assert data["style"] in {"memphis", "swiss"}
    assert data["from_pool"]["layout"] in {"primary", "alternative", "outsider", "fallback"}


def test_post_pick_deterministic_with_seed(client):
    body = {"data_type": "overview", "tone": "Business", "seed": 12345}
    r1 = client.post("/api/infographic/pick", json=body)
    r2 = client.post("/api/infographic/pick", json=body)
    assert r1.json()["layout"] == r2.json()["layout"]
    assert r1.json()["style"] == r2.json()["style"]


def test_post_pick_lock_layout_preserves_layout(client):
    for seed in range(20):
        r = client.post("/api/infographic/pick", json={
            "data_type": "overview",
            "tone": "Business",
            "lock": "layout",
            "current": {"layout": "bento", "style": "memphis"},
            "seed": seed,
        })
        assert r.status_code == 200, r.text
        assert r.json()["layout"] == "bento"


def test_post_pick_lock_style_preserves_style(client):
    for seed in range(20):
        r = client.post("/api/infographic/pick", json={
            "data_type": "overview",
            "tone": "Business",
            "lock": "style",
            "current": {"layout": "bento", "style": "memphis"},
            "seed": seed,
        })
        assert r.status_code == 200
        assert r.json()["style"] == "memphis"


def test_post_pick_unknown_data_type_returns_fallback(client):
    """Unknown data_type doesn't 400 — sampler returns the fallback layout
    with from_pool='fallback'. That keeps the UI responsive when a stale
    dropdown is in play; the frontend can refresh /catalog at its leisure."""
    r = client.post("/api/infographic/pick", json={
        "data_type": "does-not-exist",
        "tone": "Business",
    })
    assert r.status_code == 200
    assert r.json()["from_pool"]["layout"] == "fallback"


def test_post_pick_invalid_lock_returns_400(client):
    """lock set without current → 400."""
    r = client.post("/api/infographic/pick", json={
        "data_type": "overview",
        "tone": "Business",
        "lock": "layout",
        # current omitted
    })
    assert r.status_code == 400
    assert "current" in r.json()["detail"].lower()


def test_post_pick_lock_with_unknown_current_returns_400(client):
    r = client.post("/api/infographic/pick", json={
        "data_type": "overview",
        "tone": "Business",
        "lock": "layout",
        "current": {"layout": "not-a-real-layout", "style": "memphis"},
    })
    assert r.status_code == 400
```

> **Note on the spec deviation:** the spec said "unknown_data_type returns 400". We're returning 200 + fallback because the catalog already has a fallback row and the UX is better. Update the spec doc with a one-line note after Task 4 lands.

- [ ] **Step 3: Run the tests — they must fail**

```bash
pytest tests/test_api_infographic_endpoints.py -v
```

Expected: 404 on `/api/infographic/catalog` (endpoint not yet added).

### Task 4b: Add the singleton and endpoints to server.py

- [ ] **Step 4: Find the right insertion point in server.py**

```bash
grep -n "^# ----\|^app = FastAPI\|^job_queue = " server.py | head -20
```

Find a block close to other singleton initialisations (around `job_queue = JobQueue()` near line 36) and just below the existing studio routes (`@app.get("/studio/infographic")` near line 265). The new singleton initialises at module import; the two endpoints go after the existing `/api/sensenova/precheck` block (~line 5208) for locality with related sensenova/render endpoints.

- [ ] **Step 5: Add the singleton + helper near server.py:36**

Edit `server.py` near the top, just below `job_queue = JobQueue()`:

```python
# Infographic catalog — vendored from sn-infographic; built by
# scripts/build_infographic_catalog.py. We load lazily on first access to
# keep import-time fast and to make the Freeform tab keep working on a
# fresh clone where the catalog hasn't been built yet.
_INFOGRAPHIC_CATALOG = None
_INFOGRAPHIC_CATALOG_DIR = os.environ.get(
    "INFOGRAPHIC_CATALOG_DIR", "static/studio/catalogs"
)


def _get_infographic_catalog():
    """Lazy singleton accessor. Returns None if the catalog isn't built —
    callers must handle that path (Catalog tab disabled, Freeform still works)."""
    global _INFOGRAPHIC_CATALOG
    if _INFOGRAPHIC_CATALOG is not None:
        return _INFOGRAPHIC_CATALOG
    try:
        from studio.infographic_catalog import InfographicCatalog
        _INFOGRAPHIC_CATALOG = InfographicCatalog(Path(_INFOGRAPHIC_CATALOG_DIR))
        print(f"[infographic_catalog] loaded from {_INFOGRAPHIC_CATALOG_DIR}: "
              f"{_INFOGRAPHIC_CATALOG.counts()}")
        return _INFOGRAPHIC_CATALOG
    except FileNotFoundError as e:
        print(f"[infographic_catalog] not built — run "
              f"`python -m scripts.build_infographic_catalog` ({e})")
        return None
```

(If `os` and `Path` aren't already imported at top of server.py, they are — verified at lines 17–18.)

- [ ] **Step 6: Add the `/api/infographic/catalog` endpoint after the `/api/sensenova/precheck` block**

```python
# -----------------------------------------------------------------------------
# /api/infographic/* — catalog-driven flow (Move #1 of the SenseNova-Skills port).
#
# /catalog → dropdown content (data_types, contexts, counts).
# /pick    → weighted-random layout+style sample with optional lock.
# /render  → expand prompt via Ollama, then dispatch to /api/sensenova/render's
#            internals. Defined further below in this section.
# -----------------------------------------------------------------------------


@app.get("/api/infographic/catalog")
async def infographic_catalog():
    cat = _get_infographic_catalog()
    if cat is None:
        raise HTTPException(status_code=503,
                            detail="catalog_not_built — run scripts/build_infographic_catalog")
    return {
        "version": cat.index.get("version", "1"),
        "data_types": cat.list_data_types(),
        "contexts": cat.list_contexts(),
        "counts": cat.counts(),
    }


class _InfographicPickBody(BaseModel):
    data_type: str = Field(min_length=1)
    tone: str = Field(min_length=1)
    lock: Optional[Literal["layout", "style"]] = None
    current: Optional[dict] = None  # {"layout": str, "style": str}
    seed: Optional[int] = None


@app.post("/api/infographic/pick")
async def infographic_pick(body: _InfographicPickBody):
    cat = _get_infographic_catalog()
    if cat is None:
        raise HTTPException(status_code=503, detail="catalog_not_built")

    current_tuple: Optional[tuple[str, str]] = None
    if body.lock is not None:
        if not body.current or "layout" not in body.current or "style" not in body.current:
            raise HTTPException(
                status_code=400,
                detail="invalid_lock — lock requires current.layout and current.style",
            )
        layout_name = body.current["layout"]
        style_name = body.current["style"]
        if layout_name not in cat._layout_set:
            raise HTTPException(status_code=400,
                                detail=f"invalid_lock — unknown current.layout {layout_name!r}")
        if style_name not in cat._style_set:
            raise HTTPException(status_code=400,
                                detail=f"invalid_lock — unknown current.style {style_name!r}")
        current_tuple = (layout_name, style_name)

    (layout, style), from_pool = cat.sample_with_label(
        body.data_type, body.tone,
        seed=body.seed, lock=body.lock, current=current_tuple,
    )
    print(f"[infographic_pick] data_type={body.data_type!r} tone={body.tone!r} "
          f"layout={layout} style={style} lock={body.lock} from_pool={from_pool}")
    return {"layout": layout, "style": style, "from_pool": from_pool}
```

If `HTTPException`, `Optional`, or `Literal` are not imported at the top of `server.py`, add them. Quick check:

```bash
grep -n "^from fastapi\|^from typing\|^from pydantic" server.py | head -5
```

If `HTTPException` is missing from the FastAPI import, append it to that line. If `Literal` / `Optional` are missing from `typing`, add them. (Pydantic v2 also exports both via `typing`.)

- [ ] **Step 7: Run the tests — they must pass**

```bash
pytest tests/test_api_infographic_endpoints.py -v
```

Expected: all 8 tests PASS. If `test_post_pick_invalid_lock_returns_400` fails because Pydantic rejects the body before our handler runs, loosen the model (use `dict` rather than a sub-model) or relax the validator — the spec wants the 400 to come from our handler with a precise detail message.

- [ ] **Step 8: Manual smoke**

```bash
# Reload the running server (it's a `systemctl --user` service per memory)
systemctl --user restart open-palette.service
sleep 2
curl -s http://127.0.0.1:8000/api/infographic/catalog | python3 -m json.tool | head -20
curl -s -X POST http://127.0.0.1:8000/api/infographic/pick \
    -H 'Content-Type: application/json' \
    -d '{"data_type":"overview / summary","tone":"Professional / Business","seed":42}' \
    | python3 -m json.tool
```

Expected: catalog returns 21 data_types + 21 contexts and counts `{"layouts": 87, "styles": 66}`. Pick returns a `{layout, style, from_pool}` triple.

- [ ] **Step 9: Commit**

```bash
git add server.py tests/test_api_infographic_endpoints.py
git commit -m "feat: add /api/infographic/catalog + /pick endpoints"
```

---

## Task 5: Render endpoint `/api/infographic/render` (TDD)

Adds the third endpoint. It runs `expand()` inline, then forwards into the same JobQueue path as `/api/sensenova/render`. The render response carries the expanded prompt + expansion metadata so the frontend can show what was actually rendered.

**Files:**

- Modify: `server.py` (+1 endpoint, ~60 LOC)
- Modify: `tests/test_api_infographic_endpoints.py` (+render tests)

### Task 5a: Add render tests

- [ ] **Step 1: Append render tests to tests/test_api_infographic_endpoints.py**

```python
# ── /api/infographic/render ────────────────────────────────────────────────


def test_post_render_expansion_inline_then_enqueues(client, monkeypatch):
    """Render path: expand() runs inline, then a JobQueue submission happens.
    We mock both — JobQueue.submit_background to capture the call, and
    expand() to short-circuit Ollama."""
    import server
    from studio.infographic_expander import ExpansionResult

    captured = {}
    def fake_submit(coro, *, lane, job_id, timeout):
        captured["lane"] = lane
        captured["job_id"] = job_id
        captured["timeout"] = timeout
        coro.close()  # we never run the actual render

    def fake_expand(user_prompt, layout, style, *, catalog):
        return ExpansionResult(
            prompt=f"EXPANDED({user_prompt}) layout={layout} style={style}",
            fallback_used=False, elapsed_s=1.5, model="gpt-oss:20b",
        )

    monkeypatch.setattr(server.job_queue, "submit_background", fake_submit)
    monkeypatch.setattr("server.expand", fake_expand)

    r = client.post("/api/infographic/render", json={
        "user_prompt": "Q4 capability matrix",
        "data_type": "overview",
        "tone": "Business",
        "layout": "bento",
        "style": "memphis",
        "backend": "sensenova",
        "width": 1024,
        "height": 1820,
        "seed": 42,
        "num_steps": 50,
    })
    assert r.status_code == 202, r.text
    data = r.json()
    assert data["job_id"]
    assert "EXPANDED(Q4 capability matrix)" in data["expanded_prompt"]
    assert data["expansion"]["fallback_used"] is False
    assert data["expansion"]["model"] == "gpt-oss:20b"
    assert captured["lane"] == "gpu"
    assert captured["job_id"] == data["job_id"]


def test_post_render_propagates_fallback_used(client, monkeypatch):
    import server
    from studio.infographic_expander import ExpansionResult

    monkeypatch.setattr(server.job_queue, "submit_background", lambda c, **kw: c.close())
    monkeypatch.setattr("server.expand", lambda *a, **kw: ExpansionResult(
        prompt="template prompt", fallback_used=True, elapsed_s=0.0, model="gpt-oss:20b",
    ))
    r = client.post("/api/infographic/render", json={
        "user_prompt": "p", "data_type": "overview", "tone": "Business",
        "layout": "bento", "style": "memphis",
    })
    assert r.status_code == 202
    assert r.json()["expansion"]["fallback_used"] is True


def test_post_render_unknown_layout_returns_400(client):
    r = client.post("/api/infographic/render", json={
        "user_prompt": "p", "data_type": "overview", "tone": "Business",
        "layout": "no-such-layout", "style": "memphis",
    })
    assert r.status_code == 400
    assert "layout" in r.json()["detail"]


def test_post_render_unknown_style_returns_400(client):
    r = client.post("/api/infographic/render", json={
        "user_prompt": "p", "data_type": "overview", "tone": "Business",
        "layout": "bento", "style": "no-such-style",
    })
    assert r.status_code == 400
```

- [ ] **Step 2: Run the new tests — they must fail**

```bash
pytest tests/test_api_infographic_endpoints.py -k render -v
```

Expected: 404 on `/api/infographic/render` for all four.

### Task 5b: Implement the render endpoint

- [ ] **Step 3: Add `from studio.infographic_expander import expand, ExpansionResult` near the top of server.py**

Place it next to the other `from studio.*` imports — `grep -n "^from studio\." server.py | head` will show the cluster.

- [ ] **Step 4: Append the render endpoint after the `/pick` block**

```python
class _InfographicRenderBody(BaseModel):
    user_prompt: str = Field(min_length=1)
    data_type: str = Field(min_length=1)
    tone: str = Field(min_length=1)
    layout: str = Field(min_length=1)
    style: str = Field(min_length=1)
    # Render params — same defaults as /api/sensenova/render's body.
    backend: str = Field(default="sensenova", pattern="^(sensenova|hidream)$")
    width: int = Field(default=1024, ge=512, le=2720)
    height: int = Field(default=1820, ge=512, le=2720)
    seed: int = Field(default=42, ge=0)
    cfg_scale: float = Field(default=4.0, ge=0.5, le=10.0)
    num_steps: int = Field(default=50, ge=4, le=100)
    use_prompt_agent: bool = Field(default=True)
    reserve_logo_slots: int = Field(default=0, ge=0, le=10)


@app.post("/api/infographic/render", status_code=202)
async def infographic_render(body: _InfographicRenderBody):
    """Two-stage: inline expand() (~2s) → JobQueue render (~80s).

    Returns the job_id immediately along with the expanded prompt and the
    expansion metadata so the UI can show what was sent to the renderer
    and chip "fallback used" when Ollama wasn't reachable.
    """
    cat = _get_infographic_catalog()
    if cat is None:
        raise HTTPException(status_code=503, detail="catalog_not_built")
    if body.layout not in cat._layout_set:
        raise HTTPException(status_code=400, detail=f"unknown_layout: {body.layout!r}")
    if body.style not in cat._style_set:
        raise HTTPException(status_code=400, detail=f"unknown_style: {body.style!r}")

    expansion = expand(body.user_prompt, body.layout, body.style, catalog=cat)

    job_id = uuid.uuid4().hex[:12]
    params = {
        "prompt": expansion.prompt,
        "width": body.width,
        "height": body.height,
        "seed": body.seed,
        "cfg_scale": body.cfg_scale,
        "num_steps": body.num_steps,
        "backend": body.backend,
        "use_prompt_agent": body.use_prompt_agent,
        "reserve_logo_slots": body.reserve_logo_slots,
    }
    jobs[job_id] = {"status": "queued", "params": params, "progress": 0}
    runner = (
        _run_hidream_render_job
        if body.backend == "hidream"
        else _run_sensenova_render_job
    )
    job_queue.submit_background(
        runner(job_id, params),
        lane="gpu",
        job_id=job_id,
        timeout=1800,
    )
    print(f"[infographic_render] job_id={job_id} backend={body.backend} "
          f"layout={body.layout} style={body.style} "
          f"fallback={expansion.fallback_used} model={expansion.model}")
    return {
        "job_id": job_id,
        "expanded_prompt": expansion.prompt,
        "expansion": {
            "elapsed_s": expansion.elapsed_s,
            "model": expansion.model,
            "fallback_used": expansion.fallback_used,
        },
    }
```

- [ ] **Step 5: Run the render tests — they must pass**

```bash
pytest tests/test_api_infographic_endpoints.py -v
```

Expected: all 12 tests in the file PASS.

- [ ] **Step 6: Full backend test sweep**

```bash
pytest tests/test_build_infographic_catalog.py \
       tests/test_infographic_catalog.py \
       tests/test_infographic_expander.py \
       tests/test_api_infographic_endpoints.py \
       -v
```

Expected: ~40 tests PASS, none skipped.

- [ ] **Step 7: Manual smoke against the live service**

```bash
systemctl --user restart open-palette.service
sleep 3
curl -s -X POST http://127.0.0.1:8000/api/infographic/render \
    -H 'Content-Type: application/json' \
    -d '{
      "user_prompt": "Q4 capability matrix for the platform team",
      "data_type": "overview / summary",
      "tone": "Professional / Business",
      "layout": "bento-grid",
      "style": "corporate-memphis",
      "backend": "sensenova"
    }' | python3 -m json.tool
```

Expected: 202 with a job_id, an expanded_prompt that's noticeably longer than the input, and `expansion.fallback_used: false` (assuming Ollama is up). Watch the WS for the eventual render completion.

- [ ] **Step 8: Commit**

```bash
git add server.py tests/test_api_infographic_endpoints.py
git commit -m "feat: add /api/infographic/render with inline Ollama expansion"
```

---

## Task 6: Frontend module split — lift current code to `freeform-mode.js`

Frontend work is done in three commits: (a) lift the existing gallery flow to a module without behavioural change, (b) build the dispatcher, (c) build the Catalog tab. Splitting commits this way means any regression on the existing flow shows up as a clean revert target.

**Files:**

- Create: `static/studio/js/infographic/freeform-mode.js`
- Modify: `static/studio/js/infographic.js` (will become the dispatcher in Task 7)

### Task 6a: Lift current code to freeform-mode.js

- [ ] **Step 1: Copy current infographic.js verbatim to the new module**

```bash
mkdir -p static/studio/js/infographic
cp static/studio/js/infographic.js static/studio/js/infographic/freeform-mode.js
```

- [ ] **Step 2: Wrap the module as an init function**

Edit `static/studio/js/infographic/freeform-mode.js`. The current code runs at module-import time (top-level `loadCorpus()`, `connectWS()`, `pollWorker()` calls). Wrap that bootstrap in an exported `initFreeformMode()` so the dispatcher controls when it kicks off:

Find the bottom of the file (`// ── Boot ───────...`) and change:

```javascript
// ── Boot ────────────────────────────────────────────────────────────────────
loadCorpus().catch(e => {
  clear(els.gallery);
  els.gallery.appendChild(el('div', {
    cls: 'error',
    text: `Failed to load corpus: ${String(e)}`,
    attrs: { style: 'padding:24px;color:#ffb3b3' },
  }));
});
connectWS();
pollWorker();
```

to:

```javascript
// ── Boot ────────────────────────────────────────────────────────────────────
let booted = false;
export function initFreeformMode() {
  if (booted) return;
  booted = true;
  loadCorpus().catch(e => {
    clear(els.gallery);
    els.gallery.appendChild(el('div', {
      cls: 'error',
      text: `Failed to load corpus: ${String(e)}`,
      attrs: { style: 'padding:24px;color:#ffb3b3' },
    }));
  });
  connectWS();
  pollWorker();
}
```

Important: the module still references `els.galleryWrap`, `els.editorWrap`, etc. — those DOM ids exist inside the Freeform tab panel after Task 8. Until then they remain at the top level of the page (the HTML changes happen in Task 8).

- [ ] **Step 3: Verify the file parses**

```bash
node --check static/studio/js/infographic/freeform-mode.js
```

Expected: no output. Errors here mean the wrap introduced a syntax issue — fix and re-check.

- [ ] **Step 4: Commit (split point: behavioural no-op)**

```bash
git add static/studio/js/infographic/freeform-mode.js
git commit -m "refactor: lift /studio/infographic JS to freeform-mode module (no behaviour change)"
```

> The existing `infographic.js` still exists and is what the page imports — nothing is broken yet. The dispatcher swap happens in Task 7.

---

## Task 7: Dispatcher — rewrite `infographic.js` to be a tab switcher

Replace the existing 400-line file with a small dispatcher that looks at `localStorage.infographic.activeTab`, mounts either `freeform-mode.js` or `catalog-mode.js`, and exposes a `switchTab` function the HTML tab buttons call.

**Files:**

- Modify: `static/studio/js/infographic.js`

- [ ] **Step 1: Overwrite static/studio/js/infographic.js with the dispatcher**

```javascript
// Infographic page entry — thin dispatcher between Catalog (default) and
// Freeform tabs. Each tab is a module under ./infographic/ that owns its
// own DOM panel inside the page.

import { initFreeformMode } from './infographic/freeform-mode.js';
import { initCatalogMode } from './infographic/catalog-mode.js';

const STORAGE_KEY = 'infographic.activeTab';
const VALID_TABS = ['catalog', 'freeform'];

function getInitialTab() {
  const stored = localStorage.getItem(STORAGE_KEY);
  return VALID_TABS.includes(stored) ? stored : 'catalog';
}

function setActiveTab(name) {
  if (!VALID_TABS.includes(name)) return;
  localStorage.setItem(STORAGE_KEY, name);
  for (const tab of VALID_TABS) {
    const btn = document.getElementById(`tab-${tab}`);
    const panel = document.getElementById(`panel-${tab}`);
    if (btn) {
      btn.setAttribute('aria-selected', String(tab === name));
      btn.classList.toggle('active', tab === name);
    }
    if (panel) {
      panel.hidden = tab !== name;
    }
  }
  if (name === 'catalog') initCatalogMode();
  if (name === 'freeform') initFreeformMode();
}

function wireTabButtons() {
  for (const tab of VALID_TABS) {
    const btn = document.getElementById(`tab-${tab}`);
    if (btn) btn.addEventListener('click', () => setActiveTab(tab));
  }
}

// Boot
wireTabButtons();
setActiveTab(getInitialTab());
```

- [ ] **Step 2: Check parse**

```bash
node --check static/studio/js/infographic.js
```

Expected: no output. Note the dispatcher imports `./infographic/catalog-mode.js` which doesn't exist yet — that's fine for the syntax check (ES module resolution happens in the browser); but loading the page now would 404 on the import. Task 8 lands catalog-mode.js to fix that.

- [ ] **Step 3: Stage the dispatcher swap — but don't commit yet**

Without `catalog-mode.js` the page is broken. Keep working — Task 8 completes the swap in one commit.

---

## Task 8: Catalog tab — `catalog-mode.js`

This is the meat of the frontend work. State machine, two dropdowns, pick strip with re-roll, selection details, render flow that subscribes to the existing WS infrastructure.

**Files:**

- Create: `static/studio/js/infographic/catalog-mode.js`
- Modify: `static/studio/infographic.html` (+tab strip, +catalog panel)

### Task 8a: Add the catalog panel + tab strip to infographic.html

- [ ] **Step 1: Read the current head/body skeleton of infographic.html**

You already have its full content cached above. Two surgical edits are needed:

(1) Wrap the existing worker-bar + gallery-wrap + editor-wrap inside `<div id="panel-freeform" hidden>` (with no other change).

(2) Insert a tab strip + new `<div id="panel-catalog">` containing the Catalog UI just above the freeform panel.

- [ ] **Step 2: Make the HTML edits**

Open `static/studio/infographic.html`. Find the line:

```html
  <div class="v2-wrap">
    <!-- Worker lifecycle controls (reused from v1) -->
    <div class="worker-bar" id="worker-bar">
```

Replace it (and the closing `</div>` of `.v2-wrap`) with:

```html
  <div class="v2-wrap">

    <div class="tab-strip" role="tablist" aria-label="Infographic mode">
      <button type="button" role="tab" id="tab-catalog"  aria-selected="true"  class="tab-btn active">Catalog</button>
      <button type="button" role="tab" id="tab-freeform" aria-selected="false" class="tab-btn">Freeform</button>
    </div>

    <!-- ── Catalog tab ─────────────────────────────────────────────────── -->
    <div id="panel-catalog" role="tabpanel" aria-labelledby="tab-catalog">
      <div class="catalog-card">
        <label class="catalog-prompt-label">
          What's this about?
          <textarea id="cat-user-prompt"
            placeholder="e.g. Q4 capability matrix for the platform team"
            rows="3" spellcheck="false"></textarea>
        </label>

        <div class="catalog-pickers">
          <label>Data type
            <select id="cat-data-type" disabled><option>Loading…</option></select>
          </label>
          <label>Tone / Context
            <select id="cat-tone" disabled><option>Loading…</option></select>
          </label>
        </div>

        <div class="pick-strip" id="cat-pick-strip" aria-live="polite" hidden>
          <div class="pick-row">
            <span class="pick-label">Layout</span>
            <span class="pick-value" id="cat-layout-name">—</span>
            <span class="pick-badge" id="cat-layout-badge"></span>
            <button type="button" id="cat-reroll-layout"
                    class="reroll-btn" aria-label="Re-roll layout"
                    title="Re-roll layout">🎲</button>
          </div>
          <div class="pick-row">
            <span class="pick-label">Style</span>
            <span class="pick-value" id="cat-style-name">—</span>
            <span class="pick-badge" id="cat-style-badge"></span>
            <button type="button" id="cat-reroll-style"
                    class="reroll-btn" aria-label="Re-roll style"
                    title="Re-roll style">🎲</button>
          </div>
          <details class="selection-details">
            <summary>Show selection details</summary>
            <div class="detail-body">
              <div class="detail-section">
                <h4 id="cat-layout-detail-title">Layout</h4>
                <p id="cat-layout-detail">—</p>
              </div>
              <div class="detail-section">
                <h4 id="cat-style-detail-title">Style</h4>
                <p id="cat-style-detail">—</p>
              </div>
            </div>
          </details>
        </div>

        <div class="catalog-controls">
          <label>Backend
            <select id="cat-backend">
              <option value="sensenova" selected>SenseNova U1</option>
              <option value="hidream">HiDream-O1 (better text)</option>
            </select>
          </label>
          <label>Steps
            <select id="cat-steps">
              <option value="20">20 (preview)</option>
              <option value="50" selected>50 (final)</option>
              <option value="75">75 (extra)</option>
            </select>
          </label>
          <label>Width
            <input type="number" id="cat-width" min="512" max="2720" step="32" value="1024" />
          </label>
          <label>Height
            <input type="number" id="cat-height" min="512" max="2720" step="32" value="1820" />
          </label>
        </div>

        <div class="catalog-actions">
          <button type="button" id="cat-pick-btn" disabled>Pick layout &amp; style</button>
          <button type="button" id="cat-render-btn" disabled>Render</button>
        </div>

        <div id="cat-fallback-chip" class="fallback-chip" hidden>
          Ollama unavailable — template prompt used
        </div>
        <details class="expanded-prompt-details" id="cat-expanded-wrap" hidden>
          <summary>Show expanded prompt</summary>
          <pre id="cat-expanded"></pre>
        </details>
        <div id="cat-render-status"></div>
        <div class="progress-track"><div class="progress-fill" id="cat-progress-fill"></div></div>
        <img id="cat-output-preview" hidden alt="output" />
        <div id="cat-output-actions" hidden>
          <a id="cat-download-link" class="small-btn" download>Download PNG</a>
        </div>
      </div>
    </div>

    <!-- ── Freeform tab (existing flow, unchanged) ─────────────────────── -->
    <div id="panel-freeform" role="tabpanel" aria-labelledby="tab-freeform" hidden>
      <!-- Worker lifecycle controls (reused from v1) -->
      <div class="worker-bar" id="worker-bar">
        <span class="worker-pill state-unknown" id="sense-pill">
          <span class="dot"></span><span class="label">SenseNova: …</span>
        </span>
        <button type="button" class="worker-btn" id="sense-start">Start worker</button>
        <button type="button" class="worker-btn" id="sense-restart">Restart</button>
        <button type="button" class="worker-btn danger" id="sense-stop">Stop</button>
        <span class="spacer"></span>
        <span class="vram" id="vram-readout"></span>
      </div>

      <!-- Gallery view (default) -->
      <div class="gallery-wrap" id="gallery-wrap">
        <div class="filter-row" id="filter-row">
          <span class="corpus-hint" id="corpus-hint"></span>
        </div>
        <div class="gallery" id="gallery"></div>
      </div>

      <!-- Editor view (shown after clicking a card) -->
      <div class="editor-wrap" id="editor-wrap" hidden>
        <button class="back-link" id="back-link" type="button">← Back to gallery</button>
        <div class="editor">
          <div class="pane">
            <img class="reference-img" id="reference-img" alt="reference" />
            <div class="reference-caption" id="reference-caption"></div>
          </div>
          <div class="pane">
            <textarea class="prompt-area" id="prompt-area"
              spellcheck="false"
              placeholder="Edit the prompt…"></textarea>
            <div class="controls">
              <label>Backend
                <select id="backend-input">
                  <option value="sensenova" selected>SenseNova U1 (default)</option>
                  <option value="hidream">HiDream-O1 (better text)</option>
                </select>
              </label>
              <label>Width
                <input type="number" id="width-input" min="512" max="2720" step="32" />
              </label>
              <label>Height
                <input type="number" id="height-input" min="512" max="2720" step="32" />
              </label>
              <label>Seed
                <input type="number" id="seed-input" min="0" value="42" />
              </label>
              <label>Steps
                <select id="steps-input">
                  <option value="20">20 (preview)</option>
                  <option value="50" selected>50 (final)</option>
                  <option value="75">75 (extra)</option>
                  <option value="100">100 (max)</option>
                </select>
              </label>
              <label class="checkbox-label">
                <input type="checkbox" id="use-agent-input" checked />
                <span>SCALIST rewriter (HiDream)</span>
              </label>
              <label class="checkbox-label">
                <input type="checkbox" id="reserve-slots-input" />
                <span>Reserve N logo slots</span>
              </label>
              <label id="slot-count-wrap" hidden>Slots
                <input type="number" id="slot-count-input" min="2" max="10" value="4" />
              </label>
            </div>
            <div class="actions">
              <button type="button" id="render-btn">Render</button>
              <button type="button" id="cancel-btn" hidden>Cancel</button>
            </div>
            <div id="render-status"></div>
            <div class="progress-track"><div class="progress-fill" id="progress-fill"></div></div>
            <img id="output-preview" hidden alt="output" />
            <div id="output-actions" hidden>
              <a id="download-link" class="small-btn" download>Download PNG</a>
              <a id="fill-link" class="small-btn" hidden>Place logos →</a>
            </div>
          </div>
        </div>
      </div>
    </div>

  </div>
```

- [ ] **Step 3: Add the new CSS rules**

Inside the existing `<style>` block in infographic.html, append before the closing `</style>`:

```css
    /* Tab strip */
    .tab-strip {
      display: flex; gap: 4px; margin-bottom: 12px;
      border-bottom: 1px solid var(--border, #333);
    }
    .tab-btn {
      padding: 8px 16px; font-size: 13px;
      background: transparent; color: var(--text-dim, #888);
      border: 1px solid transparent; border-bottom: none;
      border-radius: 6px 6px 0 0; cursor: pointer;
    }
    .tab-btn.active {
      color: var(--text, #eee);
      background: var(--card-bg, #1a1a1a);
      border-color: var(--border, #333);
    }
    .tab-btn:focus { outline: 2px solid var(--accent, #4a90e2); }
    [hidden] { display: none !important; }

    /* Catalog card */
    .catalog-card {
      background: var(--card-bg, #1a1a1a);
      border: 1px solid var(--border, #333);
      border-radius: 12px; padding: 16px;
      max-width: 760px; margin: 0 auto;
    }
    .catalog-prompt-label {
      display: block; font-size: 12px;
      color: var(--text-dim, #888); margin-bottom: 12px;
    }
    .catalog-prompt-label textarea {
      width: 100%; padding: 10px; margin-top: 4px;
      font: 14px/1.4 ui-sans-serif, system-ui, sans-serif;
      background: var(--input-bg, #0d0d0d); color: var(--text, #eee);
      border: 1px solid var(--border, #333); border-radius: 8px;
      box-sizing: border-box; resize: vertical;
    }
    .catalog-pickers { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px; }
    .catalog-pickers label, .catalog-controls label {
      display: flex; flex-direction: column; gap: 4px;
      font-size: 11px; color: var(--text-dim, #888);
    }
    .catalog-pickers select, .catalog-controls input, .catalog-controls select {
      padding: 6px 8px; font-size: 13px;
      background: var(--input-bg, #0d0d0d); color: var(--text, #eee);
      border: 1px solid var(--border, #333); border-radius: 6px;
    }
    .catalog-controls { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-top: 12px; }

    /* Pick strip */
    .pick-strip {
      margin: 12px 0; padding: 10px;
      border: 1px solid var(--border, #333); border-radius: 8px;
      background: rgba(255,255,255,0.02);
    }
    .pick-row { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
    .pick-label { width: 60px; font-size: 12px; color: var(--text-dim, #888); }
    .pick-value { font-family: ui-monospace, monospace; font-size: 13px; color: var(--text, #eee); }
    .pick-badge { font-size: 10px; padding: 2px 8px; border-radius: 999px; }
    .pick-badge.primary     { background: rgba(74, 222, 128, 0.15); color: #4ade80; }
    .pick-badge.alternative { background: rgba(74, 144, 226, 0.15); color: #4a90e2; }
    .pick-badge.outsider    { background: rgba(251, 191, 36, 0.15); color: #fbbf24; }
    .pick-badge.fallback    { background: rgba(239, 68, 68, 0.15);  color: #ef4444; }
    .reroll-btn {
      margin-left: auto; padding: 4px 10px; font-size: 14px;
      background: transparent; color: var(--text, #eee);
      border: 1px solid var(--border, #333); border-radius: 6px; cursor: pointer;
    }
    .reroll-btn:hover { border-color: var(--accent, #4a90e2); }
    .reroll-btn:disabled { opacity: 0.4; cursor: not-allowed; }
    .selection-details { margin-top: 8px; font-size: 12px; }
    .selection-details summary { cursor: pointer; color: var(--text-dim, #888); }
    .detail-body { padding-top: 8px; }
    .detail-section { margin-bottom: 6px; }
    .detail-section h4 { font-size: 11px; margin: 0 0 2px; color: var(--text-dim, #888); }
    .detail-section p  { font-size: 12px; margin: 0; color: var(--text, #eee); line-height: 1.4; }

    /* Catalog actions */
    .catalog-actions { display: flex; gap: 8px; margin-top: 14px; }
    .catalog-actions button {
      flex: 1; padding: 10px; border-radius: 8px;
      font-weight: 600; cursor: pointer; border: none;
      background: var(--accent, #4a90e2); color: #fff;
    }
    .catalog-actions button:disabled { opacity: 0.4; cursor: not-allowed; }
    .fallback-chip {
      margin-top: 10px; padding: 6px 10px; font-size: 12px;
      background: rgba(251, 191, 36, 0.15); color: #fbbf24;
      border: 1px solid rgba(251, 191, 36, 0.3); border-radius: 6px;
    }
    .expanded-prompt-details { margin-top: 10px; font-size: 12px; }
    .expanded-prompt-details summary { cursor: pointer; color: var(--text-dim, #888); }
    .expanded-prompt-details pre {
      margin-top: 6px; padding: 10px;
      background: var(--input-bg, #0d0d0d); color: var(--text, #eee);
      border: 1px solid var(--border, #333); border-radius: 6px;
      white-space: pre-wrap; font: 12px/1.4 ui-monospace, monospace;
      max-height: 240px; overflow-y: auto;
    }
    #cat-render-status {
      margin-top: 10px; font-size: 12px; color: var(--text-dim, #888);
      min-height: 18px;
    }
    #cat-output-preview {
      margin-top: 12px; width: 100%; border-radius: 8px;
      background: #0a0a0a; max-height: 60vh; object-fit: contain;
    }
    #cat-output-preview[hidden] { display: none; }
    #cat-output-actions { margin-top: 8px; display: flex; gap: 8px; }
    #cat-output-actions[hidden] { display: none; }
```

- [ ] **Step 4: Bump the service worker cache version**

Open `static/sw.js`, find the `CACHE_VERSION` const, and bump it by one (e.g. `'v22'` → `'v23'`). This forces existing PWA clients to fetch the new HTML + JS modules. Required per memory `feedback_pwa_cache_version_bump`.

### Task 8b: Implement catalog-mode.js

- [ ] **Step 5: Create static/studio/js/infographic/catalog-mode.js**

```javascript
// Catalog mode for /studio/infographic. State machine + two dropdowns +
// pick strip with re-roll + render flow that subscribes to the same WS
// channel the freeform flow uses.
//
// DOM construction uses textContent everywhere — never innerHTML — to
// keep XSS exposure at zero (catalog content is vendored but the user
// prompt is user input and could end up echoed back via the expanded
// prompt).

const STATE = {
  EMPTY: 'EMPTY',
  READY_TO_PICK: 'READY_TO_PICK',
  PICKED: 'PICKED',
  RENDERING: 'RENDERING',
  RENDERED: 'RENDERED',
};

const STORAGE_DATA_TYPE = 'infographic.dataType';
const STORAGE_TONE = 'infographic.tone';

// In-memory cache of `kind/name → first-paragraph` for the selection-details
// box. Catalog md files don't change at runtime, so a per-page cache is fine.
const mdParagraphCache = new Map();

// ── State ───────────────────────────────────────────────────────────────────
const state = {
  state: STATE.EMPTY,
  dataType: null,
  tone: null,
  layout: null,
  style: null,
  fromPool: { layout: null, style: null },
  jobId: null,
  ws: null,
  pollTimer: null,
  lastWsAt: 0,
};

const POLL_INTERVAL_MS = 3000;
const WS_STALENESS_MS = 8000;

// ── DOM ────────────────────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);
const els = {
  userPrompt: () => $('cat-user-prompt'),
  dataTypeSel: () => $('cat-data-type'),
  toneSel: () => $('cat-tone'),
  pickStrip: () => $('cat-pick-strip'),
  layoutName: () => $('cat-layout-name'),
  styleName: () => $('cat-style-name'),
  layoutBadge: () => $('cat-layout-badge'),
  styleBadge: () => $('cat-style-badge'),
  rerollLayout: () => $('cat-reroll-layout'),
  rerollStyle: () => $('cat-reroll-style'),
  layoutDetailTitle: () => $('cat-layout-detail-title'),
  styleDetailTitle: () => $('cat-style-detail-title'),
  layoutDetail: () => $('cat-layout-detail'),
  styleDetail: () => $('cat-style-detail'),
  backend: () => $('cat-backend'),
  steps: () => $('cat-steps'),
  width: () => $('cat-width'),
  height: () => $('cat-height'),
  pickBtn: () => $('cat-pick-btn'),
  renderBtn: () => $('cat-render-btn'),
  fallbackChip: () => $('cat-fallback-chip'),
  expandedWrap: () => $('cat-expanded-wrap'),
  expanded: () => $('cat-expanded'),
  renderStatus: () => $('cat-render-status'),
  progressFill: () => $('cat-progress-fill'),
  outputPreview: () => $('cat-output-preview'),
  outputActions: () => $('cat-output-actions'),
  downloadLink: () => $('cat-download-link'),
};

// ── Helpers ────────────────────────────────────────────────────────────────
function fillSelect(selectEl, options, selected) {
  while (selectEl.firstChild) selectEl.removeChild(selectEl.firstChild);
  const placeholder = document.createElement('option');
  placeholder.value = '';
  placeholder.textContent = '— Choose —';
  selectEl.appendChild(placeholder);
  for (const opt of options) {
    const o = document.createElement('option');
    o.value = opt;
    o.textContent = opt;
    if (opt === selected) o.selected = true;
    selectEl.appendChild(o);
  }
  selectEl.disabled = false;
}

function setBadge(el, kind) {
  el.classList.remove('primary', 'alternative', 'outsider', 'fallback');
  if (!kind) { el.textContent = ''; return; }
  el.classList.add(kind);
  el.textContent = kind;
}

async function fetchFirstParagraph(kind, name) {
  const key = `${kind}/${name}`;
  if (mdParagraphCache.has(key)) return mdParagraphCache.get(key);
  try {
    const r = await fetch(`/static/studio/catalogs/${kind}/${name}.md`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const text = await r.text();
    const para = firstParagraph(text);
    mdParagraphCache.set(key, para);
    return para;
  } catch {
    return '';
  }
}

function firstParagraph(md) {
  for (const block of md.split('\n\n')) {
    const t = block.trim();
    if (!t || t.startsWith('#')) continue;
    return t.replace(/\n/g, ' ');
  }
  return '';
}

// ── State transitions ──────────────────────────────────────────────────────
function transitionTo(next) {
  state.state = next;
  // Disable everything by default, then enable based on state.
  els.pickBtn().disabled = true;
  els.renderBtn().disabled = true;
  els.rerollLayout().disabled = true;
  els.rerollStyle().disabled = true;

  if (next === STATE.EMPTY) {
    els.pickStrip().hidden = true;
  } else if (next === STATE.READY_TO_PICK) {
    els.pickBtn().disabled = false;
  } else if (next === STATE.PICKED) {
    els.pickBtn().disabled = false;   // re-pick allowed
    els.renderBtn().disabled = false;
    els.rerollLayout().disabled = false;
    els.rerollStyle().disabled = false;
  } else if (next === STATE.RENDERING) {
    // all four stay disabled
  } else if (next === STATE.RENDERED) {
    els.pickBtn().disabled = false;
    els.renderBtn().disabled = false;
    els.rerollLayout().disabled = false;
    els.rerollStyle().disabled = false;
  }
}

function updateReadyState() {
  if (state.dataType && state.tone) {
    transitionTo(state.state === STATE.PICKED ? STATE.PICKED : STATE.READY_TO_PICK);
  } else {
    transitionTo(STATE.EMPTY);
  }
}

// ── Catalog load ───────────────────────────────────────────────────────────
async function loadCatalog() {
  try {
    const r = await fetch('/api/infographic/catalog');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    const storedDataType = localStorage.getItem(STORAGE_DATA_TYPE);
    const storedTone = localStorage.getItem(STORAGE_TONE);
    state.dataType = data.data_types.includes(storedDataType) ? storedDataType : null;
    state.tone = data.contexts.includes(storedTone) ? storedTone : null;
    fillSelect(els.dataTypeSel(), data.data_types, state.dataType);
    fillSelect(els.toneSel(), data.contexts, state.tone);
    updateReadyState();
  } catch (e) {
    els.renderStatus().textContent = `Catalog unavailable: ${e.message}`;
  }
}

// ── Pick / Re-roll ─────────────────────────────────────────────────────────
async function doPick(lock = null) {
  const body = {
    data_type: state.dataType,
    tone: state.tone,
    lock,
    current: lock
      ? { layout: state.layout, style: state.style }
      : null,
  };
  try {
    const r = await fetch('/api/infographic/pick', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: r.statusText }));
      els.renderStatus().textContent = `Pick failed: ${err.detail}`;
      return;
    }
    const data = await r.json();
    state.layout = data.layout;
    state.style = data.style;
    state.fromPool.layout = data.from_pool.layout;
    state.fromPool.style = data.from_pool.style;
    await paintPickStrip();
    els.pickStrip().hidden = false;
    transitionTo(STATE.PICKED);
  } catch (e) {
    els.renderStatus().textContent = `Pick error: ${e.message}`;
  }
}

async function paintPickStrip() {
  els.layoutName().textContent = state.layout;
  els.styleName().textContent = state.style;
  setBadge(els.layoutBadge(), state.fromPool.layout);
  setBadge(els.styleBadge(), state.fromPool.style);
  els.layoutDetailTitle().textContent = `Layout: ${state.layout}`;
  els.styleDetailTitle().textContent = `Style: ${state.style}`;
  els.layoutDetail().textContent = '…';
  els.styleDetail().textContent = '…';
  const [layoutPara, stylePara] = await Promise.all([
    fetchFirstParagraph('layouts', state.layout),
    fetchFirstParagraph('styles', state.style),
  ]);
  els.layoutDetail().textContent = layoutPara || '(no description)';
  els.styleDetail().textContent = stylePara || '(no description)';
}

// ── Render ─────────────────────────────────────────────────────────────────
async function doRender() {
  const userPrompt = els.userPrompt().value.trim();
  if (!userPrompt) {
    els.renderStatus().textContent = 'Enter a prompt first.';
    return;
  }
  transitionTo(STATE.RENDERING);
  els.fallbackChip().hidden = true;
  els.expandedWrap().hidden = true;
  els.outputPreview().hidden = true;
  els.outputActions().hidden = true;
  els.progressFill().style.width = '0%';
  els.renderStatus().textContent = 'expanding prompt…';

  const body = {
    user_prompt: userPrompt,
    data_type: state.dataType,
    tone: state.tone,
    layout: state.layout,
    style: state.style,
    backend: els.backend().value,
    width: parseInt(els.width().value, 10),
    height: parseInt(els.height().value, 10),
    num_steps: parseInt(els.steps().value, 10),
  };
  try {
    const r = await fetch('/api/infographic/render', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({ detail: r.statusText }));
      throw new Error(err.detail);
    }
    const data = await r.json();
    state.jobId = data.job_id;
    state.lastWsAt = Date.now();
    els.expanded().textContent = data.expanded_prompt;
    els.expandedWrap().hidden = false;
    if (data.expansion.fallback_used) els.fallbackChip().hidden = false;
    const elapsed = data.expansion.elapsed_s.toFixed(1);
    els.renderStatus().textContent =
      `expanded via ${data.expansion.model} (${elapsed}s) — rendering…`;
    startPolling();
  } catch (e) {
    els.renderStatus().textContent = `Render failed: ${e.message}`;
    transitionTo(STATE.PICKED);
  }
}

function applyJobUpdate(msg) {
  if (msg.type !== 'job_update') return;
  if (msg.job_id !== state.jobId) return;
  if (msg.status === 'running') {
    const pct = msg.progress || 0;
    els.progressFill().style.width = `${pct}%`;
    els.renderStatus().textContent = msg.message ? `${msg.message} (${pct}%)` : `rendering ${pct}%…`;
  } else if (msg.status === 'complete') {
    els.progressFill().style.width = '100%';
    els.outputPreview().src = `${msg.output_url}?t=${Date.now()}`;
    els.outputPreview().hidden = false;
    els.outputActions().hidden = false;
    els.downloadLink().href = msg.output_url;
    els.renderStatus().textContent = 'done';
    transitionTo(STATE.RENDERED);
    state.jobId = null;
    stopPolling();
  } else if (msg.status === 'error') {
    els.renderStatus().textContent = `error: ${msg.error || 'unknown'}`;
    transitionTo(STATE.PICKED);
    state.jobId = null;
    stopPolling();
  } else if (msg.status === 'cancelled') {
    els.renderStatus().textContent = 'cancelled';
    transitionTo(STATE.PICKED);
    state.jobId = null;
    stopPolling();
  }
}

function connectWs() {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  state.ws = new WebSocket(`${proto}://${location.host}/ws`);
  state.ws.addEventListener('message', (ev) => {
    let msg; try { msg = JSON.parse(ev.data); } catch { return; }
    if (msg.type !== 'job_update') return;
    if (msg.job_id !== state.jobId) return;
    state.lastWsAt = Date.now();
    applyJobUpdate(msg);
  });
  state.ws.addEventListener('close', () => setTimeout(connectWs, 2000));
}

function startPolling() {
  stopPolling();
  state.pollTimer = setInterval(async () => {
    if (!state.jobId) { stopPolling(); return; }
    if (Date.now() - state.lastWsAt < WS_STALENESS_MS) return;
    try {
      const r = await fetch(`/api/job/${state.jobId}`);
      if (!r.ok) return;
      const j = await r.json();
      applyJobUpdate({
        type: 'job_update', job_id: state.jobId,
        status: j.status, progress: j.progress, message: j.message,
        output_url: j.output_url, error: j.error,
      });
    } catch { /* next tick */ }
  }, POLL_INTERVAL_MS);
}

function stopPolling() {
  if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
}

// ── Init ───────────────────────────────────────────────────────────────────
let booted = false;
export function initCatalogMode() {
  if (booted) return;
  booted = true;

  els.dataTypeSel().addEventListener('change', () => {
    state.dataType = els.dataTypeSel().value || null;
    if (state.dataType) localStorage.setItem(STORAGE_DATA_TYPE, state.dataType);
    updateReadyState();
  });
  els.toneSel().addEventListener('change', () => {
    state.tone = els.toneSel().value || null;
    if (state.tone) localStorage.setItem(STORAGE_TONE, state.tone);
    updateReadyState();
  });
  els.pickBtn().addEventListener('click', () => doPick(null));
  els.renderBtn().addEventListener('click', doRender);
  els.rerollLayout().addEventListener('click', () => doPick('style'));
  els.rerollStyle().addEventListener('click', () => doPick('layout'));

  loadCatalog();
  connectWs();
}
```

- [ ] **Step 6: Parse-check all the new JS modules**

```bash
node --check static/studio/js/infographic.js
node --check static/studio/js/infographic/freeform-mode.js
node --check static/studio/js/infographic/catalog-mode.js
```

Expected: no output for all three.

- [ ] **Step 7: Manual browser smoke (golden path)**

```bash
systemctl --user restart open-palette.service
sleep 3
```

Open `http://127.0.0.1:8000/studio/infographic` in a browser. Verify:

1. Catalog tab is selected by default
2. Both dropdowns populate (21 entries each)
3. Pick button enables once both are chosen
4. Click Pick → layout + style appear with coloured badge
5. Click 🎲 next to layout → layout changes, style stays
6. "Show selection details" expands and shows the first paragraph of each md
7. Click Render → status changes to "expanding prompt…", then "rendering N%…", then image appears
8. Expanded prompt is visible in the collapsible
9. Switch to Freeform tab → existing gallery + editor flow works unchanged
10. Hard-reload (Ctrl+Shift+R) → dropdown selections persisted in localStorage

If any step fails, fix before committing. The most likely failure points are:

- A dropdown loading state stuck on "Loading…" → check `/api/infographic/catalog` returns 200 and the JSON has 21+21 entries
- `node --check` passes but browser shows `import error` → wrong path in ES import; check the module spec at the top of each file

- [ ] **Step 8: Commit (large commit — frontend reshape lands as one unit)**

```bash
git add static/studio/infographic.html \
        static/studio/js/infographic.js \
        static/studio/js/infographic/catalog-mode.js \
        static/sw.js
git commit -m "feat: add catalog tab to /studio/infographic"
```

---

## Task 9: README + smoke-test note + final commit

**Files:**

- Modify: `README.md`
- Create: `docs/superpowers/specs/2026-05-16-infographic-catalog-port-design.md` is already committed; update if Task 4 changed the error-handling contract for unknown data_type.

- [ ] **Step 1: Find the right README section**

```bash
grep -n "Studios\|infographic\|Ollama" README.md | head -10
```

Locate the "Studios" or capabilities table.

- [ ] **Step 2: Add a one-liner near the existing studio entries**

Add (or extend the existing infographic row):

```markdown
- `/studio/infographic` — catalog-driven flow (87 layouts × 66 styles), or freeform gallery. **Setup:** `ollama pull gpt-oss:20b` for prompt expansion (falls back to a template if Ollama is unavailable; alternatives: `qwen3:14b`, `gemma4:31b`, `mistral-small3.2:24b` — settable via `INFOGRAPHIC_EXPANDER_MODEL`).
```

- [ ] **Step 3: Update the spec doc if Task 4 contract drifted**

Open `docs/superpowers/specs/2026-05-16-infographic-catalog-port-design.md` and find the "API contract → /pick → Errors" block. Append a note:

```markdown
> **Implementation note:** unknown `data_type` and unknown `tone` now return 200 with `from_pool: "fallback"` rather than 400. This keeps the UI responsive when the dropdown list drifts; the frontend can refresh `/catalog` on next interaction. The 400 path is reserved for malformed `lock`/`current` payloads.
```

- [ ] **Step 4: Commit docs**

```bash
git add README.md docs/superpowers/specs/2026-05-16-infographic-catalog-port-design.md
git commit -m "docs: README + spec note for /studio/infographic catalog flow"
```

---

## Task 10: Coverage + final manual smoke

- [ ] **Step 1: Run the full new test suite with coverage**

```bash
pytest tests/test_build_infographic_catalog.py \
       tests/test_infographic_catalog.py \
       tests/test_infographic_expander.py \
       tests/test_api_infographic_endpoints.py \
       --cov=studio.infographic_catalog \
       --cov=studio.infographic_expander \
       --cov=scripts.build_infographic_catalog \
       --cov-report=term-missing -v
```

Expected: coverage ≥ 80% on each of the three target modules. If a module is under 80%, identify the uncovered lines (`term-missing` shows them), add a focused test, re-run.

- [ ] **Step 2: Run the existing test suite to confirm no regression**

```bash
pytest tests/ -x --ignore=tests/test_remix_e2e.py
```

`-x` stops on first failure. `--ignore` skips the e2e remix test which needs ComfyUI running (memory: `project_open_palette_runtime`).

Expected: all pass.

- [ ] **Step 3: 5-minute manual smoke against the live service**

Follow the smoke checklist from the spec doc (§ Manual smoke test):

1. `GET /api/infographic/catalog` → 21 data_types + 21 contexts + counts 87/66
2. `/studio/infographic` → Catalog tab default, pick overview / summary + Professional / Business → click Pick → see `bento-grid + corporate-memphis`
3. 🎲 layout three times — style stays `corporate-memphis`
4. Show selection details → first paragraphs visible
5. Render with default settings → image appears in ~80s, expanded prompt visible
6. Freeform tab → gallery + editor still works

- [ ] **Step 4: Optional — confirm Ollama fallback path**

```bash
# Temporarily mis-set the model env to force a 404 from Ollama
INFOGRAPHIC_EXPANDER_MODEL=does-not-exist:1b systemctl --user restart open-palette.service
sleep 3
# Render via UI again — verify the amber "Ollama unavailable" chip appears
# and the render still completes
# When done:
systemctl --user reset-failed open-palette.service  # noop, just clears any state
systemctl --user restart open-palette.service
```

- [ ] **Step 5: Final wrap commit (only if any in-flight tweaks)**

```bash
git status   # verify clean
git log --oneline -10
```

Expected: 5–7 new commits since master pre-Task-1; all build + tests green.

---

## Self-Review

**1. Spec coverage check (against `docs/superpowers/specs/2026-05-16-infographic-catalog-port-design.md`):**

| Spec section | Plan task |
|---|---|
| Catalog module (`InfographicCatalog`) | Task 2 |
| Expander module (`InfographicExpander` + fallback) | Task 3 |
| Build script (`build_infographic_catalog.py`) | Task 1 |
| `GET /api/infographic/catalog` | Task 4 |
| `POST /api/infographic/pick` | Task 4 |
| `POST /api/infographic/render` | Task 5 |
| Tab strip, Catalog default | Task 8 |
| State machine (EMPTY → READY → PICKED → RENDERING → RENDERED) | Task 8b step 5 |
| Per-axis 🎲 re-roll | Task 8b step 5 (`doPick('style' or 'layout')`) |
| Selection details (collapsible) | Task 8b step 5 (`paintPickStrip` + `fetchFirstParagraph`) |
| `fallback_used` amber chip | Task 8b step 5 |
| localStorage `dataType` + `tone` | Task 8b step 5 |
| Accessibility (`role="tablist"`, `aria-live="polite"`) | Task 8a step 2 |
| Tests ≥80% coverage on new modules | Task 10 step 1 |
| Manual smoke checklist | Task 10 step 3 |

Coverage looks complete.

**2. Placeholder scan:** no TBD/TODO/"add appropriate error handling"/"similar to Task N" strings remain. All code blocks are complete.

**3. Type consistency:** `sample` returns `tuple[str, str]`; `sample_with_label` returns `tuple[tuple[str, str], PickLabel]`. `ExpansionResult` is `frozen=True`. JS `state.fromPool` shape matches Python `PickLabel` (`{layout, style}` both string-or-null). Endpoint names consistent: `infographic_catalog`, `infographic_pick`, `infographic_render`. Frontend element IDs use the `cat-` prefix consistently. JSON keys (`data_type`, `tone`, `from_pool`) match between Pydantic models and JS fetch bodies.

**4. Cross-task continuity:** Task 4 (`_get_infographic_catalog`) is used by Task 5 unchanged. Task 6 lifts existing JS; Task 7 swaps the entry point; Task 8 lands the catalog tab — three commits, each individually a working state (Task 7 alone breaks the page, but the commit chain has Tasks 6→7→8 in tight sequence so master is never broken at a non-WIP commit).

One thing worth flagging: the spec says "unknown_data_type returns 400" but Task 4's tests expect 200 + fallback. The deviation is intentional (better UX), and Task 9 step 3 propagates the change back into the spec doc.
