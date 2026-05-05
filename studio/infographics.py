"""Wyltek Studio infographic template engine.

Templates are JSON files in ``templates/infographics/``. Each declares a
``slots`` list and a ``prompt_template`` (Mustache-style) that the
:func:`assemble_prompt` function renders against user-supplied slot
values. Image-reference slots produce ``[Image N]`` tokens at assembly
time; the SenseNova backend rewrites those to native ``<image>``
placeholders just before subprocess dispatch.
"""
from __future__ import annotations
import copy, json, logging, re
from dataclasses import dataclass, field
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


# ---------------------------------------------------------------------------
# Prompt assembler
# ---------------------------------------------------------------------------

class SlotValidationError(ValueError):
    """Raised when slot values violate the template's declared constraints."""


@dataclass
class AssemblyResult:
    prompt: str
    image_paths: list[str] = field(default_factory=list)


_SECTION_RE = re.compile(r"\{\{#(\w+)\}\}(.*?)\{\{/\1\}\}", re.DOTALL)
_VAR_RE = re.compile(r"\{\{(\w+)\}\}")


def _validate_slot(slot: dict, value, path: str) -> None:
    sid, typ = slot["id"], slot["type"]
    required = slot.get("required", False)
    if value in (None, "", [], {}):
        if required:
            raise SlotValidationError(f"Required slot missing: {path}{sid}")
        return
    if typ == "text":
        if not isinstance(value, str):
            raise SlotValidationError(f"Expected string for {path}{sid}")
        ml = slot.get("max_len")
        if ml and len(value) > ml:
            raise SlotValidationError(f"{path}{sid} exceeds max_len {ml}")
    elif typ == "image_ref":
        if not isinstance(value, str):
            raise SlotValidationError(f"Expected path for {path}{sid}")
    elif typ == "color":
        if not (isinstance(value, str) and value.startswith("#")):
            raise SlotValidationError(f"Expected hex color for {path}{sid}")
    elif typ == "enum":
        if value not in slot.get("choices", []):
            raise SlotValidationError(f"{path}{sid}={value!r} not in choices")
    elif typ == "list":
        if not isinstance(value, list):
            raise SlotValidationError(f"Expected list for {path}{sid}")
        if "min" in slot and len(value) < slot["min"]:
            raise SlotValidationError(f"{path}{sid} needs >= {slot['min']} items")
        if "max" in slot and len(value) > slot["max"]:
            raise SlotValidationError(f"{path}{sid} allows <= {slot['max']} items")
        for i, item in enumerate(value):
            for sub in slot.get("item_slots", []):
                _validate_slot(sub, item.get(sub["id"]), f"{path}{sid}[{i}].")


def _render_section(body: str, value) -> str:
    if isinstance(value, list):
        out = []
        for item in value:
            piece = _SECTION_RE.sub(
                lambda m, _item=item: _render_section(m.group(2), _item.get(m.group(1))), body)
            piece = _VAR_RE.sub(lambda m, _item=item: str(_item.get(m.group(1), "")), piece)
            out.append(piece)
        return "".join(out)
    return body if value else ""


def assemble_prompt(template: dict, values: dict) -> AssemblyResult:
    """Render ``template['prompt_template']`` against ``values``."""
    for slot in template["slots"]:
        _validate_slot(slot, values.get(slot["id"]), "")

    image_paths: list[str] = []
    rewritten = copy.deepcopy(values)

    def _walk(slots: list, vals: dict) -> None:
        for slot in slots:
            sid = slot["id"]
            v = vals.get(sid)
            if v in (None, "", [], {}):
                continue
            if slot["type"] == "image_ref":
                image_paths.append(v)
                vals[sid] = f"[Image {len(image_paths)}]"
            elif slot["type"] == "list":
                for item in v:
                    _walk(slot.get("item_slots", []), item)

    _walk(template["slots"], rewritten)

    body = template["prompt_template"]
    body = _SECTION_RE.sub(
        lambda m: _render_section(m.group(2), rewritten.get(m.group(1))), body)
    body = _VAR_RE.sub(lambda m: str(rewritten.get(m.group(1), "")), body)
    return AssemblyResult(prompt=body, image_paths=image_paths)
