"""AudioGen backend - text-to-SFX/environmental-sound via Meta's audiocraft.

Sibling to :mod:`studio.music_gen`. Same library, same lifecycle, same
GPU footprint (~5 GB on facebook/audiogen-medium at fp16) - intentionally
mirrored so the operator can reason about both engines as one resource.

Differences from MusicGen:

* **One model only.** AudioGen ships a single medium-size variant
  (1.5B, ``facebook/audiogen-medium``); there is no -small / -large.
* **Single-shot generation.** AudioGen was trained on 10-second clips
  of environmental audio. The model can be coerced into longer outputs
  via ``generate_continuation``, but the natural unit is a discrete
  sound effect, so v1 caps duration at 10s and skips the continuation
  / loop paths from MusicGen. (Add them later if a user wants ambient
  beds rather than SFX.)
* **16 kHz mono.** AudioGen outputs at 16 kHz, MusicGen at 32 kHz.
  The wav-to-numpy path is identical (mono channel-0 take).
"""

from __future__ import annotations

import asyncio
import os


class SfxGenEngine:
    name = "sfxgen"

    # AudioGen ships exactly one model; expose it as a list anyway so the
    # API shape matches MusicGen and the UI can grow if a -large drops.
    MODELS = [
        {"id": "facebook/audiogen-medium", "name": "AudioGen Medium",
         "size": "medium", "params": "1.5B"},
    ]

    # SFX clips are short by nature; cap at the model's native training
    # window. Anything over 10 s starts to drift in quality.
    MAX_DURATION = 10.0

    def __init__(self, config: dict | None = None):
        self._model = None
        self._model_id: str | None = None
        self._device: str | None = None
        config = config or {}
        self.default_model = config.get("model", "facebook/audiogen-medium")

    def available(self) -> bool:
        """True iff audiocraft.models.AudioGen is importable.

        Cheap probe - imports the symbol but does not load weights.
        """
        try:
            from audiocraft.models import AudioGen  # noqa: F401
            return True
        except ImportError:
            return False

    def models(self) -> list[dict]:
        return [dict(m) for m in self.MODELS]

    def preload(self, model_id: str | None = None):
        """Load model on the main thread so the CUDA context is initialised.

        Mirror of MusicGenEngine.preload - the GPU claim endpoint calls
        this after freeing ComfyUI, so the first /api/sfx/generate doesn't
        pay the cold-load tax.
        """
        return self._get_model(model_id)

    def _get_model(self, model_id: str | None = None):
        model_id = model_id or self.default_model
        if self._model is None or self._model_id != model_id:
            import torch
            from audiocraft.models import AudioGen

            device = "cpu"
            if torch.cuda.is_available():
                free_vram_mb = torch.cuda.mem_get_info()[0] / 1024 ** 2
                # 1.5B params at fp16 ~= 3 GB weights + activations during
                # generation push to ~5 GB. Keep 1 GB headroom over that
                # to avoid the same OOM cliff musicgen-large hits.
                needed_mb = 6000
                if free_vram_mb > needed_mb:
                    device = "cuda"
                else:
                    print(f"[AudioGen] Only {free_vram_mb:.0f}MB free VRAM, "
                          f"need {needed_mb}MB - using CPU")

            print(f"[AudioGen] Loading {model_id} on {device}")
            self._model = AudioGen.get_pretrained(model_id, device=device)
            self._model_id = model_id
            self._device = device
        return self._model

    def _unload_model(self) -> None:
        """Release the model so ComfyUI / other workloads can use the GPU."""
        if self._model is not None:
            import torch
            del self._model
            self._model = None
            self._model_id = None
            self._device = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    async def generate(
        self,
        prompt: str,
        output_path: str,
        duration: float = 5.0,
        model_id: str | None = None,
    ) -> dict:
        """Generate an SFX clip from a text prompt. Returns metadata.

        Synchronous Torch work runs in a thread executor so the FastAPI
        event loop stays responsive while the model decodes. Same pattern
        as :class:`MusicGenEngine.generate`.
        """
        loop = asyncio.get_event_loop()
        duration = max(0.5, min(float(duration), self.MAX_DURATION))

        def _do() -> dict:
            import torch
            import soundfile as sf

            try:
                model = self._get_model(model_id)
            except torch.cuda.OutOfMemoryError:
                # CPU fallback - same recovery path MusicGen uses.
                print("[AudioGen] GPU OOM on load, falling back to CPU")
                self._unload_model()
                from audiocraft.models import AudioGen
                self._model = AudioGen.get_pretrained(
                    model_id or self.default_model, device="cpu")
                self._model_id = model_id or self.default_model
                self._device = "cpu"
                model = self._model
            except Exception as exc:
                raise RuntimeError(f"Failed to load AudioGen model: {exc}")

            sample_rate = model.sample_rate

            try:
                model.set_generation_params(duration=duration)
                with torch.no_grad():
                    wav = model.generate([prompt])
            except torch.cuda.OutOfMemoryError:
                # Generation-time OOM - reload on CPU and retry once. Same
                # belt-and-braces as MusicGen.
                print("[AudioGen] GPU OOM during generation, retrying on CPU")
                self._unload_model()
                from audiocraft.models import AudioGen
                self._model = AudioGen.get_pretrained(
                    model_id or self.default_model, device="cpu")
                self._model_id = model_id or self.default_model
                self._device = "cpu"
                model = self._model
                sample_rate = model.sample_rate
                model.set_generation_params(duration=duration)
                with torch.no_grad():
                    wav = model.generate([prompt])

            audio = self._wav_to_numpy(wav[0])
            sf.write(output_path, audio, sample_rate)

            return {
                "duration": round(len(audio) / sample_rate, 2),
                "sample_rate": sample_rate,
                "file_size": os.path.getsize(output_path),
                "model": self._model_id or self.default_model,
                "mode": "single",
            }

        return await loop.run_in_executor(None, _do)

    @staticmethod
    def _wav_to_numpy(wav_tensor):
        """Convert (channels, samples) tensor to mono 1-D numpy.

        AudioGen returns 1-channel output by default; this is the same
        path MusicGen uses (defensive against stereo).
        """
        audio = wav_tensor.cpu().numpy()
        if audio.ndim == 2:
            if audio.shape[0] <= 2:
                audio = audio[0]
            else:
                audio = audio.mean(axis=-1)
        return audio.flatten()
