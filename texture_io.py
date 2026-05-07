"""GLB texture extraction & swap — Path B of the 3D re-texture feature.

Pure-function module. Reads/writes the baseColor PNG embedded in a GLB
without disturbing geometry, UVs, or other PBR channels (metallicRoughness,
normal, occlusion, emissive). Used by the `/api/3d/extract-texture` and
`/api/3d/apply-texture` endpoints.

Design notes
------------
- We use `pygltflib` rather than trimesh's higher-level API so the swap
  is byte-stable: trimesh's GLB exporter re-encodes geometry, while
  pygltflib lets us mutate the bufferView slice that holds the PNG and
  leave everything else untouched.
- Only `baseColor` is supported in v1. Multi-material GLBs are addressable
  via `material_index`, default 0 (TRELLIS / Hy3D output is single-material).
"""

import io
from pathlib import Path

from pygltflib import GLTF2
from PIL import Image


def _resolve_basecolor_image_idx(gltf: GLTF2, material_index: int) -> int:
    """Walk material → texture → image to find the GLB image index that
    backs the baseColor of the requested material."""
    if material_index >= len(gltf.materials):
        raise ValueError(
            f"material_index {material_index} out of range "
            f"(GLB has {len(gltf.materials)} materials)"
        )
    mat = gltf.materials[material_index]
    pbr = mat.pbrMetallicRoughness
    if pbr is None or pbr.baseColorTexture is None:
        raise ValueError(
            f"Material {material_index} has no baseColorTexture — nothing to extract"
        )
    return gltf.textures[pbr.baseColorTexture.index].source


def extract_basecolor(glb_path: Path, material_index: int = 0) -> tuple[bytes, int, int]:
    """Extract the baseColor PNG from a GLB.

    Returns
    -------
    (png_bytes, width, height)
        Raw PNG bytes ready to write to disk or pipe to a 2D editor, plus
        the pixel dimensions so the caller can validate a later apply.
    """
    gltf = GLTF2().load(str(glb_path))
    img_idx = _resolve_basecolor_image_idx(gltf, material_index)
    image = gltf.images[img_idx]

    if image.bufferView is None:
        raise ValueError(
            "Image has no bufferView — only embedded GLB textures are supported in v1"
        )

    bv = gltf.bufferViews[image.bufferView]
    binary = gltf.binary_blob()
    offset = bv.byteOffset or 0
    png_bytes = bytes(binary[offset:offset + bv.byteLength])

    decoded = Image.open(io.BytesIO(png_bytes))
    return png_bytes, decoded.width, decoded.height


def _pad_to_4(data: bytes) -> bytes:
    """GLB binary slices must align to 4-byte boundaries; pad with zeros."""
    pad = (-len(data)) % 4
    return data + b"\x00" * pad


def composite_with_mask(
    generated: "Image.Image",
    base: "Image.Image",
    mask: "Image.Image",
) -> "Image.Image":
    """Blend `generated` into `base` only where `mask` is non-zero.

    Used by the atlas-SAM re-texture flow: the user marks a region on the
    atlas (SAM mask), runs Style Remix on the whole atlas (the only thing
    IP-Adapter can do), then composites the generated output back into
    the base atlas, keeping unmasked regions byte-stable.

    `base` dictates the output dimensions — its UVs are what the GLB's
    bufferViews already point at, so growing or shrinking would break
    the texture mapping. `generated` and `mask` are resampled to match.
    `mask` must be a single-channel ('L'); grey values produce
    proportional blends rather than a hard threshold.
    """
    base_rgb = base.convert("RGB")
    target_size = base_rgb.size

    gen_rgb = generated.convert("RGB")
    if gen_rgb.size != target_size:
        gen_rgb = gen_rgb.resize(target_size, Image.LANCZOS)

    mask_l = mask.convert("L")
    if mask_l.size != target_size:
        mask_l = mask_l.resize(target_size, Image.LANCZOS)

    return Image.composite(gen_rgb, base_rgb, mask_l)


def apply_basecolor(
    source_glb: Path,
    new_png: bytes,
    out_glb: Path,
    material_index: int = 0,
) -> Path:
    """Write `out_glb` = `source_glb` with the baseColor PNG replaced.

    Geometry, UVs, and other PBR channels (metallicRoughness, normal,
    occlusion, emissive) are byte-stable. Only the bufferView holding
    the baseColor PNG is rewritten; bufferViews positioned after it
    shift by the size delta so accessors keep reading the right bytes.
    """
    # Reject non-square replacements up front: UV layouts are normalized
    # to a square atlas in TRELLIS / Hy3D output, and a non-square input
    # almost always means the user accidentally ran the atlas through a
    # 2D pipeline that didn't preserve aspect (e.g. inpaint with default
    # output dims). Failing fast here is friendlier than silently
    # distorting the texture mapping.
    probe = Image.open(io.BytesIO(new_png))
    if probe.width != probe.height:
        raise ValueError(
            f"Replacement texture must be square; got {probe.width}x{probe.height}"
        )

    gltf = GLTF2().load(str(source_glb))
    img_idx = _resolve_basecolor_image_idx(gltf, material_index)
    image = gltf.images[img_idx]

    if image.bufferView is None:
        raise ValueError(
            "Image has no bufferView — only embedded GLB textures are supported in v1"
        )

    target_bv = gltf.bufferViews[image.bufferView]
    binary = bytes(gltf.binary_blob())

    old_offset = target_bv.byteOffset or 0
    old_len = target_bv.byteLength
    # Padded length of the OLD slot, to find where the next bv starts.
    old_padded_len = (old_len + 3) & ~3

    new_padded = _pad_to_4(new_png)
    delta = len(new_padded) - old_padded_len

    # Splice the binary buffer.
    new_binary = (
        binary[:old_offset]
        + new_padded
        + binary[old_offset + old_padded_len:]
    )

    # Update the image's bufferView: new (unpadded) length, same offset.
    target_bv.byteLength = len(new_png)

    # Shift every other bufferView that started after this one.
    for i, other in enumerate(gltf.bufferViews):
        if i == image.bufferView:
            continue
        other_off = other.byteOffset or 0
        if other_off > old_offset:
            other.byteOffset = other_off + delta

    # Update the single backing buffer's total length.
    if gltf.buffers:
        gltf.buffers[0].byteLength = len(new_binary)
    gltf.set_binary_blob(new_binary)
    gltf.save(str(out_glb))
    return out_glb
