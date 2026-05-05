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
