"""GET /api/infographic/history returns recent renders newest-first with png_url + sidecar."""
import json
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from server import app


def test_history_lists_recent_renders(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "outputs" / "infographic"
    for j in ("a", "b", "c"):
        d = base / j
        d.mkdir(parents=True)
        (d / "out.png").write_bytes(b"\x89PNG")
        (d / "out.json").write_text(json.dumps({
            "template_id": "hub_and_spoke",
            "slots": {"title": j.upper()},
            "tier": "draft",
        }))
    r = TestClient(app).get("/api/infographic/history")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 3
    ids = {e["job_id"] for e in body}
    assert ids == {"a", "b", "c"}
    for e in body:
        assert "png_url" in e and e["png_url"].startswith("/outputs/infographic/")
        assert "sidecar" in e and e["sidecar"]["template_id"] == "hub_and_spoke"


def test_history_skips_dirs_without_sidecar(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "outputs" / "infographic"
    (base / "a").mkdir(parents=True)
    (base / "a" / "out.png").write_bytes(b"\x89PNG")
    # no sidecar JSON
    r = TestClient(app).get("/api/infographic/history")
    assert r.status_code == 200
    assert r.json() == []


def test_history_empty_when_dir_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    r = TestClient(app).get("/api/infographic/history")
    assert r.status_code == 200
    assert r.json() == []


def test_history_limit_respected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    base = tmp_path / "outputs" / "infographic"
    for j in ("a", "b", "c", "d", "e"):
        d = base / j
        d.mkdir(parents=True)
        (d / "out.png").write_bytes(b"\x89PNG")
        (d / "out.json").write_text(json.dumps({"template_id": "x", "slots": {}, "tier": "draft"}))
    r = TestClient(app).get("/api/infographic/history?limit=2")
    body = r.json()
    assert len(body) == 2
