"""Integration tests for /api/infographic/catalog and /pick.

Render endpoint tests are in Task 5 — they need JobQueue mocking.
"""

from __future__ import annotations

import json
from pathlib import Path

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


@pytest.fixture
def client_no_catalog(monkeypatch) -> TestClient:
    """Point the singleton at a non-existent dir to exercise the 503 path."""
    monkeypatch.setenv("INFOGRAPHIC_CATALOG_DIR", "/tmp/wyltek-does-not-exist-xyz")
    import importlib
    import server
    importlib.reload(server)
    return TestClient(server.app)


def test_get_catalog_returns_503_when_not_built(client_no_catalog):
    r = client_no_catalog.get("/api/infographic/catalog")
    assert r.status_code == 503
    assert "catalog_not_built" in r.json()["detail"]


def test_post_pick_returns_503_when_not_built(client_no_catalog):
    r = client_no_catalog.post(
        "/api/infographic/pick",
        json={"data_type": "anything", "tone": "anything"},
    )
    assert r.status_code == 503


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
