"""Tests for texture_io — Path B (texture swap) of 3D re-texture feature.

Covers extracting the baseColor PNG from a GLB and swapping it back in
without disturbing geometry, UVs, or other PBR channels.

Fixtures are built programmatically via trimesh so the tests don't depend
on any pre-existing GLB on disk.
"""

import io
from pathlib import Path

import numpy as np
import pytest
import trimesh
from PIL import Image


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_checker_png(size: int = 64, color_a: tuple = (255, 0, 0),
                      color_b: tuple = (0, 0, 255)) -> bytes:
    """Tiny 2-color checker PNG. We use this both as the baseline texture
    and as a sentinel for the 'replacement' texture in apply tests."""
    img = Image.new("RGB", (size, size), color_a)
    half = size // 2
    for x in range(size):
        for y in range(size):
            if (x // (half // 2 or 1) + y // (half // 2 or 1)) % 2:
                img.putpixel((x, y), color_b)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_textured_glb(out_path: Path, texture_png: bytes,
                        texture_size: int = 64) -> Path:
    """Build a unit-cube GLB with a single material whose baseColorTexture
    is the given PNG. Uses trimesh's primitives + visual API so the test
    has a known-good GLB without any external fixture file."""
    mesh = trimesh.creation.box(extents=(1, 1, 1))
    # Trimesh needs a PIL image for the texture, plus per-vertex UVs.
    pil = Image.open(io.BytesIO(texture_png))
    # Cube has 8 verts; flat UVs are fine for a smoke fixture (no texture
    # quality assertion — just round-trip integrity).
    uv = np.tile([[0.0, 0.0]], (len(mesh.vertices), 1))
    mesh.visual = trimesh.visual.TextureVisuals(
        uv=uv,
        image=pil,
    )
    mesh.export(out_path)
    return out_path


# ---------------------------------------------------------------------------
# extract_basecolor
# ---------------------------------------------------------------------------

def test_extract_basecolor_returns_png_bytes_and_dims(tmp_path):
    """extract_basecolor pulls the embedded PNG out of a GLB and reports
    the texture's pixel dimensions so the caller can validate a later
    apply step against the same atlas size."""
    from texture_io import extract_basecolor

    src_png = _make_checker_png(size=64)
    glb = _build_textured_glb(tmp_path / "fixture.glb", src_png)

    png_bytes, width, height = extract_basecolor(glb, material_index=0)

    assert width == 64
    assert height == 64
    # Round-trip: the extracted PNG should decode to the same dimensions.
    decoded = Image.open(io.BytesIO(png_bytes))
    assert decoded.size == (64, 64)


# ---------------------------------------------------------------------------
# apply_basecolor
# ---------------------------------------------------------------------------

def test_apply_basecolor_writes_new_glb_with_swapped_texture(tmp_path):
    """apply_basecolor produces a new GLB whose baseColor decodes to the
    new PNG, while geometry (vertex count) is preserved verbatim."""
    from texture_io import extract_basecolor, apply_basecolor

    # Build fixture with red/blue checker
    original_png = _make_checker_png(size=64, color_a=(255, 0, 0), color_b=(0, 0, 255))
    src_glb = _build_textured_glb(tmp_path / "src.glb", original_png)

    # Replacement: green/yellow checker, same size
    replacement_png = _make_checker_png(
        size=64, color_a=(0, 255, 0), color_b=(255, 255, 0)
    )

    out_glb = tmp_path / "out.glb"
    apply_basecolor(src_glb, replacement_png, out_glb, material_index=0)

    # The new GLB's baseColor should be the replacement, not the original.
    extracted, w, h = extract_basecolor(out_glb, material_index=0)
    assert (w, h) == (64, 64)
    extracted_img = Image.open(io.BytesIO(extracted)).convert("RGB")
    # Sample center pixel — replacement is green or yellow, original was
    # red or blue. Either replacement colour is acceptable; neither
    # original colour is.
    sampled = set()
    for x in (8, 24, 40, 56):
        for y in (8, 24, 40, 56):
            sampled.add(extracted_img.getpixel((x, y)))
    assert sampled.issubset({(0, 255, 0), (255, 255, 0)}), (
        f"baseColor was not replaced — sampled pixels: {sampled}"
    )

    # Geometry preservation: vertex count via trimesh load should match.
    src_loaded = trimesh.load(src_glb, force="mesh")
    out_loaded = trimesh.load(out_glb, force="mesh")
    assert len(src_loaded.vertices) == len(out_loaded.vertices)
    assert len(src_loaded.faces) == len(out_loaded.faces)


def test_apply_basecolor_accepts_square_input_at_any_resolution(tmp_path):
    """Policy C: any square replacement PNG is accepted as-is. UVs are
    normalized [0,1] so atlas resolution is free to grow or shrink. A
    higher-res replacement gives sharper output for free."""
    from texture_io import extract_basecolor, apply_basecolor

    # Source atlas: 64x64
    src_png = _make_checker_png(size=64)
    src_glb = _build_textured_glb(tmp_path / "src.glb", src_png)

    # Replacement: 128x128 — bigger than source, still square
    larger_png = _make_checker_png(size=128, color_a=(0, 200, 0), color_b=(0, 80, 0))

    out_glb = tmp_path / "out.glb"
    apply_basecolor(src_glb, larger_png, out_glb)

    _, w, h = extract_basecolor(out_glb)
    assert (w, h) == (128, 128), "output atlas should match the replacement, not the source"


def test_apply_basecolor_rejects_non_square_input(tmp_path):
    """Policy C: non-square replacement is almost always a mistake (the
    user ran the atlas through a non-aspect-preserving 2D pipeline).
    Fail fast rather than silently distort the texture."""
    from texture_io import apply_basecolor

    src_png = _make_checker_png(size=64)
    src_glb = _build_textured_glb(tmp_path / "src.glb", src_png)

    # Build a 64x32 PNG manually — _make_checker_png is square-only.
    img = Image.new("RGB", (64, 32), (128, 128, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    non_square = buf.getvalue()

    with pytest.raises(ValueError, match="square"):
        apply_basecolor(src_glb, non_square, tmp_path / "out.glb")


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# composite_with_mask  (atlas re-texture path)
# ---------------------------------------------------------------------------

def test_composite_with_mask_replaces_only_white_regions(tmp_path):
    """Inside the mask (white pixels) the GENERATED image wins; outside
    the mask (black pixels) the BASE wins. This is what the atlas-SAM
    flow needs: SAM marks 'restyle this region', mask gates the swap."""
    from texture_io import composite_with_mask

    # Base atlas: solid red. Generated remix: solid green. Mask: half
    # white (left), half black (right). Expected: left half green
    # (replaced from generated), right half red (preserved from base).
    base = Image.new("RGB", (32, 32), (255, 0, 0))
    generated = Image.new("RGB", (32, 32), (0, 255, 0))
    mask = Image.new("L", (32, 32), 0)
    for x in range(16):
        for y in range(32):
            mask.putpixel((x, y), 255)

    out = composite_with_mask(generated, base, mask)
    assert out.size == (32, 32)
    assert out.getpixel((4, 16)) == (0, 255, 0), "left half should be green (generated)"
    assert out.getpixel((28, 16)) == (255, 0, 0), "right half should be red (preserved)"


def test_composite_with_mask_resamples_mismatched_dims(tmp_path):
    """Mask comes from SAM at the atlas-display resolution, which may not
    match the actual atlas size if the user resized. The composite must
    resample mask + generated to the base atlas dims so UV mapping stays
    consistent — the base dims are the source of truth."""
    from texture_io import composite_with_mask

    base = Image.new("RGB", (64, 64), (10, 10, 10))
    generated = Image.new("RGB", (32, 32), (200, 200, 200))  # half-res
    mask = Image.new("L", (32, 32), 255)  # all-replace, half-res

    out = composite_with_mask(generated, base, mask)
    assert out.size == (64, 64), "output should match base dims, not generated"


def test_composite_with_mask_anti_aliases_mask_edges(tmp_path):
    """Grey pixels in the mask (e.g. SAM edge antialiasing) should produce
    proportional blends — not a hard threshold. PIL.composite handles
    this naturally; this test pins the behaviour so it doesn't regress
    if the implementation switches to e.g. bitmask-only."""
    from texture_io import composite_with_mask

    base = Image.new("RGB", (4, 4), (0, 0, 0))
    generated = Image.new("RGB", (4, 4), (200, 200, 200))
    # Mask = uniform grey (50% blend) → result should be ~100,100,100.
    mask = Image.new("L", (4, 4), 128)

    out = composite_with_mask(generated, base, mask)
    r, g, b = out.getpixel((1, 1))
    # PIL.composite uses int math — accept ±2 for rounding.
    assert 98 <= r <= 102, f"expected ~100, got {r}"
    assert 98 <= g <= 102
    assert 98 <= b <= 102


def test_extract_basecolor_raises_on_no_basecolor_texture(tmp_path):
    """A GLB with no baseColorTexture (e.g. plain-coloured PBR material)
    has nothing to extract — fail with a clear, caller-actionable message."""
    from texture_io import extract_basecolor

    # Build an untextured cube.
    mesh = trimesh.creation.box(extents=(1, 1, 1))
    glb = tmp_path / "untextured.glb"
    mesh.export(glb)

    with pytest.raises(ValueError, match="baseColorTexture|materials"):
        extract_basecolor(glb)
