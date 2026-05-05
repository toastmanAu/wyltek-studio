"""Sidecar JSON is written next to the PNG when _run_infographic_job succeeds."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest


@pytest.mark.asyncio
async def test_sidecar_written_on_success(tmp_path, monkeypatch):
    import server
    # Mirror tmp_path layout: outputs/infographic/j1/out.png
    real_outputs = tmp_path / "outputs" / "infographic" / "j1"
    real_outputs.mkdir(parents=True)
    real_png = real_outputs / "out.png"
    real_png.write_bytes(b"\x89PNG")

    # Run from tmp_path so server.py's Path("outputs/infographic")/job_id resolves under tmp_path.
    monkeypatch.chdir(tmp_path)

    server.jobs["j1"] = {"status": "queued", "params": {}, "progress": 0}
    params = {
        "prompt": "p", "image_paths": [], "aspect": "1:1", "seed": 42, "tier": "draft",
        "template_id": "hub_and_spoke", "slots": {"title": "T"},
    }

    async def _fake_generate(**kw):
        return real_png

    with patch("backends.sensenova.generate", new=AsyncMock(side_effect=_fake_generate)), \
         patch("server.broadcast", new=AsyncMock()):
        await server._run_infographic_job("j1", params)

    sidecar = real_png.with_suffix(".json")
    assert sidecar.exists(), f"sidecar missing at {sidecar}"
    data = json.loads(sidecar.read_text())
    assert data["template_id"] == "hub_and_spoke"
    assert data["slots"]["title"] == "T"
    assert data["tier"] == "draft"
    assert data["aspect"] == "1:1"
    assert data["seed"] == 42
    assert data["prompt"] == "p"
