"""XTTS v2 TTS engine — voice cloning, multi-language, high quality."""

import asyncio
import os
from pathlib import Path

# TTS engines use device="cpu" explicitly in their model init.
# Do NOT set CUDA_VISIBLE_DEVICES — it poisons GPU access for MusicGen.

# Coqui TTS prompts for CPML (non-commercial) licence acceptance on first load.
# Server has no stdin, so the interactive input() call raises EOFError.
# Setting this env var before the TTS.api import auto-accepts the non-commercial
# licence. NOTE: CPML forbids commercial use — see https://coqui.ai/cpml
os.environ.setdefault("COQUI_TOS_AGREED", "1")

# Compatibility shim for transformers 5.x
#
# coqui-tts 0.27.5 declares `transformers>=4.57` but its code still imports
# `isin_mps_friendly` from `transformers.pytorch_utils`, a helper that was
# present in the 4.x line and removed in the 5.x rewrite. We're pinned to
# transformers 5.x system-wide (unsloth / Bark / Kokoro / MusicGen all use it),
# so downgrading is not an option. Instead we reinject the missing symbol as
# a thin wrapper over torch.isin. On CPU (which XTTS is forced onto) the MPS
# branch is never hit, so the wrapper is behaviourally identical to the 4.x
# original. If coqui-tts 0.28+ drops the import, this shim becomes a no-op.
try:
    import transformers.pytorch_utils as _tpu
    if not hasattr(_tpu, "isin_mps_friendly"):
        import torch as _torch

        def _isin_mps_friendly(elements, test_elements):
            # transformers 4.x implementation: torch.isin crashes on MPS for
            # some dtypes, so they fall back to broadcasting. We don't use MPS
            # here, but we keep the branch for parity.
            if elements.device.type == "mps":
                return (elements.unsqueeze(-1) == test_elements).any(dim=-1)
            return _torch.isin(elements, test_elements)

        _tpu.isin_mps_friendly = _isin_mps_friendly
except ImportError:
    # transformers not yet importable — the real import inside coqui-tts will
    # fail with a clearer error downstream.
    pass

VOICES_DIR = Path(__file__).parent.parent / "engines" / "xtts_voices"

# XTTS v2 ships 58 built-in speakers. Their embeddings live in speakers_xtts.pth
# inside the Coqui model cache. We read the speaker names at voices() time
# without loading the full model, so startup stays cheap.
_XTTS_SPEAKERS_PTH = (
    Path.home()
    / ".local" / "share" / "tts"
    / "tts_models--multilingual--multi-dataset--xtts_v2"
    / "speakers_xtts.pth"
)

# Cache the speaker list — reading the pth is cheap but not free, and voices()
# is called on every /api/tts/engines request.
_builtin_speakers_cache: list[str] | None = None


def _load_builtin_speakers() -> list[str]:
    """Return the list of XTTS v2 built-in speaker names, or [] if unavailable.

    The speakers pth only exists after the model has been downloaded at least
    once (happens on first generate() call). If missing, we return an empty
    list — the UI will fall back to clones only.
    """
    global _builtin_speakers_cache
    if _builtin_speakers_cache is not None:
        return _builtin_speakers_cache
    if not _XTTS_SPEAKERS_PTH.exists():
        return []
    try:
        import torch
        data = torch.load(str(_XTTS_SPEAKERS_PTH), weights_only=False, map_location="cpu")
        if isinstance(data, dict):
            _builtin_speakers_cache = sorted(data.keys())
            return _builtin_speakers_cache
    except Exception:
        pass
    return []


class XTTSEngine:
    name = "xtts"
    supports_cloning = True

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
        result = []

        # Built-in speakers — 58 of them once the model has been downloaded
        for speaker in _load_builtin_speakers():
            result.append({
                "id": speaker,
                "name": speaker,
                "language": "en",
                "gender": "builtin",
            })

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
