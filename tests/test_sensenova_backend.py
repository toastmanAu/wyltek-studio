import pytest
from backends.sensenova import (
    SenseNovaError, _build_argv, _build_jsonl_payload, _resolve_weights)


def test_payload_text_only():
    p = _build_jsonl_payload(prompt="hi", image_paths=[], aspect="1:1", seed=42)
    assert p["prompt"] == "hi" and p["image"] == []
    assert p["width"] == 1536 and p["height"] == 1536
    assert p["seed"] == 42 and p["think_mode"] is False

def test_payload_with_images_uses_placeholders():
    p = _build_jsonl_payload(
        prompt="Compare [Image 1] and [Image 2].",
        image_paths=["/u/a.png","/u/b.png"], aspect=None, seed=7)
    assert "<image>" in p["prompt"] and "[Image 1]" not in p["prompt"]
    assert p["image"] == ["/u/a.png","/u/b.png"]
    assert "width" not in p or p.get("width") is None

def test_aspect_buckets():
    p = _build_jsonl_payload("x", [], "16:9", 0)
    assert (p["width"], p["height"]) == (2048, 1152)

def test_unknown_aspect_raises():
    with pytest.raises(SenseNovaError):
        _build_jsonl_payload("x", [], "13:7", 0)

def test_resolve_weights():
    assert "8step" not in _resolve_weights("final")
    assert "8step" in _resolve_weights("draft")

def test_resolve_weights_bad():
    with pytest.raises(SenseNovaError):
        _resolve_weights("turbo")

def test_argv_includes_jsonl_and_no_think(tmp_path):
    j = tmp_path / "j.jsonl"; j.write_text("{}")
    argv = _build_argv(jsonl_path=j, output_dir=tmp_path, tier="final")
    assert "--jsonl" in argv and str(j) in argv
    assert "--no-think_mode" in argv
    assert any("sensenova-u1-weights" in a for a in argv)
