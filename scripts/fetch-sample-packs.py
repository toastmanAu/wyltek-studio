#!/usr/bin/env python3
"""
Generate synthesized sample packs for Wyltek Studio beat builder.

Creates 3 genre packs (hip-hop-kit, lo-fi-kit, electronic-kit) plus an empty user pack.
Each pack contains 8 normalised WAV samples and a pack.json descriptor.
"""

import json
import math
import os
import random
import struct
import wave
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SAMPLE_RATE = 44100
TARGET_DBFS = -14.0
DATA_DIR = Path(__file__).parent.parent / "data" / "sample-packs"

# ---------------------------------------------------------------------------
# Low-level audio helpers (no external deps beyond stdlib)
# ---------------------------------------------------------------------------


def make_silent(num_samples: int) -> list[float]:
    return [0.0] * num_samples


def sine_wave(freq: float, duration_s: float, amplitude: float = 1.0) -> list[float]:
    n = int(SAMPLE_RATE * duration_s)
    return [amplitude * math.sin(2 * math.pi * freq * i / SAMPLE_RATE) for i in range(n)]


def white_noise(duration_s: float, amplitude: float = 1.0) -> list[float]:
    n = int(SAMPLE_RATE * duration_s)
    return [amplitude * (random.random() * 2 - 1) for _ in range(n)]


def apply_envelope(samples: list[float], attack_s: float = 0.002, release_s: float = 0.01) -> list[float]:
    """Apply a simple linear attack and exponential release envelope."""
    n = len(samples)
    attack_n = int(SAMPLE_RATE * attack_s)
    release_n = int(SAMPLE_RATE * release_s)
    result = list(samples)
    for i in range(min(attack_n, n)):
        result[i] *= i / attack_n
    for i in range(min(release_n, n)):
        idx = n - release_n + i
        if idx >= 0:
            result[idx] *= (release_n - i) / release_n
    return result


def exponential_decay(samples: list[float], decay_s: float) -> list[float]:
    """Apply exponential decay over the entire buffer."""
    n = len(samples)
    result = []
    for i, s in enumerate(samples):
        env = math.exp(-5.0 * i / max(1, int(SAMPLE_RATE * decay_s)))
        result.append(s * env)
    return result


def mix(a: list[float], b: list[float]) -> list[float]:
    length = max(len(a), len(b))
    result = [0.0] * length
    for i, v in enumerate(a):
        result[i] += v
    for i, v in enumerate(b):
        result[i] += v
    return result


def fade_in(samples: list[float], fade_s: float) -> list[float]:
    fade_n = int(SAMPLE_RATE * fade_s)
    result = list(samples)
    for i in range(min(fade_n, len(result))):
        result[i] *= i / fade_n
    return result


def fade_out(samples: list[float], fade_s: float) -> list[float]:
    fade_n = int(SAMPLE_RATE * fade_s)
    result = list(samples)
    for i in range(min(fade_n, len(result))):
        idx = len(result) - fade_n + i
        if idx >= 0:
            result[idx] *= i / fade_n
    return result


def normalise(samples: list[float], target_dbfs: float = TARGET_DBFS) -> list[float]:
    """Normalise peak amplitude to target_dbfs."""
    peak = max(abs(s) for s in samples) if samples else 1.0
    if peak == 0:
        return samples
    target_amplitude = 10 ** (target_dbfs / 20.0)
    scale = target_amplitude / peak
    return [s * scale for s in samples]


def write_wav(path: Path, samples: list[float]) -> None:
    """Write a mono 16-bit WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    int_samples = []
    for s in samples:
        clamped = max(-1.0, min(1.0, s))
        int_samples.append(int(clamped * 32767))
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(struct.pack(f"<{len(int_samples)}h", *int_samples))


# ---------------------------------------------------------------------------
# Sample synthesis functions
# ---------------------------------------------------------------------------


def make_kick() -> list[float]:
    """Sine sweep 150 Hz → 40 Hz with exponential decay (~200 ms)."""
    duration = 0.200
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        # Exponential frequency sweep
        freq = 150.0 * math.exp(-math.log(150.0 / 40.0) * t / duration)
        phase = 2 * math.pi * freq * t
        env = math.exp(-8.0 * t / duration)
        samples.append(math.sin(phase) * env)
    return normalise(samples)


def make_snare() -> list[float]:
    """White noise burst + 200 Hz tone, faded (~150 ms)."""
    duration = 0.150
    noise = white_noise(duration, 0.7)
    tone = sine_wave(200, duration, 0.3)
    mixed = mix(noise, tone)
    decayed = exponential_decay(mixed, duration * 0.8)
    enveloped = apply_envelope(decayed, attack_s=0.001, release_s=0.020)
    return normalise(enveloped)


def make_hihat() -> list[float]:
    """Short noise burst (~80 ms)."""
    duration = 0.080
    noise = white_noise(duration, 1.0)
    decayed = exponential_decay(noise, duration * 0.5)
    enveloped = apply_envelope(decayed, attack_s=0.001, release_s=0.010)
    return normalise(enveloped)


def make_openhat() -> list[float]:
    """Longer noise burst (~300 ms)."""
    duration = 0.300
    noise = white_noise(duration, 1.0)
    decayed = exponential_decay(noise, duration * 0.7)
    enveloped = apply_envelope(decayed, attack_s=0.002, release_s=0.050)
    return normalise(enveloped)


def make_bass(bpm: float) -> list[float]:
    """2-bar loop at pack BPM, 55 Hz sine on beats 1 and 3."""
    beat_s = 60.0 / bpm
    bar_s = beat_s * 4
    loop_s = bar_s * 2
    n = int(SAMPLE_RATE * loop_s)
    samples = [0.0] * n

    beat_duration = beat_s * 0.9  # note length slightly shorter than beat

    for bar in range(2):
        for beat_in_bar in [0, 2]:  # beats 1 and 3
            beat_offset = int((bar * bar_s + beat_in_bar * beat_s) * SAMPLE_RATE)
            note_n = int(beat_duration * SAMPLE_RATE)
            for i in range(note_n):
                if beat_offset + i >= n:
                    break
                t = i / SAMPLE_RATE
                env = math.exp(-3.0 * t / beat_duration)
                samples[beat_offset + i] += math.sin(2 * math.pi * 55 * t) * env

    return normalise(samples)


def make_melody(bpm: float) -> list[float]:
    """2-bar loop at pack BPM, 4 ascending sine tones."""
    beat_s = 60.0 / bpm
    bar_s = beat_s * 4
    loop_s = bar_s * 2
    n = int(SAMPLE_RATE * loop_s)
    samples = [0.0] * n

    # C4 pentatonic: C4, D4, E4, G4
    freqs = [261.63, 293.66, 329.63, 392.00]
    note_dur = beat_s * 0.85

    for i, freq in enumerate(freqs):
        note_offset = int(i * beat_s * SAMPLE_RATE)
        note_n = int(note_dur * SAMPLE_RATE)
        for j in range(note_n):
            if note_offset + j >= n:
                break
            t = j / SAMPLE_RATE
            env = math.exp(-2.0 * t / note_dur)
            samples[note_offset + j] += math.sin(2 * math.pi * freq * t) * 0.5 * env

    # Second bar: same pattern an octave up
    for i, freq in enumerate(freqs):
        note_offset = int((bar_s + i * beat_s) * SAMPLE_RATE)
        note_n = int(note_dur * SAMPLE_RATE)
        for j in range(note_n):
            if note_offset + j >= n:
                break
            t = j / SAMPLE_RATE
            env = math.exp(-2.0 * t / note_dur)
            samples[note_offset + j] += math.sin(2 * math.pi * freq * 2 * t) * 0.5 * env

    return normalise(samples)


def make_pad(bpm: float) -> list[float]:
    """4-bar sustained sine with slow fade in/out."""
    beat_s = 60.0 / bpm
    bar_s = beat_s * 4
    loop_s = bar_s * 4
    # Root note: A3 = 220 Hz, with slight detune for warmth
    freqs = [220.0, 220.0 * 1.005, 330.0]  # root + slight detune + fifth
    n = int(SAMPLE_RATE * loop_s)
    samples = [0.0] * n

    for freq in freqs:
        for i in range(n):
            t = i / SAMPLE_RATE
            samples[i] += math.sin(2 * math.pi * freq * t) * (1.0 / len(freqs))

    samples = fade_in(samples, loop_s * 0.2)
    samples = fade_out(samples, loop_s * 0.2)
    return normalise(samples)


def make_fx() -> list[float]:
    """Ascending frequency sweep (~500 ms)."""
    duration = 0.500
    n = int(SAMPLE_RATE * duration)
    samples = []
    for i in range(n):
        t = i / SAMPLE_RATE
        freq = 200.0 + (2000.0 - 200.0) * (t / duration) ** 2
        env = math.sin(math.pi * t / duration)  # half-sine envelope
        samples.append(math.sin(2 * math.pi * freq * t) * env)
    return normalise(samples)


# ---------------------------------------------------------------------------
# Pack definitions
# ---------------------------------------------------------------------------

PACKS = [
    {
        "dir": "hip-hop-kit",
        "name": "Hip-Hop Kit",
        "description": "Boom bap drums, deep bass, and soulful melodies for classic hip-hop production.",
        "bpm": 90,
        "bpm_range": [80, 100],
        "genre_tags": ["hip-hop", "boom-bap", "rap"],
    },
    {
        "dir": "lo-fi-kit",
        "name": "Lo-Fi Kit",
        "description": "Dusty drums, warm bass, and jazzy chords for chill lo-fi beats.",
        "bpm": 80,
        "bpm_range": [70, 90],
        "genre_tags": ["lo-fi", "chill", "jazzy"],
    },
    {
        "dir": "electronic-kit",
        "name": "Electronic Kit",
        "description": "Punchy drums, synth bass, and arpeggiated melodies for house and techno.",
        "bpm": 128,
        "bpm_range": [120, 140],
        "genre_tags": ["house", "techno", "electronic"],
    },
]


def build_pack(pack_def: dict) -> None:
    pack_dir = DATA_DIR / pack_def["dir"]
    pack_dir.mkdir(parents=True, exist_ok=True)
    bpm = pack_def["bpm"]

    print(f"  Generating {pack_def['name']} ({bpm} BPM)...")

    samples = {
        "kick":    (make_kick(),         "oneshot"),
        "snare":   (make_snare(),        "oneshot"),
        "hihat":   (make_hihat(),        "oneshot"),
        "openhat": (make_openhat(),      "oneshot"),
        "bass":    (make_bass(bpm),      "loop"),
        "melody":  (make_melody(bpm),    "loop"),
        "pad":     (make_pad(bpm),       "loop"),
        "fx":      (make_fx(),           "oneshot"),
    }

    pack_json_samples = {}
    for name, (data, sample_type) in samples.items():
        filename = f"{name}.wav"
        write_wav(pack_dir / filename, data)
        pack_json_samples[name] = {"file": filename, "type": sample_type}
        print(f"    wrote {filename} ({len(data)} samples)")

    pack_json = {
        "name": pack_def["name"],
        "description": pack_def["description"],
        "bpm_range": pack_def["bpm_range"],
        "genre_tags": pack_def["genre_tags"],
        "samples": pack_json_samples,
    }

    with open(pack_dir / "pack.json", "w") as f:
        json.dump(pack_json, f, indent=2)
    print(f"    wrote pack.json")


def build_user_pack() -> None:
    pack_dir = DATA_DIR / "user"
    pack_dir.mkdir(parents=True, exist_ok=True)

    pack_json = {
        "name": "User Pack",
        "description": "Your personal sample collection. Drop WAV files here and update this file.",
        "bpm_range": [60, 200],
        "genre_tags": [],
        "samples": {},
    }

    with open(pack_dir / "pack.json", "w") as f:
        json.dump(pack_json, f, indent=2)
    print("  wrote user/pack.json (empty pack)")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    print(f"Generating sample packs in {DATA_DIR}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    for pack_def in PACKS:
        build_pack(pack_def)

    print("Building empty user pack...")
    build_user_pack()

    print("\nDone. Pack summary:")
    for entry in sorted(DATA_DIR.iterdir()):
        if entry.is_dir():
            wavs = list(entry.glob("*.wav"))
            print(f"  {entry.name}/  ({len(wavs)} WAV files)")


if __name__ == "__main__":
    main()
