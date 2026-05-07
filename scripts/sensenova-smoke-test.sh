#!/usr/bin/env bash
# SenseNova-U1 T2I smoke test on driveThree (RX 7900 XTX, ROCm 7.2).
#
# Two checkpoint variants supported:
#   - 50-step base   (sensenova/SenseNova-U1-8B-MoT)            — high quality, ~5 min/render
#   - 8-step preview (sensenova/SenseNova-U1-8B-MoT-8step-preview) — distilled, ~50-70s/render
#
# Both use the same patched inference.py (device_map="auto") and the same v1
# locked prompt — direct A/B comparable.
#
# PREREQUISITE: stop ComfyUI + Wyltek to free ~14GB VRAM:
#   systemctl --user stop comfyui.service open-palette.service
# Restart after with:
#   systemctl --user start comfyui.service open-palette.service
#
# Usage:
#   ./scripts/sensenova-smoke-test.sh             # default: 50-step base, 2048x2048
#   ./scripts/sensenova-smoke-test.sh 8step       # 8-step preview, 2048x2048
#   ./scripts/sensenova-smoke-test.sh fallback    # 50-step base, 1024x1024 (OOM rescue)
#   ./scripts/sensenova-smoke-test.sh 8step-fast  # 8-step preview, 1024x1024 (rapid iteration)

set -euo pipefail

VENV=/data/venvs/sensenova-u1
REPO=$HOME/SenseNova-U1
OUT_DIR=$HOME/open-palette/outputs/sensenova
mkdir -p "$OUT_DIR"

# v1 expanded prompt — locked from playground run 001. See
# wyltek-infographic-log.md for provenance. Identical input across variants
# enables direct A/B comparison.
PROMPT='The theme of the infographic is "Wyltek Studio", executed in a playful, modern flat illustration style inspired by children'\''s science books and editorial Notion cover art. The overall layout is a symmetrical hub-and-spoke configuration, featuring a central focal point with six equidistant radiating spokes at 12, 2, 4, 6, 8, and 10 o'\''clock positions. The background is a crisp, soft cream paper texture with a subtle, delicate dotted grid overlay. The title "Wyltek Studio" is prominently displayed in a bold, rounded sans-serif font within the center hub, which contains a friendly, multi-colored cartoon robot mascot smiling broadly, grasping a painter'\''s brush in its right mechanical hand and a vintage microphone in its left. The six radiating spokes are arranged clockwise: At 12 o'\''clock, a mint green circular icon contains a smiling picture frame holding a paintbrush. Above the icon, the text "Frames" is written in a clean, rounded font, with the tagline "Text to Image" placed directly underneath in a smaller, monospaced typeface. At 2 o'\''clock, a sky blue circular icon features a cartoon magic eraser actively rubbing away a blurred section of a photograph. Above it, the text "Image Edit" is displayed, with the tagline "Remove and Fill" positioned below. At 4 o'\''clock, a sunshine yellow circular icon shows three cartoon dice, each face displaying a different photographic texture, captured in a mid-air shuffle. Above the icon is the text "Remix", with the tagline "Image Variations" below. At 6 o'\''clock, a lavender purple circular icon depicts a pair of sleek headphones surrounded by floating musical notes and vibrant, rhythmic sound waves. Above the icon is the text "Music", with the tagline "Text to Music" beneath it. At 8 o'\''clock, a coral pink circular icon features a cartoon dynamic microphone with a large, expressive speech bubble extending from its mesh head. Above the icon is the text "Voice", with the tagline "Text to Speech" situated below. At 10 o'\''clock, a peach orange circular icon showcases a floating, glowing wireframe planet with a tiny, stylized spaceship orbiting its equator. Above the icon is the text "WorldGen", with the tagline "Text to 3D" centered beneath it. All elements utilize thick, consistent black outlines. Each spoke maintains a specific, harmonious pastel color palette (mint green, sky blue, sunshine yellow, lavender purple, coral pink, and peach orange) to delineate categories. Gentle, soft drop shadows are applied to the hub and spokes to create a sense of depth against the cream background. The composition is highly balanced, emphasizing abundant white space to ensure maximum readability and a professional, approachable visual flow.'

VARIANT="${1:-50step}"
case "$VARIANT" in
  50step|"")
    WEIGHTS=/data/sensenova-u1-weights
    STEPS=50
    WIDTH=2048; HEIGHT=2048
    TAG=50step-2048
    ;;
  8step)
    WEIGHTS=/data/sensenova-u1-weights-8step
    STEPS=8
    WIDTH=2048; HEIGHT=2048
    TAG=8step-2048
    ;;
  fallback)
    WEIGHTS=/data/sensenova-u1-weights
    STEPS=50
    WIDTH=1024; HEIGHT=1024
    TAG=50step-1024-fallback
    ;;
  8step-fast)
    WEIGHTS=/data/sensenova-u1-weights-8step
    STEPS=8
    WIDTH=1024; HEIGHT=1024
    TAG=8step-1024
    ;;
  *)
    echo "Unknown variant: $VARIANT (expected: 50step | 8step | fallback | 8step-fast)" >&2
    exit 2
    ;;
esac

OUT=$OUT_DIR/wyltek-v1-${TAG}-$(date +%Y%m%d-%H%M%S).png

echo "[smoke] variant=$VARIANT  weights=$WEIGHTS  steps=$STEPS  res=${WIDTH}x${HEIGHT}"
echo "[smoke] output -> $OUT"

# attn_backend=auto picks SDPA when flash_attn isn't installed (it isn't).
# Seed pinned to 42 for direct A/B reproducibility across variants.
START=$SECONDS
"$VENV/bin/python" "$REPO/examples/t2i/inference.py" \
  --model_path "$WEIGHTS" \
  --prompt "$PROMPT" \
  --width "$WIDTH" \
  --height "$HEIGHT" \
  --output "$OUT" \
  --num_steps "$STEPS" \
  --cfg_scale 4.0 \
  --seed 42 \
  --device cuda \
  --dtype bfloat16 \
  --attn_backend auto
ELAPSED=$((SECONDS - START))

echo
echo "[smoke] DONE in ${ELAPSED}s : $OUT"
echo "[smoke] reminder: systemctl --user start comfyui.service open-palette.service"
