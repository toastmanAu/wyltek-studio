"""Mesh format conversion via trimesh.

Ported from modly's api/routers/export.py. Loads with trimesh.load,
flattens any Scene to a single concatenated mesh, exports via the
target format's writer. Pure Python except for trimesh's optional C
deps. ROCm-safe.
"""

from pathlib import Path

SUPPORTED_FORMATS = frozenset({"glb", "stl", "obj", "ply"})


class UnsupportedFormatError(ValueError):
    pass


def export_mesh(input_path: str, output_path: str, fmt: str) -> None:
    """Convert a mesh from any trimesh-supported format to {glb,stl,obj,ply}.

    Raises:
        FileNotFoundError: input does not exist.
        UnsupportedFormatError: fmt not in SUPPORTED_FORMATS.
    """
    import trimesh

    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"input mesh not found: {input_path}")

    fmt_lower = fmt.lower().lstrip(".")
    if fmt_lower not in SUPPORTED_FORMATS:
        raise UnsupportedFormatError(
            f"format {fmt!r} not supported; pick from {sorted(SUPPORTED_FORMATS)}"
        )

    loaded = trimesh.load(str(src), force="mesh")
    # `force='mesh'` flattens Scene objects to a single concatenated mesh.
    if isinstance(loaded, trimesh.Scene):
        loaded = trimesh.util.concatenate(tuple(loaded.geometry.values()))

    loaded.export(str(output_path), file_type=fmt_lower)
