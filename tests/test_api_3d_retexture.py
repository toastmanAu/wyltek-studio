"""Integration tests for /api/3d/extract-texture and /api/3d/apply-texture.

End-to-end flow: build a GLB → extract → POST it back through apply-texture
→ verify the result GLB has the swapped baseColor. Exercises URL resolution,
caching, error paths, and the contract the frontend will rely on.
"""

import io
from pathlib import Path

import numpy as np
import pytest
import trimesh
from fastapi.testclient import TestClient
from PIL import Image


def _make_png(size: int, fill: tuple) -> bytes:
    img = Image.new("RGB", (size, size), fill)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_glb_with_texture(out_path: Path, png_bytes: bytes) -> None:
    mesh = trimesh.creation.box(extents=(1, 1, 1))
    pil = Image.open(io.BytesIO(png_bytes))
    uv = np.tile([[0.0, 0.0]], (len(mesh.vertices), 1))
    mesh.visual = trimesh.visual.TextureVisuals(uv=uv, image=pil)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(out_path)


@pytest.fixture
def client_with_glb(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    meshes_dir = storage / "unsorted" / "2026-05-03" / "meshes"
    meshes_dir.mkdir(parents=True)
    images_dir = storage / "unsorted" / "2026-05-03" / "images"
    images_dir.mkdir(parents=True)
    (storage / "projects").mkdir(parents=True)

    # Source GLB with a red atlas.
    src_glb = meshes_dir / "src.glb"
    _build_glb_with_texture(src_glb, _make_png(64, (220, 50, 50)))

    # server.py mounts these at startup; create empty stubs so reload works.
    (tmp_path / "static").mkdir()
    (tmp_path / "data" / "sample-packs").mkdir(parents=True)
    (tmp_path / "data" / "templates").mkdir(parents=True)
    (tmp_path / "outputs" / "audio").mkdir(parents=True)

    monkeypatch.chdir(tmp_path)

    import importlib
    import server as server_mod
    importlib.reload(server_mod)
    import storage as storage_mod
    monkeypatch.setattr(storage_mod, "STORAGE_ROOT", storage)

    return TestClient(server_mod.app), src_glb, storage


def test_extract_texture_returns_texture_url_and_dims(client_with_glb):
    """POST /api/3d/extract-texture pulls the baseColor PNG out and
    returns a /storage/ URL the caller can fetch + dimensions."""
    client, src_glb, storage = client_with_glb

    resp = client.post(
        "/api/3d/extract-texture",
        json={"source_glb": "/storage/unsorted/2026-05-03/meshes/src.glb"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["width"] == 64
    assert body["height"] == 64
    assert body["material_index"] == 0
    assert body["texture_url"].startswith("/storage/")
    assert body["texture_url"].endswith(".png")

    # texture_url is the shorthand /storage/<basename> form — resolve via
    # storage.resolve_asset, same way the /storage/{filename:path} route does.
    import storage as store
    cache_path = store.resolve_asset(body["texture_url"])
    assert cache_path is not None and cache_path.exists()
    decoded = Image.open(cache_path)
    assert decoded.size == (64, 64)


def test_apply_texture_round_trips_swapped_baseColor(client_with_glb):
    """Round-trip: extract → user-edit (here: synthesised replacement)
    → apply → new GLB whose baseColor matches the replacement."""
    client, src_glb, storage = client_with_glb

    # Drop a replacement PNG (yellow) into storage so the API can
    # resolve it the same way it would for a user-edited texture.
    replacement = storage / "unsorted" / "2026-05-03" / "images" / "yellow.png"
    replacement.write_bytes(_make_png(64, (255, 230, 0)))

    resp = client.post(
        "/api/3d/apply-texture",
        json={
            "source_glb": "/storage/unsorted/2026-05-03/meshes/src.glb",
            "edited_texture": "/storage/unsorted/2026-05-03/images/yellow.png",
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["new_glb_url"].startswith("/storage/")
    assert body["new_glb_url"].endswith(".glb")

    import storage as store
    new_glb = store.resolve_asset(body["new_glb_url"])
    assert new_glb is not None and new_glb.exists()

    # The swapped baseColor should now read yellow-dominant.
    from texture_io import extract_basecolor
    out_png, _, _ = extract_basecolor(new_glb)
    out_img = Image.open(io.BytesIO(out_png)).convert("RGB")
    r, g, b = out_img.getpixel((32, 32))
    assert r > 200 and g > 200 and b < 50, f"expected yellow, got ({r},{g},{b})"


def test_extract_texture_404s_on_missing_glb(client_with_glb):
    """Caller-friendly 404 when the source GLB doesn't exist (vs. 500)."""
    client, *_ = client_with_glb
    resp = client.post(
        "/api/3d/extract-texture",
        json={"source_glb": "/storage/unsorted/2026-05-03/meshes/does-not-exist.glb"},
    )
    assert resp.status_code == 404


def test_apply_texture_accepts_frame_serve_urls(client_with_glb):
    """The image-tools tabs (bg-remove, object-remove) return
    /api/frame/serve?path=<abs> URLs where the real path lives inside
    the query string. The resolver must parse this form correctly —
    splitting at `?` would drop the path entirely."""
    client, src_glb, storage = client_with_glb

    # Drop a replacement texture in storage.
    replacement = storage / "unsorted" / "2026-05-03" / "images" / "edited.png"
    replacement.write_bytes(_make_png(64, (60, 200, 60)))

    # Build the same URL form image-tools renders into <img src=…>:
    # /api/frame/serve?path=<absolute>&t=<cache_bust>
    abs_path = str(replacement.resolve())
    frame_serve_url = f"/api/frame/serve?path={abs_path}&t=1234567890"

    resp = client.post(
        "/api/3d/apply-texture",
        json={
            "source_glb": "/storage/unsorted/2026-05-03/meshes/src.glb",
            "edited_texture": frame_serve_url,
        },
    )
    assert resp.status_code == 200, resp.text


def test_apply_texture_400s_on_non_square_input(client_with_glb):
    """The texture_io guard surfaces as a 400 (caller error) not 500."""
    client, src_glb, storage = client_with_glb

    img = Image.new("RGB", (64, 32), (128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    bad = storage / "unsorted" / "2026-05-03" / "images" / "non_square.png"
    bad.write_bytes(buf.getvalue())

    resp = client.post(
        "/api/3d/apply-texture",
        json={
            "source_glb": "/storage/unsorted/2026-05-03/meshes/src.glb",
            "edited_texture": "/storage/unsorted/2026-05-03/images/non_square.png",
        },
    )
    assert resp.status_code == 400
    assert "square" in resp.json().get("error", "").lower()
