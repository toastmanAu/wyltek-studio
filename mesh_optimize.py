"""In-process mesh optimisation via pymeshlab.

Decimation and Laplacian smoothing for GLB inputs. CPU-only — pymeshlab
is a C++ library with no GPU dep, so this is ROCm-safe.

Ported from modly's api/routers/optimize.py:1313-1448. Modly handles
textured-OBJ round-trip with a regex-patched .mtl; this port intentionally
keeps the GLB→GLB path only for now, since open-palette's GLB outputs
either embed textures (TRELLIS) or are geometry-only (Hy3D shape mode).
The textured OBJ intermediate is a follow-up if texture-preserving
decimation becomes a real need.

Implementation note: pymeshlab can't write GLB directly. We round-trip
through PLY in a temp dir and use trimesh to emit the final GLB. This
loses textures — acceptable for the geometry-only operations exposed
here.
"""

import tempfile
from pathlib import Path

MIN_TARGET_FACES = 100
MAX_TARGET_FACES = 1_000_000
DEFAULT_TARGET_FACES = 50_000
MAX_SMOOTH_ITERATIONS = 20


def _clamp_faces(target: int) -> int:
    if not target:
        return DEFAULT_TARGET_FACES
    return max(MIN_TARGET_FACES, min(MAX_TARGET_FACES, int(target)))


def _clamp_iterations(n: int) -> int:
    return max(1, min(MAX_SMOOTH_ITERATIONS, int(n)))


def _save_through_trimesh(ms, output_path: str) -> None:
    """Write pymeshlab MeshSet's current mesh to GLB via PLY intermediate."""
    import trimesh

    out = Path(output_path)
    if out.suffix.lower() == ".glb":
        with tempfile.TemporaryDirectory() as td:
            ply_tmp = Path(td) / "intermediate.ply"
            ms.save_current_mesh(str(ply_tmp))
            mesh = trimesh.load(str(ply_tmp), force="mesh")
            mesh.export(str(out), file_type="glb")
    else:
        ms.save_current_mesh(str(out))


def decimate_mesh(input_path: str, output_path: str, target_faces: int = 0) -> None:
    """Decimate a mesh to target face count via quadric edge collapse.

    Loads input (any format pymeshlab supports), writes output as GLB
    (via PLY intermediate) or whatever native format pymeshlab supports.
    Raises FileNotFoundError if input is missing.
    """
    import pymeshlab

    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"input mesh not found: {input_path}")

    target = _clamp_faces(target_faces)
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(str(src))
    ms.apply_filter(
        "meshing_decimation_quadric_edge_collapse",
        targetfacenum=target,
        preservenormal=True,
        preservetopology=True,
    )
    _save_through_trimesh(ms, output_path)


def smooth_mesh(input_path: str, output_path: str, iterations: int = 3) -> None:
    """Apply Laplacian smoothing to a mesh.

    Loads input, applies coord laplacian smoothing N times, writes output.
    """
    import pymeshlab

    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"input mesh not found: {input_path}")

    n = _clamp_iterations(iterations)
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(str(src))
    ms.apply_filter("apply_coord_laplacian_smoothing", stepsmoothnum=n)
    _save_through_trimesh(ms, output_path)
