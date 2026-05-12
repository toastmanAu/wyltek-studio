from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from server import app
from studio.worker_lifecycle import WorkerStatus


def _ws(name: str, running: bool) -> WorkerStatus:
    """Build a WorkerStatus matching what worker_lifecycle returns."""
    return WorkerStatus(
        name=name,
        state="running" if running else "stopped",
        unit_active=running,
        unit_substate="running" if running else "dead",
        listening=running,
        detail={"loaded": running} if running else {},
    )


def _patch_install(*, venv: bool, weights: bool, comfyui: bool, worker: bool = True):
    """Compose patches for every probe the /api/sensenova/precheck endpoint
    consults. The endpoint calls both the cheap booleans (venv/weights) and
    the async worker-lifecycle status helpers (comfyui/sensenova), so all
    four need to be mocked to get a deterministic response."""
    return (
        patch("server._sensenova_venv_present", return_value=venv),
        patch("server._sensenova_weights_present", return_value=weights),
        # _comfyui_running is kept for backward-compat callers but the
        # precheck endpoint actually consults _wl.comfyui_status().
        patch("server._comfyui_running", return_value=comfyui),
        patch("server._wl.comfyui_status",
              new=AsyncMock(return_value=_ws("comfyui", comfyui))),
        patch("server._wl.sensenova_status",
              new=AsyncMock(return_value=_ws("sensenova-worker", worker))),
    )


def _get(venv: bool, weights: bool, comfyui: bool, worker: bool = True):
    patches = _patch_install(venv=venv, weights=weights, comfyui=comfyui, worker=worker)
    pa, pb, pc, pd, pe = patches
    with pa, pb, pc, pd, pe:
        return TestClient(app).get("/api/sensenova/precheck").json()


def test_precheck_ready_when_installed_and_no_tenant():
    body = _get(venv=True, weights=True, comfyui=False)
    assert body["ready"] is True
    assert body["installed"] is True
    assert body["blockers"] == []


def test_precheck_blocks_on_comfyui_when_installed():
    body = _get(venv=True, weights=True, comfyui=True)
    assert body["ready"] is False
    assert body["installed"] is True
    assert any("comfy" in b.lower() for b in body["blockers"])


def test_precheck_blocks_when_venv_missing():
    """No worker venv → not installed → render must be blocked."""
    body = _get(venv=False, weights=True, comfyui=False)
    assert body["ready"] is False
    assert body["installed"] is False
    assert any("not installed" in b.lower() or "venv" in b.lower()
               for b in body["blockers"])


def test_precheck_blocks_when_weights_missing():
    """Venv present but weights missing → still treated as not installed."""
    body = _get(venv=True, weights=False, comfyui=False)
    assert body["ready"] is False
    assert body["installed"] is False
    assert any("weight" in b.lower() or "not installed" in b.lower()
               for b in body["blockers"])


def test_precheck_install_hint_when_not_installed():
    """UI needs a one-shot install command to surface to the user."""
    body = _get(venv=False, weights=False, comfyui=False)
    assert body["installed"] is False
    details = body.get("details") or {}
    assert details.get("install_hint"), "expected install_hint when not installed"
    assert "setup-sensenova" in details["install_hint"]


def test_precheck_details_shape_when_ready():
    body = _get(venv=True, weights=True, comfyui=False)
    details = body.get("details") or {}
    # paths surfaced so the UI can show "looking at X" diagnostics
    assert details.get("venv_path")
    assert details.get("weights_path")
    assert details.get("venv_present") is True
    assert details.get("weights_present") is True
    assert details.get("comfyui_running") is False
