"""Supertonic-3 TTS engine — multilingual ONNX, CPU-only.

99M-param ONNX pipeline (text_encoder → duration_predictor → vector_estimator
→ vocoder) covering 31 languages with 10 shared voice styles (M1–M5, F1–F5).
Runs entirely on CPU via onnxruntime; no GPU contention with the diffusion
workers. Local weights ship in ``/data/hf-models/transformers/supertonic-3``.

We pass ``auto_download=False`` and an explicit ``model_dir`` so the SDK never
phones home — useful since the host is sometimes off-net and the weights are
already on disk.
"""

from __future__ import annotations

import asyncio
import json
import wave
from pathlib import Path

import numpy as np


# The 2026-05-13 pull put weights here. Override via ``config["model_dir"]`` if
# Phill ever moves them.
DEFAULT_MODEL_DIR = Path("/data/hf-models/transformers/supertonic-3")


class SupertonicEngine:
    name = "supertonic"
    supports_cloning = False  # SDK only loads pre-rendered style vectors

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.model_dir = Path(config.get("model_dir", DEFAULT_MODEL_DIR))
        self.default_lang: str | None = config.get("default_lang") or None
        self.total_steps = int(config.get("total_steps", 8))
        # Lazy: instantiate the TTS object only on first synth so registry
        # discovery stays cheap (ORT session init is ~200 ms).
        self._tts = None

    def available(self) -> bool:
        """True if the SDK is importable AND the local weights are present."""
        try:
            import supertonic  # noqa: F401
        except Exception:
            return False
        return (self.model_dir / "onnx" / "vocoder.onnx").exists() and \
               (self.model_dir / "voice_styles").is_dir()

    def voices(self) -> list[dict]:
        """Enumerate voice-style JSONs. 10 multilingual styles ship out of
        the box; users can add custom ``*.json`` style vectors to the same
        dir if they have them."""
        styles_dir = self.model_dir / "voice_styles"
        if not styles_dir.is_dir():
            return []
        result = []
        for path in sorted(styles_dir.glob("*.json")):
            voice_id = path.stem
            # Names like M1/F3 map to gender by first letter; everything else
            # is opaque to the engine — the SDK reads the style vector raw.
            gender = {"M": "male", "F": "female"}.get(voice_id[:1], "unknown")
            result.append({
                "id": voice_id,
                "name": voice_id,
                "language": "multilingual",  # 31-language model; pick at synth time
                "gender": gender,
                "quality": "high",
                "sample_rate": 22050,  # vocoder default; corrected post-synth
            })
        return result

    def _ensure_loaded(self):
        """Instantiate the TTS object on first use. Idempotent."""
        if self._tts is not None:
            return self._tts
        from supertonic import TTS
        # auto_download=False — fail loud if model_dir is wrong, rather than
        # silently pulling 380 MB over a flaky link.
        self._tts = TTS(
            model="supertonic-3",
            model_dir=str(self.model_dir),
            auto_download=False,
        )
        return self._tts

    async def generate(self, text: str, voice: str, output_path: str,
                       speed: float = 1.0) -> dict:
        """Run synth on a worker thread so the asyncio loop stays free.

        ORT inference is CPU-bound and may block 1–3 s for a long
        utterance; ``asyncio.to_thread`` keeps the FastAPI loop responsive
        for concurrent requests (the registry already routes TTS to the
        ``cpu`` job-queue lane upstream).
        """
        def _synth_sync() -> dict:
            tts = self._ensure_loaded()
            style = tts.get_voice_style(voice_name=voice)
            # SDK default speed is 1.05 (slight uptick over natural). Map
            # caller's "1.0 = normal" by multiplying through.
            wav, _duration_array = tts.synthesize(
                text=text,
                voice_style=style,
                total_steps=self.total_steps,
                speed=speed * 1.05,
                lang=self.default_lang,  # None → SDK auto-detects from text
            )
            tts.save_audio(wav, output_path)

            duration_s = 0.0
            sample_rate = 22050
            with wave.open(output_path, "rb") as wf:
                sample_rate = wf.getframerate()
                duration_s = wf.getnframes() / float(sample_rate)
            return {
                "duration": round(duration_s, 2),
                "sample_rate": sample_rate,
                "file_size": Path(output_path).stat().st_size,
            }

        return await asyncio.to_thread(_synth_sync)
