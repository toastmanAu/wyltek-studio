#!/usr/bin/env bash
# setup-sensenova.sh — install SenseNova-U1 dependencies for Wyltek Studio.
#
# Detects platform (linux+ROCm | linux+CUDA | macOS-ARM64) and installs:
#   - dedicated Python venv at $SENSENOVA_VENV
#   - platform-appropriate torch wheel
#   - the SenseNova-U1 repo at $SENSENOVA_REPO
#   - 50-step + 8-step weights via huggingface-cli
#
# Idempotent: re-running is safe. Skips already-present components.
#
# Override paths via env vars:
#   SENSENOVA_VENV          (default: /data/venvs/sensenova-u1)
#   SENSENOVA_REPO          (default: $HOME/SenseNova-U1)
#   SENSENOVA_WEIGHTS_FINAL (default: /data/sensenova-u1-weights)
#   SENSENOVA_WEIGHTS_DRAFT (default: /data/sensenova-u1-weights-8step)

set -euo pipefail

VENV=${SENSENOVA_VENV:-/data/venvs/sensenova-u1}
REPO=${SENSENOVA_REPO:-$HOME/SenseNova-U1}
WEIGHTS_FINAL=${SENSENOVA_WEIGHTS_FINAL:-/data/sensenova-u1-weights}
WEIGHTS_DRAFT=${SENSENOVA_WEIGHTS_DRAFT:-/data/sensenova-u1-weights-8step}

# --- platform detection ---
detect_platform() {
  case "$(uname -s)" in
    Linux)
      if command -v rocminfo >/dev/null 2>&1; then echo "linux-rocm"; return; fi
      if command -v nvidia-smi >/dev/null 2>&1; then echo "linux-cuda"; return; fi
      echo "linux-cpu" ;;
    Darwin)
      if [[ "$(uname -m)" == "arm64" ]]; then echo "macos-arm64"; else echo "macos-intel"; fi ;;
    *) echo "unsupported" ;;
  esac
}

PLATFORM=$(detect_platform)
echo "[setup] platform=$PLATFORM"
case "$PLATFORM" in
  linux-rocm|linux-cuda|macos-arm64) ;;
  *)
    echo "[setup] unsupported platform: $PLATFORM. SenseNova requires Linux+ROCm, Linux+CUDA, or macOS Apple Silicon." >&2
    exit 1 ;;
esac

# --- venv ---
if [[ ! -d "$VENV" ]]; then
  echo "[setup] creating venv at $VENV"
  mkdir -p "$(dirname "$VENV")"
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install --upgrade pip wheel >/dev/null

# --- torch (platform-specific) ---
echo "[setup] installing torch for $PLATFORM"
case "$PLATFORM" in
  linux-rocm)
    # Match the working stack on driveThree (memory: project_sensenova_u1_rocm.md):
    # torch 2.11+rocm7.2 with SDPA; flash_attn omitted on ROCm.
    "$VENV/bin/pip" install --upgrade --pre torch \
      --index-url https://download.pytorch.org/whl/nightly/rocm7.2
    ;;
  linux-cuda)
    "$VENV/bin/pip" install --upgrade torch \
      --index-url https://download.pytorch.org/whl/cu121
    ;;
  macos-arm64)
    # Apple Silicon: stock wheel ships MPS backend.
    "$VENV/bin/pip" install --upgrade torch
    ;;
esac

# --- SenseNova-U1 repo ---
if [[ ! -d "$REPO" ]]; then
  echo "[setup] cloning SenseNova-U1 to $REPO"
  git clone https://github.com/sensenova/SenseNova-U1 "$REPO"
fi
if [[ -f "$REPO/requirements.txt" ]]; then
  echo "[setup] installing repo requirements (some CUDA-only deps may no-op on ROCm/MPS — that's OK)"
  "$VENV/bin/pip" install -r "$REPO/requirements.txt" || true
fi

# --- weights ---
"$VENV/bin/pip" install --upgrade huggingface-hub >/dev/null

if [[ ! -d "$WEIGHTS_FINAL" || -z "$(ls -A "$WEIGHTS_FINAL" 2>/dev/null)" ]]; then
  echo "[setup] downloading 50-step weights (~33GB) to $WEIGHTS_FINAL"
  mkdir -p "$WEIGHTS_FINAL"
  "$VENV/bin/huggingface-cli" download sensenova/SenseNova-U1-8B-MoT \
    --local-dir "$WEIGHTS_FINAL"
fi

if [[ ! -d "$WEIGHTS_DRAFT" || -z "$(ls -A "$WEIGHTS_DRAFT" 2>/dev/null)" ]]; then
  echo "[setup] downloading 8-step preview weights (~33GB) to $WEIGHTS_DRAFT"
  mkdir -p "$WEIGHTS_DRAFT"
  "$VENV/bin/huggingface-cli" download sensenova/SenseNova-U1-8B-MoT-8step-preview \
    --local-dir "$WEIGHTS_DRAFT"
fi

echo
echo "[setup] done."
echo
echo "Configure open-palette with these env vars (add to ~/.bashrc or systemd service):"
echo "  export SENSENOVA_VENV=$VENV"
echo "  export SENSENOVA_REPO=$REPO"
echo "  export SENSENOVA_WEIGHTS_FINAL=$WEIGHTS_FINAL"
echo "  export SENSENOVA_WEIGHTS_DRAFT=$WEIGHTS_DRAFT"
echo
echo "Smoke test (after stopping ComfyUI):"
echo "  curl -X POST http://localhost:8000/api/infographic/render \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"template_id\":\"hub_and_spoke\",\"tier\":\"draft\",\"aspect\":\"1:1\",\"slots\":{\"title\":\"Test\",\"hub_desc\":\"x\",\"spokes\":[{\"label\":\"A\"},{\"label\":\"B\"},{\"label\":\"C\"},{\"label\":\"D\"}]}}'"
