from unittest.mock import patch
from fastapi.testclient import TestClient
from server import app


def _patch_install(*, venv: bool, weights: bool, comfyui: bool):
    """Compose patches for all three precheck probes in one place."""
    return (
        patch("server._sensenova_venv_present", return_value=venv),
        patch("server._sensenova_weights_present", return_value=weights),
        patch("server._comfyui_running", return_value=comfyui),
    )


def _get(venv: bool, weights: bool, comfyui: bool):
    pa, pb, pc = _patch_install(venv=venv, weights=weights, comfyui=comfyui)
    with pa, pb, pc:
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
