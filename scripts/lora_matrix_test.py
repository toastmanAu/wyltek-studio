#!/usr/bin/env python3
"""LoRA + prompt-optimizer matrix test runner for Wyltek Studio.

For one or more seed prompts, generates the full matrix:
  - raw                × {no LoRA, each style LoRA}
  - OP'd by each model × {no LoRA, each style LoRA}

Usage:
    # single seed
    python scripts/lora_matrix_test.py "a digital blockchain background image"

    # multiple seeds from a file (one per line, # for comments)
    python scripts/lora_matrix_test.py --prompt-file seeds.txt

    # override base image model or other knobs
    python scripts/lora_matrix_test.py "a cat" --base-model dreamshaper-xl-v21.safetensors --steps 8 --cfg 2

Outputs per run (one folder per seed):
    storage/test-runs/{YYYY-MM-DD}-lora-matrix-{slug}/
        summary.md          human-readable report
        results.json        machine-readable full record
        op_prompts.json     cached Ollama enhancements
Images land in the normal storage path via the server pipeline.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path

import httpx

# --------------------------------------------------------------------------- #
# Defaults — all CLI-overridable                                              #
# --------------------------------------------------------------------------- #

SERVER = "http://localhost:7860"
OLLAMA = "http://[::1]:11434"

DEFAULT_BASE_MODEL = "juggernautXL_v9.safetensors"
DEFAULT_SEED = 42
DEFAULT_STEPS = 30
DEFAULT_CFG = 7.0
DEFAULT_WIDTH = 1024
DEFAULT_HEIGHT = 1024
DEFAULT_LORA_MODEL_STRENGTH = 0.8
DEFAULT_LORA_CLIP_STRENGTH = 0.5

STYLE_LORAS: list[str] = [
    "pixel-art-xl.safetensors",
    "voxel-xl.safetensors",
    "crayon-style-xl.safetensors",
    "watercolor-xl.safetensors",
    "sticker-style-xl.safetensors",
    "anime-detailer-xl.safetensors",
]

# Ordered small → large so the report reads intuitively.
OP_MODELS: list[str] = [
    "gemma3n:e4b",        # ~6.9B
    "qwen3:8b",           # ~8.2B
    "gemma4:latest",      # ~8.0B
    "carnice-9b:latest",  # ~9.0B
    "qwen3.5:9b",         # ~9.7B
    "qwen2.5:14b",        # ~14.8B
    "qwen3:14b",          # ~14.8B
    "qwen3.5:35b-a3b",    # ~34.7B MoE — current default
]

SYSTEM_PROMPT = """You are an expert Stable Diffusion prompt engineer. The user will give you an image generation prompt. Your job is to enhance it for maximum quality.

The target generation model is: {target_model}

Rules:
- Add specific quality descriptors (lighting, composition, detail level, style)
- Remove ambiguity — make vague descriptions concrete
- Keep the user's core intent intact
- Suggest a negative prompt to avoid common artifacts
- Be concise — SD prompts work best under 75 tokens

Respond ONLY with valid JSON (no markdown, no code fences):
{{"enhanced_prompt": "...", "negative_prompt": "...", "changes_made": "brief explanation of what you improved"}}"""


# --------------------------------------------------------------------------- #
# Data shapes                                                                 #
# --------------------------------------------------------------------------- #


@dataclass
class RunConfig:
    base_model: str = DEFAULT_BASE_MODEL
    seed: int = DEFAULT_SEED
    steps: int = DEFAULT_STEPS
    cfg: float = DEFAULT_CFG
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    lora_strength_model: float = DEFAULT_LORA_MODEL_STRENGTH
    lora_strength_clip: float = DEFAULT_LORA_CLIP_STRENGTH
    op_models: list[str] = field(default_factory=lambda: list(OP_MODELS))
    style_loras: list[str] = field(default_factory=lambda: list(STYLE_LORAS))


@dataclass
class Enhancement:
    model: str
    enhanced_prompt: str
    negative_prompt: str
    changes_made: str
    latency_s: float
    ok: bool
    raw_response: str = ""


@dataclass
class GenResult:
    label: str            # e.g. "raw+voxel-xl" or "qwen3:8b+no-lora"
    prompt: str
    negative: str
    lora: str             # "" when no LoRA
    op_model: str         # "" for raw
    job_id: str
    status: str           # "complete", "error", "timeout"
    duration_s: float
    image_path: str       # relative path or empty on failure
    error: str = ""


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def slugify(text: str, max_len: int = 40) -> str:
    """Short filesystem-safe slug from a free-form prompt."""
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:max_len] or "run").rstrip("-")


def lora_label(lora: str) -> str:
    return "no-lora" if not lora else lora.replace(".safetensors", "")


async def enhance_prompt(
    client: httpx.AsyncClient,
    ollama_model: str,
    target_model: str,
    user_prompt: str,
) -> Enhancement:
    """Call Ollama directly with the same system prompt the server uses."""
    sys_prompt = SYSTEM_PROMPT.format(target_model=target_model)
    started = time.monotonic()
    try:
        resp = await client.post(
            f"{OLLAMA}/api/generate",
            json={
                "model": ollama_model,
                "prompt": user_prompt,
                "system": sys_prompt,
                "stream": False,
                "options": {"temperature": 0.3, "num_gpu": 0},
            },
            timeout=240,
        )
        resp.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        return Enhancement(
            model=ollama_model, enhanced_prompt=user_prompt, negative_prompt="",
            changes_made=f"(error: {exc})", latency_s=time.monotonic() - started, ok=False,
        )

    text = resp.json().get("response", "")
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return Enhancement(
            model=ollama_model, enhanced_prompt=user_prompt, negative_prompt="",
            changes_made="(parse failure — no JSON in response)",
            latency_s=time.monotonic() - started, ok=False, raw_response=text,
        )
    try:
        parsed = json.loads(match.group())
    except json.JSONDecodeError as exc:
        return Enhancement(
            model=ollama_model, enhanced_prompt=user_prompt, negative_prompt="",
            changes_made=f"(invalid JSON: {exc})",
            latency_s=time.monotonic() - started, ok=False, raw_response=text,
        )

    return Enhancement(
        model=ollama_model,
        enhanced_prompt=parsed.get("enhanced_prompt", user_prompt),
        negative_prompt=parsed.get("negative_prompt", ""),
        changes_made=parsed.get("changes_made", ""),
        latency_s=time.monotonic() - started,
        ok=True,
    )


async def submit_generation(
    client: httpx.AsyncClient, cfg: RunConfig, prompt: str, negative: str, lora: str,
) -> str:
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
        "lora_strength": str(cfg.lora_strength_model),
        "lora_strength_model": str(cfg.lora_strength_model),
        "lora_strength_clip": str(cfg.lora_strength_clip),
    }
    resp = await client.post(f"{SERVER}/api/generate", data=form, timeout=30)
    resp.raise_for_status()
    return resp.json()["job_id"]


async def poll_until_done(
    client: httpx.AsyncClient, job_id: str, timeout: int = 600,
) -> dict:
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        try:
            resp = await client.get(f"{SERVER}/api/job/{job_id}", timeout=10)
            data = resp.json()
        except httpx.HTTPError:
            await asyncio.sleep(2)
            continue
        if data.get("status") in ("complete", "error"):
            data["_duration_s"] = time.monotonic() - started
            return data
        await asyncio.sleep(1.5)
    return {"status": "timeout", "_duration_s": time.monotonic() - started}


def find_image_path(job_id: str) -> str:
    """Resolve a job_id to its on-disk image (sidecar-aware)."""
    today = datetime.now().strftime("%Y-%m-%d")
    for day in (today, ""):
        candidate = Path("storage/unsorted") / day / "images" / f"{job_id}.png"
        if candidate.exists():
            return str(candidate)
    # Fallback: scan today's directory for an exact match
    today_dir = Path("storage/unsorted") / today / "images"
    if today_dir.exists():
        for p in today_dir.glob(f"{job_id}*.png"):
            return str(p)
    return ""


# --------------------------------------------------------------------------- #
# Matrix orchestration                                                        #
# --------------------------------------------------------------------------- #


async def run_one(
    client: httpx.AsyncClient, cfg: RunConfig,
    label: str, prompt: str, negative: str, lora: str, op_model: str,
) -> GenResult:
    print(f"  [{label}] submitting...", flush=True)
    try:
        job_id = await submit_generation(client, cfg, prompt, negative, lora)
    except httpx.HTTPError as exc:
        return GenResult(
            label=label, prompt=prompt, negative=negative, lora=lora, op_model=op_model,
            job_id="", status="error", duration_s=0.0, image_path="", error=str(exc),
        )
    result = await poll_until_done(client, job_id)
    status = result.get("status", "unknown")
    duration = result.get("_duration_s", 0.0)
    err = result.get("error", "") if status == "error" else ""
    image_path = find_image_path(job_id) if status == "complete" else ""
    print(f"  [{label}] {status} in {duration:.1f}s → {image_path or '(no file)'}", flush=True)
    return GenResult(
        label=label, prompt=prompt, negative=negative, lora=lora, op_model=op_model,
        job_id=job_id, status=status, duration_s=duration,
        image_path=image_path, error=err,
    )


async def run_matrix_for_seed(
    client: httpx.AsyncClient, cfg: RunConfig, seed_prompt: str,
) -> tuple[list[Enhancement], list[GenResult]]:
    """Full matrix for one seed prompt. Returns (enhancements, gen_results)."""
    print(f"\n=== Seed: {seed_prompt!r} ===", flush=True)

    # Step 1: enhance the seed prompt with every Ollama model up-front.
    # Doing them sequentially (not parallel) because Ollama serves one model
    # at a time on a single GPU and swapping dominates total time anyway.
    print(f"\n-- Enhancing with {len(cfg.op_models)} Ollama models --", flush=True)
    enhancements: list[Enhancement] = []
    for model in cfg.op_models:
        print(f"  {model}...", end=" ", flush=True)
        enh = await enhance_prompt(client, model, cfg.base_model, seed_prompt)
        enhancements.append(enh)
        status = "ok" if enh.ok else "FAIL"
        print(f"{status} ({enh.latency_s:.1f}s, {len(enh.enhanced_prompt.split())} words)", flush=True)

    # Step 2: build the full matrix. Image gens are serial because the server's
    # GPU lane is limit=1 — parallelism would just queue them.
    print(f"\n-- Generating images --", flush=True)
    results: list[GenResult] = []
    loras_with_none: list[str] = [""] + cfg.style_loras

    # Raw (no OP) runs first.
    for lora in loras_with_none:
        label = f"raw+{lora_label(lora)}"
        results.append(await run_one(
            client, cfg, label, seed_prompt, "", lora, "",
        ))

    # OP'd runs.
    for enh in enhancements:
        if not enh.ok:
            print(f"  skipping failed model: {enh.model}", flush=True)
            continue
        for lora in loras_with_none:
            label = f"{enh.model}+{lora_label(lora)}"
            results.append(await run_one(
                client, cfg, label,
                enh.enhanced_prompt, enh.negative_prompt, lora, enh.model,
            ))

    return enhancements, results


# --------------------------------------------------------------------------- #
# Report                                                                      #
# --------------------------------------------------------------------------- #


def write_report(
    run_dir: Path, seed_prompt: str, cfg: RunConfig,
    enhancements: list[Enhancement], results: list[GenResult],
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)

    # Machine-readable
    payload = {
        "generated_at": datetime.now().isoformat(),
        "seed_prompt": seed_prompt,
        "config": asdict(cfg),
        "enhancements": [asdict(e) for e in enhancements],
        "results": [asdict(r) for r in results],
    }
    (run_dir / "results.json").write_text(json.dumps(payload, indent=2))

    # Cached enhancements (simple map, handy for re-runs)
    (run_dir / "op_prompts.json").write_text(json.dumps(
        {e.model: {"enhanced": e.enhanced_prompt, "negative": e.negative_prompt,
                   "changes": e.changes_made, "ok": e.ok} for e in enhancements},
        indent=2,
    ))

    # Human-readable markdown
    lines: list[str] = []
    a = lines.append
    a(f"# LoRA Matrix — `{seed_prompt}`")
    a("")
    a(f"- **Generated:** {datetime.now().isoformat(timespec='seconds')}")
    a(f"- **Base image model:** `{cfg.base_model}`")
    a(f"- **Seed / steps / cfg:** `{cfg.seed}` / `{cfg.steps}` / `{cfg.cfg}`")
    a(f"- **LoRA strengths:** model `{cfg.lora_strength_model}`, clip `{cfg.lora_strength_clip}`")
    a(f"- **Style LoRAs tested:** {', '.join(lora_label(l) for l in cfg.style_loras)}")
    a(f"- **OP models tested:** {', '.join(cfg.op_models)}")
    a("")

    # Summary stats
    ok_gens = [r for r in results if r.status == "complete"]
    failed = [r for r in results if r.status != "complete"]
    total_time = sum(r.duration_s for r in results)
    a(f"**Summary:** {len(ok_gens)}/{len(results)} images generated "
      f"in {total_time/60:.1f} min wall time. Failures: {len(failed)}.")
    a("")

    # Enhanced prompts per model
    a("## Enhanced prompts by Ollama model")
    a("")
    a("| Model | Latency | Words | Enhanced prompt | Negative |")
    a("|---|---|---|---|---|")
    seed_words = len(seed_prompt.split())
    a(f"| *(seed)* | — | {seed_words} | {seed_prompt} | |")
    for e in enhancements:
        status = "" if e.ok else " ⚠️"
        wc = len(e.enhanced_prompt.split())
        prompt_cell = e.enhanced_prompt.replace("|", "\\|").replace("\n", " ")
        neg_cell = e.negative_prompt.replace("|", "\\|").replace("\n", " ")
        a(f"| `{e.model}`{status} | {e.latency_s:.1f}s | {wc} | {prompt_cell} | {neg_cell} |")
    a("")

    # Per-run grid — one row per generation
    a("## All generations")
    a("")
    a("| OP model | LoRA | Job ID | Status | Time | Image |")
    a("|---|---|---|---|---|---|")
    for r in results:
        op = r.op_model or "*(raw)*"
        lora = lora_label(r.lora)
        img = f"`{r.image_path}`" if r.image_path else "—"
        status_mark = "✓" if r.status == "complete" else f"✗ {r.status}"
        a(f"| {op} | {lora} | `{r.job_id}` | {status_mark} | {r.duration_s:.1f}s | {img} |")
    a("")

    # Any errors surfaced up front
    if failed:
        a("## Failed / timed-out jobs")
        a("")
        for r in failed:
            a(f"- `{r.label}` → {r.status}: {r.error or '(no error message)'}")
        a("")

    a("---")
    a("Images saved via the normal Wyltek Studio pipeline — each `.png` has a "
      "`.json` sidecar in the same directory capturing model, LoRA, seed, "
      "prompt, and (if the hybrid injector fired) `original_prompt` + "
      "`trigger_injected`.")

    (run_dir / "summary.md").write_text("\n".join(lines))
    print(f"\nReport written to: {run_dir / 'summary.md'}", flush=True)


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #


def load_seeds(args: argparse.Namespace) -> list[str]:
    seeds: list[str] = []
    if args.prompt_file:
        for raw in Path(args.prompt_file).read_text().splitlines():
            stripped = raw.strip()
            if stripped and not stripped.startswith("#"):
                seeds.append(stripped)
    if args.prompt:
        seeds.append(args.prompt)
    if not seeds:
        sys.exit("error: supply a prompt as positional arg or --prompt-file")
    return seeds


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("prompt", nargs="?", help="Seed prompt (or use --prompt-file)")
    p.add_argument("--prompt-file", help="File of seed prompts (one per line, # for comments)")
    p.add_argument("--base-model", default=DEFAULT_BASE_MODEL,
                   help=f"Base image checkpoint (default: {DEFAULT_BASE_MODEL})")
    p.add_argument("--seed", type=int, default=DEFAULT_SEED)
    p.add_argument("--steps", type=int, default=DEFAULT_STEPS)
    p.add_argument("--cfg", type=float, default=DEFAULT_CFG)
    p.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    p.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    p.add_argument("--lora-model-strength", type=float, default=DEFAULT_LORA_MODEL_STRENGTH)
    p.add_argument("--lora-clip-strength", type=float, default=DEFAULT_LORA_CLIP_STRENGTH)
    p.add_argument("--skip-op", action="store_true",
                   help="Skip OP runs — only do raw + each style LoRA (7 images instead of 63)")
    p.add_argument("--only-ops", help="Comma-separated Ollama model names to test (overrides default list)")
    p.add_argument("--only-loras", help="Comma-separated LoRA filenames to test (overrides default list)")
    return p.parse_args()


async def main() -> int:
    args = parse_args()
    seeds = load_seeds(args)

    cfg = RunConfig(
        base_model=args.base_model,
        seed=args.seed,
        steps=args.steps,
        cfg=args.cfg,
        width=args.width,
        height=args.height,
        lora_strength_model=args.lora_model_strength,
        lora_strength_clip=args.lora_clip_strength,
        op_models=[m.strip() for m in args.only_ops.split(",")] if args.only_ops else list(OP_MODELS),
        style_loras=[m.strip() for m in args.only_loras.split(",")] if args.only_loras else list(STYLE_LORAS),
    )
    if args.skip_op:
        cfg.op_models = []

    # Quick reachability checks before starting a 30-minute run.
    async with httpx.AsyncClient() as client:
        try:
            await client.get(f"{SERVER}/api/queue", timeout=5)
        except httpx.HTTPError as exc:
            sys.exit(f"error: server unreachable at {SERVER} — is it running? ({exc})")
        try:
            await client.get(f"{OLLAMA}/api/tags", timeout=5)
        except httpx.HTTPError as exc:
            sys.exit(f"error: Ollama unreachable at {OLLAMA} ({exc})")

    run_ts = datetime.now().strftime("%Y-%m-%d")
    overall_started = time.monotonic()

    async with httpx.AsyncClient() as client:
        for idx, seed_prompt in enumerate(seeds, 1):
            print(f"\n{'=' * 60}\nSeed {idx}/{len(seeds)}: {seed_prompt}\n{'=' * 60}")
            run_dir = Path("storage/test-runs") / f"{run_ts}-lora-matrix-{slugify(seed_prompt)}"
            enhancements, results = await run_matrix_for_seed(client, cfg, seed_prompt)
            write_report(run_dir, seed_prompt, cfg, enhancements, results)

    elapsed = time.monotonic() - overall_started
    print(f"\nAll seeds complete in {elapsed/60:.1f} min.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
