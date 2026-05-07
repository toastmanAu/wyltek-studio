"""Single source of truth for model architecture classification.

Used by the UI to ghost incompatible model/LoRA/IP-Adapter combinations in
Compare mode. The existing generate path in comfyui.py keeps its own inline
sniffs for workflow branching — this helper is additive, not a refactor.

Returns one of:
  "sdxl"  | "sd15" | "sd3"   | "sd35"  |
  "flux"  | "klein"| "pixart"| "other"

`"lightning"` is a family of SDXL distillations, reported as "sdxl" here so
LoRA/IP-Adapter compat checks work transparently.
"""
from __future__ import annotations
import re

# Ordered substring hints — first match wins; more specific before more general.
_HINTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("klein",),                        "klein"),   # flux 2 klein
    (("flux2", "flux-2"),               "flux"),    # flux 2 family
    (("pixart",),                       "pixart"),
    (("sd3.5", "sd35", "sd3_5"),        "sd35"),
    (("sd3",),                          "sd3"),
    (("flux",),                         "flux"),
    (("sdxl",),                         "sdxl"),
    (("sd15", "v1-5", "v1_5"),          "sd15"),
)

# Separate regex for SDXL-by-naming-convention. Filenames in the wild use the
# `xl` suffix with any separator (or none): `juggernautXL_v9`, `realvisxl-v4`,
# `pixel-art-xl.safetensors`, `dreamshaper-xl-v21`. Any `xl` NOT followed by a
# letter (so `xlarge` / `mxlayer` don't match) is good enough in practice.
_XL_SUFFIX = re.compile(r"xl(?![a-z])")


def arch_of(name: str | None) -> str:
    """Classify a checkpoint / UNet / LoRA / IP-Adapter filename by family.

    Falls back to "other" when no hint matches — the UI treats "other" as
    universally compatible so we don't accidentally ghost something valid.
    """
    if not name:
        return "other"
    n = name.lower()
    for needles, tag in _HINTS:
        if any(h in n for h in needles):
            return tag
    if _XL_SUFFIX.search(n):
        return "sdxl"
    return "other"


def compatible(model_arch: str, lora_arch: str) -> bool:
    """Is a model with `model_arch` safe to combine with a LoRA (or
    IP-Adapter) of `lora_arch`?

    - "other" on either side is treated as a wildcard (don't ghost).
    - SDXL LoRAs apply to SDXL base only (the "lightning" subfamily is
      also classified as "sdxl").
    - Everything else must match exactly.
    """
    if model_arch == "other" or lora_arch == "other":
        return True
    return model_arch == lora_arch
