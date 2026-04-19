"""Shared pytest fixtures for open-palette tests."""

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def temp_outputs(monkeypatch):
    """Redirect CWD to a temp dir for the duration of a test."""
    tmp = Path(tempfile.mkdtemp(prefix="wyltek-test-"))
    monkeypatch.chdir(tmp)
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)
