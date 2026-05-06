"""Tests for backends.sensenova (HTTP-client wrapper around the worker).

The worker itself is exercised end-to-end in test_sensenova_worker.py;
these tests focus on the prompt/image resolver and the dispatch logic
that decides T2I vs interleave routing without actually hitting the
worker (we patch the client module).
"""
from pathlib import Path
import pytest

from backends.sensenova import (
    SenseNovaError, _resolve_image_refs, _resolve_dims, generate,
    ASPECT_BUCKETS,
)


# -----------------------------------------------------------------------------
# Image-ref resolver
# -----------------------------------------------------------------------------

def test_resolve_skips_unreferenced_image():
    """User uploads img1, img2, img3 but only references [Image 1] and
    [Image 3]. img2 must NOT leak into the model's image array; the two
    <image> tokens should map to img1 and img3 in left-to-right order."""
    rewritten, used = _resolve_image_refs(
        "header [Image 1] divider [Image 3] footer",
        ["/u/img1.png", "/u/img2.png", "/u/img3.png"],
    )
    assert rewritten == "header <image> divider <image> footer"
    assert used == ["/u/img1.png", "/u/img3.png"]


def test_resolve_handles_duplicate_refs():
    """Same ref used twice → image array gets two copies, both <image>
    tokens then positionally bind to the same physical image."""
    rewritten, used = _resolve_image_refs(
        "[Image 1] vs [Image 1] again",
        ["/u/only.png"],
    )
    assert rewritten == "<image> vs <image> again"
    assert used == ["/u/only.png", "/u/only.png"]


def test_resolve_leaves_out_of_range_unresolved():
    """Reference to nonexistent image stays as literal text — visible
    to the user in the assembled prompt rather than silently dropped."""
    rewritten, used = _resolve_image_refs(
        "good [Image 1] bad [Image 5]",
        ["/u/only.png"],
    )
    assert rewritten == "good <image> bad [Image 5]"
    assert used == ["/u/only.png"]


def test_resolve_no_refs_in_prompt():
    """Prompt without any [Image N] tokens: nothing in image array even
    if uploads were supplied — routes the request to T2I (lighter)."""
    rewritten, used = _resolve_image_refs(
        "Plain text prompt with no refs",
        ["/u/orphan.png"],
    )
    assert rewritten == "Plain text prompt with no refs"
    assert used == []


# -----------------------------------------------------------------------------
# Aspect-ratio resolver
# -----------------------------------------------------------------------------

def test_resolve_dims_default_is_square():
    assert _resolve_dims(None) == (1536, 1536)


def test_resolve_dims_known_buckets():
    for aspect, dims in ASPECT_BUCKETS.items():
        assert _resolve_dims(aspect) == dims


def test_resolve_dims_unknown_raises():
    with pytest.raises(SenseNovaError, match="not in"):
        _resolve_dims("7:5")


# -----------------------------------------------------------------------------
# Dispatch logic — patches sensenova_client to avoid hitting the worker
# -----------------------------------------------------------------------------

class _FakeClient:
    """In-memory stand-in for the HTTP client. Records calls."""
    def __init__(self, png_path: Path):
        self._png = png_path
        self.t2i_calls: list[dict] = []
        self.interleave_calls: list[dict] = []

    async def render_t2i(self, **kwargs):
        self.t2i_calls.append(kwargs)
        return self._png

    async def render_interleave(self, **kwargs):
        self.interleave_calls.append(kwargs)
        return self._png


@pytest.fixture
def fake_client(monkeypatch, tmp_path):
    out_png = tmp_path / "out.png"
    out_png.write_bytes(b"\x89PNG\r\n\x1a\n")  # placeholder
    fake = _FakeClient(out_png)
    monkeypatch.setattr("backends.sensenova.sensenova_client.render_t2i",
                        fake.render_t2i)
    monkeypatch.setattr("backends.sensenova.sensenova_client.render_interleave",
                        fake.render_interleave)
    return fake


@pytest.mark.asyncio
async def test_no_images_routes_to_t2i(fake_client, tmp_path):
    png = await generate(
        prompt="A single text prompt", image_paths=[],
        aspect="16:9", seed=42, tier="final",
        output_dir=tmp_path,
    )
    assert png.name == "out.png"
    assert len(fake_client.t2i_calls) == 1
    assert len(fake_client.interleave_calls) == 0
    call = fake_client.t2i_calls[0]
    assert call["width"] == 2048 and call["height"] == 1152
    assert call["prompt"] == "A single text prompt"


@pytest.mark.asyncio
async def test_uploaded_but_unreferenced_images_routes_to_t2i(fake_client, tmp_path):
    """Bare uploads with no [Image N] in prompt should still go T2I."""
    await generate(
        prompt="No refs here", image_paths=["/u/orphan.png"],
        aspect=None, seed=7, tier="final",
        output_dir=tmp_path,
    )
    assert len(fake_client.t2i_calls) == 1
    assert len(fake_client.interleave_calls) == 0


@pytest.mark.asyncio
async def test_referenced_images_routes_to_interleave(fake_client, tmp_path):
    await generate(
        prompt="show [Image 1] next to [Image 2]",
        image_paths=["/u/a.png", "/u/b.png"],
        aspect="1:1", seed=42, tier="final",
        output_dir=tmp_path,
    )
    assert len(fake_client.interleave_calls) == 1
    assert len(fake_client.t2i_calls) == 0
    call = fake_client.interleave_calls[0]
    assert call["image_paths"] == ["/u/a.png", "/u/b.png"]
    assert call["prompt"] == "show <image> next to <image>"


@pytest.mark.asyncio
async def test_unknown_aspect_raises(tmp_path):
    with pytest.raises(SenseNovaError, match="not in"):
        await generate(
            prompt="x", image_paths=[],
            aspect="bogus", seed=42, tier="final",
            output_dir=tmp_path,
        )


@pytest.mark.asyncio
async def test_worker_error_wrapped(monkeypatch, tmp_path):
    from backends.sensenova_client import SenseNovaWorkerError

    async def _raise(**_kwargs):
        raise SenseNovaWorkerError("worker unreachable: connection refused")

    monkeypatch.setattr("backends.sensenova.sensenova_client.render_t2i", _raise)

    with pytest.raises(SenseNovaError, match="worker unreachable"):
        await generate(
            prompt="x", image_paths=[],
            aspect="1:1", seed=42, tier="final",
            output_dir=tmp_path,
        )
