"""Tests for the ComfyUI orphan-GLB rescue helper.

Background: when an open-palette job times out (asyncio.wait_for) but
ComfyUI later finishes the prompt and writes the .glb to disk, this
helper finds it and copies it into the expected output_path so the job
reports "complete (rescued)" instead of "failed".
"""

import asyncio
from pathlib import Path

import pytest

from backends.comfyui import _rescue_orphan_glb


@pytest.mark.asyncio
async def test_rescue_finds_textured_glb_written_during_grace(tmp_path):
    """ComfyUI writes the GLB after we've timed out — rescue should find it."""
    comfy_out = tmp_path / "comfy"
    comfy_out.mkdir()
    file_prefix = "3D/wyltek-trellis_abc12345"
    (comfy_out / "3D").mkdir()

    output_path = tmp_path / "rescued.glb"

    async def write_late():
        await asyncio.sleep(1.0)  # simulate ComfyUI finishing 1s late
        target = comfy_out / f"{file_prefix}_textured_00001_.glb"
        target.write_bytes(b"fake glb content")

    writer = asyncio.create_task(write_late())
    result = await _rescue_orphan_glb(
        file_prefix, str(output_path),
        grace_seconds=5, poll_interval=0.2,
        comfy_output_dir=comfy_out,
    )
    await writer

    assert result is not None
    assert result["rescued"] is True
    assert "_textured_" in result["source"]
    assert output_path.exists()
    assert output_path.read_bytes() == b"fake glb content"


@pytest.mark.asyncio
async def test_rescue_returns_none_when_no_artifact_in_grace_window(tmp_path):
    comfy_out = tmp_path / "comfy"
    comfy_out.mkdir()
    output_path = tmp_path / "out.glb"
    result = await _rescue_orphan_glb(
        "3D/never-existed", str(output_path),
        grace_seconds=1, poll_interval=0.2,
        comfy_output_dir=comfy_out,
    )
    assert result is None
    assert not output_path.exists()


@pytest.mark.asyncio
async def test_rescue_prefers_textured_over_white_when_both_present(tmp_path):
    """When both untextured and textured exist (PBR pipeline writes both),
    prefer the textured variant — it's the actual final artifact."""
    comfy_out = tmp_path / "comfy"
    (comfy_out / "3D").mkdir(parents=True)
    file_prefix = "3D/wyltek-trellis_xyz98765"
    (comfy_out / f"{file_prefix}_white_00001_.glb").write_bytes(b"white")
    (comfy_out / f"{file_prefix}_textured_00001_.glb").write_bytes(b"textured")

    output_path = tmp_path / "rescued.glb"
    result = await _rescue_orphan_glb(
        file_prefix, str(output_path),
        grace_seconds=2, poll_interval=0.2,
        comfy_output_dir=comfy_out,
    )
    assert result is not None
    assert "_textured_" in result["source"]
    assert output_path.read_bytes() == b"textured"
