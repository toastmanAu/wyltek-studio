"""Tests for mesh_export (trimesh-based format conversion).

Verifies geometry survives round-trip and that unsupported formats raise.
"""

import importlib.util

import pytest
import trimesh

TRIMESH_AVAILABLE = importlib.util.find_spec("trimesh") is not None


@pytest.fixture
def src_glb(tmp_path):
    mesh = trimesh.creation.icosphere(subdivisions=2)
    out = tmp_path / "src.glb"
    mesh.export(str(out))
    return out


@pytest.mark.skipif(not TRIMESH_AVAILABLE, reason="trimesh not installed")
@pytest.mark.parametrize("fmt", ["stl", "obj", "ply", "glb"])
def test_export_to_each_supported_format(src_glb, tmp_path, fmt):
    from mesh_export import export_mesh, SUPPORTED_FORMATS

    assert fmt in SUPPORTED_FORMATS
    out = tmp_path / f"out.{fmt}"
    export_mesh(str(src_glb), str(out), fmt)
    assert out.exists()
    assert out.stat().st_size > 0

    # Round-trip: load result, vertex count should match source.
    src = trimesh.load(str(src_glb), force="mesh")
    dst = trimesh.load(str(out), force="mesh")
    assert len(dst.vertices) == len(src.vertices)


@pytest.mark.skipif(not TRIMESH_AVAILABLE, reason="trimesh not installed")
def test_unsupported_format_raises(src_glb, tmp_path):
    from mesh_export import export_mesh, UnsupportedFormatError

    out = tmp_path / "out.fbx"
    with pytest.raises(UnsupportedFormatError):
        export_mesh(str(src_glb), str(out), "fbx")


@pytest.mark.skipif(not TRIMESH_AVAILABLE, reason="trimesh not installed")
def test_missing_input_raises(tmp_path):
    from mesh_export import export_mesh

    with pytest.raises(FileNotFoundError):
        export_mesh(str(tmp_path / "missing.glb"), str(tmp_path / "out.stl"), "stl")
