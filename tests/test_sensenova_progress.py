"""Progress-callback test for backends.sensenova.

The previous test mocked subprocess internals; the architecture is now a
persistent HTTP worker, so we mock the client call instead and verify
that ``generate`` emits the expected progress sequence: an initial
``rendering`` anchor, SmoothProgress creep, and a terminal ``done``.
"""
import asyncio
from pathlib import Path
import pytest
from backends import sensenova


@pytest.mark.asyncio
async def test_generate_emits_progress_creep(tmp_path, monkeypatch):
    seen: list[tuple[int, str]] = []

    async def cb(pct: int, msg: str = "") -> None:
        seen.append((pct, msg))

    async def fake_t2i(**kwargs):
        # Simulate a few seconds of model work; SmoothProgress should creep
        # progress upward in the meantime.
        await asyncio.sleep(5)
        out = Path(kwargs["output_dir"]) / "out.png"
        out.write_bytes(b"\x89PNG\r\n\x1a\n")
        return out

    monkeypatch.setattr(
        "backends.sensenova.sensenova_client.render_t2i", fake_t2i)

    await sensenova.generate(
        prompt="x", image_paths=[], aspect="1:1", seed=0,
        tier="final", output_dir=tmp_path, on_progress=cb,
    )

    pcts = [p for p, _ in seen]
    assert pcts[0] <= 10, f"first emit should anchor near 10, got {pcts[0]}"
    assert any(p > 10 for p in pcts), f"expected creep > 10, got {pcts}"
    assert pcts[-1] == 100, f"last emit should be 100=done, got {pcts}"
