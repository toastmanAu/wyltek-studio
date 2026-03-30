"""Kokoro TTS engine — high quality, 82M parameter model, CPU-friendly."""

import asyncio
import os
import wave
from pathlib import Path

# Kokoro must run on CPU to avoid GPU contention with ComfyUI
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

VOICES = [
    {"id": "af_heart", "name": "Heart", "language": "en-US", "gender": "female"},
    {"id": "af_bella", "name": "Bella", "language": "en-US", "gender": "female"},
    {"id": "af_nicole", "name": "Nicole", "language": "en-US", "gender": "female"},
    {"id": "af_sarah", "name": "Sarah", "language": "en-US", "gender": "female"},
    {"id": "af_sky", "name": "Sky", "language": "en-US", "gender": "female"},
    {"id": "am_adam", "name": "Adam", "language": "en-US", "gender": "male"},
    {"id": "am_michael", "name": "Michael", "language": "en-US", "gender": "male"},
    {"id": "bf_emma", "name": "Emma", "language": "en-GB", "gender": "female"},
    {"id": "bf_isabella", "name": "Isabella", "language": "en-GB", "gender": "female"},
    {"id": "bm_george", "name": "George", "language": "en-GB", "gender": "male"},
    {"id": "bm_lewis", "name": "Lewis", "language": "en-GB", "gender": "male"},
]


class KokoroEngine:
    name = "kokoro"

    def __init__(self, config: dict = None):
        self._pipe = None

    def available(self) -> bool:
        try:
            import kokoro  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_pipe(self):
        if self._pipe is None:
            from kokoro import KPipeline
            self._pipe = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
        return self._pipe

    def voices(self) -> list[dict]:
        return [dict(v) for v in VOICES]

    async def generate(self, text: str, voice: str, output_path: str,
                       speed: float = 1.0) -> dict:
        """Generate speech via Kokoro. Runs in thread executor (CPU-bound)."""
        loop = asyncio.get_event_loop()

        def _do():
            import torch
            import soundfile as sf

            pipe = self._get_pipe()
            chunks = []
            for gs, ps, audio in pipe(text, voice=voice, speed=speed):
                chunks.append(audio)

            if not chunks:
                raise RuntimeError("Kokoro produced no audio")

            full = torch.cat(chunks)
            audio_np = full.numpy()
            sf.write(output_path, audio_np, 24000)

            duration = len(audio_np) / 24000
            return {
                "duration": round(duration, 2),
                "sample_rate": 24000,
                "file_size": os.path.getsize(output_path),
            }

        return await loop.run_in_executor(None, _do)
