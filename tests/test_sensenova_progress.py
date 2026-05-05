import asyncio
from pathlib import Path
from unittest.mock import patch
import pytest
from backends import sensenova


class _FakeProc:
    def __init__(self, dur, output_dir):
        self._dur, self._output_dir = dur, output_dir
        self.stdout = self; self.returncode = 0; self._sent = False
    def __aiter__(self): return self
    async def __anext__(self):
        if self._sent: raise StopAsyncIteration
        self._sent = True
        await asyncio.sleep(self._dur)
        (self._output_dir / "out.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        return b""
    async def wait(self): return 0
    def terminate(self): return None


@pytest.mark.asyncio
async def test_generate_emits_progress_creep(tmp_path):
    seen: list[tuple[int, str]] = []
    async def cb(pct, msg=""): seen.append((pct, msg))

    async def _spawn(*a, **kw): return _FakeProc(5, tmp_path)
    with patch.object(sensenova, "_validate_environment", lambda: None), \
         patch.object(sensenova, "_start_subprocess", _spawn):
        await sensenova.generate(
            prompt="x", image_paths=[], aspect="1:1", seed=0,
            tier="draft", output_dir=tmp_path, on_progress=cb, timeout_s=10)

    pcts = [p for p, _ in seen]
    assert pcts[0] <= 10
    assert any(p > 10 for p in pcts), f"expected creep > 10, got {pcts}"
    assert pcts[-1] >= 95
