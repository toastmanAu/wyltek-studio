"""Piper TTS engine — fast, lightweight, CPU-only."""

import asyncio
import json
import os
import wave
from pathlib import Path


DEFAULT_PIPER_DIR = Path(__file__).parent.parent / "engines" / "piper"
DEFAULT_VOICES_DIR = Path(__file__).parent.parent / "engines" / "voices"


class PiperEngine:
    name = "piper"

    def __init__(self, config: dict = None):
        config = config or {}
        self.piper_bin = Path(config.get("binary", DEFAULT_PIPER_DIR / "piper"))
        self.voices_dir = Path(config.get("voices_dir", DEFAULT_VOICES_DIR))

    def available(self) -> bool:
        """Check if Piper binary and at least one voice exist."""
        if not self.piper_bin.exists():
            return False
        return len(list(self.voices_dir.glob("*.onnx"))) > 0

    def voices(self) -> list[dict]:
        """Discover installed voice models."""
        result = []
        for model_path in sorted(self.voices_dir.glob("*.onnx")):
            voice_id = model_path.stem
            meta = self._load_meta(model_path)
            result.append({
                "id": voice_id,
                "name": meta.get("name", voice_id),
                "language": meta.get("language", {}).get("code", "en"),
                "gender": meta.get("speaker_id_map", {}).get("0", "unknown"),
                "quality": meta.get("quality", "medium"),
                "sample_rate": meta.get("audio", {}).get("sample_rate", 22050),
            })
        return result

    def _load_meta(self, model_path: Path) -> dict:
        """Load the .onnx.json metadata file."""
        meta_path = Path(str(model_path) + ".json")
        if meta_path.exists():
            try:
                with open(meta_path) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    async def generate(self, text: str, voice: str, output_path: str,
                       speed: float = 1.0) -> dict:
        """Generate speech via Piper binary. Returns metadata dict."""
        model_path = self.voices_dir / f"{voice}.onnx"
        if not model_path.exists():
            raise ValueError(f"Voice model not found: {voice}")

        # Piper reads from stdin, writes WAV to output file
        length_scale = 1.0 / max(speed, 0.1)  # speed=2.0 → length_scale=0.5

        proc = await asyncio.create_subprocess_exec(
            str(self.piper_bin),
            "--model", str(model_path),
            "--output_file", output_path,
            "--length_scale", str(length_scale),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate(text.encode("utf-8"))

        if proc.returncode != 0:
            raise RuntimeError(f"Piper failed: {stderr.decode()}")

        if not os.path.exists(output_path):
            raise RuntimeError("Piper produced no output file")

        # Read WAV metadata
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
