"""Unit tests for remix input resolvers."""

from pathlib import Path

import pytest

# Import resolvers at module-load time (cwd = project root, where static/ exists).
from server import resolve_crypto_logo, resolve_gallery_image


def _make_storage(tmp_path: Path) -> Path:
    storage = tmp_path / "storage"
    (storage / "crypto-logos").mkdir(parents=True)
    (storage / "unsorted" / "2026-04-19" / "images").mkdir(parents=True)
    (storage / "projects").mkdir(parents=True)
    (storage / "crypto-logos" / "bitcoin-btc.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (storage / "unsorted" / "2026-04-19" / "images" / "abc12345.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return storage


def test_resolve_crypto_logo_hits_storage_subdir(tmp_path, monkeypatch):
    _make_storage(tmp_path)
    monkeypatch.chdir(tmp_path)
    path = resolve_crypto_logo("bitcoin-btc")
    assert path is not None
    assert path.name == "bitcoin-btc.png"


def test_resolve_crypto_logo_missing_returns_none(tmp_path, monkeypatch):
    _make_storage(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert resolve_crypto_logo("ripple-xrp") is None


def test_resolve_crypto_logo_rejects_path_traversal(tmp_path, monkeypatch):
    _make_storage(tmp_path)
    monkeypatch.chdir(tmp_path)
    assert resolve_crypto_logo("../unsorted/2026-04-19/images/abc12345") is None
    assert resolve_crypto_logo("..") is None
    assert resolve_crypto_logo("a/b") is None


def test_resolve_gallery_image_hits_unsorted(tmp_path, monkeypatch):
    storage = _make_storage(tmp_path)
    import storage as store
    monkeypatch.setattr(store, "STORAGE_ROOT", storage)
    path = resolve_gallery_image("abc12345.png")
    assert path is not None
    assert path.name == "abc12345.png"


def test_resolve_gallery_image_missing_returns_none(tmp_path, monkeypatch):
    storage = _make_storage(tmp_path)
    import storage as store
    monkeypatch.setattr(store, "STORAGE_ROOT", storage)
    assert resolve_gallery_image("does_not_exist.png") is None
