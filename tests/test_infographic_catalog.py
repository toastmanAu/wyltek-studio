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
        from {timeline, asymmetry} (up to 3 added).
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
    (theoretical: 10 / (10+9+up-to-3) ≈ 45-50%). Alternative should be ≥ 35%
    (theoretical: 9/22 ≈ 40%). Outsiders ≤ 25% (theoretical: 3/22 ≈ 14%)."""
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


def test_version(catalog_dir):
    cat = InfographicCatalog(catalog_dir)
    assert cat.version() == "1"


def test_is_known_layout(catalog_dir):
    cat = InfographicCatalog(catalog_dir)
    assert cat.is_known_layout("bento") is True
    assert cat.is_known_layout("does-not-exist") is False


def test_is_known_style(catalog_dir):
    cat = InfographicCatalog(catalog_dir)
    assert cat.is_known_style("memphis") is True
    assert cat.is_known_style("does-not-exist") is False


def test_classify_unknown_name_returns_fallback(catalog_dir):
    """When `lock`+`current` provides a layout name that doesn't exist in
    the catalog at all (e.g., a stale dropdown value), classify should
    return 'fallback', not 'outsider'."""
    cat = InfographicCatalog(catalog_dir)
    (layout, style), label = cat.sample_with_label(
        "overview", "Business", seed=0,
        lock="layout", current=("not-in-catalog", "memphis"),
    )
    assert layout == "not-in-catalog"  # lock preserves caller's value
    assert label["layout"] == "fallback"


def test_classify_unknown_style_name_returns_fallback(catalog_dir):
    cat = InfographicCatalog(catalog_dir)
    (layout, style), label = cat.sample_with_label(
        "overview", "Business", seed=0,
        lock="style", current=("bento", "not-in-catalog"),
    )
    assert style == "not-in-catalog"
    assert label["style"] == "fallback"
