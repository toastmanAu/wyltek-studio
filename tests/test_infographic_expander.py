"""Tests for studio.infographic_expander.

Ollama is mocked via httpx.MockTransport — we never reach the network.
The template fallback path is exercised by simulating Connect/Timeout/bad-
response failures.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from studio.infographic_catalog import InfographicCatalog
from studio.infographic_expander import (
    ExpansionResult,
    expand,
    template_fallback,
)


@pytest.fixture
def catalog(tmp_path: Path) -> InfographicCatalog:
    (tmp_path / "layouts").mkdir()
    (tmp_path / "styles").mkdir()
    (tmp_path / "layouts" / "bento.md").write_text(
        "# Bento\n\n## Structure\nGrid of rectangular cells with one hero cell.\n\n"
        "## Visual Elements\nThick borders, drop shadows, varied cell sizes.\n\n"
        "## Text Placement\nLabel inside each cell, hero cell holds title.\n"
    )
    (tmp_path / "styles" / "memphis.md").write_text(
        "# Memphis\n\n## Color Palette\nPastels with one accent (#FF6B6B).\n\n"
        "## Visual Elements\nSquiggles, dots, geometric shapes.\n"
    )
    index = {
        "version": "1",
        "data_types": [{"key": "overview", "primary": "bento", "alternatives": []}],
        "contexts": [{"key": "Business", "primary": "memphis", "alternatives": []}],
        "all_layouts": ["bento"],
        "all_styles": ["memphis"],
        "fallback": {"layout": "bento", "style": "memphis"},
    }
    (tmp_path / "index.json").write_text(json.dumps(index))
    (tmp_path / "prompts-expand-system.md").write_text(
        "You expand user prompts into infographic descriptions."
    )
    return InfographicCatalog(tmp_path)


def _mock_ollama_ok(response_text: str) -> httpx.MockTransport:
    """Mock transport that returns a successful OpenAI-shaped response."""
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": response_text}}],
            "model": body["model"],
        })
    return httpx.MockTransport(handler)


def test_expand_builds_request_with_layout_and_style_bodies(catalog):
    captured = {}
    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
    with patch("studio.infographic_expander._build_client",
               return_value=httpx.Client(transport=httpx.MockTransport(handler))):
        expand("Q4 results", "bento", "memphis", catalog=catalog)
    msgs = captured["body"]["messages"]
    assert msgs[0]["role"] == "system"
    assert "expand" in msgs[0]["content"].lower()
    assert "Q4 results" in msgs[1]["content"]
    assert "Bento" in msgs[1]["content"]  # layout md was embedded
    assert "Memphis" in msgs[1]["content"]  # style md was embedded


def test_expand_uses_env_model(catalog, monkeypatch):
    monkeypatch.setenv("INFOGRAPHIC_EXPANDER_MODEL", "qwen3:14b")
    captured = {}
    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})
    with patch("studio.infographic_expander._build_client",
               return_value=httpx.Client(transport=httpx.MockTransport(handler))):
        expand("p", "bento", "memphis", catalog=catalog)
    assert captured["body"]["model"] == "qwen3:14b"


def test_expand_returns_ollama_response_on_success(catalog):
    transport = _mock_ollama_ok("An expanded bento-grid prompt with Memphis flair.")
    with patch("studio.infographic_expander._build_client",
               return_value=httpx.Client(transport=transport)):
        result = expand("Q4", "bento", "memphis", catalog=catalog)
    assert isinstance(result, ExpansionResult)
    assert "expanded bento-grid" in result.prompt
    assert result.fallback_used is False
    assert result.elapsed_s >= 0.0
    assert result.model  # whatever the env said


def test_expand_falls_back_on_connect_error(catalog):
    def handler(_request):
        raise httpx.ConnectError("no route to host")
    transport = httpx.MockTransport(handler)
    with patch("studio.infographic_expander._build_client",
               return_value=httpx.Client(transport=transport)):
        result = expand("Q4", "bento", "memphis", catalog=catalog)
    assert result.fallback_used is True
    assert result.prompt  # template fallback returned something


def test_expand_falls_back_on_timeout(catalog):
    def handler(_request):
        raise httpx.ReadTimeout("read timeout")
    transport = httpx.MockTransport(handler)
    with patch("studio.infographic_expander._build_client",
               return_value=httpx.Client(transport=transport)):
        result = expand("Q4", "bento", "memphis", catalog=catalog)
    assert result.fallback_used is True


def test_expand_falls_back_on_bad_response_shape(catalog):
    def handler(_request):
        return httpx.Response(200, json={"unexpected": "shape"})
    transport = httpx.MockTransport(handler)
    with patch("studio.infographic_expander._build_client",
               return_value=httpx.Client(transport=transport)):
        result = expand("Q4", "bento", "memphis", catalog=catalog)
    assert result.fallback_used is True


def test_expand_falls_back_on_http_404_model_missing(catalog):
    """Ollama returns 404 when the model isn't pulled — must fall back."""
    def handler(_request):
        return httpx.Response(404, json={"error": "model 'foo' not found"})
    transport = httpx.MockTransport(handler)
    with patch("studio.infographic_expander._build_client",
               return_value=httpx.Client(transport=transport)):
        result = expand("Q4", "bento", "memphis", catalog=catalog)
    assert result.fallback_used is True


def test_template_fallback_is_deterministic(catalog):
    layout_md = catalog.read_markdown("layouts", "bento")
    style_md = catalog.read_markdown("styles", "memphis")
    a = template_fallback("Q4", "bento", "memphis", layout_md, style_md)
    b = template_fallback("Q4", "bento", "memphis", layout_md, style_md)
    assert a == b


def test_template_fallback_includes_layout_structure(catalog):
    layout_md = catalog.read_markdown("layouts", "bento")
    style_md = catalog.read_markdown("styles", "memphis")
    out = template_fallback("Q4 results", "bento", "memphis", layout_md, style_md)
    assert "Q4 results" in out
    assert "Grid of rectangular cells" in out  # from layout's ## Structure


def test_template_fallback_includes_style_palette(catalog):
    layout_md = catalog.read_markdown("layouts", "bento")
    style_md = catalog.read_markdown("styles", "memphis")
    out = template_fallback("p", "bento", "memphis", layout_md, style_md)
    assert "Pastels with one accent" in out  # from style's ## Color Palette


def test_template_fallback_tolerates_missing_sections(catalog):
    """If a layout md has no `## Structure` heading, fallback still returns
    a usable string (uses whatever paragraphs are present)."""
    bare_layout = "# Sparse layout\n\nJust one paragraph, no headers.\n"
    bare_style = "# Sparse style\n\nOne paragraph.\n"
    out = template_fallback("p", "sparse", "sparse", bare_layout, bare_style)
    assert "p" in out
    assert len(out) > 50  # not empty
