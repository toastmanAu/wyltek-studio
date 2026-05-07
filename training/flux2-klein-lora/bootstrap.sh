#!/usr/bin/env bash
# Bootstrap SimpleTuner with ROCm into /bulk/simpletuner (shared install).
# Run once. Safe to re-run — skips finished steps.

set -euo pipefail

INSTALL_DIR="/bulk/simpletuner"
VENV_DIR="${INSTALL_DIR}/.venv"

log() { echo "[bootstrap] $*"; }

# ── 1. Clone SimpleTuner ──────────────────────────────────────
if [ ! -d "${INSTALL_DIR}/.git" ]; then
    log "Cloning SimpleTuner to ${INSTALL_DIR}..."
    git clone https://github.com/bghira/SimpleTuner "${INSTALL_DIR}"
else
    log "SimpleTuner already cloned — pulling latest..."
    git -C "${INSTALL_DIR}" pull --ff-only || log "pull skipped (dirty tree?)"
fi

# ── 2. Create venv ────────────────────────────────────────────
if [ ! -d "${VENV_DIR}" ]; then
    log "Creating venv..."
    python3 -m venv "${VENV_DIR}"
fi
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
python -m pip install --upgrade pip wheel

# ── 3. Install ROCm-flavoured deps ────────────────────────────
# SimpleTuner extras target ROCm torch. If this fails, try:
#   pip install torch torchvision --index-url https://download.pytorch.org/whl/rocm6.2
#   pip install -e "${INSTALL_DIR}[rocm]"
log "Installing SimpleTuner with ROCm extras..."
pip install -e "${INSTALL_DIR}[rocm]"

# ── 4. HF auth reminder ───────────────────────────────────────
if ! huggingface-cli whoami &>/dev/null; then
    log "WARNING: not logged into HuggingFace."
    log "FLUX.2-Klein-9B requires accepting the license at https://huggingface.co/black-forest-labs/FLUX.2-klein-base-9B"
    log "Then run: huggingface-cli login"
fi

log "Done. Activate with: source ${VENV_DIR}/bin/activate"
