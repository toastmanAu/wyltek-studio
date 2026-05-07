"""POST /api/infographic/composite — accepts a PNG blob + base_render_id,
creates a new c-{hex} subdirectory under outputs/infographic/."""
import io
import json
from fastapi.testclient import TestClient
from server import app


def _png_bytes() -> bytes:
    return (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4"
            b"\x89\x00\x00\x00\rIDATx\x9cc\xfc\xcf\xc0P\x0f\x00\x02\x00\x01"
            b"\xa5{\xfa\xf3\x00\x00\x00\x00IEND\xaeB`\x82")


def test_composite_saves_png(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "outputs" / "infographic").mkdir(parents=True)
    r = TestClient(app).post(
        "/api/infographic/composite",
        files={"file": ("composite.png", io.BytesIO(_png_bytes()), "image/png")},
        data={"base_render_id": "abc123"},
    )
    assert r.status_code == 200
    body = r.json()
    new_id = body["job_id"]
    assert new_id.startswith("c-")
    assert new_id != "abc123"
    out_png = tmp_path / "outputs" / "infographic" / new_id / "out.png"
    sidecar = tmp_path / "outputs" / "infographic" / new_id / "out.json"
    assert out_png.exists() and out_png.stat().st_size > 0
    assert sidecar.exists()
    data = json.loads(sidecar.read_text())
    assert data.get("composite_of") == "abc123"
    assert data.get("template_id") == "composite"
    assert "png_url" in body
    assert body["png_url"].endswith("/out.png")


def test_composite_rejects_non_image(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "outputs" / "infographic").mkdir(parents=True)
    r = TestClient(app).post(
        "/api/infographic/composite",
        files={"file": ("bad.txt", io.BytesIO(b"not a png"), "text/plain")},
        data={"base_render_id": ""},
    )
    assert r.status_code == 400


def test_composite_appears_in_history(tmp_path, monkeypatch):
    """A composite should be listable via /api/infographic/history."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "outputs" / "infographic").mkdir(parents=True)
    client = TestClient(app)
    r1 = client.post(
        "/api/infographic/composite",
        files={"file": ("c.png", io.BytesIO(_png_bytes()), "image/png")},
        data={"base_render_id": "xyz"},
    )
    new_id = r1.json()["job_id"]

    r2 = client.get("/api/infographic/history")
    assert r2.status_code == 200
    ids = [e["job_id"] for e in r2.json()]
    assert new_id in ids
