"""Hyperframes backend — HTML -> MP4 via local author model + hyperframes renderer.

SKETCH / DRAFT — not yet registered. Lives on feature/hyperframes-backend
while the integration incubates. Requires the hyperframes-ollama fork:

    git clone https://github.com/toastmanAu/hyperframes-ollama.git ~/hyperframes
    cd ~/hyperframes && git checkout ollama-generate && bun install && bun run build

Other requirements:
  - Node >= 22 + bun on PATH (for the build above)
  - ffmpeg + chromium on PATH (hyperframes picks these up automatically)
  - A local Ollama model capable of authoring hyperframes HTML. Tested
    passers (as of 2026-04-18): qwen3:8b, qwen3.5:35b-a3b, gemma4:26b,
    devstral-small-2:24b, gpt-oss:20b, qwen3.6:35b-a3b-q4_K_M and -q8_0.

Flow:
  params -> _author() -> HTML string -> _render() -> MP4 at output_path
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Awaitable, Callable

import aiohttp

from backends.base import BaseBackend

logger = logging.getLogger(__name__)

ProgressCb = Callable[[int, str], Awaitable[None]]

DEFAULT_OLLAMA_HOST = "http://localhost:11434"
DEFAULT_HYPERFRAMES_CLI = Path.home() / "hyperframes" / "packages" / "cli" / "dist" / "cli.js"

# Compact authoring prompt — lives here so the backend is self-contained. Keep in sync
# with the slate-tested prompt at ~/tmp/hf-auth-test/prompts/system.md when we settle
# on a final version.
SYSTEM_PROMPT = """You are authoring a HyperFrames composition — an HTML file that renders deterministically to video.

Structure (copy this skeleton exactly):
<!doctype html>
<html lang="en"><head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=1920, height=1080"/>
  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <style>*{margin:0;padding:0;box-sizing:border-box}html,body{width:1920px;height:1080px;overflow:hidden;background:#0a0a0a}</style>
</head><body>
  <div id="root" data-composition-id="main" data-start="0" data-duration="{DURATION}" data-width="1920" data-height="1080">
    <!-- clips here -->
  </div>
  <script>
    window.__timelines = window.__timelines || {};
    const tl = gsap.timeline({paused:true});
    // tweens here
    window.__timelines["main"] = tl;
  </script>
</body></html>

Rules:
- Every clip: <div class="clip" id=... data-start=... data-duration=... data-track-index=...>
- Position with CSS (absolute or flex), keep content inside 1920x1080
- Animate with tl.from() for entrances, tl.to() for exits. Third arg = timeline-absolute seconds.
- No external assets (no images/videos/audio URLs). Text + CSS + GSAP only.
- No frameworks (React/Vue). Plain HTML + inline <script>.
- Output ONLY the raw HTML starting with <!doctype html>. No markdown fences, no commentary.
"""


class HyperframesBackend(BaseBackend):
    """Generate HTML via Ollama, render to MP4 via the hyperframes CLI."""

    def __init__(self, config: dict):
        super().__init__(config)
        self.ollama_host: str = config.get("ollama_host") or DEFAULT_OLLAMA_HOST
        self.default_model: str = config.get("model") or "qwen3-coder:30b"
        self.cli_path: Path = Path(config.get("cli_path") or DEFAULT_HYPERFRAMES_CLI)
        self.temperature: float = float(config.get("temperature", 0.2))
        self.num_ctx: int = int(config.get("num_ctx", 8192))
        self.num_predict: int = int(config.get("num_predict", 6000))
        self.max_retries: int = int(config.get("max_retries", 2))

        if not self.cli_path.exists():
            logger.warning(
                "Hyperframes CLI not found at %s — renders will fail until built",
                self.cli_path,
            )

    async def generate(
        self,
        params: dict,
        output_path: str,
        on_progress: ProgressCb,
    ) -> None:
        prompt: str = params.get("prompt", "").strip()
        if not prompt:
            raise ValueError("hyperframes backend requires 'prompt' in params")

        model: str = params.get("model") or self.default_model
        duration: float = float(params.get("duration_s", 6))

        await on_progress(5, f"Authoring with {model}")
        html = await self._author(model, prompt, duration, on_progress)

        await on_progress(50, "Rendering to MP4")
        await asyncio.to_thread(self._render_sync, html, Path(output_path))

        await on_progress(100, "Done")

    async def _author(
        self,
        model: str,
        user_prompt: str,
        duration: float,
        on_progress: ProgressCb,
    ) -> str:
        system = SYSTEM_PROMPT.replace("{DURATION}", str(duration))
        payload = {
            "model": model,
            "stream": False,
            "think": False,
            "options": {
                "temperature": self.temperature,
                "num_ctx": self.num_ctx,
                "num_predict": self.num_predict,
            },
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_prompt},
            ],
        }

        attempt = 0
        last_error = ""
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=600)
        ) as session:
            while attempt <= self.max_retries:
                async with session.post(
                    f"{self.ollama_host}/api/chat", json=payload
                ) as resp:
                    resp.raise_for_status()
                    body = await resp.json()

                msg = body.get("message") or {}
                content = msg.get("content") or msg.get("thinking") or ""
                html = _extract_html(content)
                if html and _looks_valid(html):
                    return html

                last_error = f"attempt {attempt + 1}: no valid doctype in response"
                logger.warning("hyperframes authoring %s — retrying", last_error)
                attempt += 1
                await on_progress(
                    10 + attempt * 10, f"Retrying ({attempt}/{self.max_retries})"
                )

        raise RuntimeError(
            f"hyperframes authoring failed after {self.max_retries + 1} attempts: {last_error}"
        )

    def _render_sync(self, html: str, output_path: Path) -> None:
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(prefix="hyperframes-") as tmp:
            tmp_dir = Path(tmp)
            (tmp_dir / "index.html").write_text(html)
            (tmp_dir / "hyperframes.json").write_text(
                json.dumps({"entry": "index.html"})
            )
            (tmp_dir / "meta.json").write_text(
                json.dumps({"name": "wyltek-hf", "version": "0.0.0"})
            )

            cmd = [
                "node",
                str(self.cli_path),
                "render",
                "--output",
                str(output_path),
            ]
            result = subprocess.run(
                cmd,
                cwd=tmp_dir,
                capture_output=True,
                text=True,
                timeout=300,
                check=False,
            )
            if result.returncode != 0:
                tail = (result.stdout + result.stderr)[-2000:]
                raise RuntimeError(
                    f"hyperframes render failed (rc={result.returncode}):\n{tail}"
                )


def _extract_html(content: str) -> str:
    """Pull the HTML document out of a possibly noisy model response."""
    text = content.strip()
    if text.startswith("```"):
        lines = [l for l in text.split("\n") if not l.strip().startswith("```")]
        text = "\n".join(lines)
    lower = text.lower()
    idx = lower.find("<!doctype html>")
    if idx == -1:
        idx = lower.find("<html")
    return text[idx:].strip() if idx >= 0 else ""


def _looks_valid(html: str) -> bool:
    return (
        "data-composition-id" in html
        and "__timelines" in html
        and "gsap" in html.lower()
    )
