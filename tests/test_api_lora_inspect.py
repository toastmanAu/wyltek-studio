"""Tests for /api/lora/inspect — surfaces a LoRA's safetensors header so the
compare modal can advise the user about trigger words and partial TE binding."""
from __future__ import annotations

import json
import struct
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from server import app


def _write_fake_safetensors(path: Path, keys: list[str]) -> None:
    """Build a minimal valid .safetensors file that has the given tensor names
    in its JSON header but zero bytes of tensor data — enough to exercise our
    header reader without writing real weights."""
    # Each tensor metadata entry needs dtype, shape, data_offsets — but offsets
    # can all be (0, 0) for empty placeholders, which still parses.
    header: dict = {}
    for k in keys:
        header[k] = {"dtype": "F16", "shape": [1], "data_offsets": [0, 0]}
    payload = json.dumps(header).encode("utf-8")
    path.write_bytes(struct.pack("<Q", len(payload)) + payload)


@pytest.fixture
def fake_lora_dir(tmp_path, monkeypatch):
    """Point the inspect endpoint at a tmp dir we control."""
    monkeypatch.setattr("server.LORA_DIR", tmp_path)
    # Reset the module-level inspect cache so prior tests don't leak.
    monkeypatch.setattr("server._LORA_INSPECT_CACHE", {})
    return tmp_path


def test_inspect_kohya_lora_with_te_and_unet(fake_lora_dir):
    keys = [
        "lora_te1_text_model_encoder_layers_0_self_attn_k_proj.lora_down.weight",
        "lora_te2_text_model_encoder_layers_5_mlp_fc1.lora_up.weight",
        "lora_unet_input_blocks_1_0_in_layers_0.lora_down.weight",
        "lora_unet_output_blocks_5_1_proj_out.lora_up.weight",
    ]
    _write_fake_safetensors(fake_lora_dir / "voxel-xl.safetensors", keys)
    r = TestClient(app).get("/api/lora/inspect", params={"name": "voxel-xl.safetensors"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "voxel-xl.safetensors"
    assert body["has_te_keys"] is True
    assert body["te_key_count"] == 2
    assert body["has_unet_keys"] is True
    assert body["unet_key_count"] == 2
    assert body["format"] == "kohya"
    # Catalog trigger words should be attached for LoRAs we know about.
    assert "voxel" in body["triggers"]


def test_inspect_unet_only_lora(fake_lora_dir):
    """Distillation LoRAs (e.g. lightning) carry only UNet keys — no TE
    advisory needed."""
    keys = [
        "lora_unet_input_blocks_1_0_in_layers_0.lora_down.weight",
        "lora_unet_input_blocks_1_0_in_layers_0.lora_up.weight",
    ]
    _write_fake_safetensors(fake_lora_dir / "speed-lora.safetensors", keys)
    body = TestClient(app).get(
        "/api/lora/inspect", params={"name": "speed-lora.safetensors"}).json()
    assert body["has_te_keys"] is False
    assert body["te_key_count"] == 0
    assert body["has_unet_keys"] is True


def test_inspect_diffusers_format(fake_lora_dir):
    """Modern diffusers-style key naming is recognised distinctly from kohya."""
    keys = [
        "text_encoder.text_model.encoder.layers.0.self_attn.k_proj.lora_down.weight",
        "unet.down_blocks.0.attentions.0.transformer_blocks.0.attn1.to_q.lora_down.weight",
    ]
    _write_fake_safetensors(fake_lora_dir / "modern.safetensors", keys)
    body = TestClient(app).get(
        "/api/lora/inspect", params={"name": "modern.safetensors"}).json()
    assert body["format"] == "diffusers"
    assert body["has_te_keys"] is True
    assert body["has_unet_keys"] is True


def test_inspect_404_when_missing(fake_lora_dir):
    r = TestClient(app).get(
        "/api/lora/inspect", params={"name": "nonexistent.safetensors"})
    assert r.status_code == 404


def test_inspect_rejects_path_traversal(fake_lora_dir):
    """Any name containing path separators must be rejected — the endpoint
    must never read outside LORA_DIR."""
    for bad in ["../etc/passwd", "subdir/x.safetensors", "/abs/x.safetensors"]:
        r = TestClient(app).get("/api/lora/inspect", params={"name": bad})
        assert r.status_code == 400, f"expected 400 for {bad!r}, got {r.status_code}"


def test_inspect_rejects_non_safetensors(fake_lora_dir):
    """Limit to .safetensors extension — defends against accidental reads of
    other files in the loras dir (e.g. .json sidecars, .txt notes)."""
    (fake_lora_dir / "notes.txt").write_text("hi")
    r = TestClient(app).get("/api/lora/inspect", params={"name": "notes.txt"})
    assert r.status_code == 400


def test_inspect_caches_by_mtime(fake_lora_dir):
    """Cache hits avoid re-reading the file; cache invalidates when mtime
    changes (user replaces the LoRA on disk)."""
    keys_v1 = ["lora_unet_a.lora_down.weight"]
    path = fake_lora_dir / "x.safetensors"
    _write_fake_safetensors(path, keys_v1)

    body1 = TestClient(app).get(
        "/api/lora/inspect", params={"name": "x.safetensors"}).json()
    assert body1["unet_key_count"] == 1

    # Replace with a different file — bump mtime so cache invalidates.
    keys_v2 = ["lora_unet_a.lora_down.weight", "lora_unet_b.lora_down.weight",
               "lora_te1_x.lora_down.weight"]
    _write_fake_safetensors(path, keys_v2)
    import os, time
    new_mtime = path.stat().st_mtime + 5
    os.utime(path, (new_mtime, new_mtime))

    body2 = TestClient(app).get(
        "/api/lora/inspect", params={"name": "x.safetensors"}).json()
    assert body2["unet_key_count"] == 2
    assert body2["has_te_keys"] is True
