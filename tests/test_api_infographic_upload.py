"""POST /api/infographic/upload — accepts an image, returns {url, path}."""
import io
from fastapi.testclient import TestClient
from server import app


def _png_bytes() -> bytes:
    # 1x1 transparent PNG
    return (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4"
            b"\x89\x00\x00\x00\rIDATx\x9cc\xfc\xcf\xc0P\x0f\x00\x02\x00\x01"
            b"\xa5{\xfa\xf3\x00\x00\x00\x00IEND\xaeB`\x82")


def test_upload_returns_url_and_path():
    client = TestClient(app)
    r = client.post("/api/infographic/upload",
                    files={"file": ("ref.png", io.BytesIO(_png_bytes()), "image/png")})
    assert r.status_code == 200
    body = r.json()
    assert "url" in body and body["url"].startswith("/uploads/infographic/")
    assert "path" in body and body["path"].startswith("uploads/infographic/")
    assert body["path"].endswith(".png")


def test_upload_rejects_empty():
    client = TestClient(app)
    r = client.post("/api/infographic/upload",
                    files={"file": ("empty.png", io.BytesIO(b""), "image/png")})
    assert r.status_code == 400


def test_upload_rejects_non_image():
    client = TestClient(app)
    r = client.post("/api/infographic/upload",
                    files={"file": ("bad.txt", io.BytesIO(b"not an image"), "text/plain")})
    assert r.status_code == 400
