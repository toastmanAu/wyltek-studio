"""Tests for the per-engine/mode 3D timeout resolver.

Property under test: every entry has outer = inner + slack so that a healthy
ComfyUI run inside the inner timeout never trips the outer wait_for.
"""

from server import resolve_3d_timeouts, _3D_OUTER_HANDOFF_SLACK, _3D_INNER_TIMEOUT_DEFAULT


def test_trellis_textured_outer_exceeds_inner_with_slack():
    outer, inner = resolve_3d_timeouts("trellis", "textured")
    assert inner == 3000
    assert outer == inner + _3D_OUTER_HANDOFF_SLACK


def test_hy3d_pbr_has_real_room():
    """Hy3D PBR is ~3-5 min typical but can hit ~30 min on max settings;
    inner must be sized for the long tail, not the median."""
    outer, inner = resolve_3d_timeouts("hy3d", "pbr")
    assert inner >= 1800, f"Hy3D PBR inner={inner}; needs >=1800s"


def test_unknown_combo_falls_back():
    outer, inner = resolve_3d_timeouts("magic-box-3d", "ultra-mode")
    assert inner == _3D_INNER_TIMEOUT_DEFAULT
    assert outer == inner + _3D_OUTER_HANDOFF_SLACK


def test_outer_always_strictly_greater_than_inner():
    """Property: every entry must satisfy outer > inner so a healthy run
    finishes inside the inner cap before the outer fires."""
    for engine in ("trellis", "hy3d"):
        for mode in ("textured", "shape", "pbr"):
            outer, inner = resolve_3d_timeouts(engine, mode)
            assert outer > inner, f"{engine}/{mode}: outer={outer} not > inner={inner}"
