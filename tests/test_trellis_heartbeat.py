"""Tests for the TRELLIS DiT progress-heartbeat formatting.

The heartbeat itself is a closure inside generate_trellis (driven by aiohttp
WS events), so the unit-testable surface is the ETA formatter that backs
its user-facing message.
"""

from backends.comfyui import _fmt_eta


def test_fmt_eta_subminute_drops_minutes():
    assert _fmt_eta(0) == "0s"
    assert _fmt_eta(1) == "1s"
    assert _fmt_eta(59) == "59s"


def test_fmt_eta_zero_pads_seconds_in_mmss():
    assert _fmt_eta(60) == "1m00s"
    assert _fmt_eta(75) == "1m15s"
    assert _fmt_eta(3599) == "59m59s"


def test_fmt_eta_negative_clamped_to_zero():
    """Avg×remaining can briefly go slightly negative on the last step
    when avg is stale; never surface a negative ETA."""
    assert _fmt_eta(-5) == "0s"


def test_fmt_eta_truncates_subsecond_floats():
    assert _fmt_eta(14.7) == "14s"
    assert _fmt_eta(120.9) == "2m00s"
