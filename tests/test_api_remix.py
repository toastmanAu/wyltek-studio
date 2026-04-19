"""Validation tests for POST /api/remix. Uses FastAPI TestClient; no ComfyUI required."""

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    (storage / "crypto-logos").mkdir(parents=True)
    (storage / "unsorted" / "2026-04-19" / "images").mkdir(parents=True)
    (storage / "projects").mkdir(parents=True)
    (storage / "crypto-logos" / "bitcoin-btc.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (storage / "unsorted" / "2026-04-19" / "images" / "abc12345.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / "uploads").mkdir()
    (tmp_path / "static").mkdir()
    (tmp_path / "outputs" / "audio").mkdir(parents=True)
    (tmp_path / "data" / "sample-packs").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    import importlib
    import server as server_mod
    importlib.reload(server_mod)
    # STORAGE_ROOT in the storage module is anchored to the source file's dir,
    # not cwd, so also monkeypatch it for this test run.
    import storage as storage_mod
    monkeypatch.setattr(storage_mod, "STORAGE_ROOT", storage)

    # Stub out the job_queue submission and ComfyUI input copy so no real GPU
    # work is triggered. The endpoint still exercises resolution, validation,
    # seed math, and param assembly — that's what we want to verify.
    monkeypatch.setattr(server_mod.job_queue, "submit_background",
                        lambda *a, **kw: None)

    # Redirect the hardcoded ComfyUI input dir to the tmp tree
    import shutil
    orig_copy2 = shutil.copy2
    def tolerant_copy2(src, dst):
        # Create parent dir on the fly, write the same bytes
        dst_path = Path(dst) if not isinstance(dst, Path) else dst
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        dst_path.write_bytes(Path(src).read_bytes())
    monkeypatch.setattr(server_mod, "_shutil", None, raising=False)  # harmless
    monkeypatch.setattr(shutil, "copy2", tolerant_copy2)

    return TestClient(server_mod.app)


def _valid_form(**overrides):
    base = {
        "base_gallery_id": "abc12345.png",
        "crypto_logo_id": "bitcoin-btc",
        "preserve_character": "0.45",
        "style_strength": "0.75",
        "ip_start": "0.0",
        "ip_end": "0.8",
        "blend_mode": "style transfer",
        "lora_model": "",
        "lora_strength": "0.55",
        "model": "juggernautXL_v9.safetensors",
        "steps": "20",
        "cfg": "6.0",
        "seed": "-1",
        "batch_size": "2",
        "hint": "",
    }
    base.update({k: str(v) for k, v in overrides.items()})
    return base


def test_remix_rejects_missing_base(client):
    form = _valid_form()
    del form["base_gallery_id"]
    resp = client.post("/api/remix", data=form)
    assert resp.status_code == 400
    assert "base" in resp.json()["error"].lower()


def test_remix_rejects_missing_style_ref(client):
    form = _valid_form()
    del form["crypto_logo_id"]
    resp = client.post("/api/remix", data=form)
    assert resp.status_code == 400
    assert "style" in resp.json()["error"].lower()


def test_remix_rejects_unknown_gallery_id(client):
    resp = client.post("/api/remix", data=_valid_form(base_gallery_id="nothing.png"))
    assert resp.status_code == 404


def test_remix_rejects_unknown_crypto_logo(client):
    resp = client.post("/api/remix", data=_valid_form(crypto_logo_id="ripple-xrp"))
    assert resp.status_code == 404


def test_remix_rejects_out_of_range_preserve_character(client):
    resp_low = client.post("/api/remix", data=_valid_form(preserve_character=0.1))
    resp_high = client.post("/api/remix", data=_valid_form(preserve_character=0.95))
    assert resp_low.status_code == 400
    assert resp_high.status_code == 400


def test_remix_rejects_out_of_range_batch_size(client):
    resp_zero = client.post("/api/remix", data=_valid_form(batch_size=0))
    resp_big = client.post("/api/remix", data=_valid_form(batch_size=20))
    assert resp_zero.status_code == 400
    assert resp_big.status_code == 400


def test_remix_accepts_valid_submission_and_returns_jobs(client):
    resp = client.post("/api/remix", data=_valid_form(batch_size=3))
    assert resp.status_code == 200
    body = resp.json()
    assert "remix_id" in body
    assert len(body["jobs"]) == 3
    for j in body["jobs"]:
        assert "job_id" in j


def test_remix_seed_expansion_deterministic(client):
    resp = client.post("/api/remix", data=_valid_form(batch_size=3, seed=100))
    assert resp.status_code == 200
    import server as server_mod
    seeds = sorted(server_mod.jobs[j["job_id"]]["params"]["seed"] for j in resp.json()["jobs"])
    assert seeds == [100, 101, 102]


def test_remix_seed_minus_one_picks_random_base(client):
    resp = client.post("/api/remix", data=_valid_form(batch_size=2, seed=-1))
    assert resp.status_code == 200
    import server as server_mod
    seeds = [server_mod.jobs[j["job_id"]]["params"]["seed"] for j in resp.json()["jobs"]]
    assert all(s >= 0 for s in seeds)
    assert abs(seeds[1] - seeds[0]) == 1
