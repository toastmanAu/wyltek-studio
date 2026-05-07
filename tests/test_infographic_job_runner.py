"""_run_infographic_job — verify it calls sensenova.generate with the right
params, updates job status, broadcasts on success/failure."""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest


@pytest.mark.asyncio
async def test_run_infographic_job_success(tmp_path):
    import server
    fake_png = tmp_path / "out.png"
    fake_png.write_bytes(b"\x89PNG")

    server.jobs["test-1"] = {"status": "queued", "params": {}, "progress": 0}
    params = {
        "prompt": "p", "image_paths": [], "aspect": "1:1",
        "seed": 42, "tier": "draft",
        "template_id": "hub_and_spoke", "slots": {"title": "T"},
    }

    with patch("backends.sensenova.generate", new=AsyncMock(return_value=fake_png)) as m, \
         patch("server.broadcast", new=AsyncMock()) as bc:
        await server._run_infographic_job("test-1", params)

    m.assert_called_once()
    kwargs = m.call_args.kwargs
    assert kwargs["tier"] == "draft"
    assert kwargs["aspect"] == "1:1"
    assert kwargs["prompt"] == "p"
    assert kwargs["seed"] == 42
    assert isinstance(kwargs["output_dir"], Path)
    assert "test-1" in str(kwargs["output_dir"])
    assert server.jobs["test-1"]["status"] == "complete"
    assert server.jobs["test-1"]["progress"] == 100
    assert "output_url" in server.jobs["test-1"]
    bc.assert_called()  # at least one broadcast happened


@pytest.mark.asyncio
async def test_run_infographic_job_error_path():
    import server
    server.jobs["test-2"] = {"status": "queued", "params": {}, "progress": 0}
    params = {"prompt": "p", "image_paths": [], "aspect": "1:1",
              "seed": 42, "tier": "draft", "template_id": "hub_and_spoke", "slots": {}}

    async def _boom(**kw): raise RuntimeError("kaboom")
    with patch("backends.sensenova.generate", new=_boom), \
         patch("server.broadcast", new=AsyncMock()):
        await server._run_infographic_job("test-2", params)

    assert server.jobs["test-2"]["status"] == "error"
    assert "kaboom" in server.jobs["test-2"]["error"]
