"""POST /api/infographic/render — validation + job submission."""
import asyncio
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from server import app


def _good():
    return {
        "template_id": "hub_and_spoke",
        "tier": "draft",
        "aspect": "1:1",
        "slots": {
            "title": "T", "hub_desc": "x",
            "spokes": [{"label": str(i)} for i in range(4)],
        },
        "image_refs": [],
    }


def test_render_returns_202_with_job_id():
    # Patch job_queue.submit_background so we don't actually run anything.
    with patch("job_queue.JobQueue.submit_background", return_value=None):
        r = TestClient(app).post("/api/infographic/render", json=_good())
    assert r.status_code == 202
    body = r.json()
    assert "job_id" in body
    assert isinstance(body["job_id"], str) and body["job_id"]


def test_render_unknown_template_404():
    body = _good(); body["template_id"] = "no_such"
    r = TestClient(app).post("/api/infographic/render", json=body)
    assert r.status_code == 404


def test_render_missing_required_400():
    body = _good(); del body["slots"]["title"]
    r = TestClient(app).post("/api/infographic/render", json=body)
    assert r.status_code == 400


def test_render_invalid_tier_400():
    body = _good(); body["tier"] = "turbo"
    r = TestClient(app).post("/api/infographic/render", json=body)
    # 422 is also acceptable here (Pydantic regex validation).
    assert r.status_code in (400, 422)


def test_render_invalid_aspect_400():
    body = _good(); body["aspect"] = "13:7"
    with patch("job_queue.JobQueue.submit_background", return_value=None):
        r = TestClient(app).post("/api/infographic/render", json=body)
    assert r.status_code == 400


def test_render_merges_external_image_refs(tmp_path, monkeypatch):
    """When the body supplies image_refs[] AND template slots include
    image_ref typed slots, the resulting image_paths should be the union
    in declaration order, slot-derived first, then external refs not
    already present."""
    # Create real upload files so path-traversal validation passes.
    uploads = tmp_path / "uploads" / "infographic"
    uploads.mkdir(parents=True)
    (uploads / "a.png").write_bytes(b"")
    (uploads / "b.png").write_bytes(b"")
    monkeypatch.chdir(tmp_path)
    # Re-resolve the module-level constant to match tmp_path.
    import server as _srv
    monkeypatch.setattr(_srv, "_INFOGRAPHIC_UPLOADS_DIR", (tmp_path / "uploads" / "infographic").resolve())

    body = _good()
    body["image_refs"] = [
        str(uploads / "a.png"),
        str(uploads / "b.png"),
    ]
    body["slots"]["hub_desc"] = "See [Image 1] and [Image 2]"

    from server import jobs as _jobs
    _jobs.clear()
    with patch("job_queue.JobQueue.submit_background", return_value=None):
        r = TestClient(app).post("/api/infographic/render", json=body)
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    assert job_id in _jobs
    params = _jobs[job_id]["params"]
    # hub_and_spoke template has no image_ref slots filled in this body, so
    # only the externals should be present, in user order.
    assert params["image_paths"] == [str(uploads / "a.png"), str(uploads / "b.png")]


def test_render_dedupes_when_external_overlaps_slot_path(tmp_path, monkeypatch):
    """If an external ref has the same value as a slot-derived path, only
    keep one (slot-derived comes first)."""
    uploads = tmp_path / "uploads" / "infographic"
    uploads.mkdir(parents=True)
    (uploads / "logo.png").write_bytes(b"")
    (uploads / "extra.png").write_bytes(b"")
    monkeypatch.chdir(tmp_path)
    import server as _srv
    monkeypatch.setattr(_srv, "_INFOGRAPHIC_UPLOADS_DIR", (tmp_path / "uploads" / "infographic").resolve())

    body = _good()
    body["slots"]["hub_image"] = str(uploads / "logo.png")   # image_ref slot
    body["image_refs"] = [str(uploads / "logo.png"), str(uploads / "extra.png")]
    from server import jobs as _jobs
    _jobs.clear()
    with patch("job_queue.JobQueue.submit_background", return_value=None):
        r = TestClient(app).post("/api/infographic/render", json=body)
    assert r.status_code == 202
    params = _jobs[r.json()["job_id"]]["params"]
    assert params["image_paths"] == [str(uploads / "logo.png"), str(uploads / "extra.png")]   # de-duped


def test_render_rejects_path_traversal_in_image_refs():
    body = _good()
    body["image_refs"] = ["/etc/passwd"]
    r = TestClient(app).post("/api/infographic/render", json=body)
    assert r.status_code == 400
    assert "outside uploads dir" in r.text or "invalid" in r.text.lower()


def test_render_rejects_relative_path_traversal():
    body = _good()
    body["image_refs"] = ["uploads/infographic/../../../etc/passwd"]
    r = TestClient(app).post("/api/infographic/render", json=body)
    assert r.status_code == 400
