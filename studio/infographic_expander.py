"""Ollama-backed prompt expander with deterministic template fallback.

Posts to Ollama's OpenAI-compatible /v1/chat/completions. On any failure
(connect, timeout, HTTP error, malformed JSON, missing model) falls back
to a regex-based template that always returns a usable prompt string so
the render path never blocks on the LLM.
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass

import httpx

from studio.infographic_catalog import InfographicCatalog

log = logging.getLogger(__name__)

DEFAULT_MODEL = "gpt-oss:20b"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_TIMEOUT_S = 30.0


@dataclass(frozen=True)
class ExpansionResult:
    prompt: str
    fallback_used: bool
    elapsed_s: float
    model: str


def expand(
    user_prompt: str,
    layout: str,
    style: str,
    *,
    catalog: InfographicCatalog,
    model: str | None = None,
    ollama_url: str | None = None,
    timeout_s: float | None = None,
) -> ExpansionResult:
    """Expand user_prompt into a full infographic prompt.

    Reads layout/style markdown bodies from the catalog and embeds them in
    the user message. Returns ExpansionResult either way — callers should
    surface fallback_used so the UI can chip "Ollama unavailable".
    """
    if model is None:
        model = os.environ.get("INFOGRAPHIC_EXPANDER_MODEL", DEFAULT_MODEL)
    if ollama_url is None:
        ollama_url = os.environ.get("OLLAMA_BASE_URL", DEFAULT_OLLAMA_URL)
    if timeout_s is None:
        timeout_s = float(os.environ.get("INFOGRAPHIC_EXPANDER_TIMEOUT_S", DEFAULT_TIMEOUT_S))

    layout_md = catalog.read_markdown("layouts", layout)
    style_md = catalog.read_markdown("styles", style)
    system = catalog.expander_system_prompt()
    user = _build_user_message(user_prompt, layout, style, layout_md, style_md)

    start = time.monotonic()
    try:
        with _build_client(ollama_url, timeout_s) as client:
            # Use absolute URL so callers that patch _build_client with a bare
            # httpx.Client(transport=...) (no base_url) still route correctly.
            r = client.post(
                f"{ollama_url.rstrip('/')}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "stream": False,
                    "temperature": 0.7,
                },
            )
        if r.status_code != 200:
            raise RuntimeError(f"ollama HTTP {r.status_code}: {r.text[:200]}")
        data = r.json()
        prompt = data["choices"][0]["message"]["content"].strip()
        if not prompt:
            raise RuntimeError("ollama returned empty content")
        elapsed = time.monotonic() - start
        log.info("infographic_expand model=%s elapsed_s=%.2f chars=%d",
                 model, elapsed, len(prompt))
        return ExpansionResult(prompt=prompt, fallback_used=False,
                                elapsed_s=elapsed, model=model)
    except Exception as exc:
        elapsed = time.monotonic() - start
        log.warning("infographic_expand fallback=template model=%s elapsed_s=%.2f reason=%r",
                    model, elapsed, exc)
        fallback_prompt = template_fallback(user_prompt, layout, style, layout_md, style_md)
        return ExpansionResult(prompt=fallback_prompt, fallback_used=True,
                                elapsed_s=elapsed, model=model)


def _build_client(ollama_url: str, timeout_s: float) -> httpx.Client:
    """Seam for tests to inject a MockTransport."""
    return httpx.Client(base_url=ollama_url, timeout=timeout_s)


def _build_user_message(
    user_prompt: str, layout: str, style: str, layout_md: str, style_md: str,
) -> str:
    return (
        f"## User prompt\n{user_prompt}\n\n"
        f"## Layout reference: {layout}\n{layout_md}\n\n"
        f"## Style reference: {style}\n{style_md}\n"
    )


# ── Template fallback ──────────────────────────────────────────────────────
#
# Deterministic — same inputs always produce the same output. Extracts the
# Structure/Visual Elements/Text Placement sections from the layout md and
# the Color Palette/Visual Elements sections from the style md. Concatenates
# into a single descriptive prompt that always passes through to the model.

_SECTION_RE = re.compile(r"^##\s+(.+?)$\n(.*?)(?=^##\s+|\Z)", re.MULTILINE | re.DOTALL)


def template_fallback(
    user_prompt: str, layout: str, style: str, layout_md: str, style_md: str,
) -> str:
    layout_sections = _extract_sections(layout_md)
    style_sections = _extract_sections(style_md)

    parts: list[str] = [f"Infographic about: {user_prompt}."]

    structure = layout_sections.get("Structure") or _first_paragraph(layout_md)
    if structure:
        parts.append(f"Layout ({layout}): {structure}")

    elements = layout_sections.get("Visual Elements")
    if elements:
        parts.append(f"Layout elements: {elements}")

    placement = layout_sections.get("Text Placement")
    if placement:
        parts.append(f"Text placement: {placement}")

    palette = style_sections.get("Color Palette") or _first_paragraph(style_md)
    if palette:
        parts.append(f"Style palette ({style}): {palette}")

    style_elements = style_sections.get("Visual Elements")
    if style_elements:
        parts.append(f"Style elements: {style_elements}")

    return " ".join(p.strip() for p in parts if p)


def _extract_sections(md: str) -> dict[str, str]:
    """Return a {heading: body-text} map for top-level `## Heading` sections."""
    out: dict[str, str] = {}
    for m in _SECTION_RE.finditer(md):
        heading = m.group(1).strip()
        body = m.group(2).strip().replace("\n", " ")
        out[heading] = body
    return out


def _first_paragraph(md: str) -> str:
    for block in md.split("\n\n"):
        block = block.strip()
        if not block or block.startswith("#"):
            continue
        return block.replace("\n", " ")
    return ""
