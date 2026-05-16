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
    dropdown is in play."""
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
