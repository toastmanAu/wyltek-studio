"""TTS engine registry — discovers and manages text-to-speech backends."""

from __future__ import annotations
from typing import Protocol

_engines: dict[str, "TTSEngine"] = {}


class TTSEngine(Protocol):
    name: str

    def voices(self) -> list[dict]:
        """Return available voices: [{id, name, language, gender}]"""
        ...

    async def generate(self, text: str, voice: str, output_path: str,
                       speed: float = 1.0) -> dict:
        """Generate speech. Returns {duration, sample_rate, file_size}."""
        ...


def register(engine: TTSEngine):
    _engines[engine.name] = engine


def get_engine(name: str) -> TTSEngine | None:
    return _engines.get(name)


def list_engines() -> list[dict]:
    """Return all registered engines with their voices."""
    result = []
    for name, engine in _engines.items():
        result.append({
            "name": name,
            "voices": engine.voices(),
        })
    return result


def init_engines(tts_config: dict):
    """Auto-detect and register available TTS engines."""
    _engines.clear()

    # Piper — check if binary exists
    from studio.tts_piper import PiperEngine
    piper = PiperEngine(tts_config.get("piper", {}))
    if piper.available():
        register(piper)

    # Kokoro — check if pip package installed
    try:
        from studio.tts_kokoro import KokoroEngine
        kokoro = KokoroEngine(tts_config.get("kokoro", {}))
        if kokoro.available():
            register(kokoro)
    except Exception:
        pass
