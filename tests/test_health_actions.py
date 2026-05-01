"""Tests for health_actions: classifiers, orphan rescue, reset shapes."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

import health_actions
from health_actions import (
    HEALTH_POLICY,
    _classify_higher_is_worse,
    _classify_lower_is_worse,
    _rescue_orphan_meshes,
    check_queue,
    soft_reset,
)


# --------------------------------------------------------------------------
# Classifier unit tests
# --------------------------------------------------------------------------

class TestClassifiers:
    def test_lower_is_worse_red_at_or_below_red_threshold(self):
        assert _classify_lower_is_worse(value=1.0, amber=4.0, red=1.0) == "red"
        assert _classify_lower_is_worse(value=0.5, amber=4.0, red=1.0) == "red"

    def test_lower_is_worse_amber_between_thresholds(self):
        assert _classify_lower_is_worse(value=2.5, amber=4.0, red=1.0) == "amber"
        assert _classify_lower_is_worse(value=4.0, amber=4.0, red=1.0) == "amber"

    def test_lower_is_worse_green_above_amber(self):
        assert _classify_lower_is_worse(value=4.1, amber=4.0, red=1.0) == "green"
        assert _classify_lower_is_worse(value=20.0, amber=4.0, red=1.0) == "green"

    def test_higher_is_worse_red_at_or_above_red_threshold(self):
        assert _classify_higher_is_worse(value=4, amber=2, red=4) == "red"
        assert _classify_higher_is_worse(value=10, amber=2, red=4) == "red"

    def test_higher_is_worse_amber_between(self):
        assert _classify_higher_is_worse(value=2, amber=2, red=4) == "amber"
        assert _classify_higher_is_worse(value=3, amber=2, red=4) == "amber"

    def test_higher_is_worse_green_below_amber(self):
        assert _classify_higher_is_worse(value=0, amber=2, red=4) == "green"
        assert _classify_higher_is_worse(value=1, amber=2, red=4) == "green"


# --------------------------------------------------------------------------
# Orphan rescue
# --------------------------------------------------------------------------

@pytest.fixture
def fake_dirs(tmp_path, monkeypatch):
    """Redirect HEALTH_POLICY paths into a tmp filesystem layout."""
    comfy_root = tmp_path / "ComfyUI" / "output"
    comfy_3d = comfy_root / "3D"
    storage = tmp_path / "storage" / "unsorted"
    comfy_3d.mkdir(parents=True)
    storage.mkdir(parents=True)

    monkeypatch.setitem(HEALTH_POLICY, "comfy_output_dir", str(comfy_root))
    monkeypatch.setitem(HEALTH_POLICY, "storage_unsorted_dir", str(storage))
    return comfy_3d, storage


class TestOrphanRescue:
    def test_no_comfy_output_dir(self, tmp_path, monkeypatch):
        monkeypatch.setitem(HEALTH_POLICY, "comfy_output_dir", str(tmp_path / "missing"))
        monkeypatch.setitem(HEALTH_POLICY, "storage_unsorted_dir", str(tmp_path / "storage"))
        result = _rescue_orphan_meshes()
        assert result == {"rescued": [], "skipped_existing": 0, "comfy_3d_missing": True}

    def test_rescues_a_lone_textured_glb(self, fake_dirs):
        comfy_3d, storage = fake_dirs
        src = comfy_3d / "wyltek-trellis_abc12345_textured_00001_.glb"
        src.write_bytes(b"FAKE-GLB-BODY")

        result = _rescue_orphan_meshes()

        assert result["skipped_existing"] == 0
        assert len(result["rescued"]) == 1
        rescued_path = Path(result["rescued"][0])
        assert rescued_path.exists()
        assert rescued_path.read_bytes() == b"FAKE-GLB-BODY"
        # Sidecar JSON must mark rescued=True so gallery can flag it.
        sidecar = rescued_path.with_suffix(".json")
        meta = json.loads(sidecar.read_text())
        assert meta["rescued"] is True
        assert meta["job_id"] == "abc12345"
        assert meta["engine"] == "trellis"

    def test_skips_when_size_already_in_storage(self, fake_dirs):
        """Re-running the rescue must not create duplicate copies."""
        comfy_3d, storage = fake_dirs
        src = comfy_3d / "wyltek-trellis_dup12345_textured_00001_.glb"
        src.write_bytes(b"X" * 1024)

        # Pre-seed storage with a same-size file from the same day.
        from datetime import datetime
        day = datetime.fromtimestamp(src.stat().st_mtime).strftime("%Y-%m-%d")
        target_dir = storage / day / "meshes"
        target_dir.mkdir(parents=True)
        (target_dir / "preexisting.glb").write_bytes(b"Y" * 1024)

        result = _rescue_orphan_meshes()
        assert result["skipped_existing"] == 1
        assert result["rescued"] == []

    def test_handles_unparseable_filename_with_stem_fallback(self, fake_dirs):
        comfy_3d, _ = fake_dirs
        # No "_textured_" segment to split on — should fall back to stem[:8].
        src = comfy_3d / "wyltek-weird_textured_singletoken.glb"
        src.write_bytes(b"WEIRD")
        result = _rescue_orphan_meshes()
        # Pattern still matches the glob; rescue copies it under fallback id.
        assert len(result["rescued"]) == 1


# --------------------------------------------------------------------------
# Queue check
# --------------------------------------------------------------------------

class FakeQueue:
    """Minimal stand-in matching JobQueue.status() shape."""
    def __init__(self, totals):
        self._totals = totals  # {lane: {"running": int, "queued": int}}

    def status(self):
        return {
            lane: {"running": v["running"], "queued": v["queued"]}
            for lane, v in self._totals.items()
        }


class TestQueueCheck:
    def test_empty_queue_is_green(self):
        q = FakeQueue({"gpu": {"running": 0, "queued": 0}})
        assert check_queue(q).status == "green"

    def test_one_in_flight_is_green(self):
        q = FakeQueue({"gpu": {"running": 1, "queued": 0}})
        assert check_queue(q).status == "green"

    def test_at_amber_threshold(self):
        q = FakeQueue({"gpu": {"running": 1, "queued": 1}})  # 2 total = amber
        assert check_queue(q).status == "amber"

    def test_at_red_threshold(self):
        q = FakeQueue({"gpu": {"running": 2, "queued": 2}})  # 4 total = red
        assert check_queue(q).status == "red"


# --------------------------------------------------------------------------
# soft_reset shape
# --------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_soft_reset_shape(fake_dirs):
    """soft_reset must always return a dict with rescue + components keys."""
    comfy_3d, _ = fake_dirs
    (comfy_3d / "wyltek-trellis_xyz99999_textured_00001_.glb").write_bytes(b"abc")

    q = FakeQueue({"gpu": {"running": 0, "queued": 0}})

    # Stub out external probes so the test doesn't depend on network/rocm-smi.
    async def fake_alive(url, timeout):
        return False
    with patch.object(health_actions, "_http_alive", side_effect=fake_alive), \
         patch.object(health_actions, "check_gpu_vram",
                      return_value=health_actions.ComponentStatus(
                          "gpu", "green", "stub")), \
         patch.object(health_actions, "check_disk",
                      return_value=health_actions.ComponentStatus(
                          "disk", "green", "stub")):
        result = await soft_reset(q)

    assert result["level"] == "soft"
    assert result["rescue"]["skipped_existing"] == 0
    assert len(result["rescue"]["rescued"]) == 1
    component_names = {c["name"] for c in result["components"]}
    assert component_names == {"comfyui", "ollama", "gpu", "disk", "queue"}
