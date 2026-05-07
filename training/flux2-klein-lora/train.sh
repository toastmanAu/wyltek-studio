#!/usr/bin/env bash
# Launch FLUX.2-Klein LoRA training for open-palette.
# Assumes bootstrap.sh has been run and dataset/ has images + captions.

set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SIMPLETUNER_DIR="/bulk/simpletuner"
VENV_DIR="${SIMPLETUNER_DIR}/.venv"

# ── ROCm env for Radeon 7900 XTX (RDNA3 / gfx1100) ────────────
export HSA_OVERRIDE_GFX_VERSION=11.0.0
export PYTORCH_ROCM_ARCH=gfx1100
export HIP_VISIBLE_DEVICES=0
export PYTORCH_HIP_ALLOC_CONF=expandable_segments:True
# Suppress Triton autotune spam on ROCm
export TRITON_CACHE_DIR="${HERE}/cache/triton"

# ── Guard: dataset must have images ───────────────────────────
IMG_COUNT=$(find "${HERE}/dataset" -maxdepth 1 \( -iname "*.png" -o -iname "*.jpg" -o -iname "*.jpeg" -o -iname "*.webp" \) 2>/dev/null | wc -l)
TXT_COUNT=$(find "${HERE}/dataset" -maxdepth 1 -iname "*.txt" 2>/dev/null | wc -l)

if [ "${IMG_COUNT}" -lt 10 ]; then
    echo "ERROR: only ${IMG_COUNT} images in ${HERE}/dataset (need 10+)."
    echo "Drop images (.png/.jpg/.webp) and matching .txt captions in that dir."
    exit 1
fi

if [ "${TXT_COUNT}" -lt "${IMG_COUNT}" ]; then
    echo "WARNING: ${TXT_COUNT} captions for ${IMG_COUNT} images — some will be skipped."
    echo "Each image.png needs a image.txt caption next to it."
fi

echo "[train] dataset: ${IMG_COUNT} images, ${TXT_COUNT} captions"
echo "[train] config:  ${HERE}/config.json"
echo "[train] output:  ${HERE}/outputs"

# ── Activate SimpleTuner venv ─────────────────────────────────
if [ ! -d "${VENV_DIR}" ]; then
    echo "ERROR: ${VENV_DIR} missing. Run bootstrap.sh first."
    exit 1
fi
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

# ── Launch ────────────────────────────────────────────────────
cd "${SIMPLETUNER_DIR}"
exec simpletuner train --config "${HERE}/config.json"
