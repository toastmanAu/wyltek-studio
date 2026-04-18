#!/usr/bin/env python3
"""LoRA strength sweep — find the sweet spot for each style LoRA.

For a single subject + OP model, runs the matrix:
    strength tiers × LoRAs                     (default: 4 × 6 = 24 images)
or with --with-trigger-ab:
    strength × LoRA × {trigger-off, trigger-on}  (48 images)

Output format matches `lora_matrix_test.py` exactly, so `matrix_gallery.py`
renders it without changes — rows become strength tiers instead of OP models.

Usage:
    # Basic sweep: 4 strengths × 6 LoRAs, 24 images
    python scripts/lora_strength_sweep.py "a pokemon style Cat"

    # Custom strength tiers (model-strength/clip-strength pairs)
    python scripts/lora_strength_sweep.py "a knight" \\
        --strengths "0.6/0.3,0.8/0.5,1.0/0.7,1.2/0.9"

    # Add the trigger A/B axis: 4 × 6 × 2 = 48 images
    python scripts/lora_strength_sweep.py "a cat" --with-trigger-ab

    # Override OP model or base (defaults: gemma4:latest + juggernaut full)
    python scripts/lora_strength_sweep.py "a wizard" \\
        --op-model qwen3.5:35b-a3b --base-model sdxl_base_1.0-Q4_0.gguf
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

import httpx

# Re-use the existing matrix test's helpers so we don't duplicate HTTP/polling logic.
sys.path.insert(0, str(Path(__file__).parent))
from lora_matrix_test import (  # type: ignore
    OLLAMA, SERVER,
    enhance_prompt, poll_until_done, find_image_path, slugify, lora_label,
)

# Import trigger registry so --with-trigger-ab knows what to append per LoRA.
sys.path.insert(0, str(Path(__file__).parent.parent))
from model_catalog import LORA_TRIGGERS  # type: ignore


# --------------------------------------------------------------------------- #
# Config                                                                      #
# --------------------------------------------------------------------------- #

DEFAULT_OP_MODEL = "gemma4:latest"
DEFAULT_BASE_MODEL = "juggernautXL_v9.safetensors"
DEFAULT_SEED = 42
DEFAULT_STEPS = 30
DEFAULT_CFG = 7.0
DEFAULT_W = 1024
DEFAULT_H = 1024

# (model_strength, clip_strength). Bracket the useful range: tame / current /
# standard / strong. If 0.6/0.3 shows nothing and 1.2/0.9 burns out, we've
# found the LoRA's useful window.
DEFAULT_STRENGTHS: list[tuple[float, float]] = [
    (0.6, 0.3),
    (0.8, 0.5),
    (1.0, 0.7),
    (1.2, 0.9),
]

STYLE_LORAS: list[str] = [
    "pixel-art-xl.safetensors",
    "voxel-xl.safetensors",
    "crayon-style-xl.safetensors",
    "watercolor-xl.safetensors",
    "sticker-style-xl.safetensors",
    "anime-detailer-xl.safetensors",
]


@dataclass
class SweepConfig:
    base_model: str = DEFAULT_BASE_MODEL
    seed: int = DEFAULT_SEED
    steps: int = DEFAULT_STEPS
    cfg: float = DEFAULT_CFG
    width: int = DEFAULT_W
    height: int = DEFAULT_H
    op_model: str = DEFAULT_OP_MODEL
    strengths: list[tuple[float, float]] = field(
        default_factory=lambda: list(DEFAULT_STRENGTHS))
    style_loras: list[str] = field(default_factory=lambda: list(STYLE_LORAS))
    with_trigger_ab: bool = False


def strength_label(ms: float, cs: float, trigger_on: bool | None = None) -> str:
    """Human-readable tier name used as the 'OP model' row label so the
    existing gallery treats it as a legitimate axis value."""
    base = f"m={ms:.2f}/c={cs:.2f}"
    if trigger_on is None:
        return base
    return base + (" +trigger" if trigger_on else " −trigger")


def add_trigger(prompt: str, lora: str) -> str:
    """Manually append the LoRA's canonical trigger — used by --with-trigger-ab
    so we can test the trigger effect even if the server's auto-injector isn't
    live. Returns the prompt unchanged if the LoRA has no registered trigger."""
    triggers = LORA_TRIGGERS.get(lora, [])
    if not triggers:
        return prompt
    return f"{prompt}, {triggers[0]}" if prompt else triggers[0]


# --------------------------------------------------------------------------- #
# Submission                                                                  #
# --------------------------------------------------------------------------- #


async def submit_with_strength(
    client: httpx.AsyncClient, cfg: SweepConfig,
    prompt: str, negative: str, lora: str, ms: float, cs: float,
) -> str:
    """Send one gen to the server with explicit per-call strengths."""
    form = {
        "prompt": prompt,
        "negative_prompt": negative,
        "backend": "comfyui",
        "model": cfg.base_model,
        "width": str(cfg.width),
        "height": str(cfg.height),
        "steps": str(cfg.steps),
        "cfg_scale": str(cfg.cfg),
        "seed": str(cfg.seed),
        "lora_model": lora,
        "lora_strength": str(ms),
        "lora_strength_model": str(ms),
        "lora_strength_clip": str(cs),
    }
    resp = await client.post(f"{SERVER}/api/generate", data=form, timeout=30)
    resp.raise_for_status()
    return resp.json()["job_id"]


# --------------------------------------------------------------------------- #
# Orchestration                                                               #
# --------------------------------------------------------------------------- #


async def run_sweep(
    client: httpx.AsyncClient, cfg: SweepConfig, seed_prompt: str,
) -> tuple[dict, list[dict]]:
    """Returns (enhancement_record, list_of_gen_result_dicts) in the same shape
    as lora_matrix_test so matrix_gallery.py can render it unchanged."""
    print(f"\n=== Sweep on: {seed_prompt!r} ===")
    print(f"Base: {cfg.base_model} · OP: {cfg.op_model} · "
          f"{len(cfg.strengths)} strength tiers × {len(cfg.style_loras)} LoRAs"
          + (" × 2 trigger states" if cfg.with_trigger_ab else ""))

    # Enhance once — sweep uses a single OP model.
    print(f"\n-- Enhancing with {cfg.op_model} --")
    enh = await enhance_prompt(client, cfg.op_model, cfg.base_model, seed_prompt)
    print(f"  {'ok' if enh.ok else 'FAIL'} ({enh.latency_s:.1f}s, "
          f"{len(enh.enhanced_prompt.split())} words)")
    if not enh.ok:
        print(f"  enhancement failed — falling back to raw seed")

    base_prompt = enh.enhanced_prompt if enh.ok else seed_prompt
    negative = enh.negative_prompt if enh.ok else ""

    # Build cells.
    print(f"\n-- Generating images --")
    results: list[dict] = []
    for ms, cs in cfg.strengths:
        trigger_states: list[bool | None] = (
            [False, True] if cfg.with_trigger_ab else [None]
        )
        for trigger_on in trigger_states:
            row_label = strength_label(ms, cs, trigger_on)
            for lora in cfg.style_loras:
                effective = add_trigger(base_prompt, lora) if trigger_on else base_prompt
                cell_label = f"{row_label}+{lora_label(lora)}"
                print(f"  [{cell_label}] submitting...")
                try:
                    job_id = await submit_with_strength(
                        client, cfg, effective, negative, lora, ms, cs,
                    )
                except httpx.HTTPError as exc:
                    results.append({
                        "label": cell_label, "prompt": effective, "negative": negative,
                        "lora": lora, "op_model": row_label,
                        "job_id": "", "status": "error", "duration_s": 0.0,
                        "image_path": "", "error": str(exc),
                    })
                    continue
                poll = await poll_until_done(client, job_id)
                status = poll.get("status", "unknown")
                dt = poll.get("_duration_s", 0.0)
                image_path = find_image_path(job_id) if status == "complete" else ""
                print(f"  [{cell_label}] {status} in {dt:.1f}s → "
                      f"{image_path or '(no file)'}")
                results.append({
                    "label": cell_label, "prompt": effective, "negative": negative,
                    "lora": lora, "op_model": row_label,  # row identifier for gallery
                    "job_id": job_id, "status": status, "duration_s": dt,
                    "image_path": image_path,
                    "error": poll.get("error", "") if status == "error" else "",
                })

    return asdict(enh), results


# --------------------------------------------------------------------------- #
# Report                                                                      #
# --------------------------------------------------------------------------- #


def write_report(run_dir: Path, seed_prompt: str, cfg: SweepConfig,
                 enhancement: dict, results: list[dict]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)

    # The gallery script keys off `config.op_models` and `config.style_loras`.
    # We shoehorn strength tiers into the op_models slot so no gallery change
    # is needed. Row labels follow strength_label() so they read naturally.
    row_order: list[str] = []
    for ms, cs in cfg.strengths:
        if cfg.with_trigger_ab:
            row_order.append(strength_label(ms, cs, False))
            row_order.append(strength_label(ms, cs, True))
        else:
            row_order.append(strength_label(ms, cs))

    gallery_config = {
        "base_model": cfg.base_model,
        "seed": cfg.seed,
        "steps": cfg.steps,
        "cfg": cfg.cfg,
        "width": cfg.width,
        "height": cfg.height,
        # Gallery's per-row "OP model" column becomes our strength tier labels.
        "op_models": row_order,
        "style_loras": cfg.style_loras,
        # These fields are for the human-readable report only, ignored by gallery.
        "sweep_type": "strength-sweep",
        "sweep_op_model": cfg.op_model,
        "strengths": [list(s) for s in cfg.strengths],
        "with_trigger_ab": cfg.with_trigger_ab,
        # Kept for gallery's header display; represents the "baseline" strength.
        "lora_strength_model": cfg.strengths[0][0],
        "lora_strength_clip": cfg.strengths[0][1],
    }

    # The gallery also expects an `enhancements` list keyed by `model` (which
    # in sweep-land is the row label). We synthesise one entry per row that
    # carries the enhancement info, so the row header still shows useful meta.
    synthesised_enhancements = []
    for row in row_order:
        synthesised_enhancements.append({
            "model": row,
            "enhanced_prompt": enhancement["enhanced_prompt"],
            "negative_prompt": enhancement["negative_prompt"],
            "changes_made": enhancement["changes_made"],
            "latency_s": enhancement["latency_s"],
            "ok": enhancement["ok"],
            "raw_response": enhancement.get("raw_response", ""),
        })

    payload = {
        "generated_at": datetime.now().isoformat(),
        "seed_prompt": seed_prompt,
        "config": gallery_config,
        "enhancements": synthesised_enhancements,
        "results": results,
    }
    (run_dir / "results.json").write_text(json.dumps(payload, indent=2))

    # Human-readable markdown
    lines: list[str] = []
    a = lines.append
    a(f"# LoRA Strength Sweep — `{seed_prompt}`")
    a("")
    a(f"- **Generated:** {datetime.now().isoformat(timespec='seconds')}")
    a(f"- **Base image model:** `{cfg.base_model}`")
    a(f"- **OP model (single):** `{cfg.op_model}`")
    a(f"- **Seed / steps / cfg:** `{cfg.seed}` / `{cfg.steps}` / `{cfg.cfg}`")
    a(f"- **Strength tiers:** " + ", ".join(
        f"`m={ms:.2f}/c={cs:.2f}`" for ms, cs in cfg.strengths))
    a(f"- **Trigger A/B axis:** {'yes' if cfg.with_trigger_ab else 'no'}")
    a("")
    a(f"## Enhanced prompt (used for every cell)")
    a("")
    a(f"> {enhancement['enhanced_prompt']}")
    if enhancement['negative_prompt']:
        a("")
        a(f"**Negative:** {enhancement['negative_prompt']}")
    a("")
    ok = sum(1 for r in results if r['status'] == 'complete')
    total_time = sum(r['duration_s'] for r in results)
    a(f"**Summary:** {ok}/{len(results)} images generated "
      f"in {total_time/60:.1f} min.")
    a("")
    a("Render with `python scripts/matrix_gallery.py " + str(run_dir) + "`")

    (run_dir / "summary.md").write_text("\n".join(lines))
    print(f"\nReport written to: {run_dir / 'summary.md'}")
    print(f"Render gallery with: python scripts/matrix_gallery.py {run_dir}")


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #


def parse_strengths(spec: str) -> list[tuple[float, float]]:
    """Parse '0.6/0.3,0.8/0.5,1.0/0.7' → [(0.6,0.3),(0.8,0.5),(1.0,0.7)]."""
    out: list[tuple[float, float]] = []
    for pair in spec.split(","):
        pair = pair.strip()
        if not pair:
            continue
        m = re.match(r"([\d.]+)\s*/\s*([\d.]+)", pair)
        if not m:
            sys.exit(f"bad strength spec: {pair!r} (want 'model/clip' pairs)")
        out.append((float(m.group(1)), float(m.group(2))))
    if not out:
        sys.exit("no strengths parsed")
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("prompt", help="Seed prompt to sweep against")
    p.add_argument("--op-model", default=DEFAULT_OP_MODEL,
                   help=f"Ollama model for prompt enhancement (default: {DEFAULT_OP_MODEL})")
    p.add_argument("--base-model", default=DEFAULT_BASE_MODEL,
                   help=f"Base image checkpoint (default: {DEFAULT_BASE_MODEL})")
    p.add_argument("--strengths", default=None,
                   help="Comma-separated model/clip pairs, e.g. '0.6/0.3,0.8/0.5,1.0/0.7,1.2/0.9'. "
                        "Default: the four-tier bracket.")
    p.add_argument("--with-trigger-ab", action="store_true",
                   help="Add a second axis: each strength × LoRA gets tested both "
                        "with and without the LoRA's canonical trigger word appended.")
    p.add_argument("--only-loras", default=None,
                   help="Comma-separated LoRA filenames to test (overrides default 6).")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    p.add_argument("--cfg", type=float, default=DEFAULT_CFG)
    return p.parse_args()


async def main() -> int:
    args = parse_args()
    strengths = parse_strengths(args.strengths) if args.strengths else list(DEFAULT_STRENGTHS)
    loras = ([m.strip() for m in args.only_loras.split(",")]
             if args.only_loras else list(STYLE_LORAS))

    cfg = SweepConfig(
        base_model=args.base_model,
        seed=args.seed,
        steps=args.steps,
        cfg=args.cfg,
        op_model=args.op_model,
        strengths=strengths,
        style_loras=loras,
        with_trigger_ab=args.with_trigger_ab,
    )

    # Pre-flight
    async with httpx.AsyncClient() as client:
        try:
            await client.get(f"{SERVER}/api/queue", timeout=5)
        except httpx.HTTPError as exc:
            sys.exit(f"error: server unreachable at {SERVER} ({exc})")
        try:
            await client.get(f"{OLLAMA}/api/tags", timeout=5)
        except httpx.HTTPError as exc:
            sys.exit(f"error: Ollama unreachable ({exc})")

    run_ts = datetime.now().strftime("%Y-%m-%d")
    slug = slugify(args.prompt)
    suffix = "-trigger-ab" if args.with_trigger_ab else ""
    run_dir = Path("storage/test-runs") / f"{run_ts}-strength-sweep-{slug}{suffix}"

    started = time.monotonic()
    async with httpx.AsyncClient() as client:
        enh, results = await run_sweep(client, cfg, args.prompt)

    write_report(run_dir, args.prompt, cfg, enh, results)
    print(f"\nDone in {(time.monotonic()-started)/60:.1f} min.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
