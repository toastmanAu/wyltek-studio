from fastapi.testclient import TestClient
from server import app


def test_templates_endpoint():
    r = TestClient(app).get("/api/infographic/templates")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    ids = {t["id"] for t in body}
    assert "hub_and_spoke" in ids
    hub = next(t for t in body if t["id"] == "hub_and_spoke")
    assert any(s["id"] == "title" for s in hub["slots"])
