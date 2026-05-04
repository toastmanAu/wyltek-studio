"""Tests for mesh_optimize (pymeshlab-backed decimation/smoothing).

Uses trimesh to author tiny synthetic meshes so tests don't depend on
real model output. pymeshlab itself is not mocked — these are integration
tests against the real library, gated by import availability.
"""

import importlib.util

import pytest
import trimesh

PYMESHLAB_AVAILABLE = importlib.util.find_spec("pymeshlab") is not None


@pytest.fixture
def cube_glb(tmp_path):
    """A simple textured cube as GLB (12 triangles)."""
    mesh = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
    out = tmp_path / "cube.glb"
    mesh.export(str(out))
    return out


@pytest.fixture
def dense_sphere_glb(tmp_path):
    """A subdivided sphere with ~5000 triangles for decimation tests."""
    mesh = trimesh.creation.icosphere(subdivisions=4)
    out = tmp_path / "sphere.glb"
    mesh.export(str(out))
    return out


@pytest.mark.skipif(not PYMESHLAB_AVAILABLE, reason="pymeshlab not installed")
def test_decimate_reduces_face_count(dense_sphere_glb, tmp_path):
    from mesh_optimize import decimate_mesh

    out = tmp_path / "decimated.glb"
    target = 500
    decimate_mesh(str(dense_sphere_glb), str(out), target_faces=target)

    result = trimesh.load(str(out), force="mesh")
    assert len(result.faces) <= target * 1.05, (
        f"got {len(result.faces)} faces, expected ≤{target}"
    )
    assert len(result.faces) >= target * 0.5, (
        f"decimator over-shot: {len(result.faces)} ≪ target {target}"
    )


@pytest.mark.skipif(not PYMESHLAB_AVAILABLE, reason="pymeshlab not installed")
def test_decimate_clamps_target_to_minimum(cube_glb, tmp_path):
    from mesh_optimize import decimate_mesh, MIN_TARGET_FACES

    out = tmp_path / "tiny.glb"
    decimate_mesh(str(cube_glb), str(out), target_faces=10)

    result = trimesh.load(str(out), force="mesh")
    # Cube starts at 12 faces; floor clamps to MIN_TARGET_FACES.
    assert len(result.faces) >= min(12, MIN_TARGET_FACES)


@pytest.mark.skipif(not PYMESHLAB_AVAILABLE, reason="pymeshlab not installed")
def test_decimate_clamps_target_to_maximum(dense_sphere_glb, tmp_path):
    from mesh_optimize import decimate_mesh, MAX_TARGET_FACES

    out = tmp_path / "huge.glb"
    decimate_mesh(str(dense_sphere_glb), str(out), target_faces=10_000_000)

    result = trimesh.load(str(out), force="mesh")
    # We requested an absurd target; resolver should cap at MAX_TARGET_FACES.
    assert len(result.faces) <= MAX_TARGET_FACES


@pytest.mark.skipif(not PYMESHLAB_AVAILABLE, reason="pymeshlab not installed")
def test_smooth_changes_vertex_positions(cube_glb, tmp_path):
    from mesh_optimize import smooth_mesh
    import numpy as np

    before = trimesh.load(str(cube_glb), force="mesh")
    out = tmp_path / "smoothed.glb"
    smooth_mesh(str(cube_glb), str(out), iterations=3)

    after = trimesh.load(str(out), force="mesh")
    assert before.vertices.shape == after.vertices.shape
    # Smoothing must have moved vertices (Laplacian shrinks a cube).
    assert not np.allclose(before.vertices, after.vertices)


@pytest.mark.skipif(not PYMESHLAB_AVAILABLE, reason="pymeshlab not installed")
def test_smooth_iterations_are_clamped(cube_glb, tmp_path):
    from mesh_optimize import smooth_mesh, MAX_SMOOTH_ITERATIONS

    out = tmp_path / "smoothed.glb"
    # Should not raise even with absurdly high count — just clamps.
    smooth_mesh(str(cube_glb), str(out), iterations=10_000)

    result = trimesh.load(str(out), force="mesh")
    assert len(result.vertices) > 0
