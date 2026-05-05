"""Wyltek Studio infographic template engine.

Templates are JSON files in ``templates/infographics/``. Each declares a
``slots`` list and a ``prompt_template`` (Mustache-style) that the
:func:`assemble_prompt` function renders against user-supplied slot
values. Image-reference slots produce ``[Image N]`` tokens at assembly
time; the SenseNova backend rewrites those to native ``<image>``
placeholders just before subprocess dispatch.
"""
from __future__ import annotations
import json, logging
from pathlib import Path
import jsonschema

logger = logging.getLogger(__name__)
_SCHEMA_PATH = Path(__file__).resolve().parent / "infographics_schema.json"


class TemplateLoadError(RuntimeError):
    """Raised when the templates directory itself cannot be read."""


def _load_schema() -> dict:
    with _SCHEMA_PATH.open() as f:
        return json.load(f)


def load_templates(dir_path: Path) -> dict[str, dict]:
    if not dir_path.exists() or not dir_path.is_dir():
        raise TemplateLoadError(f"Template dir missing: {dir_path}")
    schema = _load_schema()
    out: dict[str, dict] = {}
    for path in sorted(dir_path.glob("*.json")):
        try:
            doc = json.loads(path.read_text())
            jsonschema.validate(doc, schema)
        except (json.JSONDecodeError, jsonschema.ValidationError) as exc:
            logger.warning("Skipping malformed template %s: %s", path.name, exc)
            continue
        if doc["id"] in out:
            logger.warning("Duplicate id %s in %s", doc["id"], path.name)
            continue
        out[doc["id"]] = doc
    return out
