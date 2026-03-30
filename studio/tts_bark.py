"""Bark TTS engine — most expressive, supports laughter, music, emotions."""

import asyncio
import os
from pathlib import Path

# Force CPU
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

# Bark speaker presets
VOICES = [
    {"id": "v2/en_speaker_0", "name": "Speaker 0 (Male)", "language": "en", "gender": "male"},
    {"id": "v2/en_speaker_1", "name": "Speaker 1 (Male)", "language": "en", "gender": "male"},
    {"id": "v2/en_speaker_2", "name": "Speaker 2 (Male)", "language": "en", "gender": "male"},
    {"id": "v2/en_speaker_3", "name": "Speaker 3 (Female)", "language": "en", "gender": "female"},
    {"id": "v2/en_speaker_4", "name": "Speaker 4 (Female)", "language": "en", "gender": "female"},
    {"id": "v2/en_speaker_5", "name": "Speaker 5 (Female)", "language": "en", "gender": "female"},
    {"id": "v2/en_speaker_6", "name": "Speaker 6 (Male, deep)", "language": "en", "gender": "male"},
    {"id": "v2/en_speaker_7", "name": "Speaker 7 (Male, narrator)", "language": "en", "gender": "male"},
    {"id": "v2/en_speaker_8", "name": "Speaker 8 (Female, warm)", "language": "en", "gender": "female"},
    {"id": "v2/en_speaker_9", "name": "Speaker 9 (Female, bright)", "language": "en", "gender": "female"},
]


class BarkEngine:
    name = "bark"

    def __init__(self, config: dict = None):
        self._loaded = False

    def available(self) -> bool:
        try:
            import bark  # noqa: F401
            return True
        except ImportError:
            return False

    def _ensure_loaded(self):
        if not self._loaded:
            from bark import preload_models
            preload_models()
            self._loaded = True

    def voices(self) -> list[dict]:
        return [dict(v) for v in VOICES]

    async def generate(self, text: str, voice: str, output_path: str,
                       speed: float = 1.0) -> dict:
        """Generate speech with Bark. Supports expressive tags like [laughs], [music]."""
        loop = asyncio.get_event_loop()

        def _do():
            self._ensure_loaded()
            from bark import generate_audio, SAMPLE_RATE
            import numpy as np
            import soundfile as sf

            audio = generate_audio(
                text,
                history_prompt=voice if voice else None,
            )

            sf.write(output_path, audio, SAMPLE_RATE)

            duration = len(audio) / SAMPLE_RATE

            return {
                "duration": round(duration, 2),
                "sample_rate": SAMPLE_RATE,
                "file_size": os.path.getsize(output_path),
            }

        return await loop.run_in_executor(None, _do)
