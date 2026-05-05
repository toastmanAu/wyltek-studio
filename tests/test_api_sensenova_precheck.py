from unittest.mock import patch
from fastapi.testclient import TestClient
from server import app

def test_precheck_ready():
    with patch("server._comfyui_running", return_value=False):
        r = TestClient(app).get("/api/sensenova/precheck")
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is True and body["blockers"] == []

def test_precheck_blocks_on_comfyui():
    with patch("server._comfyui_running", return_value=True):
        r = TestClient(app).get("/api/sensenova/precheck")
    body = r.json()
    assert body["ready"] is False
    assert any("comfy" in b.lower() for b in body["blockers"])
