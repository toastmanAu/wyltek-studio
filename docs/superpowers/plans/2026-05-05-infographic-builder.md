# Infographic Builder — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `/studio/infographic` — a template-driven infographic page in Wyltek Studio, powered by SenseNova-U1-8B-MoT in `interleave` mode, with optional numbered image references, draft/final tier toggle, and an inline post-edit canvas (V1-canvas scope).

**Architecture:** New self-contained Python module `studio/infographics.py` (template loader + prompt assembler), new subprocess-style backend `backends/sensenova.py` mirroring `backends/worldgen.py`, eight JSON template files in `templates/infographics/`, new HTML page + JS at `static/studio/infographic.html` + `static/studio/js/infographic.js`, and a separate `static/studio/js/canvas-edit.js` for the post-edit canvas. Server routes added to `server.py`. Hooks into the existing job queue (`job_queue.py`) and storage (`storage.py`) — no schema changes; sidecar JSON per render. Uses the `progress_smooth.py` interpolator that recently landed (commit `49080a0`) for ETA-style heartbeat since SenseNova's inference doesn't emit native progress lines.

**Tech Stack:** Python 3, FastAPI, asyncio, subprocess to a SenseNova-U1 venv at `/data/venvs/sensenova-u1`, pytest + `@pytest.mark.asyncio`, vanilla HTML/JS frontend (no framework), HTML5 Canvas API, Clipboard API.

**Spec:** `docs/superpowers/specs/2026-05-05-infographic-builder-design.md` (commit `a2779a9`).

**Pre-flight:**

- The working tree currently has uncommitted edits to `backends/comfyui.py`, `server.py`, `static/css/style.css`, `static/index.html`, `static/js/app.js`, `static/js/nav.js`, `storage.py`, `studio/tts_xtts.py`, `tests/test_api_remix.py`, plus several studio HTML files. **Tasks that modify any of these existing files must wait until the dirty edits are committed or stashed**, otherwise the diff will conflate concerns. Tasks 1–6 only create new files, so they're safe on the dirty tree. The first task that touches an existing shared file is Task 8 (`server.py`); a checkpoint at the top of Task 8 enforces the commit/stash gate.
- The SenseNova-U1 repo is at `/home/phill/SenseNova-U1`. Weights at `/data/sensenova-u1-weights` (50-step) and `/data/sensenova-u1-weights-8step` (8-step preview). Venv at `/data/venvs/sensenova-u1`. All three are existing on driveThree; the install script in Phase 8 makes them reproducible elsewhere.
- All renders require ComfyUI to be stopped on driveThree (VRAM tenancy — see memory `project_vram_tenancy.md`). The `/api/sensenova/precheck` endpoint surfaces this to the UI; runtime enforcement is on the user.
- The plan is structured into **8 phases**. Each phase ends with shippable software. The recommended split for review checkpoints is: `Phase 1+2` → `Phase 3` → `Phase 4` → `Phase 5` → `Phase 6` → `Phase 7` → `Phase 8`.

---

## Phase 1 — Foundations: template engine + first template + backend wrapper

Goal of phase: a Python-only path that takes `(template_id, slot_values, image_paths, tier)` and produces a PNG on disk. Verifiable from a pytest. No UI yet.

### Task 1 — Template schema (JSON Schema)

**Why:** A formal schema for templates lets us validate built-in and user-dropped JSON consistently. It also gives the frontend a contract to render forms from. The schema itself is small — five slot types, a few constraints — and committing it first makes Tasks 2–6 testable against a real document.

**Files:**
- Create: `studio/infographics_schema.json`
- Test: `tests/test_infographics_schema.py`

- [ ] **Step 1 — Write the failing test** at `tests/test_infographics_schema.py`:

```python
import json
from pathlib import Path
import jsonschema, pytest

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "studio" / "infographics_schema.json"

@pytest.fixture
def schema():
    with SCHEMA_PATH.open() as f: return json.load(f)

def _minimal():
    return {"id":"minimal","name":"Minimal","description":"x",
            "slots":[{"id":"title","type":"text","required":True}],
            "prompt_template":"{{title}}"}

def test_minimal_validates(schema): jsonschema.validate(_minimal(), schema)
def test_missing_required_rejected(schema):
    bad = _minimal(); del bad["prompt_template"]
    with pytest.raises(jsonschema.ValidationError): jsonschema.validate(bad, schema)
def test_unknown_slot_type_rejected(schema):
    bad = _minimal(); bad["slots"][0]["type"] = "magic"
    with pytest.raises(jsonschema.ValidationError): jsonschema.validate(bad, schema)
def test_list_slot_validates(schema):
    tpl = _minimal()
    tpl["slots"].append({"id":"rows","type":"list","min":2,"max":5,
        "item_slots":[{"id":"label","type":"text","required":True},
                      {"id":"image","type":"image_ref","required":False}]})
    jsonschema.validate(tpl, schema)
```

- [ ] **Step 2 — Run** `pytest tests/test_infographics_schema.py -v`. Expected: FAIL (`FileNotFoundError`).

- [ ] **Step 3 — Write the schema** at `studio/infographics_schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Wyltek Infographic Template",
  "type": "object",
  "required": ["id", "name", "description", "slots", "prompt_template"],
  "properties": {
    "id":          {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
    "name":        {"type": "string", "minLength": 1, "maxLength": 60},
    "description": {"type": "string", "minLength": 1, "maxLength": 240},
    "preview":     {"type": "string"},
    "slots":       {"type": "array", "items": {"$ref": "#/definitions/slot"}},
    "prompt_template": {"type": "string", "minLength": 1}
  },
  "additionalProperties": false,
  "definitions": {
    "slot": {
      "type": "object",
      "required": ["id", "type"],
      "properties": {
        "id":       {"type": "string", "pattern": "^[a-z][a-z0-9_]*$"},
        "type":     {"enum": ["text", "image_ref", "color", "list", "enum"]},
        "label":    {"type": "string"},
        "required": {"type": "boolean"},
        "max_len":  {"type": "integer", "minimum": 1},
        "min":      {"type": "integer", "minimum": 0},
        "max":      {"type": "integer", "minimum": 1},
        "choices":  {"type": "array", "items": {"type": "string"}},
        "item_slots": {"type": "array", "items": {"$ref": "#/definitions/slot"}}
      },
      "additionalProperties": false
    }
  }
}
```

- [ ] **Step 4 — Run** `pytest tests/test_infographics_schema.py -v`. Expected: 4 passed.

- [ ] **Step 5 — Commit:**

```bash
git add studio/infographics_schema.json tests/test_infographics_schema.py
git commit -m "feat(infographic): json schema for templates"
```

---

### Task 2 — Template loader

**Why:** Loading templates is its own concern (filesystem walk, JSON parse, schema validate, hot-reload on each request). Splitting it from the prompt assembler keeps both small. The loader returns a typed dict keyed by template id; a malformed template is logged and excluded rather than crashing the whole studio.

**Files:**
- Create: `studio/infographics.py`
- Test: `tests/test_infographics_loader.py`

- [ ] **Step 1 — Write the failing test** at `tests/test_infographics_loader.py`:

```python
import json
from pathlib import Path
import pytest
from studio.infographics import load_templates, TemplateLoadError

def _write(p: Path, doc: dict): (p / f"{doc['id']}.json").write_text(json.dumps(doc))
def _good(id_="hub"):
    return {"id": id_, "name": "T", "description": "x",
            "slots": [{"id":"title","type":"text","required":True}],
            "prompt_template": "{{title}}"}

def test_loads_valid(tmp_path):
    _write(tmp_path, _good("a")); _write(tmp_path, _good("b"))
    out = load_templates(tmp_path)
    assert set(out.keys()) == {"a","b"}

def test_skips_invalid(tmp_path, caplog):
    _write(tmp_path, _good("ok"))
    bad = _good("bad"); del bad["prompt_template"]
    _write(tmp_path, bad)
    out = load_templates(tmp_path)
    assert set(out.keys()) == {"ok"}
    assert "bad" in caplog.text

def test_empty_dir_returns_empty(tmp_path):
    assert load_templates(tmp_path) == {}

def test_missing_dir_raises(tmp_path):
    with pytest.raises(TemplateLoadError):
        load_templates(tmp_path / "no")
```

- [ ] **Step 2 — Run.** Expected: FAIL (module doesn't exist).

- [ ] **Step 3 — Write the implementation** at `studio/infographics.py`:

```python
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
```

- [ ] **Step 4 — Run** `pytest tests/test_infographics_loader.py -v`. Expected: 4 passed.

- [ ] **Step 5 — Commit:**

```bash
git add studio/infographics.py tests/test_infographics_loader.py
git commit -m "feat(infographic): template loader with schema validation"
```

---

### Task 3 — Prompt assembler

**Why:** Slot values + template → final prompt string. This is where Mustache-style rendering happens, where required-field validation kicks in, and where `[Image N]` tokens are stamped for image-ref slots. Keeping it pure (no I/O, no subprocess) makes it cheap to test exhaustively.

**Files:**
- Modify: `studio/infographics.py`
- Test: `tests/test_infographics_assemble.py`

- [ ] **Step 1 — Write the failing test** at `tests/test_infographics_assemble.py`:

```python
import pytest
from studio.infographics import AssemblyResult, SlotValidationError, assemble_prompt

HUB = {
    "id":"hub","name":"Hub","description":"t",
    "slots":[
        {"id":"title","type":"text","required":True,"max_len":30},
        {"id":"hub_image","type":"image_ref","required":False},
        {"id":"spokes","type":"list","min":2,"max":4,
         "item_slots":[
            {"id":"label","type":"text","required":True,"max_len":20},
            {"id":"image","type":"image_ref","required":False}]},
    ],
    "prompt_template": ("Title: {{title}}.{{#hub_image}} Hub: {{hub_image}}.{{/hub_image}} "
                       "Spokes: {{#spokes}}[{{label}}{{#image}} -> {{image}}{{/image}}] {{/spokes}}"),
}

def test_text_slot():
    r = assemble_prompt(HUB, {"title":"Hello","spokes":[{"label":"A"},{"label":"B"}]})
    assert "Title: Hello." in r.prompt and "[A] [B]" in r.prompt
    assert r.image_paths == []

def test_image_ref_numbered():
    r = assemble_prompt(HUB, {
        "title":"X", "hub_image":"/u/foo.png",
        "spokes":[{"label":"S1","image":"/u/bar.png"},{"label":"S2"}]})
    assert "Hub: [Image 1]." in r.prompt
    assert "[S1 -> [Image 2]]" in r.prompt
    assert r.image_paths == ["/u/foo.png","/u/bar.png"]

def test_required_missing():
    with pytest.raises(SlotValidationError):
        assemble_prompt(HUB, {"spokes":[{"label":"A"},{"label":"B"}]})

def test_max_len():
    with pytest.raises(SlotValidationError):
        assemble_prompt(HUB, {"title":"x"*31, "spokes":[{"label":"A"},{"label":"B"}]})

def test_list_min():
    with pytest.raises(SlotValidationError):
        assemble_prompt(HUB, {"title":"T", "spokes":[{"label":"A"}]})

def test_result_dataclass():
    r = assemble_prompt(HUB, {"title":"T","spokes":[{"label":"A"},{"label":"B"}]})
    assert isinstance(r, AssemblyResult)
    assert hasattr(r,"prompt") and hasattr(r,"image_paths")
```

- [ ] **Step 2 — Run.** Expected: FAIL (`assemble_prompt` undefined).

- [ ] **Step 3 — Append to `studio/infographics.py`:**

```python
import re, copy
from dataclasses import dataclass, field


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
                lambda m: _render_section(m.group(2), item.get(m.group(1))), body)
            piece = _VAR_RE.sub(lambda m: str(item.get(m.group(1), "")), piece)
            out.append(piece)
        return "".join(out)
    return body if value else ""


def assemble_prompt(template: dict, values: dict) -> AssemblyResult:
    """Render ``template['prompt_template']`` against ``values``."""
    for slot in template["slots"]:
        _validate_slot(slot, values.get(slot["id"]), "")

    image_paths: list[str] = []
    rewritten = copy.deepcopy(values)

    def _walk(slots, vals):
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
```

- [ ] **Step 4 — Run** `pytest tests/test_infographics_assemble.py -v`. Expected: 6 passed.

- [ ] **Step 5 — Commit:**

```bash
git add studio/infographics.py tests/test_infographics_assemble.py
git commit -m "feat(infographic): prompt assembler with image-ref token stamping"
```

---

### Task 4 — First template: `hub_and_spoke.json`

**Why:** A real template proves the schema/loader/assembler combination produces a usable prompt for SenseNova. We use the v1 prompt structure that's already battle-tested in `wyltek-infographic-log.md` Run 001/002 — same color rhetoric, same composition. The other 7 templates (Phase 5) follow the same pattern.

**Files:**
- Create: `templates/infographics/hub_and_spoke.json`
- Test: `tests/test_infographics_hub_and_spoke.py`

- [ ] **Step 1 — Write the test** at `tests/test_infographics_hub_and_spoke.py`:

```python
from pathlib import Path
from studio.infographics import assemble_prompt, load_templates

T = Path(__file__).resolve().parent.parent / "templates" / "infographics"

def test_loads_and_renders():
    tpl = load_templates(T)["hub_and_spoke"]
    r = assemble_prompt(tpl, {
        "title":"Wyltek Studio","hub_desc":"a friendly mascot",
        "spokes":[{"label":"Frames","tagline":"Text to Image","color":"#9be6c4"},
                  {"label":"Edit"},{"label":"Remix"},{"label":"Music"}]})
    assert "Wyltek Studio" in r.prompt and "Frames" in r.prompt
    assert r.image_paths == []

def test_with_hub_image():
    tpl = load_templates(T)["hub_and_spoke"]
    r = assemble_prompt(tpl, {
        "title":"Brand","hub_desc":"logo","hub_image":"/u/logo.png",
        "spokes":[{"label":"A"},{"label":"B"},{"label":"C"},{"label":"D"}]})
    assert "[Image 1]" in r.prompt
    assert r.image_paths == ["/u/logo.png"]
```

- [ ] **Step 2 — Run.** Expected: FAIL (template missing).

- [ ] **Step 3 — Create** `templates/infographics/hub_and_spoke.json`:

```json
{
  "id": "hub_and_spoke",
  "name": "Hub & Spoke",
  "description": "Central concept with N radiating spokes. Best for feature overviews.",
  "preview": "templates/infographics/_previews/hub_and_spoke.png",
  "slots": [
    {"id":"title","type":"text","label":"Title","max_len":60,"required":true},
    {"id":"hub_desc","type":"text","label":"Hub concept","max_len":200,"required":true},
    {"id":"hub_image","type":"image_ref","label":"Hub image (optional)","required":false},
    {"id":"spokes","type":"list","label":"Spokes","min":4,"max":8,
     "item_slots":[
        {"id":"label","type":"text","label":"Label","max_len":24,"required":true},
        {"id":"tagline","type":"text","label":"Tagline","max_len":60,"required":false},
        {"id":"color","type":"color","label":"Color","required":false},
        {"id":"image","type":"image_ref","label":"Icon image (optional)","required":false}
     ]}
  ],
  "prompt_template": "An infographic titled \"{{title}}\", playful flat illustration on cream paper with thick black outlines. Hub-and-spoke layout: a central focal point with equidistant radiating spokes arranged clockwise, soft drop shadows, dotted-grid background. Center hub: {{hub_desc}}.{{#hub_image}} Hub illustration reference: [Image 1].{{/hub_image}} Spokes:{{#spokes}} A circular badge{{#color}} in {{color}}{{/color}} containing {{label}}{{#tagline}} (tagline \"{{tagline}}\"){{/tagline}}{{#image}}, illustration reference {{image}}{{/image}};{{/spokes}} High balance, generous white space, professional approachable visual flow."
}
```

- [ ] **Step 4 — Run.** Expected: 2 passed.

- [ ] **Step 5 — Commit:**

```bash
git add templates/infographics/hub_and_spoke.json tests/test_infographics_hub_and_spoke.py
git commit -m "feat(infographic): hub_and_spoke template (v1 prompt from log)"
```

---

### Task 5 — SenseNova subprocess backend (skeleton)

**Why:** Mirror the `backends/worldgen.py` shape: validate environment, build argv, popen, parse stdout for progress. SenseNova's `examples/interleave/inference.py` doesn't emit native progress lines; we'll hook the smooth_progress interpolator on top in Task 6 to keep the UI bar moving. This task lands the subprocess plumbing and the JSONL payload writer.

**Files:**
- Create: `backends/sensenova.py`
- Test: `tests/test_sensenova_backend.py`

- [ ] **Step 1 — Write the failing test** at `tests/test_sensenova_backend.py`:

```python
import pytest
from backends.sensenova import (
    SenseNovaError, _build_argv, _build_jsonl_payload, _resolve_weights)


def test_payload_text_only():
    p = _build_jsonl_payload(prompt="hi", image_paths=[], aspect="1:1", seed=42)
    assert p["prompt"] == "hi" and p["image"] == []
    assert p["width"] == 1536 and p["height"] == 1536
    assert p["seed"] == 42 and p["think_mode"] is False

def test_payload_with_images_uses_placeholders():
    p = _build_jsonl_payload(
        prompt="Compare [Image 1] and [Image 2].",
        image_paths=["/u/a.png","/u/b.png"], aspect=None, seed=7)
    assert "<image>" in p["prompt"] and "[Image 1]" not in p["prompt"]
    assert p["image"] == ["/u/a.png","/u/b.png"]
    assert "width" not in p or p.get("width") is None

def test_aspect_buckets():
    p = _build_jsonl_payload("x", [], "16:9", 0)
    assert (p["width"], p["height"]) == (2048, 1152)

def test_unknown_aspect_raises():
    with pytest.raises(SenseNovaError):
        _build_jsonl_payload("x", [], "13:7", 0)

def test_resolve_weights():
    assert "8step" not in _resolve_weights("final")
    assert "8step" in _resolve_weights("draft")

def test_resolve_weights_bad():
    with pytest.raises(SenseNovaError):
        _resolve_weights("turbo")

def test_argv_includes_jsonl_and_no_think(tmp_path):
    j = tmp_path / "j.jsonl"; j.write_text("{}")
    argv = _build_argv(jsonl_path=j, output_dir=tmp_path, tier="final")
    assert "--jsonl" in argv and str(j) in argv
    assert "--no-think_mode" in argv
    assert any("sensenova-u1-weights" in a for a in argv)
```

- [ ] **Step 2 — Run.** Expected: FAIL (module missing).

- [ ] **Step 3 — Write** `backends/sensenova.py`:

```python
"""SenseNova-U1 subprocess backend (interleave mode).

Runs the `examples/interleave/inference.py` script from the SenseNova-U1
repo against a JSONL payload we write to /tmp. Two tiers select between
the 50-step and 8-step-preview weight sets. Output PNG path is returned
on success; non-zero exit raises :class:`SenseNovaError`.

Progress reporting is layered on top via :mod:`progress_smooth` (Task 6).
See spec: docs/superpowers/specs/2026-05-05-infographic-builder-design.md
"""
from __future__ import annotations
import asyncio, json, os, re, time
from asyncio import create_subprocess_exec as _start_subprocess
from pathlib import Path
from typing import Awaitable, Callable

SENSENOVA_REPO = Path(os.environ.get("SENSENOVA_REPO", "/home/phill/SenseNova-U1"))
SENSENOVA_VENV_PYTHON = Path(os.environ.get("SENSENOVA_VENV", "/data/venvs/sensenova-u1")) / "bin" / "python"
WEIGHTS_FINAL = Path(os.environ.get("SENSENOVA_WEIGHTS_FINAL", "/data/sensenova-u1-weights"))
WEIGHTS_DRAFT = Path(os.environ.get("SENSENOVA_WEIGHTS_DRAFT", "/data/sensenova-u1-weights-8step"))
INFER_SCRIPT = SENSENOVA_REPO / "examples" / "interleave" / "inference.py"

DEFAULT_DRAFT_TIMEOUT_S = 180
DEFAULT_FINAL_TIMEOUT_S = 600

ASPECT_BUCKETS: dict[str, tuple[int, int]] = {
    "1:1": (1536, 1536), "16:9": (2048, 1152), "9:16": (1152, 2048),
    "3:2": (1888, 1248), "2:3": (1248, 1888), "4:3": (1760, 1312),
    "3:4": (1312, 1760), "1:2": (1088, 2144), "2:1": (2144, 1088),
    "1:3": (864, 2592),  "3:1": (2592, 864),
}

ProgressCallback = Callable[[int, str], Awaitable[None]]
_IMAGE_TOKEN_RE = re.compile(r"\[Image \d+\]")


class SenseNovaError(RuntimeError):
    """Raised on bad config, malformed inputs, or non-zero subprocess exit."""


def _resolve_weights(tier: str) -> str:
    if tier == "final": return str(WEIGHTS_FINAL)
    if tier == "draft": return str(WEIGHTS_DRAFT)
    raise SenseNovaError(f"Unknown tier: {tier!r}")


def _build_jsonl_payload(prompt, image_paths, aspect, seed) -> dict:
    has_images = bool(image_paths)
    rewritten = _IMAGE_TOKEN_RE.sub("<image>", prompt) if has_images else prompt
    payload: dict = {
        "prompt": rewritten,
        "image": list(image_paths),
        "seed": seed,
        "think_mode": False,
    }
    if not has_images:
        if aspect is None:
            aspect = "1:1"
        if aspect not in ASPECT_BUCKETS:
            raise SenseNovaError(
                f"aspect={aspect!r} not in supported buckets {sorted(ASPECT_BUCKETS)}")
        w, h = ASPECT_BUCKETS[aspect]
        payload["width"], payload["height"] = w, h
    return payload


def _build_argv(*, jsonl_path: Path, output_dir: Path, tier: str) -> list[str]:
    return [
        str(SENSENOVA_VENV_PYTHON),
        str(INFER_SCRIPT),
        "--model_path", _resolve_weights(tier),
        "--jsonl", str(jsonl_path),
        "--output_dir", str(output_dir),
        "--no-think_mode",
    ]


def _validate_environment() -> None:
    if not INFER_SCRIPT.exists():
        raise SenseNovaError(f"Interleave script missing at {INFER_SCRIPT}")
    if not SENSENOVA_VENV_PYTHON.exists():
        raise SenseNovaError(f"SenseNova venv python missing at {SENSENOVA_VENV_PYTHON}")
    if not WEIGHTS_FINAL.exists() or not WEIGHTS_DRAFT.exists():
        raise SenseNovaError("SenseNova weights missing")


async def generate(*, prompt, image_paths, aspect, seed, tier,
                   output_dir: Path,
                   on_progress: ProgressCallback | None = None,
                   timeout_s: int | None = None) -> Path:
    """Run a single SenseNova interleave render and return the PNG path."""
    _validate_environment()
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = _build_jsonl_payload(prompt, image_paths, aspect, seed)
    jsonl = output_dir / "input.jsonl"
    jsonl.write_text(json.dumps(payload) + "\n")

    argv = _build_argv(jsonl_path=jsonl, output_dir=output_dir, tier=tier)
    timeout = timeout_s or (DEFAULT_DRAFT_TIMEOUT_S if tier == "draft" else DEFAULT_FINAL_TIMEOUT_S)

    start = time.monotonic()
    proc = await _start_subprocess(*argv,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    stdout = bytearray()
    try:
        async for raw in proc.stdout:  # type: ignore[union-attr]
            stdout.extend(raw)
            if (time.monotonic() - start) > timeout:
                proc.terminate()
                raise SenseNovaError(f"SenseNova render exceeded {timeout}s")
        rc = await proc.wait()
    except asyncio.CancelledError:
        proc.terminate()
        await proc.wait()
        raise

    if rc != 0:
        raise SenseNovaError(
            f"SenseNova subprocess exited {rc}; tail:\n"
            + stdout.decode("utf-8", errors="replace")[-2000:])

    pngs = sorted(output_dir.glob("*.png"))
    if not pngs:
        raise SenseNovaError(f"No PNG produced in {output_dir}")
    return pngs[-1]
```

- [ ] **Step 4 — Run.** Expected: 7 passed.

- [ ] **Step 5 — Commit:**

```bash
git add backends/sensenova.py tests/test_sensenova_backend.py
git commit -m "feat(sensenova): subprocess backend with JSONL payload + tier routing"
```

---

### Task 6 — Wire smooth_progress for ETA-style heartbeat

**Why:** SenseNova doesn't emit progress lines. Without intervention the UI bar sits at 0% for 73s (draft) or 5min (final) and looks frozen. The `progress_smooth.SmoothProgress` interpolator (commit `49080a0`) creeps the bar between explicit anchors. We anchor 5% on subprocess start and 95% on the first PNG appearing in `output_dir`; the interpolator fills the middle.

**Files:**
- Modify: `backends/sensenova.py`
- Test: `tests/test_sensenova_progress.py`

- [ ] **Step 1 — Write the failing test** at `tests/test_sensenova_progress.py`:

```python
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

    async def _spawn(*a, **kw): return _FakeProc(0.2, tmp_path)
    with patch.object(sensenova, "_validate_environment", lambda: None), \
         patch.object(sensenova, "_start_subprocess", _spawn):
        await sensenova.generate(
            prompt="x", image_paths=[], aspect="1:1", seed=0,
            tier="draft", output_dir=tmp_path, on_progress=cb, timeout_s=5)

    pcts = [p for p, _ in seen]
    assert pcts[0] <= 10
    assert any(p > 10 for p in pcts), f"expected creep > 10, got {pcts}"
    assert pcts[-1] >= 95
```

- [ ] **Step 2 — Run.** Expected: FAIL (no creep emitted).

- [ ] **Step 3 — Replace the body of the `try` block in `generate()`:**

```python
    expected = 73 if tier == "draft" else 300  # mean wall times from runs 002/003
    from progress_smooth import SmoothProgress

    if on_progress is None:
        async def _noop(_p, _m=""): return None
        cb: ProgressCallback = _noop
    else:
        cb = on_progress

    async with SmoothProgress(cb, tick_seconds=2.0, max_creep=85) as sp:
        await sp.set(5, "loading model")
        try:
            async for raw in proc.stdout:  # type: ignore[union-attr]
                stdout.extend(raw)
                if (time.monotonic() - start) > timeout:
                    proc.terminate()
                    raise SenseNovaError(f"SenseNova render exceeded {timeout}s")
            rc = await proc.wait()
        except asyncio.CancelledError:
            proc.terminate()
            await proc.wait()
            raise
        await sp.set(95, "saving image")

    if rc != 0:
        raise SenseNovaError(
            f"SenseNova subprocess exited {rc}; tail:\n"
            + stdout.decode("utf-8", errors="replace")[-2000:])

    pngs = sorted(output_dir.glob("*.png"))
    if not pngs:
        raise SenseNovaError(f"No PNG produced in {output_dir}")
    if on_progress is not None:
        await on_progress(100, "done")
    return pngs[-1]
```

> Note: confirm `SmoothProgress`'s constructor accepts `tick_seconds=` and `max_creep=` by reading `progress_smooth.py`. If different kwargs, adjust here. The test only asserts creep > 10 and final ≥ 95, so it tolerates either ETA-aware or fixed-cadence behavior.

- [ ] **Step 4 — Run** `pytest tests/test_sensenova_progress.py tests/test_sensenova_backend.py -v`. Expected: 8 passed.

- [ ] **Step 5 — Commit:**

```bash
git add backends/sensenova.py tests/test_sensenova_progress.py
git commit -m "feat(sensenova): ETA-style heartbeat via smooth_progress"
```

---

### Task 7 — Phase 1 integration test (offline)

**Why:** Verify the loader → assembler → backend (mocked) pipeline end-to-end. Catches type/path drift between modules; gives Phase 2 confidence to move.

**Files:**
- Test: `tests/test_infographic_pipeline.py`

- [ ] **Step 1 — Write the test:**

```python
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from backends import sensenova
from studio.infographics import assemble_prompt, load_templates

@pytest.mark.asyncio
async def test_pipeline_text_only(tmp_path):
    tpl = load_templates(Path(__file__).resolve().parent.parent
                         / "templates" / "infographics")["hub_and_spoke"]
    r = assemble_prompt(tpl, {
        "title":"Test","hub_desc":"robot",
        "spokes":[{"label":str(i)} for i in range(4)]})

    out_png = tmp_path / "out.png"; out_png.write_bytes(b"")
    with patch.object(sensenova, "generate", new=AsyncMock(return_value=out_png)) as m:
        result = await sensenova.generate(
            prompt=r.prompt, image_paths=r.image_paths,
            aspect="1:1", seed=42, tier="draft", output_dir=tmp_path)
    assert result == out_png
    assert "Test" in m.call_args.kwargs["prompt"]
    assert m.call_args.kwargs["aspect"] == "1:1"
    assert m.call_args.kwargs["tier"] == "draft"
```

- [ ] **Step 2 — Run.** Expected: passed.

- [ ] **Step 3 — Commit:**

```bash
git add tests/test_infographic_pipeline.py
git commit -m "test(infographic): pipeline integration test (mocked backend)"
```

---

## Phase 2 — API + job-queue integration

Goal of phase: hit `/api/infographic/render` from a curl, get a job id, poll until done, GET the PNG. UI not yet involved.

> **CHECKPOINT — start of Phase 2:** Phase 2 begins by editing `server.py`, which currently has uncommitted work in the tree. **Confirm before proceeding:** either commit or `git stash` the working-tree edits to `server.py`, `static/`, `storage.py`, and friends. Plan tasks below assume a clean tree.

---

### Task 8 — Backend registry hook

**Why:** Open-palette's existing `backends/registry.py` lets `server.py` route `engine="sensenova"` to our new module. Mirroring how `worldgen` is wired keeps the dispatcher consistent.

**Files:**
- Modify: `backends/registry.py`
- Test: `tests/test_sensenova_registry.py`

- [ ] **Step 1 — Read the existing registry:** `sed -n '1,80p' backends/registry.py`. Identify whether it's a dict or a function — match the existing pattern; do not introduce new abstractions.

- [ ] **Step 2 — Write the test:**

```python
from backends import registry
def test_sensenova_registered():
    assert "sensenova" in registry.list_engines()
```

> If `list_engines` does not exist, replace with whichever introspection method `registry.py` offers (e.g., key in a module-level dict). The point is: a string lookup for `"sensenova"` succeeds.

- [ ] **Step 3 — Run.** Expected: FAIL.

- [ ] **Step 4 — Edit `backends/registry.py`:** add an import + dispatch entry pointing at `backends.sensenova.generate`, matching the existing `worldgen` style exactly.

- [ ] **Step 5 — Run.** Expected: passed.

- [ ] **Step 6 — Commit:**

```bash
git add backends/registry.py tests/test_sensenova_registry.py
git commit -m "feat(sensenova): register engine in backends registry"
```

---

### Task 9 — `GET /api/infographic/templates`

**Why:** The frontend reads this to populate the template dropdown and render slot forms. Returning the full slot schema lets the page generate forms with zero per-template UI code.

**Files:**
- Modify: `server.py`
- Test: `tests/test_api_infographic_templates.py`

- [ ] **Step 1 — Write the test:**

```python
from fastapi.testclient import TestClient
from server import app

def test_templates_endpoint():
    r = TestClient(app).get("/api/infographic/templates")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    ids = {t["id"] for t in body}
    assert "hub_and_spoke" in ids
    hub = next(t for t in body if t["id"] == "hub_and_spoke")
    assert any(s["id"] == "title" for s in hub["slots"])
```

- [ ] **Step 2 — Run.** Expected: 404.

- [ ] **Step 3 — Add to `server.py`:**

```python
from pathlib import Path as _Path
from studio.infographics import load_templates as _load_infographic_templates

_INFOGRAPHIC_TEMPLATES_DIR = _Path(__file__).resolve().parent / "templates" / "infographics"

@app.get("/api/infographic/templates")
async def infographic_templates():
    templates = _load_infographic_templates(_INFOGRAPHIC_TEMPLATES_DIR)
    return [{"id": t["id"], "name": t["name"], "description": t["description"],
             "preview": t.get("preview"), "slots": t["slots"]}
            for t in templates.values()]
```

- [ ] **Step 4 — Run.** Expected: passed.

- [ ] **Step 5 — Commit:**

```bash
git add server.py tests/test_api_infographic_templates.py
git commit -m "feat(api): GET /api/infographic/templates"
```

---

### Task 10 — `POST /api/infographic/render` (job submission)

**Why:** Submit a render → get a `job_id` → poll. The endpoint validates the body, assembles the prompt, calls `submit_background`, returns 202. Slot validation failures surface as 400; subprocess errors don't surface here (they go through job status).

**Files:**
- Modify: `server.py`
- Test: `tests/test_api_infographic_render.py`

- [ ] **Step 1 — Write the test:**

```python
from unittest.mock import patch
from fastapi.testclient import TestClient
from server import app

def _good():
    return {"template_id":"hub_and_spoke","tier":"draft","aspect":"1:1",
            "slots":{"title":"T","hub_desc":"x","spokes":[{"label":str(i)} for i in range(4)]},
            "image_refs":[]}

def test_render_returns_202():
    with patch("server.submit_background", return_value="job-abc"):
        r = TestClient(app).post("/api/infographic/render", json=_good())
    assert r.status_code == 202 and r.json()["job_id"] == "job-abc"

def test_render_unknown_template_404():
    body = _good(); body["template_id"] = "no_such"
    r = TestClient(app).post("/api/infographic/render", json=body)
    assert r.status_code == 404

def test_render_missing_required_400():
    body = _good(); del body["slots"]["title"]
    r = TestClient(app).post("/api/infographic/render", json=body)
    assert r.status_code == 400

def test_render_invalid_tier_400():
    body = _good(); body["tier"] = "turbo"
    r = TestClient(app).post("/api/infographic/render", json=body)
    assert r.status_code == 400
```

- [ ] **Step 2 — Run.** Expected: 4 failures (404).

- [ ] **Step 3 — Add to `server.py`:**

```python
from pydantic import BaseModel, Field
from studio.infographics import (
    SlotValidationError as _InfographicSlotError,
    assemble_prompt as _assemble_infographic_prompt)
from backends.sensenova import ASPECT_BUCKETS as _SENSENOVA_ASPECTS


class _InfographicRenderBody(BaseModel):
    template_id: str
    tier: str = Field(pattern="^(draft|final)$")
    aspect: str | None = None
    slots: dict
    image_refs: list[str] = []


@app.post("/api/infographic/render", status_code=202)
async def infographic_render(body: _InfographicRenderBody):
    if body.aspect is not None and body.aspect not in _SENSENOVA_ASPECTS:
        raise HTTPException(400, f"aspect={body.aspect!r} not in supported buckets")
    templates = _load_infographic_templates(_INFOGRAPHIC_TEMPLATES_DIR)
    tpl = templates.get(body.template_id)
    if tpl is None:
        raise HTTPException(404, f"Unknown template_id: {body.template_id}")
    try:
        result = _assemble_infographic_prompt(tpl, body.slots)
    except _InfographicSlotError as exc:
        raise HTTPException(400, str(exc)) from exc

    job_id = submit_background(engine="sensenova", params={
        "prompt": result.prompt,
        "image_paths": result.image_paths or list(body.image_refs),
        "aspect": body.aspect,
        "tier": body.tier,
        "template_id": body.template_id,
        "slots": body.slots,
    })
    return {"job_id": job_id}
```

- [ ] **Step 4 — Run.** Expected: 4 passed.

- [ ] **Step 5 — Commit:**

```bash
git add server.py tests/test_api_infographic_render.py
git commit -m "feat(api): POST /api/infographic/render with slot validation"
```

---

### Task 11 — Job runner dispatch to SenseNova

**Why:** `server.py:_run_job` currently routes to worldgen / comfyui based on `params["engine"]`. Add a `"sensenova"` branch that calls `backends.sensenova.generate` and writes output under `outputs/infographic/`.

**Files:**
- Modify: `server.py`
- Test: `tests/test_sensenova_job_dispatch.py`

- [ ] **Step 1 — Locate the runner:** `grep -n "_run_job\|engine ==" server.py | head -30`. Identify the dispatch site (likely a `match` or `if/elif` on `engine`).

- [ ] **Step 2 — Write the test:**

```python
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from server import _run_job   # adjust if the runner is named differently

@pytest.mark.asyncio
async def test_run_job_routes_sensenova(tmp_path):
    fake_png = tmp_path / "out.png"; fake_png.write_bytes(b"\x89PNG")
    with patch("backends.sensenova.generate", new=AsyncMock(return_value=fake_png)) as m, \
         patch("server.OUTPUTS_ROOT", tmp_path):
        await _run_job("t1", {
            "engine":"sensenova","prompt":"p","image_paths":[],
            "aspect":"1:1","tier":"draft","template_id":"hub_and_spoke","slots":{"title":"T"},
        }, on_progress=AsyncMock())
    m.assert_called_once()
    kw = m.call_args.kwargs
    assert kw["tier"] == "draft" and kw["aspect"] == "1:1"
```

> Adjust `_run_job` import + `OUTPUTS_ROOT` patch target after Step 1's grep.

- [ ] **Step 3 — Run.** Expected: FAIL.

- [ ] **Step 4 — Add the dispatch branch in `server.py`'s job runner:**

```python
elif engine == "sensenova":
    from backends.sensenova import generate as _sensenova_generate
    output_dir = OUTPUTS_ROOT / "infographic" / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    png = await _sensenova_generate(
        prompt=params["prompt"],
        image_paths=params.get("image_paths") or [],
        aspect=params.get("aspect"),
        seed=params.get("seed", 42),
        tier=params["tier"],
        output_dir=output_dir,
        on_progress=on_progress,
    )
    return str(png)
```

(Adjust `OUTPUTS_ROOT` to whatever the existing constant is named — check Step 1's grep.)

- [ ] **Step 5 — Run.** Expected: passed.

- [ ] **Step 6 — Commit:**

```bash
git add server.py tests/test_sensenova_job_dispatch.py
git commit -m "feat(server): dispatch sensenova engine to backend"
```

---

### Task 12 — `GET /api/sensenova/precheck`

**Why:** On driveThree-class hardware ComfyUI shares the GPU with SenseNova; running both OOMs. The UI calls this endpoint before submit to surface a "stop ComfyUI" affordance. On Mac unified-memory hardware ComfyUI may not be running; precheck returns `ready: true`.

**Files:**
- Modify: `server.py`
- Test: `tests/test_api_sensenova_precheck.py`

- [ ] **Step 1 — Write the test:**

```python
from unittest.mock import patch
from fastapi.testclient import TestClient
from server import app

def test_precheck_ready():
    with patch("server._comfyui_running", return_value=False):
        r = TestClient(app).get("/api/sensenova/precheck")
    assert r.status_code == 200
    body = r.json()
    assert body["ready"] is True and body["blockers"] == []

def test_precheck_blocks_on_comfyui():
    with patch("server._comfyui_running", return_value=True):
        r = TestClient(app).get("/api/sensenova/precheck")
    body = r.json()
    assert body["ready"] is False
    assert any("comfy" in b.lower() for b in body["blockers"])
```

- [ ] **Step 2 — Run.** Expected: FAIL.

- [ ] **Step 3 — Add to `server.py`:**

```python
import socket as _socket

def _comfyui_running(host="127.0.0.1", port=8188, timeout=0.5) -> bool:
    try:
        with _socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False

@app.get("/api/sensenova/precheck")
async def sensenova_precheck():
    blockers: list[str] = []
    if _comfyui_running():
        blockers.append(
            "ComfyUI is running on localhost:8188. SenseNova needs the full GPU; "
            "stop ComfyUI before rendering.")
    return {"ready": not blockers, "blockers": blockers}
```

- [ ] **Step 4 — Run.** Expected: 2 passed.

- [ ] **Step 5 — Commit:**

```bash
git add server.py tests/test_api_sensenova_precheck.py
git commit -m "feat(api): GET /api/sensenova/precheck (ComfyUI tenancy guard)"
```

---

### Phase 2 manual verification

Before moving to UI, run a real render via curl on driveThree:

```bash
systemctl --user stop comfyui.service
systemctl --user start open-palette.service
curl -X POST http://localhost:8000/api/infographic/render \
  -H "Content-Type: application/json" \
  -d '{"template_id":"hub_and_spoke","tier":"draft","aspect":"1:1",
       "slots":{"title":"Wyltek","hub_desc":"robot mascot",
       "spokes":[{"label":"Frames"},{"label":"Edit"},{"label":"Remix"},{"label":"Music"}]}}'
```

Expected: `{"job_id":"..."}`. Poll `/api/jobs/<id>` until `status=done`, verify a PNG appears under `outputs/infographic/<job_id>/`. If this works, Phase 1+2 ship.

---

## Phase 3 — Builder UI MVP (one template, no image refs)

Goal of phase: a working `/studio/infographic` page that renders the hub_and_spoke template, submits a render, displays the result. No image refs, no history pane, no canvas — just the basic vertical slice.

### Task 13 — Page skeleton: HTML + nav wiring

**Why:** Land the route + the layout shell first. Empty panes are fine — Tasks 14–17 fill them.

**Files:**
- Create: `static/studio/infographic.html`
- Modify: `static/js/nav.js`

- [ ] **Step 1 — Read existing nav structure:** `sed -n '1,80p' static/js/nav.js`. Identify how studio pages are listed; mirror the worldgen / image-edit recent additions.

- [ ] **Step 2 — Create the HTML shell** at `static/studio/infographic.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>Infographic Builder — Wyltek Studio</title>
  <link rel="stylesheet" href="/static/css/style.css" />
</head>
<body>
  <header id="studio-header"><a href="/" class="back">← Studio</a><h1>Infographic Builder</h1></header>
  <main class="infographic-page">
    <aside class="template-pane" id="template-pane">
      <label>Template
        <select id="template-select" disabled><option>Loading…</option></select>
      </label>
      <form id="slot-form"></form>
      <fieldset class="render-tier">
        <legend>Render</legend>
        <label><input type="radio" name="tier" value="draft" checked /> Draft (~73s)</label>
        <label><input type="radio" name="tier" value="final" /> Final (~5min)</label>
        <button type="button" id="render-btn" disabled>Render</button>
      </fieldset>
    </aside>
    <section class="preview-pane">
      <div id="preview-status" class="muted">Pick a template, fill it in, hit Render.</div>
      <img id="preview-img" alt="" hidden />
    </section>
    <aside class="history-pane" id="history-pane"><h3>Recent</h3><ul id="history-list"></ul></aside>
  </main>
  <script type="module" src="/static/studio/js/infographic.js"></script>
</body>
</html>
```

- [ ] **Step 3 — Add the nav entry** in `static/js/nav.js` for `Infographic` → `/studio/infographic.html`. Match existing tile schema (icon emoji, label, subtitle).

- [ ] **Step 4 — Manual verification:** `curl -I http://localhost:8000/studio/infographic.html` → 200. Visit `/` in a browser; confirm the new tile appears and clicking it loads the empty page.

- [ ] **Step 5 — Commit:**

```bash
git add static/studio/infographic.html static/js/nav.js
git commit -m "feat(infographic): page shell + nav tile"
```

---

### Task 14 — Frontend module: load templates, render dropdown

**Why:** First slice of `infographic.js`. Fetch `/api/infographic/templates`, populate the dropdown, store the chosen template's slot schema.

**Files:**
- Create: `static/studio/js/infographic.js`

- [ ] **Step 1 — Create the module:**

```js
// /studio/infographic — template loader + form generator + render submit.

const els = {
  select: document.getElementById('template-select'),
  form: document.getElementById('slot-form'),
  renderBtn: document.getElementById('render-btn'),
  previewImg: document.getElementById('preview-img'),
  previewStatus: document.getElementById('preview-status'),
  tierInputs: () => Array.from(document.querySelectorAll('input[name="tier"]')),
};

const state = { templates: {}, current: null };

async function loadTemplates() {
  const r = await fetch('/api/infographic/templates');
  if (!r.ok) throw new Error(`templates fetch: ${r.status}`);
  const list = await r.json();
  state.templates = Object.fromEntries(list.map((t) => [t.id, t]));
  els.select.innerHTML = '';
  for (const t of list) {
    const opt = document.createElement('option');
    opt.value = t.id; opt.textContent = t.name;
    els.select.appendChild(opt);
  }
  els.select.disabled = false;
  if (list.length) {
    state.current = list[0];
    els.select.value = list[0].id;
    onTemplateChange();
  }
}

function onTemplateChange() {
  state.current = state.templates[els.select.value];
  els.renderBtn.disabled = !state.current;
  // Form generation arrives in Task 15.
}

els.select.addEventListener('change', onTemplateChange);
loadTemplates().catch((e) => {
  els.previewStatus.textContent = `Failed to load templates: ${e.message}`;
});
```

- [ ] **Step 2 — Manual verification:** reload `/studio/infographic.html`, open DevTools → Network, confirm `/api/infographic/templates` returns 200 with hub_and_spoke; the dropdown shows "Hub & Spoke".

- [ ] **Step 3 — Commit:**

```bash
git add static/studio/js/infographic.js
git commit -m "feat(infographic-ui): template loader + dropdown"
```

---

### Task 15 — Form generator from slot schema

**Why:** Render a form from the slot schema so we never write per-template UI code. Supports text, list (composite), color, and enum slots in this task; `image_ref` is added in Phase 4.

**Files:**
- Modify: `static/studio/js/infographic.js`

- [ ] **Step 1 — Append the generator:**

```js
function fieldId(path) { return `slot__${path.replace(/[^a-z0-9_]/gi, '_')}`; }

function renderSlot(slot, path, value) {
  const id = fieldId(path);
  const wrap = document.createElement('div');
  wrap.className = 'slot slot-' + slot.type;
  const label = slot.label || slot.id;

  if (slot.type === 'text') {
    wrap.innerHTML = `<label for="${id}">${label}${slot.required ? ' *' : ''}</label>`;
    const input = (slot.max_len && slot.max_len > 60)
      ? document.createElement('textarea')
      : document.createElement('input');
    input.id = id; input.name = path;
    if (slot.max_len) input.setAttribute('maxlength', slot.max_len);
    if (value != null) input.value = value;
    wrap.appendChild(input);
  } else if (slot.type === 'color') {
    wrap.innerHTML = `<label for="${id}">${label}</label>`;
    const input = document.createElement('input');
    input.type = 'color'; input.id = id; input.name = path;
    if (value) input.value = value;
    wrap.appendChild(input);
  } else if (slot.type === 'enum') {
    wrap.innerHTML = `<label for="${id}">${label}</label>`;
    const sel = document.createElement('select');
    sel.id = id; sel.name = path;
    for (const choice of slot.choices || []) {
      const o = document.createElement('option');
      o.value = o.textContent = choice;
      sel.appendChild(o);
    }
    if (value) sel.value = value;
    wrap.appendChild(sel);
  } else if (slot.type === 'list') {
    const fs = document.createElement('fieldset');
    fs.className = 'list-slot';
    const legend = document.createElement('legend'); legend.textContent = label; fs.appendChild(legend);
    const items = document.createElement('div'); items.className = 'list-items'; fs.appendChild(items);
    const initial = Array.isArray(value) ? value : Array.from({length: slot.min || 1}, () => ({}));
    for (const [i, item] of initial.entries()) addListItem(slot, path, items, i, item);
    const addBtn = document.createElement('button');
    addBtn.type = 'button'; addBtn.textContent = '+ Add row';
    addBtn.addEventListener('click', () => {
      const idx = items.children.length;
      if (slot.max && idx >= slot.max) return;
      addListItem(slot, path, items, idx, {});
    });
    fs.appendChild(addBtn);
    wrap.appendChild(fs);
  }
  return wrap;
}

function addListItem(parentSlot, parentPath, container, idx, value) {
  const item = document.createElement('div');
  item.className = 'list-item';
  for (const sub of parentSlot.item_slots || []) {
    item.appendChild(renderSlot(sub, `${parentPath}[${idx}].${sub.id}`, value[sub.id]));
  }
  const rm = document.createElement('button');
  rm.type = 'button'; rm.className = 'remove-row'; rm.textContent = '×';
  rm.addEventListener('click', () => item.remove());
  item.appendChild(rm);
  container.appendChild(item);
}

function buildForm(template) {
  els.form.innerHTML = '';
  for (const slot of template.slots) els.form.appendChild(renderSlot(slot, slot.id, null));
}

const _origOnTemplateChange = onTemplateChange;
window.onTemplateChange = function () {
  _origOnTemplateChange();
  if (state.current) buildForm(state.current);
};
els.select.removeEventListener('change', onTemplateChange);
els.select.addEventListener('change', window.onTemplateChange);
window.onTemplateChange();
```

- [ ] **Step 2 — Manual verification:** reload, hub_and_spoke renders with title/hub_desc inputs, hub_image (placeholder for Phase 4), spokes fieldset with 4 rows + "+ Add row" button.

- [ ] **Step 3 — Commit:**

```bash
git add static/studio/js/infographic.js
git commit -m "feat(infographic-ui): form generator from slot schema"
```

---

### Task 16 — Slot value harvest + render submit

**Why:** Walk the form back into a `{template_id, tier, aspect, slots, image_refs}` JSON body. Submit to `/api/infographic/render`, get a `job_id`, poll, display the PNG.

**Files:**
- Modify: `static/studio/js/infographic.js`

- [ ] **Step 1 — Locate the existing job-status route:** `grep -n "@app.get.*/api/jobs" server.py`. Confirm path and the `job.status` / `job.result_url` field names returned.

- [ ] **Step 2 — Append harvest + submit + poll:**

```js
function harvestForm(template) {
  function walk(slots) {
    const acc = {};
    for (const slot of slots) {
      if (slot.type === 'list') {
        const fsIdx = template.slots.findIndex((s) => s.id === slot.id);
        const itemsContainer = els.form.querySelectorAll('.list-items')[fsIdx];
        const list = [];
        if (itemsContainer) {
          for (const itemEl of itemsContainer.querySelectorAll('.list-item')) {
            const itemVal = {};
            for (const sub of slot.item_slots || []) {
              const input = itemEl.querySelector(`[name$="${sub.id}"]`);
              if (input && input.value) itemVal[sub.id] = input.value;
            }
            list.push(itemVal);
          }
        }
        acc[slot.id] = list;
      } else {
        const input = els.form.querySelector(`[name="${slot.id}"]`);
        if (input && input.value) acc[slot.id] = input.value;
      }
    }
    return acc;
  }
  return walk(template.slots);
}

function getTier() {
  const checked = els.tierInputs().find((i) => i.checked);
  return checked ? checked.value : 'draft';
}

async function submitRender() {
  const tpl = state.current;
  if (!tpl) return;
  els.renderBtn.disabled = true;
  els.previewStatus.textContent = 'Submitting…';
  try {
    const body = {
      template_id: tpl.id, tier: getTier(), aspect: '1:1',
      slots: harvestForm(tpl), image_refs: [],
    };
    const r = await fetch('/api/infographic/render', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`render: ${r.status} ${await r.text()}`);
    const {job_id} = await r.json();
    els.previewStatus.textContent = `Job ${job_id} submitted; polling…`;
    pollJob(job_id);
  } catch (e) {
    els.previewStatus.textContent = `Error: ${e.message}`;
    els.renderBtn.disabled = false;
  }
}

async function pollJob(jobId) {
  while (true) {
    await new Promise((r) => setTimeout(r, 2000));
    const r = await fetch(`/api/jobs/${jobId}`);
    if (!r.ok) { els.previewStatus.textContent = `Poll failed: ${r.status}`; break; }
    const job = await r.json();
    els.previewStatus.textContent = `${job.status} ${job.progress ?? ''}% ${job.message ?? ''}`;
    if (job.status === 'done') {
      const url = job.result_url || `/outputs/infographic/${jobId}/out.png`;
      els.previewImg.src = url + `?t=${Date.now()}`;
      els.previewImg.hidden = false;
      els.previewStatus.textContent = '';
      els.renderBtn.disabled = false;
      break;
    }
    if (job.status === 'error' || job.status === 'failed') {
      els.previewStatus.textContent = `Failed: ${job.message ?? ''}`;
      els.renderBtn.disabled = false;
      break;
    }
  }
}

els.renderBtn.addEventListener('click', submitRender);
```

> If the existing `/api/jobs/{id}` shape uses different field names (e.g., `state` instead of `status`), adjust `pollJob` accordingly.

- [ ] **Step 3 — Manual verification (real render):** stop ComfyUI, fill out hub_and_spoke (4 spokes), hit Render Draft, wait ~73s, PNG appears.

- [ ] **Step 4 — Commit:**

```bash
git add static/studio/js/infographic.js
git commit -m "feat(infographic-ui): submit render + poll job + display result"
```

---

### Task 17 — Aspect ratio dropdown

**Why:** Hard-coding `aspect: '1:1'` works for the MVP test; the user wants a real picker. Eleven trained buckets, dropdown, disabled when image refs are present (Phase 4 wires the disable behavior).

**Files:**
- Modify: `static/studio/infographic.html`
- Modify: `static/studio/js/infographic.js`

- [ ] **Step 1 — Add the dropdown** in `infographic.html`, inside `.render-tier` before the Render button:

```html
<label>Aspect
  <select id="aspect-select">
    <option value="1:1">1:1 (square)</option>
    <option value="16:9">16:9</option>
    <option value="9:16">9:16</option>
    <option value="3:2">3:2</option>
    <option value="2:3">2:3</option>
    <option value="4:3">4:3</option>
    <option value="3:4">3:4</option>
    <option value="1:2">1:2</option>
    <option value="2:1">2:1</option>
    <option value="1:3">1:3</option>
    <option value="3:1">3:1</option>
  </select>
</label>
```

- [ ] **Step 2 — Read it in JS:** in `submitRender()`, replace `aspect: '1:1'` with `aspect: document.getElementById('aspect-select').value`.

- [ ] **Step 3 — Manual verification:** reload, pick `16:9`, render, confirm PNG is 2048×1152.

- [ ] **Step 4 — Commit:**

```bash
git add static/studio/infographic.html static/studio/js/infographic.js
git commit -m "feat(infographic-ui): aspect ratio dropdown (11 trained buckets)"
```

---

## Phase 4 — Image references

Goal of phase: user adds 0..4 image refs labeled "Image 1, 2, …", references them in any text slot via "Insert Image N" chips, ref slots accept uploaded image paths. Aspect picker greys out when refs present.

### Task 18 — Image upload integration

**Why:** Reuse the existing `/api/upload` endpoint (or whatever the studio uses elsewhere — `image-edit.html` already accepts user uploads). Adds a single uploader function.

**Files:**
- Modify: `static/studio/js/infographic.js`

- [ ] **Step 1 — Locate the existing endpoint:** `grep -rn "FormData\|/api/upload\|/api/uploads" static/studio/js/ server.py | head`. Match its signature.

- [ ] **Step 2 — Add `uploadImage()` to infographic.js:**

```js
async function uploadImage(file) {
  const fd = new FormData();
  fd.append('file', file);
  const r = await fetch('/api/upload', {method: 'POST', body: fd});
  if (!r.ok) throw new Error(`upload: ${r.status}`);
  const j = await r.json();
  return j.url || j.path;  // adjust to actual response shape
}
```

> Adjust `/api/upload` to whatever the existing endpoint is called. Keep `uploadImage` as the single point of upload responsibility.

- [ ] **Step 3 — Commit:**

```bash
git add static/studio/js/infographic.js
git commit -m "feat(infographic-ui): uploadImage helper"
```

---

### Task 19 — Image-ref state model + “Add Image” button

**Why:** Numbered list of `{label: 'Image 1', url}` records. "Add image" button triggers a file picker. Each ref shows a thumbnail and a remove ×. Cap at 4 (per spec). Removing renumbers the rest.

**Files:**
- Modify: `static/studio/infographic.html`
- Modify: `static/studio/js/infographic.js`

- [ ] **Step 1 — Add the image-refs region** in `infographic.html`, after `<form id="slot-form">`:

```html
<section class="image-refs">
  <h4>Image references (optional, max 4)</h4>
  <ul id="image-ref-list"></ul>
  <input type="file" id="image-ref-input" accept="image/png,image/jpeg" hidden />
  <button type="button" id="image-ref-add">+ Add image</button>
</section>
```

- [ ] **Step 2 — State + render in JS:**

```js
state.imageRefs = [];

function renderImageRefs() {
  const ul = document.getElementById('image-ref-list');
  ul.innerHTML = '';
  for (const [i, ref] of state.imageRefs.entries()) {
    const li = document.createElement('li');
    li.className = 'image-ref';
    li.innerHTML = `
      <span class="ref-label">Image ${i + 1}</span>
      <img src="${ref.url}" alt="Image ${i + 1}" />
      <button type="button" class="remove" data-i="${i}">×</button>`;
    li.querySelector('button.remove').addEventListener('click', () => {
      state.imageRefs.splice(i, 1);
      renderImageRefs();
      updateAspectDisabled();
    });
    ul.appendChild(li);
  }
  document.getElementById('image-ref-add').disabled = state.imageRefs.length >= 4;
}

document.getElementById('image-ref-add').addEventListener('click', () => {
  document.getElementById('image-ref-input').click();
});
document.getElementById('image-ref-input').addEventListener('change', async (ev) => {
  const f = ev.target.files[0];
  if (!f || state.imageRefs.length >= 4) return;
  try {
    const url = await uploadImage(f);
    state.imageRefs.push({url});
    renderImageRefs();
    updateAspectDisabled();
  } catch (e) {
    els.previewStatus.textContent = `Upload failed: ${e.message}`;
  }
  ev.target.value = '';
});

function updateAspectDisabled() {
  const sel = document.getElementById('aspect-select');
  if (state.imageRefs.length > 0) {
    sel.disabled = true;
    sel.title = 'Output size auto-derived from Image 1 when refs are present';
  } else {
    sel.disabled = false; sel.removeAttribute('title');
  }
}
```

- [ ] **Step 3 — Manual verification:** add 2 PNGs → Image 1 + Image 2. Remove Image 1 → former Image 2 renumbers. Aspect select greys when ≥1 ref.

- [ ] **Step 4 — Commit:**

```bash
git add static/studio/infographic.html static/studio/js/infographic.js
git commit -m "feat(infographic-ui): image references with Add Image + remove"
```

---

### Task 20 — Image-ref slot rendering + “Insert Image N” chips

**Why:** Slots typed `image_ref` get a select dropdown listing the current refs (`Image 1`, …) plus `(none)`. Free-text slots get chip buttons that insert `[Image N]` at the cursor — prevents typos.

**Files:**
- Modify: `static/studio/js/infographic.js`

- [ ] **Step 1 — Render `image_ref` slots:** in `renderSlot()`, add:

```js
} else if (slot.type === 'image_ref') {
  wrap.innerHTML = `<label for="${id}">${label}</label>`;
  const sel = document.createElement('select');
  sel.id = id; sel.name = path; sel.dataset.imageRef = '1';
  rebuildImageRefSelect(sel);
  if (value) sel.value = value;
  wrap.appendChild(sel);
}
```

Helper:

```js
function rebuildImageRefSelect(sel) {
  const cur = sel.value;
  sel.innerHTML = '<option value="">(none)</option>';
  for (const [i, ref] of state.imageRefs.entries()) {
    const o = document.createElement('option');
    o.value = ref.url; o.textContent = `Image ${i + 1}`;
    sel.appendChild(o);
  }
  if (cur && Array.from(sel.options).some((o) => o.value === cur)) sel.value = cur;
}
```

In `renderImageRefs()`, after rebuilding:

```js
for (const sel of els.form.querySelectorAll('select[data-image-ref]')) rebuildImageRefSelect(sel);
```

- [ ] **Step 2 — Add chip-insert for free-text slots:** in `renderSlot` text branch, after the input is created:

```js
if (slot.max_len === undefined || slot.max_len > 60) {
  const chips = document.createElement('div');
  chips.className = 'image-chips';
  chips.dataset.target = id;
  wrap.appendChild(chips);
}
```

Helper:

```js
function rebuildChips() {
  for (const cont of els.form.querySelectorAll('.image-chips')) {
    const targetId = cont.dataset.target;
    cont.innerHTML = '';
    for (const i of state.imageRefs.keys()) {
      const b = document.createElement('button');
      b.type = 'button'; b.className = 'chip';
      b.textContent = `Insert Image ${i + 1}`;
      b.addEventListener('click', () => {
        const ta = document.getElementById(targetId);
        const tok = `[Image ${i + 1}]`;
        const start = ta.selectionStart ?? ta.value.length;
        const end = ta.selectionEnd ?? ta.value.length;
        ta.value = ta.value.slice(0, start) + tok + ta.value.slice(end);
        ta.focus();
        ta.selectionStart = ta.selectionEnd = start + tok.length;
      });
      cont.appendChild(b);
    }
  }
}
```

Call `rebuildChips()` from `renderImageRefs()` and after `buildForm()`.

- [ ] **Step 3 — Submit harvest:** in `submitRender()`, change `image_refs: []` to:

```js
image_refs: state.imageRefs.map((r) => r.url),
```

- [ ] **Step 4 — Manual verification (real render):** stop ComfyUI; add 2 image refs; in hub_and_spoke "Hub concept", type `A friendly mascot like [Image 1] holding [Image 2]`; render Draft; confirm visible influence of both refs.

- [ ] **Step 5 — Commit:**

```bash
git add static/studio/js/infographic.js
git commit -m "feat(infographic-ui): image-ref slots + Insert Image N chips"
```

---

### Task 21 — Backend: pass image_refs through assembler reliably

**Why:** When users put `[Image 1]` directly in a text slot the assembler doesn't see those tokens — it only stamps `[Image N]` for slots typed `image_ref`. Phase 4 introduces a hybrid: text-slot inline tokens are passed through, and `image_refs[]` in the request body defines the path list. The server merges both lists.

**Files:**
- Test: `tests/test_infographics_assemble.py` (add)
- Modify: `server.py`
- Test: `tests/test_api_infographic_render.py` (add)

- [ ] **Step 1 — Add an assembler test:**

```python
def test_inline_image_token_in_text_slot_passthrough():
    tpl = {"id":"f","name":"F","description":"x",
           "slots":[{"id":"body","type":"text","required":True}],
           "prompt_template":"{{body}}"}
    r = assemble_prompt(tpl, {"body":"Show [Image 1] next to [Image 2]."})
    assert r.image_paths == []
    assert "[Image 1]" in r.prompt and "[Image 2]" in r.prompt
```

- [ ] **Step 2 — Run.** Expected: passed (assembler is pass-through).

- [ ] **Step 3 — Update `infographic_render`** in `server.py` so the path list merges:

```python
all_paths = list(result.image_paths)
external = [u for u in body.image_refs if u not in all_paths]
all_paths.extend(external)
```

Use `all_paths` in the `submit_background` call (replacing `result.image_paths or list(body.image_refs)`).

- [ ] **Step 4 — Add API test:**

```python
def test_render_merges_external_refs():
    body = _good()
    body["image_refs"] = ["/u/a.png","/u/b.png"]
    body["slots"]["hub_desc"] = "See [Image 1] and [Image 2]"
    captured = {}
    def _fake(engine, params):
        captured.update(params); return "job-z"
    with patch("server.submit_background", side_effect=_fake):
        r = TestClient(app).post("/api/infographic/render", json=body)
    assert r.status_code == 202
    assert captured["image_paths"] == ["/u/a.png","/u/b.png"]
```

- [ ] **Step 5 — Run** all infographic tests:

```
pytest tests/test_infographics_*.py tests/test_api_infographic_*.py tests/test_sensenova_*.py -v
```

Expected: all passed.

- [ ] **Step 6 — Commit:**

```bash
git add server.py tests/test_infographics_assemble.py tests/test_api_infographic_render.py
git commit -m "feat(api): merge external image_refs with slot-derived paths"
```

---

### Task 22 — Numbering invariant test

**Why:** "Image-ref-typed slot paths come first (declaration order), then external refs (user order)" is the contract. Lock it down.

**Files:**
- Test: `tests/test_image_ref_numbering.py`

- [ ] **Step 1 — Write the test:**

```python
from studio.infographics import assemble_prompt

def test_slot_refs_first_then_inline():
    tpl = {"id":"x","name":"x","description":"x",
        "slots":[
            {"id":"hub","type":"image_ref"},
            {"id":"body","type":"text","required":True},
            {"id":"foot","type":"image_ref"}],
        "prompt_template":"{{hub}} body={{body}} foot={{foot}}"}
    r = assemble_prompt(tpl, {
        "hub":"/u/hub.png","foot":"/u/foot.png",
        "body":"compare with [Image 3] and [Image 4]"})
    assert "[Image 1]" in r.prompt and "[Image 2]" in r.prompt
    assert "[Image 3]" in r.prompt and "[Image 4]" in r.prompt
    assert r.image_paths == ["/u/hub.png","/u/foot.png"]
```

- [ ] **Step 2 — Run.** Expected: passed.

- [ ] **Step 3 — Commit:**

```bash
git add tests/test_image_ref_numbering.py
git commit -m "test(infographic): lock numbering invariant for slot vs inline refs"
```

---

## Phase 5 — Remaining 7 templates

Goal of phase: ship comparison, timeline, stats, quadrant, list, geographic-map, hierarchical templates with preview thumbnails. Each is a JSON file + a small "loads & assembles" test.

### Task 23 — `comparison.json`

**Why:** Side-by-side "vs." infographic. Two columns × (heading, 3-5 bullets, optional image).

**Files:**
- Create: `templates/infographics/comparison.json`
- Test: `tests/test_infographics_comparison.py`

- [ ] **Step 1 — Write the test:**

```python
from pathlib import Path
from studio.infographics import assemble_prompt, load_templates
T = Path(__file__).resolve().parent.parent / "templates" / "infographics"

def test_comparison_assembles():
    tpl = load_templates(T)["comparison"]
    r = assemble_prompt(tpl, {
        "title":"Coffee vs Tea",
        "left":[{"heading":"Coffee","bullets":[{"text":"bold"},{"text":"rich"},{"text":"warm"}]}],
        "right":[{"heading":"Tea","bullets":[{"text":"light"},{"text":"clean"},{"text":"warm"}]}]})
    assert "Coffee" in r.prompt and "Tea" in r.prompt
```

- [ ] **Step 2 — Run.** Expected: FAIL.

- [ ] **Step 3 — Create the JSON:**

```json
{
  "id":"comparison","name":"Comparison / vs.","description":"Two side-by-side columns. Best for before/after, A vs B, pros/cons.",
  "preview":"templates/infographics/_previews/comparison.png",
  "slots":[
    {"id":"title","type":"text","label":"Title","max_len":60,"required":true},
    {"id":"left","type":"list","label":"Left column","min":1,"max":1,
     "item_slots":[
        {"id":"heading","type":"text","label":"Heading","max_len":30,"required":true},
        {"id":"bullets","type":"list","min":3,"max":5,
         "item_slots":[{"id":"text","type":"text","max_len":60,"required":true}]},
        {"id":"image","type":"image_ref","label":"Image (optional)"}
     ]},
    {"id":"right","type":"list","label":"Right column","min":1,"max":1,
     "item_slots":[
        {"id":"heading","type":"text","label":"Heading","max_len":30,"required":true},
        {"id":"bullets","type":"list","min":3,"max":5,
         "item_slots":[{"id":"text","type":"text","max_len":60,"required":true}]},
        {"id":"image","type":"image_ref","label":"Image (optional)"}
     ]}
  ],
  "prompt_template":"A side-by-side comparison infographic titled \"{{title}}\", flat illustration on cream paper with thick black outlines and gentle drop shadows. Two equal columns separated by a center divider.{{#left}} Left column titled \"{{heading}}\":{{#bullets}} • {{text}};{{/bullets}}{{#image}} illustrated with {{image}};{{/image}}{{/left}}{{#right}} Right column titled \"{{heading}}\":{{#bullets}} • {{text}};{{/bullets}}{{#image}} illustrated with {{image}};{{/image}}{{/right}} Balanced composition; monospaced bullets."
}
```

> The wrapping `min:1, max:1` list lets us reuse the existing list slot for nested fields without a new slot type. The form generator handles it as a one-row list.

- [ ] **Step 4 — Run.** Expected: passed.

- [ ] **Step 5 — Commit:**

```bash
git add templates/infographics/comparison.json tests/test_infographics_comparison.py
git commit -m "feat(infographic): comparison template"
```

---

### Task 24 — `timeline.json`, `stats.json`, `quadrant.json`, `list.json`

**Why:** Four straightforward templates, each created via the same TDD shape as Tasks 4 + 23. Batched: one test file per template, one JSON per template, one commit at the end.

**Files:**
- Create: `templates/infographics/{timeline,stats,quadrant,list}.json`
- Test: `tests/test_infographics_{timeline,stats,quadrant,list}.py`

- [ ] **Step 1 — Write all four test files.** Pattern:

```python
from pathlib import Path
from studio.infographics import assemble_prompt, load_templates
T = Path(__file__).resolve().parent.parent / "templates" / "infographics"
```

Then for each template:

`tests/test_infographics_timeline.py`:

```python
def test_timeline_assembles():
    tpl = load_templates(T)["timeline"]
    r = assemble_prompt(tpl, {"title":"From idea to ship",
        "steps":[{"label":"Idea","description":"the spark"},
                 {"label":"Plan","description":"the spec"},
                 {"label":"Build","description":"the code"},
                 {"label":"Ship","description":"the world"}]})
    assert "Idea" in r.prompt and "Ship" in r.prompt
```

`tests/test_infographics_stats.py`:

```python
def test_stats_assembles():
    tpl = load_templates(T)["stats"]
    r = assemble_prompt(tpl, {"title":"By the numbers",
        "cells":[{"value":"1M+","label":"users"},
                 {"value":"99.9%","label":"uptime"},
                 {"value":"5x","label":"faster"}]})
    assert "1M+" in r.prompt and "99.9%" in r.prompt
```

`tests/test_infographics_quadrant.py`:

```python
def test_quadrant_assembles():
    tpl = load_templates(T)["quadrant"]
    r = assemble_prompt(tpl, {"title":"Strategy 2x2",
        "x_axis_low":"low cost","x_axis_high":"high cost",
        "y_axis_low":"low value","y_axis_high":"high value",
        "quadrants":[{"label":"do later"},{"label":"do now"},
                     {"label":"drop"},{"label":"delegate"}]})
    assert "Strategy 2x2" in r.prompt
```

`tests/test_infographics_list.py`:

```python
def test_list_assembles():
    tpl = load_templates(T)["list"]
    r = assemble_prompt(tpl, {"title":"5 reasons to ship",
        "rows":[{"label":"Speed","description":"faster"},
                {"label":"Quality","description":"less rework"},
                {"label":"Focus","description":"tight scope"},
                {"label":"Joy","description":"morale"},
                {"label":"Trust","description":"we deliver"}]})
    assert "5 reasons to ship" in r.prompt
```

- [ ] **Step 2 — Run all four; expect FAIL.**

- [ ] **Step 3 — Create the four JSON files:**

`timeline.json`:

```json
{"id":"timeline","name":"Timeline / Process","description":"Linear sequence of steps.",
 "preview":"templates/infographics/_previews/timeline.png",
 "slots":[
   {"id":"title","type":"text","max_len":60,"required":true},
   {"id":"steps","type":"list","min":3,"max":7,
    "item_slots":[
      {"id":"label","type":"text","max_len":24,"required":true},
      {"id":"description","type":"text","max_len":80,"required":false},
      {"id":"image","type":"image_ref"}
    ]}
 ],
 "prompt_template":"A horizontal timeline infographic titled \"{{title}}\", flat illustration on cream paper with thick black outlines, an arrow connecting steps left-to-right. Steps:{{#steps}} → \"{{label}}\"{{#description}} ({{description}}){{/description}}{{#image}} illustrated with {{image}}{{/image}};{{/steps}} Each step a circular badge; soft drop shadows; monospaced descriptions."
}
```

`stats.json`:

```json
{"id":"stats","name":"Stat Showcase","description":"Big numbers grid.",
 "preview":"templates/infographics/_previews/stats.png",
 "slots":[
   {"id":"title","type":"text","max_len":60,"required":true},
   {"id":"cells","type":"list","min":3,"max":6,
    "item_slots":[
      {"id":"value","type":"text","max_len":12,"required":true},
      {"id":"label","type":"text","max_len":40,"required":true},
      {"id":"image","type":"image_ref"}
    ]}
 ],
 "prompt_template":"A stat-showcase infographic titled \"{{title}}\", flat illustration on cream paper, thick black outlines. Stat cells:{{#cells}} \"{{value}}\" — {{label}}{{#image}} illustrated with {{image}}{{/image}};{{/cells}} Each cell soft-shadowed rectangle; value 4× label size; bold rounded sans-serif; generous whitespace."
}
```

`quadrant.json`:

```json
{"id":"quadrant","name":"Quadrant / 2×2 Matrix","description":"Two-axis 2×2 framework.",
 "preview":"templates/infographics/_previews/quadrant.png",
 "slots":[
   {"id":"title","type":"text","max_len":60,"required":true},
   {"id":"x_axis_low","type":"text","max_len":24,"required":true},
   {"id":"x_axis_high","type":"text","max_len":24,"required":true},
   {"id":"y_axis_low","type":"text","max_len":24,"required":true},
   {"id":"y_axis_high","type":"text","max_len":24,"required":true},
   {"id":"quadrants","type":"list","min":4,"max":4,
    "item_slots":[{"id":"label","type":"text","max_len":30,"required":true}]}
 ],
 "prompt_template":"A 2×2 quadrant matrix infographic titled \"{{title}}\", flat illustration on cream paper, thick black outlines. X-axis \"{{x_axis_low}}\" (left) → \"{{x_axis_high}}\" (right). Y-axis \"{{y_axis_low}}\" (bottom) → \"{{y_axis_high}}\" (top). Quadrants clockwise from top-left:{{#quadrants}} \"{{label}}\";{{/quadrants}} Each quadrant pastel-tinted; small mascot illustration; black axis arrows; soft drop shadows; monospaced axis labels."
}
```

`list.json`:

```json
{"id":"list","name":"List / N Things","description":"Vertical list of N points.",
 "preview":"templates/infographics/_previews/list.png",
 "slots":[
   {"id":"title","type":"text","max_len":60,"required":true},
   {"id":"intro","type":"text","max_len":200,"required":false},
   {"id":"rows","type":"list","min":3,"max":7,
    "item_slots":[
      {"id":"label","type":"text","max_len":30,"required":true},
      {"id":"description","type":"text","max_len":80,"required":false},
      {"id":"image","type":"image_ref"}
    ]}
 ],
 "prompt_template":"A vertical list infographic titled \"{{title}}\"{{#intro}} with intro \"{{intro}}\"{{/intro}}, flat illustration on cream paper, thick black outlines. Numbered rows:{{#rows}} \"{{label}}\"{{#description}} — {{description}}{{/description}}{{#image}} illustrated with {{image}}{{/image}};{{/rows}} Each row a horizontal pill with circular numbered badge on left; soft drop shadows; rounded sans-serif labels; monospaced descriptions."
}
```

- [ ] **Step 4 — Run all four:**

```
pytest tests/test_infographics_timeline.py tests/test_infographics_stats.py tests/test_infographics_quadrant.py tests/test_infographics_list.py -v
```

Expected: 4 passed.

- [ ] **Step 5 — Commit:**

```bash
git add templates/infographics/timeline.json templates/infographics/stats.json templates/infographics/quadrant.json templates/infographics/list.json tests/test_infographics_timeline.py tests/test_infographics_stats.py tests/test_infographics_quadrant.py tests/test_infographics_list.py
git commit -m "feat(infographic): timeline/stats/quadrant/list templates"
```

---

### Task 25 — `map.json` and `hierarchy.json`

**Why:** The two structurally novel templates: `map` has an enum slot for region; `hierarchy` is a nested list (parents and children).

**Files:**
- Create: `templates/infographics/{map,hierarchy}.json`
- Test: `tests/test_infographics_{map,hierarchy}.py`

- [ ] **Step 1 — Write tests:**

`tests/test_infographics_map.py`:

```python
from pathlib import Path
from studio.infographics import assemble_prompt, load_templates
T = Path(__file__).resolve().parent.parent / "templates" / "infographics"

def test_map_assembles():
    tpl = load_templates(T)["map"]
    r = assemble_prompt(tpl, {"title":"User distribution","region":"world",
        "overlays":[{"location":"US","label":"40%","value":"120k users"},
                    {"location":"EU","label":"25%","value":"75k users"},
                    {"location":"APAC","label":"20%","value":"60k users"}]})
    assert "User distribution" in r.prompt and "world" in r.prompt
```

`tests/test_infographics_hierarchy.py`:

```python
from pathlib import Path
from studio.infographics import assemble_prompt, load_templates
T = Path(__file__).resolve().parent.parent / "templates" / "infographics"

def test_hierarchy_assembles():
    tpl = load_templates(T)["hierarchy"]
    r = assemble_prompt(tpl, {"title":"Company structure","root":"CEO",
        "levels":[
            {"label":"C-suite","nodes":[{"label":"CTO"},{"label":"CFO"}]},
            {"label":"Directors","nodes":[{"label":"Eng"},{"label":"Ops"},{"label":"Sales"}]}]})
    assert "CEO" in r.prompt and "CTO" in r.prompt
```

- [ ] **Step 2 — Run; expect FAIL.**

- [ ] **Step 3 — Create JSONs:**

`map.json`:

```json
{"id":"map","name":"Geographic Map","description":"Map with regional overlays.",
 "preview":"templates/infographics/_previews/map.png",
 "slots":[
   {"id":"title","type":"text","max_len":60,"required":true},
   {"id":"region","type":"enum","label":"Region",
    "choices":["world","north_america","south_america","europe","africa","asia","oceania"],"required":true},
   {"id":"overlays","type":"list","min":2,"max":12,
    "item_slots":[
      {"id":"location","type":"text","max_len":40,"required":true},
      {"id":"label","type":"text","max_len":24,"required":true},
      {"id":"value","type":"text","max_len":40,"required":false},
      {"id":"image","type":"image_ref"}
    ]}
 ],
 "prompt_template":"A geographic-map infographic titled \"{{title}}\", flat illustration on cream paper, thick black outlines. Stylized cartoon map of the {{region}} region (recognizable silhouette, no realistic geography needed). Overlay markers:{{#overlays}} \"{{location}}\" — {{label}}{{#value}} ({{value}}){{/value}}{{#image}} illustrated with {{image}}{{/image}};{{/overlays}} Each marker a circular pastel badge connected to its region by a thin black leader line; soft drop shadows."
}
```

`hierarchy.json`:

```json
{"id":"hierarchy","name":"Hierarchical","description":"Pyramid, tree, or org chart.",
 "preview":"templates/infographics/_previews/hierarchy.png",
 "slots":[
   {"id":"title","type":"text","max_len":60,"required":true},
   {"id":"root","type":"text","max_len":30,"required":true},
   {"id":"levels","type":"list","min":1,"max":4,
    "item_slots":[
      {"id":"label","type":"text","max_len":30,"required":false},
      {"id":"nodes","type":"list","min":1,"max":6,
       "item_slots":[
         {"id":"label","type":"text","max_len":30,"required":true},
         {"id":"image","type":"image_ref"}
       ]}
    ]}
 ],
 "prompt_template":"A hierarchical org-chart infographic titled \"{{title}}\", flat illustration on cream paper, thick black outlines. Top: \"{{root}}\". Descending levels:{{#levels}}{{#label}} ({{label}}){{/label}}{{#nodes}} \"{{label}}\"{{#image}} illustrated with {{image}}{{/image}};{{/nodes}}{{/levels}} Each node a rounded-rectangle badge; black connector lines; alternating pastel level fills; soft drop shadows; rounded sans-serif labels."
}
```

- [ ] **Step 4 — Run.** Expected: passed.

- [ ] **Step 5 — Commit:**

```bash
git add templates/infographics/map.json templates/infographics/hierarchy.json tests/test_infographics_map.py tests/test_infographics_hierarchy.py
git commit -m "feat(infographic): map + hierarchy templates"
```

---

### Task 26 — Generate preview thumbnails

**Why:** Dropdown UX is much better with visuals. One render per template, manually run on driveThree, downscaled, committed.

**Files:**
- Create: `templates/infographics/_previews/*.png` (8 files)

- [ ] **Step 1 — Stop ComfyUI:** `systemctl --user stop comfyui.service`.

- [ ] **Step 2 — Render one example per template via the new UI** with reasonable example slots, Draft tier. After each:

```bash
mkdir -p templates/infographics/_previews
LATEST=$(ls -t outputs/infographic/*/out.png | head -1)
convert "$LATEST" -resize "600x400>" templates/infographics/_previews/<id>.png
```

Repeat for each of the eight templates.

- [ ] **Step 3 — Restart ComfyUI:** `systemctl --user start comfyui.service`.

- [ ] **Step 4 — Commit:**

```bash
git add templates/infographics/_previews/
git commit -m "feat(infographic): preview thumbnails for 8 templates"
```

---

### Task 27 — Frontend: render preview thumbnail in dropdown

**Why:** Show a 60×40 thumbnail next to the dropdown so users recognize templates by sight.

**Files:**
- Modify: `static/studio/infographic.html`
- Modify: `static/studio/js/infographic.js`

- [ ] **Step 1 — Add a preview image element** in `infographic.html`, after the template `<select>`:

```html
<img id="template-preview" alt="" hidden />
```

- [ ] **Step 2 — Update on template change** in `onTemplateChange()`:

```js
const prev = document.getElementById('template-preview');
if (state.current && state.current.preview) {
  prev.src = '/' + state.current.preview;
  prev.hidden = false;
} else {
  prev.hidden = true;
}
```

(Verify `templates/infographics/_previews/` is mounted by the static handler in `server.py`. If not, add a route — most likely `app.mount("/templates", ...)` covers it; verify via `curl -I /templates/infographics/_previews/hub_and_spoke.png`.)

- [ ] **Step 3 — Manual verification:** reload, cycle templates, thumbnail changes.

- [ ] **Step 4 — Commit:**

```bash
git add static/studio/js/infographic.js static/studio/infographic.html
git commit -m "feat(infographic-ui): template preview thumbnail"
```

---

## Phase 6 — Render history pane

Goal of phase: each render persists with a sidecar JSON; the right pane lists recent renders; clicking loads slot values + image into the form.

### Task 28 — Persist render with sidecar JSON

**Why:** Capture slot values, refs, prompt, seed, tier, template id at render time so the user can return to a render and edit from where they left off.

**Files:**
- Modify: `server.py`
- Test: `tests/test_infographic_history_persistence.py`

- [ ] **Step 1 — Write the test:**

```python
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from server import _run_job

@pytest.mark.asyncio
async def test_sidecar_written(tmp_path):
    fake = tmp_path / "infographic" / "j1" / "out.png"
    fake.parent.mkdir(parents=True); fake.write_bytes(b"\x89PNG")
    with patch("backends.sensenova.generate", new=AsyncMock(return_value=fake)), \
         patch("server.OUTPUTS_ROOT", tmp_path):
        await _run_job("j1", {"engine":"sensenova","prompt":"p","image_paths":[],
            "aspect":"1:1","tier":"draft","template_id":"hub_and_spoke","slots":{"title":"T"}},
            on_progress=AsyncMock())
    sidecar = fake.with_suffix(".json")
    assert sidecar.exists()
    data = json.loads(sidecar.read_text())
    assert data["template_id"] == "hub_and_spoke"
    assert data["slots"]["title"] == "T"
```

- [ ] **Step 2 — Run; expect FAIL.**

- [ ] **Step 3 — Add sidecar write** in `_run_job`'s sensenova branch, after the `await _sensenova_generate(...)` call:

```python
import json as _json
sidecar = png.with_suffix(".json")
sidecar.write_text(_json.dumps({
    "template_id": params.get("template_id"),
    "slots": params.get("slots", {}),
    "image_paths": params.get("image_paths", []),
    "aspect": params.get("aspect"),
    "tier": params["tier"],
    "prompt": params.get("prompt"),
    "seed": params.get("seed", 42),
}, indent=2))
```

- [ ] **Step 4 — Run.** Expected: passed.

- [ ] **Step 5 — Commit:**

```bash
git add server.py tests/test_infographic_history_persistence.py
git commit -m "feat(infographic): sidecar JSON per render"
```

---

### Task 29 — `GET /api/infographic/history`

**Why:** List recent renders for the history pane.

**Files:**
- Modify: `server.py`
- Test: `tests/test_api_infographic_history.py`

- [ ] **Step 1 — Write the test:**

```python
import json
from unittest.mock import patch
from fastapi.testclient import TestClient
from server import app

def test_history_lists(tmp_path):
    base = tmp_path / "infographic"
    for j in ("a","b","c"):
        d = base / j; d.mkdir(parents=True)
        (d / "out.png").write_bytes(b"\x89PNG")
        (d / "out.json").write_text(json.dumps({"template_id":"hub_and_spoke","slots":{"title":j.upper()},"tier":"draft"}))
    with patch("server.OUTPUTS_ROOT", tmp_path):
        r = TestClient(app).get("/api/infographic/history")
    assert r.status_code == 200
    body = r.json()
    assert {e["job_id"] for e in body} == {"a","b","c"}
    assert all("png_url" in e and "sidecar" in e for e in body)
```

- [ ] **Step 2 — Run; expect FAIL.**

- [ ] **Step 3 — Add to `server.py`:**

```python
@app.get("/api/infographic/history")
async def infographic_history(limit: int = 30):
    base = Path(OUTPUTS_ROOT) / "infographic"
    if not base.exists(): return []
    out: list[dict] = []
    for sub in sorted(base.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
        png = sub / "out.png"; sidecar = sub / "out.json"
        if not (png.exists() and sidecar.exists()): continue
        try:
            data = json.loads(sidecar.read_text())
        except json.JSONDecodeError:
            continue
        out.append({"job_id": sub.name,
                    "png_url": f"/outputs/infographic/{sub.name}/out.png",
                    "sidecar": data})
    return out
```

- [ ] **Step 4 — Run.** Expected: passed.

- [ ] **Step 5 — Commit:**

```bash
git add server.py tests/test_api_infographic_history.py
git commit -m "feat(api): GET /api/infographic/history"
```

---

### Task 30 — Frontend: render history list + click-to-load

**Why:** Right pane shows thumbnails; click loads the sidecar back into the form and the PNG into the preview.

**Files:**
- Modify: `static/studio/js/infographic.js`

- [ ] **Step 1 — Append history loader:**

```js
async function loadHistory() {
  const r = await fetch('/api/infographic/history');
  if (!r.ok) return;
  const list = await r.json();
  const ul = document.getElementById('history-list');
  ul.innerHTML = '';
  for (const entry of list) {
    const li = document.createElement('li');
    li.innerHTML = `
      <button type="button" class="history-item" data-job="${entry.job_id}">
        <img src="${entry.png_url}" alt="" />
        <span>${entry.sidecar.template_id}</span>
      </button>`;
    li.querySelector('button').addEventListener('click', () => loadFromHistory(entry));
    ul.appendChild(li);
  }
}

function loadFromHistory(entry) {
  if (state.current?.id !== entry.sidecar.template_id) {
    els.select.value = entry.sidecar.template_id;
    window.onTemplateChange();
  }
  fillFormFromSlots(state.current.slots, entry.sidecar.slots, '');
  els.previewImg.src = entry.png_url + `?t=${Date.now()}`;
  els.previewImg.hidden = false;
}

function fillFormFromSlots(slotDefs, values, path) {
  for (const slot of slotDefs) {
    const p = path ? `${path}.${slot.id}` : slot.id;
    const v = values?.[slot.id];
    if (slot.type === 'list' && Array.isArray(v)) {
      const items = els.form.querySelectorAll('.list-items')[
        state.current.slots.findIndex((s) => s.id === slot.id)];
      if (items) {
        items.innerHTML = '';
        for (const [i, item] of v.entries()) addListItem(slot, p, items, i, item);
      }
    } else {
      const input = els.form.querySelector(`[name="${p}"]`);
      if (input && v != null) input.value = v;
    }
  }
}

const _origPollJob = pollJob;
pollJob = async function (jobId) {
  await _origPollJob(jobId);
  loadHistory();
};
loadHistory();
```

- [ ] **Step 2 — Manual verification:** render several infographics, click each in history → form repopulates, preview swaps. Edit a slot, re-render → new entry on top.

- [ ] **Step 3 — Commit:**

```bash
git add static/studio/js/infographic.js
git commit -m "feat(infographic-ui): render history with click-to-load"
```

---

## Phase 7 — Post-edit canvas (V1-canvas)

Goal of phase: HTML5 canvas overlays the rendered PNG. Drop PNG from desktop, paste from clipboard, drag to move, drag corners to resize, save composite as a new render.

### Task 31 — Canvas module skeleton + base image render

**Why:** Lay down `canvas-edit.js` with the render loop and a layer model. Tasks 32–35 add interactions.

**Files:**
- Modify: `static/studio/infographic.html`
- Create: `static/studio/js/canvas-edit.js`

- [ ] **Step 1 — Replace `<img id="preview-img" ... />` in `infographic.html`** with:

```html
<div class="preview-wrap">
  <canvas id="preview-canvas" hidden></canvas>
  <div id="canvas-tools" hidden>
    <button type="button" id="canvas-paste">Paste image</button>
    <button type="button" id="canvas-delete">Delete layer</button>
    <button type="button" id="canvas-save">Save composite</button>
  </div>
</div>
```

- [ ] **Step 2 — Create the module** at `static/studio/js/canvas-edit.js`:

```js
// Inline post-edit canvas. Renders base PNG plus a stack of PNG overlay
// layers. Layers can be moved, resized, deleted, and the composite can
// be flattened back to a PNG.

export class PreviewCanvas {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.base = null;
    this.layers = [];
    this.selected = -1;
    this.drag = null;
  }

  async setBase(url) {
    const img = await loadImage(url);
    this.canvas.width = img.naturalWidth;
    this.canvas.height = img.naturalHeight;
    this.base = {img};
    this.layers = [];
    this.selected = -1;
    this.canvas.hidden = false;
    this.render();
  }

  async addLayerFromBlob(blob, x = 50, y = 50) {
    const img = await loadImage(URL.createObjectURL(blob));
    this.layers.push({img, x, y, w: img.naturalWidth, h: img.naturalHeight});
    this.selected = this.layers.length - 1;
    this.render();
  }

  deleteSelected() {
    if (this.selected < 0) return;
    this.layers.splice(this.selected, 1);
    this.selected = -1;
    this.render();
  }

  render() {
    const {ctx, canvas} = this;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (this.base) ctx.drawImage(this.base.img, 0, 0);
    for (const [i, L] of this.layers.entries()) {
      ctx.drawImage(L.img, L.x, L.y, L.w, L.h);
      if (i === this.selected) {
        ctx.strokeStyle = '#0af'; ctx.lineWidth = 2;
        ctx.strokeRect(L.x, L.y, L.w, L.h);
        for (const [hx, hy] of [[L.x,L.y],[L.x+L.w,L.y],[L.x,L.y+L.h],[L.x+L.w,L.y+L.h]]) {
          ctx.fillStyle = '#0af';
          ctx.fillRect(hx - 6, hy - 6, 12, 12);
        }
      }
    }
  }

  toBlob() {
    return new Promise((res) => this.canvas.toBlob(res, 'image/png'));
  }
}

function loadImage(src) {
  return new Promise((res, rej) => {
    const img = new Image();
    img.onload = () => res(img);
    img.onerror = rej;
    img.src = src;
  });
}
```

- [ ] **Step 3 — Wire it into `infographic.js`** — replace the preview-display lines (`els.previewImg.src = ...`) with:

```js
import {PreviewCanvas} from './canvas-edit.js';
const canvas = new PreviewCanvas(document.getElementById('preview-canvas'));
const tools = document.getElementById('canvas-tools');
// In pollJob and loadFromHistory, replace previewImg.src lines with:
await canvas.setBase(url);
tools.hidden = false;
```

(Remove the `els.previewImg` element + JS references.)

- [ ] **Step 4 — Manual verification:** render → canvas shows the PNG at native size.

- [ ] **Step 5 — Commit:**

```bash
git add static/studio/infographic.html static/studio/js/canvas-edit.js static/studio/js/infographic.js
git commit -m "feat(canvas): preview canvas skeleton + base image render"
```

---

### Task 32 — Drop PNG from desktop

**Why:** Drag-and-drop a PNG onto the canvas → adds as a layer at the drop position.

**Files:**
- Modify: `static/studio/js/canvas-edit.js`

- [ ] **Step 1 — Add drag-drop handlers** in the `PreviewCanvas` constructor:

```js
canvas.addEventListener('dragover', (e) => { e.preventDefault(); });
canvas.addEventListener('drop', async (e) => {
  e.preventDefault();
  const f = e.dataTransfer?.files?.[0];
  if (!f || !f.type.startsWith('image/')) return;
  const rect = canvas.getBoundingClientRect();
  const x = (e.clientX - rect.left) * (canvas.width / rect.width);
  const y = (e.clientY - rect.top) * (canvas.height / rect.height);
  await this.addLayerFromBlob(f, x, y);
});
```

- [ ] **Step 2 — Manual verification:** drag a PNG onto the canvas → appears at the drop point.

- [ ] **Step 3 — Commit:**

```bash
git add static/studio/js/canvas-edit.js
git commit -m "feat(canvas): drag-drop PNG to add layer"
```

---

### Task 33 — Move + resize selected layer

**Why:** Click selects; drag body to move; drag corner to resize. Hold Shift to constrain aspect.

**Files:**
- Modify: `static/studio/js/canvas-edit.js`

- [ ] **Step 1 — Add hit-testing + mouse handlers** in the constructor:

```js
canvas.addEventListener('mousedown', (e) => this._mousedown(e));
canvas.addEventListener('mousemove', (e) => this._mousemove(e));
canvas.addEventListener('mouseup',   ()  => this._mouseup());
```

Methods:

```js
_eventXY(e) {
  const r = this.canvas.getBoundingClientRect();
  return [(e.clientX - r.left) * (this.canvas.width / r.width),
          (e.clientY - r.top)  * (this.canvas.height / r.height)];
}

_hitCorner(L, x, y) {
  const corners = [
    [L.x,       L.y,       'tl'], [L.x+L.w, L.y,       'tr'],
    [L.x,       L.y+L.h,   'bl'], [L.x+L.w, L.y+L.h,   'br'],
  ];
  for (const [cx, cy, name] of corners)
    if (Math.abs(x - cx) <= 8 && Math.abs(y - cy) <= 8) return name;
  return null;
}

_mousedown(e) {
  const [x, y] = this._eventXY(e);
  for (let i = this.layers.length - 1; i >= 0; i--) {
    const L = this.layers[i];
    const corner = (i === this.selected) ? this._hitCorner(L, x, y) : null;
    if (corner) {
      this.drag = {mode:'resize', corner, startX:x, startY:y, layer0:{...L}, shift:e.shiftKey};
      return;
    }
    if (x >= L.x && x <= L.x + L.w && y >= L.y && y <= L.y + L.h) {
      this.selected = i;
      this.drag = {mode:'move', startX:x, startY:y, layer0:{...L}};
      this.render();
      return;
    }
  }
  this.selected = -1;
  this.render();
}

_mousemove(e) {
  if (!this.drag) return;
  const [x, y] = this._eventXY(e);
  const L = this.layers[this.selected];
  const dx = x - this.drag.startX, dy = y - this.drag.startY;
  const L0 = this.drag.layer0;
  if (this.drag.mode === 'move') {
    L.x = L0.x + dx; L.y = L0.y + dy;
  } else {
    let nx=L0.x, ny=L0.y, nw=L0.w, nh=L0.h;
    if (this.drag.corner.includes('r')) nw = Math.max(8, L0.w + dx);
    if (this.drag.corner.includes('l')) { nw = Math.max(8, L0.w - dx); nx = L0.x + dx; }
    if (this.drag.corner.includes('b')) nh = Math.max(8, L0.h + dy);
    if (this.drag.corner.includes('t')) { nh = Math.max(8, L0.h - dy); ny = L0.y + dy; }
    if (this.drag.shift || e.shiftKey) {
      const asp = L0.w / L0.h;
      if (nw / nh > asp) nw = nh * asp; else nh = nw / asp;
    }
    L.x = nx; L.y = ny; L.w = nw; L.h = nh;
  }
  this.render();
}

_mouseup() { this.drag = null; }
```

- [ ] **Step 2 — Wire delete button** in `infographic.js`:

```js
document.getElementById('canvas-delete').addEventListener('click', () => canvas.deleteSelected());
```

- [ ] **Step 3 — Manual verification:** drop a PNG, click → blue outline. Drag body → moves. Drag corner → resizes. Shift+drag → preserves aspect. Delete button → removes.

- [ ] **Step 4 — Commit:**

```bash
git add static/studio/js/canvas-edit.js static/studio/js/infographic.js
git commit -m "feat(canvas): select / move / resize layer with corner handles"
```

---

### Task 34 — Paste image from clipboard

**Why:** `Ctrl+V` (or "Paste image" button) pulls an image off the clipboard and adds it as a layer.

**Files:**
- Modify: `static/studio/js/canvas-edit.js`
- Modify: `static/studio/js/infographic.js`

- [ ] **Step 1 — Add `pasteFromClipboard()`** method:

```js
async pasteFromClipboard() {
  try {
    const items = await navigator.clipboard.read();
    for (const it of items) {
      for (const t of it.types) {
        if (t.startsWith('image/')) {
          const blob = await it.getType(t);
          await this.addLayerFromBlob(blob, 60, 60);
          return true;
        }
      }
    }
  } catch (e) { console.warn('clipboard read failed:', e); }
  return false;
}
```

- [ ] **Step 2 — Wire button + Ctrl+V** in `infographic.js`:

```js
document.getElementById('canvas-paste').addEventListener('click', () => canvas.pasteFromClipboard());
document.addEventListener('paste', (e) => {
  for (const it of (e.clipboardData?.items || [])) {
    if (it.type.startsWith('image/')) {
      const blob = it.getAsFile();
      if (blob) canvas.addLayerFromBlob(blob, 60, 60);
      return;
    }
  }
});
```

- [ ] **Step 3 — Manual verification:** screenshot something to OS clipboard, click "Paste image" → appears as a layer; or press Ctrl+V on the page → same.

- [ ] **Step 4 — Commit:**

```bash
git add static/studio/js/canvas-edit.js static/studio/js/infographic.js
git commit -m "feat(canvas): paste image from clipboard"
```

---

### Task 35 — Save composite as a new render

**Why:** `<canvas>.toBlob()` → POST to `/api/infographic/composite` → server stores under a new job-id-shaped folder so it shows up in history alongside generated renders.

**Files:**
- Modify: `server.py`
- Modify: `static/studio/js/infographic.js`
- Test: `tests/test_api_infographic_composite.py`

- [ ] **Step 1 — Write the API test:**

```python
import io, json
from unittest.mock import patch
from fastapi.testclient import TestClient
from server import app

def test_composite_saves_png(tmp_path):
    (tmp_path / "infographic").mkdir()
    fake = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\0" * 8)
    with patch("server.OUTPUTS_ROOT", tmp_path):
        r = TestClient(app).post("/api/infographic/composite",
            files={"file":("composite.png", fake, "image/png")},
            data={"base_render_id":"abc"})
    assert r.status_code == 200
    body = r.json()
    new_id = body["job_id"]
    assert new_id != "abc"
    assert (tmp_path / "infographic" / new_id / "out.png").exists()
    sidecar = json.loads((tmp_path / "infographic" / new_id / "out.json").read_text())
    assert sidecar.get("composite_of") == "abc"
```

- [ ] **Step 2 — Run; expect FAIL.**

- [ ] **Step 3 — Add the endpoint** in `server.py`:

```python
import secrets as _secrets
from fastapi import UploadFile, File, Form

@app.post("/api/infographic/composite")
async def infographic_composite(
    file: UploadFile = File(...),
    base_render_id: str = Form(""),
):
    new_id = "c-" + _secrets.token_hex(4)
    out_dir = Path(OUTPUTS_ROOT) / "infographic" / new_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "out.png").write_bytes(await file.read())
    (out_dir / "out.json").write_text(json.dumps({
        "composite_of": base_render_id,
        "template_id": "composite",
        "slots": {},
        "tier": "composite",
    }, indent=2))
    return {"job_id": new_id, "png_url": f"/outputs/infographic/{new_id}/out.png"}
```

- [ ] **Step 4 — Wire save button** in `infographic.js`:

```js
document.getElementById('canvas-save').addEventListener('click', async () => {
  const blob = await canvas.toBlob();
  if (!blob) return;
  const fd = new FormData();
  fd.append('file', blob, 'composite.png');
  fd.append('base_render_id', state.lastRenderId || '');
  const r = await fetch('/api/infographic/composite', {method:'POST', body: fd});
  if (r.ok) { await loadHistory(); els.previewStatus.textContent = 'Composite saved.'; }
  else      { els.previewStatus.textContent = `Save failed: ${r.status}`; }
});
```

> Track `state.lastRenderId` — set when `pollJob` completes (`state.lastRenderId = jobId;`).

- [ ] **Step 5 — Run.** Expected: passed.

- [ ] **Step 6 — Manual verification:** render → drop a PNG layer → click "Save composite" → new entry in history pane.

- [ ] **Step 7 — Commit:**

```bash
git add server.py static/studio/js/infographic.js tests/test_api_infographic_composite.py
git commit -m "feat(canvas): save composite as new render"
```

---

## Phase 8 — Self-host install + ComfyUI precheck UI

Goal of phase: anyone on supported hardware can clone and run `setup-sensenova.sh` to get a working install. The UI surfaces the precheck blocker before submit.

### Task 36 — `setup-sensenova.sh` skeleton + platform detection

**Why:** One script that detects ROCm vs CUDA vs MPS and routes to the right install path. Refuses other hardware up front.

**Files:**
- Create: `scripts/setup-sensenova.sh`

- [ ] **Step 1 — Write the script skeleton:**

```bash
#!/usr/bin/env bash
# setup-sensenova.sh — install SenseNova-U1 dependencies for Wyltek Studio.
#
# Detects platform (linux+ROCm | linux+CUDA | macOS-ARM64 | unsupported),
# creates /data/venvs/sensenova-u1, installs torch + repo deps, downloads
# weights via huggingface-cli. Idempotent: re-running is safe.

set -euo pipefail

VENV=${SENSENOVA_VENV:-/data/venvs/sensenova-u1}
REPO=${SENSENOVA_REPO:-$HOME/SenseNova-U1}
WEIGHTS_FINAL=${SENSENOVA_WEIGHTS_FINAL:-/data/sensenova-u1-weights}
WEIGHTS_DRAFT=${SENSENOVA_WEIGHTS_DRAFT:-/data/sensenova-u1-weights-8step}

detect_platform() {
  case "$(uname -s)" in
    Linux)
      if command -v rocminfo >/dev/null 2>&1; then echo "linux-rocm"; return; fi
      if command -v nvidia-smi >/dev/null 2>&1; then echo "linux-cuda"; return; fi
      echo "linux-cpu" ;;
    Darwin)
      if [[ "$(uname -m)" == "arm64" ]]; then echo "macos-arm64"; else echo "macos-intel"; fi ;;
    *) echo "unsupported" ;;
  esac
}

PLATFORM=$(detect_platform)
echo "[setup] platform=$PLATFORM"
case "$PLATFORM" in
  linux-rocm|linux-cuda|macos-arm64) ;;
  *) echo "[setup] unsupported platform: $PLATFORM. Aborting." >&2; exit 1 ;;
esac
```

- [ ] **Step 2 — `chmod +x scripts/setup-sensenova.sh`**

- [ ] **Step 3 — Manual verification:** `./scripts/setup-sensenova.sh` → on driveThree, prints `[setup] platform=linux-rocm`.

- [ ] **Step 4 — Commit:**

```bash
git add scripts/setup-sensenova.sh
git commit -m "feat(setup): SenseNova install script — platform detection"
```

---

### Task 37 — `setup-sensenova.sh` — venv + torch install

**Why:** Per-platform torch wheel install into the dedicated venv.

**Files:**
- Modify: `scripts/setup-sensenova.sh`

- [ ] **Step 1 — Append:**

```bash
# --- venv ---
if [[ ! -d "$VENV" ]]; then
  echo "[setup] creating venv at $VENV"
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install --upgrade pip wheel

# --- torch (platform-specific) ---
case "$PLATFORM" in
  linux-rocm)
    "$VENV/bin/pip" install --upgrade --pre torch --index-url https://download.pytorch.org/whl/nightly/rocm6.2
    ;;
  linux-cuda)
    "$VENV/bin/pip" install --upgrade torch --index-url https://download.pytorch.org/whl/cu121
    ;;
  macos-arm64)
    "$VENV/bin/pip" install --upgrade torch
    ;;
esac

# --- repo deps ---
if [[ ! -d "$REPO" ]]; then
  echo "[setup] cloning SenseNova-U1 to $REPO"
  git clone https://github.com/sensenova/SenseNova-U1 "$REPO"
fi
"$VENV/bin/pip" install -r "$REPO/requirements.txt" || true
```

> Verify the rocm wheel index URL matches the active install (memory `project_sensenova_u1_rocm.md`). The `|| true` on requirements.txt is intentional — SenseNova's requirements may include CUDA-only deps that no-op on ROCm.

- [ ] **Step 2 — Manual verification:** run on driveThree, confirm `"$VENV/bin/python" -c "import torch; print(torch.__version__)"` returns a working version.

- [ ] **Step 3 — Commit:**

```bash
git add scripts/setup-sensenova.sh
git commit -m "feat(setup): venv + torch + repo install"
```

---

### Task 38 — `setup-sensenova.sh` — weights download

**Why:** Both 50-step and 8-step weight sets pulled from HuggingFace.

**Files:**
- Modify: `scripts/setup-sensenova.sh`

- [ ] **Step 1 — Append:**

```bash
# --- weights ---
"$VENV/bin/pip" install --upgrade huggingface-hub

if [[ ! -d "$WEIGHTS_FINAL" || -z "$(ls -A "$WEIGHTS_FINAL" 2>/dev/null)" ]]; then
  echo "[setup] downloading 50-step weights to $WEIGHTS_FINAL"
  mkdir -p "$WEIGHTS_FINAL"
  "$VENV/bin/huggingface-cli" download sensenova/SenseNova-U1-8B-MoT --local-dir "$WEIGHTS_FINAL"
fi

if [[ ! -d "$WEIGHTS_DRAFT" || -z "$(ls -A "$WEIGHTS_DRAFT" 2>/dev/null)" ]]; then
  echo "[setup] downloading 8-step preview weights to $WEIGHTS_DRAFT"
  mkdir -p "$WEIGHTS_DRAFT"
  "$VENV/bin/huggingface-cli" download sensenova/SenseNova-U1-8B-MoT-8step-preview --local-dir "$WEIGHTS_DRAFT"
fi

echo "[setup] done. Configure open-palette with:"
echo "  SENSENOVA_VENV=$VENV"
echo "  SENSENOVA_REPO=$REPO"
echo "  SENSENOVA_WEIGHTS_FINAL=$WEIGHTS_FINAL"
echo "  SENSENOVA_WEIGHTS_DRAFT=$WEIGHTS_DRAFT"
```

> Verify HuggingFace repo names against `wyltek-infographic-log.md` Run 002/003 — those names are authoritative. If a HF mirror isn't available, document the ModelScope fallback path; do not invent URLs.

- [ ] **Step 2 — Commit:**

```bash
git add scripts/setup-sensenova.sh
git commit -m "feat(setup): weights download via huggingface-cli"
```

---

### Task 39 — Frontend: ComfyUI precheck banner

**Why:** Before render, hit `/api/sensenova/precheck`. If blockers, show a banner and disable Render until the user confirms ComfyUI is stopped.

**Files:**
- Modify: `static/studio/infographic.html`
- Modify: `static/studio/js/infographic.js`

- [ ] **Step 1 — Add a banner element** in `infographic.html`, just below `<header>`:

```html
<div id="precheck-banner" class="warning" hidden></div>
```

- [ ] **Step 2 — Probe before submit:** prepend to `submitRender()`:

```js
const pre = await (await fetch('/api/sensenova/precheck')).json();
if (!pre.ready) {
  const banner = document.getElementById('precheck-banner');
  banner.hidden = false;
  banner.innerHTML = `
    <strong>Cannot render:</strong>
    <ul>${pre.blockers.map((b) => `<li>${b}</li>`).join('')}</ul>
    <button type="button" id="precheck-recheck">Recheck</button>`;
  document.getElementById('precheck-recheck').addEventListener('click', () => {
    banner.hidden = true; submitRender();
  });
  return;
}
```

- [ ] **Step 3 — Manual verification:** start ComfyUI, try Render → banner lists ComfyUI as blocker. Stop ComfyUI, click Recheck → render proceeds.

- [ ] **Step 4 — Commit:**

```bash
git add static/studio/infographic.html static/studio/js/infographic.js
git commit -m "feat(infographic-ui): precheck banner blocks render when ComfyUI runs"
```

---

### Task 40 — README section + plan close-out

**Why:** Document for self-hosters: spec link, install script, hardware matrix, known limitations.

**Files:**
- Modify: `README.md`

- [ ] **Step 1 — Locate the README** (`ls README.md docs/README.md 2>/dev/null`).

- [ ] **Step 2 — Append:**

```markdown
## Infographic Builder

Template-driven infographic page at `/studio/infographic`, powered by
SenseNova-U1-8B-MoT. Eight built-in templates, optional numbered image
references, draft/final tier toggle, inline post-edit canvas.

### Setup

```bash
./scripts/setup-sensenova.sh
```

Detects platform (Linux ROCm, Linux CUDA, macOS Apple Silicon),
installs torch + the SenseNova-U1 repo + weights into
`/data/venvs/sensenova-u1` and `/data/sensenova-u1-weights{,-8step}`.

### Hardware matrix

| Platform | Status |
|---|---|
| Linux + ROCm 7.2+, 24GB VRAM | Verified (RX 7900 XTX) |
| Linux + CUDA 12.x, 24GB+ VRAM | Best-effort (community-verified) |
| macOS Apple Silicon, 32GB+ unified | Best-effort (community-verified) |
| Anything else | Unsupported |

### Custom templates

Drop a JSON file into `templates/infographics/` matching
`studio/infographics_schema.json`. Hot-reloaded on page refresh.

### Known limits

- Concurrent renders OOM the GPU; stop ComfyUI before rendering on
  shared-GPU hardware. The page surfaces this via a precheck banner.
- The post-edit canvas (V1-canvas) supports drop / move / resize /
  paste. Region-select to system-clipboard for GIMP round-trips is a
  v1.5 feature.
- See `docs/superpowers/specs/2026-05-05-infographic-builder-design.md`
  for the full design.
```

- [ ] **Step 3 — Commit:**

```bash
git add README.md
git commit -m "docs: README section for Infographic Builder"
```

---

## Phase verification (full system)

- [ ] Stop ComfyUI: `systemctl --user stop comfyui.service`
- [ ] Visit `/studio/infographic`, cycle through all 8 templates, render Draft of each
- [ ] Render Final of one (5-min wait)
- [ ] Add 2 image refs, render with `[Image 1]` and `[Image 2]` in slot text
- [ ] Drop a PNG onto the result, resize, paste from clipboard, save composite
- [ ] Reload page, click history entry → form repopulates
- [ ] Drop a malformed JSON in `templates/infographics/` → confirm it's skipped without breaking the page
- [ ] Restart ComfyUI: `systemctl --user start comfyui.service`

---

## Self-review

- **Spec coverage:** Every spec section maps to one or more tasks:
  - Template engine (spec §1) → Tasks 1–3
  - Builder UI (spec §2) → Tasks 13–17, 19–20, 27, 30, 39
  - SenseNova backend (spec §3) → Tasks 5–7, 8, 11
  - Render history (spec §4) → Tasks 28–30
  - Post-edit canvas V1-canvas (spec §5) → Tasks 31–35
  - Multi-image conditioning protocol → Tasks 5, 21, 22
  - 8 templates → Tasks 4, 23–25, 26 (previews)
  - Hardware story → Tasks 36–38
  - API surface → Tasks 9, 10, 11, 12, 29, 35
  - Risks (cap on image refs) → Task 19 (`>= 4` guard)
- **Placeholder scan:** No "TODO" / "TBD" / "implement later" remain. Every code block is real code; every command is runnable. Where a path or constant must be confirmed against the existing codebase (e.g., `OUTPUTS_ROOT` vs `OUTPUT_DIR` in Task 11, the upload endpoint name in Task 18), the task explicitly directs the implementer to a `grep`/`sed` step before the edit.
- **Type consistency:** `assemble_prompt` returns `AssemblyResult(prompt, image_paths)` consistently across Tasks 3, 7, 21, 22. `generate(...)` signature matches across Tasks 5, 6, 7, 11, 28. The frontend `state.imageRefs` is `[{url}]` everywhere it appears.
- **Spec scope:** One coherent feature, not a bundle of subsystems. Phased so each phase is shippable.

Plan complete and saved to `docs/superpowers/plans/2026-05-05-infographic-builder.md`.
