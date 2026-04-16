"""MusicGen backend — text-to-music generation via Meta's audiocraft."""

import asyncio
import os
from pathlib import Path


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

    def preload(self, model_id: str = None):
        """Load model on the main thread so CUDA context is initialized.

        Call this once at startup — worker threads will then reuse the
        model and its CUDA context without needing to re-init.
        """
        return self._get_model(model_id)

    def _get_model(self, model_id: str = None):
        model_id = model_id or self.default_model
        if self._model is None or self._model_id != model_id:
            import torch
            from audiocraft.models import MusicGen
            device = "cpu"
            if torch.cuda.is_available():
                free_vram = torch.cuda.mem_get_info()[0] / 1024**2
                mid = model_id or ""
                if "melody" in mid:
                    needed = 6000
                elif "medium" in mid:
                    needed = 4000
                else:
                    needed = 1500
                if free_vram > needed:
                    device = "cuda"
                else:
                    print(f"[MusicGen] Only {free_vram:.0f}MB free VRAM, need {needed}MB — using CPU")
            print(f"[MusicGen] Loading {model_id} on {device}")
            self._model = MusicGen.get_pretrained(model_id, device=device)
            self._model_id = model_id
            self._device = device
        return self._model

    def _unload_model(self):
        """Free GPU VRAM after generation so ComfyUI can use it."""
        if self._model is not None:
            import torch
            del self._model
            self._model = None
            self._model_id = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    async def generate(self, prompt: str, output_path: str,
                       duration: float = 15.0, model_id: str = None,
                       mode: str = "single") -> dict:
        """Generate music from text prompt. Returns metadata."""
        loop = asyncio.get_event_loop()

        def _do():
            import torch
            import numpy as np
            import soundfile as sf

            try:
                model = self._get_model(model_id)
            except torch.cuda.OutOfMemoryError:
                # GPU OOM on load — fall back to CPU
                print("[MusicGen] GPU OOM on load, falling back to CPU")
                self._unload_model()
                from audiocraft.models import MusicGen
                self._model = MusicGen.get_pretrained(model_id or self.default_model, device="cpu")
                self._model_id = model_id or self.default_model
                self._device = "cpu"
                model = self._model
            except Exception as e:
                raise RuntimeError(f"Failed to load MusicGen model: {e}")

            sample_rate = model.sample_rate

            try:
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
            except torch.cuda.OutOfMemoryError:
                # GPU OOM during generation — reload on CPU and retry
                print("[MusicGen] GPU OOM during generation, retrying on CPU")
                self._unload_model()
                from audiocraft.models import MusicGen
                self._model = MusicGen.get_pretrained(model_id or self.default_model, device="cpu")
                self._model_id = model_id or self.default_model
                self._device = "cpu"
                model = self._model
                sample_rate = model.sample_rate
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
        """Chain segments — each chunk seeds from the tail of the previous.

        Memory-efficient: only keeps the seed tensor on GPU (3s of audio),
        accumulates output as a single numpy buffer on CPU.
        """
        import torch
        import numpy as np
        import soundfile as sf

        overlap_samples = int(self.OVERLAP * sample_rate)
        max_samples = int(duration * sample_rate)

        # Pre-allocate output buffer
        result = np.zeros(max_samples, dtype=np.float32)
        write_pos = 0
        remaining = duration
        seed_tensor = None  # small GPU tensor — only OVERLAP seconds
        chunk_num = 0

        while remaining > 0 and write_pos < max_samples:
            chunk_dur = min(self.CHUNK_DURATION, remaining)
            model.set_generation_params(duration=chunk_dur)
            chunk_num += 1
            print(f"[MusicGen] Continuation chunk {chunk_num}, {chunk_dur:.0f}s, {remaining:.0f}s remaining")

            with torch.no_grad():
                if seed_tensor is None:
                    wav = model.generate([prompt])
                else:
                    wav = model.generate_continuation(
                        seed_tensor, sample_rate, [prompt]
                    )

            # Extract seed for next chunk (small slice, stays on GPU)
            seed_tensor = wav[0, :, -int(self.OVERLAP * sample_rate):].unsqueeze(0)

            # Move audio to CPU numpy immediately, free GPU tensor
            audio_chunk = self._wav_to_numpy(wav[0])
            del wav
            torch.cuda.empty_cache()

            if write_pos == 0:
                # First chunk — write directly
                n = min(len(audio_chunk), max_samples)
                result[:n] = audio_chunk[:n]
                write_pos = n
            else:
                # Crossfade with existing tail
                xfade_len = min(overlap_samples, write_pos, len(audio_chunk))
                fade_out = np.linspace(1, 0, xfade_len, dtype=np.float32)
                fade_in = np.linspace(0, 1, xfade_len, dtype=np.float32)

                # Blend overlap region in-place
                xfade_start = write_pos - xfade_len
                result[xfade_start:write_pos] *= fade_out
                result[xfade_start:write_pos] += audio_chunk[:xfade_len] * fade_in

                # Append remainder
                new_audio = audio_chunk[xfade_len:]
                n = min(len(new_audio), max_samples - write_pos)
                result[write_pos:write_pos + n] = new_audio[:n]
                write_pos += n

            del audio_chunk
            remaining -= chunk_dur

        # Trim to actual written length
        result = result[:write_pos]

        # Clean up seed tensor
        del seed_tensor
        torch.cuda.empty_cache()

        sf.write(output_path, result, sample_rate)
        return self._make_result(result, sample_rate, output_path, "continuation")

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
        del wav
        torch.cuda.empty_cache()

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
