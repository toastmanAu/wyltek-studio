"""XTTS v2 TTS engine — voice cloning, multi-language, high quality."""

import asyncio
import os
from pathlib import Path

# Force CPU
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

VOICES_DIR = Path(__file__).parent.parent / "engines" / "xtts_voices"

# Built-in speaker presets from XTTS
BUILTIN_VOICES = [
    {"id": "xtts_female_1", "name": "XTTS Female 1", "language": "en", "gender": "female"},
    {"id": "xtts_male_1", "name": "XTTS Male 1", "language": "en", "gender": "male"},
]


class XTTSEngine:
    name = "xtts"

    def __init__(self, config: dict = None):
        self._tts = None

    def available(self) -> bool:
        try:
            from TTS.api import TTS  # noqa: F401
            return True
        except ImportError:
            return False

    def _get_tts(self):
        if self._tts is None:
            from TTS.api import TTS
            self._tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to("cpu")
        return self._tts

    def voices(self) -> list[dict]:
        result = list(BUILTIN_VOICES)

        # Discover custom cloned voices (WAV files in xtts_voices/)
        VOICES_DIR.mkdir(parents=True, exist_ok=True)
        for wav in sorted(VOICES_DIR.glob("*.wav")):
            voice_id = f"clone_{wav.stem}"
            result.append({
                "id": voice_id,
                "name": f"Clone: {wav.stem}",
                "language": "en",
                "gender": "cloned",
                "reference": str(wav),
            })

        return result

    async def generate(self, text: str, voice: str, output_path: str,
                       speed: float = 1.0) -> dict:
        """Generate speech. Supports built-in voices and cloned voices."""
        loop = asyncio.get_event_loop()

        def _do():
            tts = self._get_tts()

            if voice.startswith("clone_"):
                # Use reference WAV for voice cloning
                ref_name = voice.replace("clone_", "") + ".wav"
                ref_path = VOICES_DIR / ref_name
                if not ref_path.exists():
                    raise ValueError(f"Clone reference not found: {ref_path}")

                tts.tts_to_file(
                    text=text,
                    speaker_wav=str(ref_path),
                    language="en",
                    file_path=output_path,
                    speed=speed,
                )
            else:
                # Use built-in speaker
                # XTTS has internal speaker embeddings
                tts.tts_to_file(
                    text=text,
                    speaker=voice,
                    language="en",
                    file_path=output_path,
                    speed=speed,
                )

            import wave
            duration = 0.0
            sample_rate = 22050
            try:
                with wave.open(output_path, "rb") as wf:
                    sample_rate = wf.getframerate()
                    frames = wf.getnframes()
                    duration = frames / sample_rate
            except Exception:
                pass

            return {
                "duration": round(duration, 2),
                "sample_rate": sample_rate,
                "file_size": os.path.getsize(output_path),
            }

        return await loop.run_in_executor(None, _do)
