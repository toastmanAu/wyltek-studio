"""MusicGen backend — text-to-music generation via Meta's audiocraft."""

import asyncio
import os
from pathlib import Path

# Force CPU to avoid GPU contention with ComfyUI
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")


class MusicGenEngine:
    name = "musicgen"

    MODELS = [
        {"id": "facebook/musicgen-small", "name": "MusicGen Small (300M)", "size": "small", "params": "300M"},
        {"id": "facebook/musicgen-medium", "name": "MusicGen Medium (1.5B)", "size": "medium", "params": "1.5B"},
    ]

    MODES = [
        {"id": "single", "name": "Single (up to 30s)", "desc": "One continuous generation."},
        {"id": "continuation", "name": "Continuation (up to 180s)", "desc": "Chains segments using the end of each as a seed for the next. Natural progression."},
        {"id": "loop", "name": "Seamless Loop (up to 180s)", "desc": "Crossfades end into beginning for a seamless repeating track."},
    ]

    CHUNK_DURATION = 30  # seconds per generation chunk
    OVERLAP = 3  # seconds of overlap for crossfade / continuation seed

    def __init__(self, config: dict = None):
        self._model = None
        self._model_id = None
        config = config or {}
        self.default_model = config.get("model", "facebook/musicgen-small")

    def available(self) -> bool:
        try:
            import audiocraft  # noqa: F401
            return True
        except ImportError:
            return False

    def models(self) -> list[dict]:
        return [dict(m) for m in self.MODELS]

    def modes(self) -> list[dict]:
        return [dict(m) for m in self.MODES]

    def _get_model(self, model_id: str = None):
        model_id = model_id or self.default_model
        if self._model is None or self._model_id != model_id:
            from audiocraft.models import MusicGen
            self._model = MusicGen.get_pretrained(model_id)
            self._model_id = model_id
        return self._model

    async def generate(self, prompt: str, output_path: str,
                       duration: float = 15.0, model_id: str = None,
                       mode: str = "single") -> dict:
        """Generate music from text prompt. Returns metadata."""
        loop = asyncio.get_event_loop()

        def _do():
            import torch
            import numpy as np
            import soundfile as sf

            model = self._get_model(model_id)
            sample_rate = model.sample_rate

            if mode == "single" or duration <= self.CHUNK_DURATION:
                return self._generate_single(model, prompt, output_path,
                                             min(duration, self.CHUNK_DURATION), sample_rate)
            elif mode == "continuation":
                return self._generate_continuation(model, prompt, output_path,
                                                   duration, sample_rate)
            elif mode == "loop":
                return self._generate_loop(model, prompt, output_path,
                                           duration, sample_rate)
            else:
                return self._generate_single(model, prompt, output_path,
                                             min(duration, self.CHUNK_DURATION), sample_rate)

        return await loop.run_in_executor(None, _do)

    def _generate_single(self, model, prompt, output_path, duration, sample_rate):
        """Standard single-chunk generation."""
        import torch
        import soundfile as sf

        model.set_generation_params(duration=duration)
        with torch.no_grad():
            wav = model.generate([prompt])

        audio = self._wav_to_numpy(wav[0])
        sf.write(output_path, audio, sample_rate)
        return self._make_result(audio, sample_rate, output_path, "single")

    def _generate_continuation(self, model, prompt, output_path, duration, sample_rate):
        """Chain segments — each chunk seeds from the tail of the previous."""
        import torch
        import numpy as np
        import soundfile as sf

        chunks = []
        remaining = duration
        prev_wav = None

        while remaining > 0:
            chunk_dur = min(self.CHUNK_DURATION, remaining + self.OVERLAP)
            model.set_generation_params(duration=chunk_dur)

            with torch.no_grad():
                if prev_wav is None:
                    wav = model.generate([prompt])
                else:
                    # Use last OVERLAP seconds as conditioning for next chunk
                    seed_samples = int(self.OVERLAP * sample_rate)
                    seed = prev_wav[:, -seed_samples:].unsqueeze(0)
                    wav = model.generate_continuation(
                        seed, sample_rate, [prompt]
                    )

            prev_wav = wav[0]
            audio_chunk = self._wav_to_numpy(wav[0])

            if chunks:
                # Crossfade with previous chunk
                audio_chunk = self._crossfade(chunks[-1], audio_chunk,
                                              self.OVERLAP, sample_rate)
                chunks[-1] = audio_chunk
            else:
                chunks.append(audio_chunk)

            remaining -= (self.CHUNK_DURATION - self.OVERLAP)

        full_audio = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
        # Trim to exact requested duration
        max_samples = int(duration * sample_rate)
        full_audio = full_audio[:max_samples]

        sf.write(output_path, full_audio, sample_rate)
        return self._make_result(full_audio, sample_rate, output_path, "continuation")

    def _generate_loop(self, model, prompt, output_path, duration, sample_rate):
        """Generate a seamless loop — crossfade end back into beginning."""
        import torch
        import numpy as np
        import soundfile as sf

        # Generate base segment (up to 30s)
        base_dur = min(self.CHUNK_DURATION, duration)
        model.set_generation_params(duration=base_dur)

        with torch.no_grad():
            wav = model.generate([prompt])

        base_audio = self._wav_to_numpy(wav[0])

        # Create seamless loop by crossfading tail into head
        fade_samples = int(self.OVERLAP * sample_rate)
        if len(base_audio) > fade_samples * 2:
            # Fade out tail, fade in head
            tail = base_audio[-fade_samples:]
            head = base_audio[:fade_samples]
            fade_in = np.linspace(0, 1, fade_samples)
            fade_out = np.linspace(1, 0, fade_samples)
            crossfaded = tail * fade_out + head * fade_in

            # Build the loop body (without the faded portions)
            loop_body = base_audio[fade_samples:-fade_samples]
            one_loop = np.concatenate([crossfaded, loop_body])
        else:
            one_loop = base_audio

        # Tile to fill requested duration
        loop_samples = int(duration * sample_rate)
        if len(one_loop) > 0:
            repeats = (loop_samples // len(one_loop)) + 1
            full_audio = np.tile(one_loop, repeats)[:loop_samples]
        else:
            full_audio = base_audio

        sf.write(output_path, full_audio, sample_rate)
        return self._make_result(full_audio, sample_rate, output_path, "loop")

    def _wav_to_numpy(self, wav_tensor):
        """Convert model output tensor to numpy array for soundfile.
        MusicGen returns (channels, samples) — we need 1D mono."""
        audio = wav_tensor.cpu().numpy()
        if audio.ndim == 2:
            # Mono: take first channel. Stereo: mix down.
            if audio.shape[0] <= 2:
                audio = audio[0]  # first channel (mono from MusicGen)
            else:
                audio = audio.mean(axis=-1)  # shouldn't happen but safe
        audio = audio.flatten()
        return audio

    def _crossfade(self, chunk_a, chunk_b, overlap_sec, sample_rate):
        """Crossfade two audio chunks."""
        import numpy as np
        fade_samples = int(overlap_sec * sample_rate)
        fade_samples = min(fade_samples, len(chunk_a), len(chunk_b))

        fade_out = np.linspace(1, 0, fade_samples)
        fade_in = np.linspace(0, 1, fade_samples)

        # Mix the overlapping region
        chunk_a_tail = chunk_a[-fade_samples:] * fade_out
        chunk_b_head = chunk_b[:fade_samples] * fade_in
        mixed = chunk_a_tail + chunk_b_head

        return np.concatenate([chunk_a[:-fade_samples], mixed, chunk_b[fade_samples:]])

    def _make_result(self, audio, sample_rate, output_path, mode):
        import os
        actual_duration = len(audio) / sample_rate if audio.ndim == 1 else audio.shape[0] / sample_rate
        return {
            "duration": round(actual_duration, 2),
            "sample_rate": sample_rate,
            "file_size": os.path.getsize(output_path),
            "model": self._model_id or self.default_model,
            "mode": mode,
        }
