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


def test_render_ignores_image_refs_field():
    """image_refs is accepted on the request schema for API back-compat
    but always ignored — image refs were dropped from the infographic
    builder because the model treats them as background style/palette
    rather than literal placement. params["image_paths"] is always [].
    Path-traversal validation is no longer needed because the field is
    never used to access disk."""
    body = _good()
    body["image_refs"] = ["/etc/passwd",  # would have been rejected before
                          "uploads/infographic/anything.png"]
    from server import jobs as _jobs
    _jobs.clear()
    with patch("job_queue.JobQueue.submit_background", return_value=None):
        r = TestClient(app).post("/api/infographic/render", json=body)
    assert r.status_code == 202
    params = _jobs[r.json()["job_id"]]["params"]
    assert params["image_paths"] == []


def test_render_appends_style_notes_to_prompt():
    """style_notes appears as the final 'Overall style:' sentence on the
    assembled prompt — that's where the model attends most strongly to
    aesthetic direction per the SenseNova showcase prompts."""
    body = _good()
    body["style_notes"] = "soft pastel palette, hand-lettered art-deco titles"
    from server import jobs as _jobs
    _jobs.clear()
    with patch("job_queue.JobQueue.submit_background", return_value=None):
        r = TestClient(app).post("/api/infographic/render", json=body)
    assert r.status_code == 202
    params = _jobs[r.json()["job_id"]]["params"]
    prompt = params["prompt"]
    assert prompt.endswith(
        "Overall style: soft pastel palette, hand-lettered art-deco titles")
    # Sidecar metadata should also carry the raw style_notes for reproducibility.
    assert params["style_notes"] == "soft pastel palette, hand-lettered art-deco titles"


def test_render_omits_style_notes_block_when_blank():
    """Blank style_notes — no trailing 'Overall style:' sentence appears."""
    body = _good()
    body["style_notes"] = "   "  # whitespace-only counts as empty
    from server import jobs as _jobs
    _jobs.clear()
    with patch("job_queue.JobQueue.submit_background", return_value=None):
        r = TestClient(app).post("/api/infographic/render", json=body)
    assert r.status_code == 202
    params = _jobs[r.json()["job_id"]]["params"]
    assert "Overall style:" not in params["prompt"]


def test_render_style_notes_field_optional_for_back_compat():
    """Body without style_notes at all (older client) still works."""
    body = _good()  # has no style_notes key
    assert "style_notes" not in body
    from server import jobs as _jobs
    _jobs.clear()
    with patch("job_queue.JobQueue.submit_background", return_value=None):
        r = TestClient(app).post("/api/infographic/render", json=body)
    assert r.status_code == 202
