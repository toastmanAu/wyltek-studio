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

    for name, body in [
        ("hub-spoke",   "# Hub-and-spoke\nCenter node radiates outward.\n"),
        ("bento-grid",  "# Bento grid\nRectangular modular cells.\n"),
        ("timeline",    "# Timeline\nLeft-to-right sequence.\n"),
    ]:
        (refs / "layouts" / f"{name}.md").write_text(body)

    for name, body in [
        ("corporate-memphis", "# Corporate Memphis\nFlat geometric.\n"),
        ("swiss-style",       "# Swiss Style\nGrid-based, sans-serif.\n"),
    ]:
        (refs / "styles" / f"{name}.md").write_text(body)

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
    out = tmp_path / "out"
    build_catalog(upstream, out)
    idx1 = json.loads((out / "index.json").read_text())
    build_catalog(upstream, out)
    idx2 = json.loads((out / "index.json").read_text())
    idx1.pop("built_at"); idx2.pop("built_at")
    assert idx1 == idx2


def test_build_catalog_fallback_uses_canonical_when_present(upstream, tmp_path):
    out = tmp_path / "out"
    build_catalog(upstream, out)
    index = json.loads((out / "index.json").read_text())
    assert index["fallback"] == {"layout": "hub-spoke", "style": "corporate-memphis"}


def test_build_catalog_fallback_uses_first_primary_when_canonical_missing(
    upstream, tmp_path
):
    """When the canonical fallback layout (hub-spoke) is absent from the
    upstream tree, fallback.layout must drop to the first data_type row's
    primary (bento-grid in the fixture). Also drop hub-spoke from the
    selection table so cross-ref validation still passes."""
    (upstream / "layouts" / "hub-spoke.md").unlink()
    sel = upstream / "layout-style-selection.md"
    sel.write_text(
        sel.read_text()
        .replace("hub-spoke, timeline", "timeline")
        .replace("| process / tutorial  | hub-spoke  | timeline, bento-grid   |",
                 "| process / tutorial  | timeline   | bento-grid             |")
    )
    out = tmp_path / "out"
    build_catalog(upstream, out)
    index = json.loads((out / "index.json").read_text())
    assert index["fallback"]["layout"] == "bento-grid"


def test_build_catalog_strips_backticks_from_table_cells(upstream, tmp_path):
    """Real upstream wraps layout/style names in markdown inline-code:
    `| timeline / history | `linear-progression` | `winding-roadmap`, … |`.
    The parser must strip the backticks before cross-ref validation,
    otherwise every real-upstream build hits ValueError."""
    sel = upstream / "layout-style-selection.md"
    sel.write_text(
        sel.read_text()
        .replace("bento-grid", "`bento-grid`")
        .replace("hub-spoke", "`hub-spoke`")
        .replace("timeline", "`timeline`")
        .replace("corporate-memphis", "`corporate-memphis`")
        .replace("swiss-style", "`swiss-style`")
    )
    out = tmp_path / "out"
    build_catalog(upstream, out)
    index = json.loads((out / "index.json").read_text())
    overview = next(dt for dt in index["data_types"] if dt["key"] == "overview / summary")
    assert overview["primary"] == "bento-grid"
    assert overview["alternatives"] == ["hub-spoke", "timeline"]
