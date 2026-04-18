#!/usr/bin/env python3
"""Warm-up-then-measure latency benchmark for Ollama OP models.

For each model:
  1. Unload any other resident models from Ollama (so we measure a clean load).
  2. Prime the target with a tiny call (pays the cold-load cost).
  3. Measure N real enhancement calls using the Wyltek Studio system prompt.
  4. Report per-call latency + whether the response parsed as valid JSON.

Usage:
    python scripts/op_latency_bench.py qwen3:14b qwen3.5:9b carnice-9b:latest
    python scripts/op_latency_bench.py --trials 3 qwen3:8b gemma4:latest
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from statistics import mean, median

import httpx

OLLAMA = "http://[::1]:11434"

SYSTEM_PROMPT = """You are an expert Stable Diffusion prompt engineer. The user will give you an image generation prompt. Your job is to enhance it for maximum quality.

The target generation model is: juggernautXL_v9.safetensors

Rules:
- Add specific quality descriptors (lighting, composition, detail level, style)
- Remove ambiguity — make vague descriptions concrete
- Keep the user's core intent intact
- Suggest a negative prompt to avoid common artifacts
- Be concise — SD prompts work best under 75 tokens

Respond ONLY with valid JSON (no markdown, no code fences):
{{"enhanced_prompt": "...", "negative_prompt": "...", "changes_made": "brief explanation of what you improved"}}"""

USER_PROMPT = "a digital blockchain background image"


async def unload_model(client: httpx.AsyncClient, model: str) -> None:
    """Ask Ollama to unload a model (keep_alive=0 evicts it from VRAM)."""
    try:
        await client.post(
            f"{OLLAMA}/api/generate",
            json={"model": model, "prompt": "", "keep_alive": 0, "stream": False},
            timeout=60,
        )
    except httpx.HTTPError:
        pass


async def list_resident(client: httpx.AsyncClient) -> list[str]:
    """Models currently loaded in VRAM."""
    try:
        resp = await client.get(f"{OLLAMA}/api/ps", timeout=10)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except httpx.HTTPError:
        return []


async def evict_others(client: httpx.AsyncClient, keep: str) -> None:
    """Unload every model except ``keep`` so the benchmark has a fair baseline."""
    for name in await list_resident(client):
        if name != keep:
            print(f"    evicting {name}...")
            await unload_model(client, name)


async def prime(client: httpx.AsyncClient, model: str) -> float:
    """Cold-load the model with a trivial call. Returns load time."""
    started = time.monotonic()
    try:
        await client.post(
            f"{OLLAMA}/api/generate",
            json={"model": model, "prompt": "hi", "stream": False,
                  "options": {"num_predict": 1, "temperature": 0}},
            timeout=600,
        )
    except httpx.HTTPError as exc:
        return -1.0  # signal failure
    return time.monotonic() - started


async def one_trial(client: httpx.AsyncClient, model: str, num_gpu: int) -> tuple[float, bool, int, str]:
    """One real enhancement call. Returns (latency, valid_json, word_count, preview).

    num_gpu: Ollama option. 0 = CPU-only; -1 = auto (use all GPU layers that fit);
    N > 0 = explicit number of layers to offload.
    """
    started = time.monotonic()
    try:
        resp = await client.post(
            f"{OLLAMA}/api/generate",
            json={
                "model": model,
                "prompt": USER_PROMPT,
                "system": SYSTEM_PROMPT,
                "stream": False,
                "options": {"temperature": 0.3, "num_gpu": num_gpu},
            },
            timeout=600,
        )
        resp.raise_for_status()
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        return (time.monotonic() - started, False, 0, f"(error: {exc})")

    dt = time.monotonic() - started
    text = resp.json().get("response", "")
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return (dt, False, len(text.split()), text[:120])
    try:
        parsed = json.loads(match.group())
        ep = parsed.get("enhanced_prompt", "")
        return (dt, True, len(ep.split()), ep[:120])
    except json.JSONDecodeError:
        return (dt, False, 0, text[:120])


async def bench_model(client: httpx.AsyncClient, model: str, trials: int, num_gpu: int) -> dict:
    print(f"\n--- {model} (num_gpu={num_gpu}) ---")
    await evict_others(client, keep="__none__")  # evict everything
    print(f"  priming (cold load)...")
    cold = await prime(client, model)
    if cold < 0:
        print(f"  FAILED to load")
        return {"model": model, "cold_load_s": -1, "trials": [], "error": "load failed",
                "num_gpu": num_gpu}
    print(f"  cold load: {cold:.1f}s")

    # Check whether Ollama actually put any weights on GPU.
    gpu_note = ""
    try:
        ps = await client.get(f"{OLLAMA}/api/ps", timeout=5)
        for m in ps.json().get("models", []):
            if m["name"] == model:
                sv = m.get("size_vram", 0) / 1e9
                sz = m.get("size", 0) / 1e9
                pct = (sv / sz * 100) if sz else 0
                gpu_note = f"VRAM: {sv:.1f}/{sz:.1f}GB ({pct:.0f}%)"
                break
    except httpx.HTTPError:
        pass
    if gpu_note:
        print(f"  {gpu_note}")

    trials_out = []
    for i in range(trials):
        print(f"  trial {i+1}/{trials}...", end=" ", flush=True)
        dt, ok, wc, preview = await one_trial(client, model, num_gpu)
        trials_out.append({"latency_s": dt, "ok": ok, "words": wc, "preview": preview})
        flag = "ok" if ok else "BAD JSON"
        print(f"{dt:.1f}s ({flag}, {wc} words)")

    warm = [t["latency_s"] for t in trials_out if t["ok"]]
    return {
        "model": model,
        "num_gpu": num_gpu,
        "cold_load_s": cold,
        "gpu_note": gpu_note,
        "trials": trials_out,
        "warm_mean_s": mean(warm) if warm else None,
        "warm_median_s": median(warm) if warm else None,
    }


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("models", nargs="+", help="Ollama model names to benchmark")
    ap.add_argument("--trials", type=int, default=2,
                    help="Warm trials per model (default: 2)")
    ap.add_argument("--num-gpu", type=int, default=0,
                    help="Ollama num_gpu option: 0=CPU-only, -1=auto (all GPU layers that fit), "
                         "N>0=offload N layers. Default: 0 (matches server).")
    args = ap.parse_args()

    async with httpx.AsyncClient() as client:
        results = []
        for m in args.models:
            results.append(await bench_model(client, m, args.trials, args.num_gpu))

    print("\n" + "=" * 80)
    print(f"{'Model':<25} {'num_gpu':>8} {'Cold load':>10} {'Warm mean':>10} {'VRAM':>20} {'OK':>5}")
    print("=" * 80)
    for r in results:
        cold = f"{r['cold_load_s']:.1f}s" if r['cold_load_s'] >= 0 else "FAIL"
        warm = f"{r['warm_mean_s']:.1f}s" if r.get('warm_mean_s') is not None else "—"
        ok = sum(1 for t in r['trials'] if t['ok'])
        vram = r.get('gpu_note', '') or '—'
        print(f"{r['model']:<25} {r.get('num_gpu', 0):>8} {cold:>10} {warm:>10} {vram:>20} {ok}/{len(r['trials']):>3}")

    # Machine-readable dump
    out_path = f"/tmp/op_latency_{int(time.time())}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nDetail: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
