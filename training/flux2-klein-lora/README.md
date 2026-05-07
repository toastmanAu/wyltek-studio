# open-palette FLUX.2-Klein LoRA

Style LoRA training for the open-palette visual identity, on top of `black-forest-labs/FLUX.2-klein-base-9B`.

## Layout

```
flux2-klein-lora/
├── config.json              SimpleTuner training config
├── multidatabackend.json    dataset + cache backend config
├── bootstrap.sh             one-time install (clones SimpleTuner to /bulk/simpletuner)
├── train.sh                 launch training with ROCm env set
├── dataset/                 DROP IMAGES + CAPTIONS HERE
├── cache/                   VAE + text-embed caches (auto-populated)
└── outputs/                 LoRA checkpoints land here
```

## One-time setup

```bash
# 1. Install SimpleTuner with ROCm into /bulk/simpletuner
bash bootstrap.sh

# 2. Accept the FLUX.2-Klein license on HF:
#    https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9B
#    Then:
source /bulk/simpletuner/.venv/bin/activate
huggingface-cli login
```

## Dataset format

Drop into `dataset/`:

```
dataset/
├── 001.png
├── 001.txt          "op_palette_v1 style, a wide landscape with layered mountains..."
├── 002.png
├── 002.txt          "op_palette_v1 style, portrait of a figure in earthy tones..."
└── ...
```

**Rules**
- Every image needs a matching `.txt` caption with the same stem
- Use `op_palette_v1` (or your chosen trigger) as the first tokens of every caption
- 20–80 images is the sweet spot. Tight, stylistically consistent set beats a noisy larger one.
- Any aspect ratio works — SimpleTuner buckets automatically. Min 768px short edge.
- PNG, JPG, JPEG, WEBP accepted.

**Caption auto-gen** (if you don't want to hand-write):
```bash
pip install transformers pillow
# Use Florence-2 or BLIP-2 to auto-caption, then prepend "op_palette_v1 style, "
# to every caption.
```

## Launch

```bash
bash train.sh
```

Progress is logged to stdout. Checkpoints save every 250 steps (3 rolling). Validation images render every 250 steps into `outputs/validation/`.

## Tuning knobs (in `config.json`)

| Field | Default | Notes |
|---|---|---|
| `max_train_steps` | 2000 | ~2–3 hours on 7900 XTX at batch 1 + grad_accum 4 |
| `lora_rank` | 32 | 16 = lighter/faster, 64 = more capacity (needs more VRAM) |
| `learning_rate` | 1e-4 | Safe for FLUX.2. Try 5e-5 if overfitting fast |
| `gradient_accumulation_steps` | 4 | Effective batch = 4. Drop to 1 for faster iteration during tuning |
| `resolution` | 1024 | 768 trains 40% faster if you're iterating |
| `validation_prompt` | change it | Hard-edit for your target trigger + scene |

## ROCm notes

- `train.sh` sets `HSA_OVERRIDE_GFX_VERSION=11.0.0` and `PYTORCH_ROCM_ARCH=gfx1100` for the 7900 XTX.
- Don't launch while `nervos-expert` training is running — FLUX.2 LoRA at rank 32 peaks around 20–22GB VRAM, and QLoRA LLM training adds another 5–6GB.
- If you hit OOM: drop `resolution` to 768, `lora_rank` to 16, or enable `--offload_param_path` in `config.json` for CPU offload of the text encoder.

## Disk budget

| Thing | Size |
|---|---|
| FLUX.2-Klein BF16 weights (HF cache) | ~18 GB |
| SimpleTuner venv + ROCm torch | ~10 GB |
| VAE cache (50 images) | ~1–2 GB |
| Text-embed cache | <500 MB |
| Per checkpoint (rank 32 LoRA) | ~200 MB |
| Total for one run | **~30 GB** |

`/bulk` is currently at 90% — watch free space, or symlink the HF cache elsewhere before launching.

## Post-training

Merge into open-palette's image pipeline: the LoRA output is diffusers-format `pytorch_lora_weights.safetensors`. Load with `pipe.load_lora_weights(...)` in the FLUX backend, or convert to the ComfyUI format if going through `model_catalog.py`.
