# Image Edit Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an image editing page to Wyltek Studio that accepts a source image (from the Generate page handoff, or direct upload), an optional painted mask, and a text prompt, then produces an edited image via ComfyUI using FLUX.1 Kontext [dev] or Qwen-Image-Edit.

**Architecture:** One new HTML/JS page at `/studio/image-edit.html` backed by a new `POST /api/edit` route. Two new workflow-builder methods added to `backends/comfyui.py` following the existing inline-dict pattern. Edits land in `outputs/edits/`. Source handoff from the Generate page uses a URL param (`?asset=<filename>`) with no file copy. Direct upload is folded into the `/api/edit` multipart body.

**Tech Stack:** FastAPI + Python backend; vanilla JS + HTML5 canvas frontend; ComfyUI as the model runtime; pytest for backend tests; Playwright for E2E.

**Design doc:** `docs/superpowers/specs/2026-04-16-image-edit-page-design.md`

---

## File Structure

**New files:**
- `static/studio/image-edit.html` — editor page (layout, CSS, markup)
- `static/studio/js/image-edit.js` — page controller (source handling, mask canvas, API call, gallery)
- `tests/__init__.py` — marks `tests/` as a package
- `tests/conftest.py` — pytest fixtures (fake ComfyUI, temp outputs dir)
- `tests/test_comfyui_edit_workflows.py` — unit tests for workflow builders
- `tests/test_api_edit.py` — unit tests for `/api/edit` route
- `tests/e2e/image-edit.spec.ts` — Playwright E2E
- `tests/e2e/package.json` — Playwright deps
- `tests/e2e/playwright.config.ts` — Playwright config
- `requirements-dev.txt` — pytest dev deps

**Modified files:**
- `backends/comfyui.py` — add `build_kontext_edit_workflow`, `build_qwen_edit_workflow`, `run_edit`
- `server.py` — add `POST /api/edit` route
- `model_catalog.py` — add Kontext + Qwen-Image-Edit entries, add `capability` field
- `static/index.html` — "Send to Editor" button on main viewer and gallery thumbnails
- `static/js/app.js` — wire "Send to Editor" clicks
- `static/js/nav.js` — add "Edit" nav entry under Studio

**Unchanged:** `static/js/project-picker.js`, `/outputs/*` static mount, toast system, ComfyUI client plumbing, job queue.

---

## Task 1: Bootstrap pytest infrastructure

**Files:**
- Create: `requirements-dev.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_smoke.py`

- [ ] **Step 1.1: Create dev requirements file**

Create `requirements-dev.txt` with:
```
pytest>=8.0.0
pytest-asyncio>=0.23.0
httpx>=0.25.0
```

- [ ] **Step 1.2: Install dev deps**

Run:
```bash
cd ~/open-palette && pip install -r requirements-dev.txt
```
Expected: all three packages install cleanly (or already present).

- [ ] **Step 1.3: Create `tests/__init__.py`**

Empty file:
```python
```

- [ ] **Step 1.4: Create `tests/conftest.py`**

```python
"""Shared pytest fixtures."""

import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_outputs(monkeypatch):
    """Redirect outputs/ to a temp dir for the duration of a test."""
    tmp = Path(tempfile.mkdtemp(prefix="wyltek-test-"))
    (tmp / "edits").mkdir()
    monkeypatch.chdir(tmp.parent)
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)
```

- [ ] **Step 1.5: Create smoke test to verify pytest runs**

Create `tests/test_smoke.py`:
```python
def test_pytest_works():
    assert 1 + 1 == 2
```

- [ ] **Step 1.6: Run smoke test**

Run:
```bash
cd ~/open-palette && pytest tests/test_smoke.py -v
```
Expected: `1 passed`.

- [ ] **Step 1.7: Commit**

```bash
cd ~/open-palette && git add requirements-dev.txt tests/__init__.py tests/conftest.py tests/test_smoke.py
git commit -m "test: bootstrap pytest infrastructure"
```

---

## Task 2: Register editing models in catalog

**Files:**
- Modify: `model_catalog.py`

- [ ] **Step 2.1: Write failing test for catalog entries**

Create `tests/test_model_catalog.py`:
```python
"""Verify edit-capable models are registered."""

from model_catalog import CATALOG


def test_kontext_dev_is_registered():
    kontext = next((m for m in CATALOG if m["id"] == "flux-kontext-dev"), None)
    assert kontext is not None
    assert kontext.get("capability") == "edit"
    assert kontext["category"] == "Image Editing"
    assert kontext["type"] == "comfyui-unet"


def test_qwen_image_edit_is_registered():
    qwen = next((m for m in CATALOG if m["id"] == "qwen-image-edit"), None)
    assert qwen is not None
    assert qwen.get("capability") == "edit"
    assert qwen["category"] == "Image Editing"


def test_edit_models_are_filterable():
    edit_models = [m for m in CATALOG if m.get("capability") == "edit"]
    assert len(edit_models) >= 2
```

- [ ] **Step 2.2: Run test to verify it fails**

Run:
```bash
cd ~/open-palette && pytest tests/test_model_catalog.py -v
```
Expected: FAIL — `kontext is None`.

- [ ] **Step 2.3: Add entries to `model_catalog.py`**

Locate the end of the Flux GGUF section (after `flux-schnell-q4`, around `flux2-klein-4b`). Insert a new section labeled "Image Editing" with two entries:

```python
    # --- Image Editing ---
    {
        "id": "flux-kontext-dev", "name": "FLUX.1 Kontext [dev]",
        "desc": "Instruction-driven image editing. Preserves identity, follows edit prompts like 'flatten, remove gradient'. ~24GB bf16, non-commercial license.",
        "url": "https://huggingface.co/black-forest-labs/FLUX.1-Kontext-dev/resolve/main/flux1-kontext-dev.safetensors",
        "filename": "flux1-kontext-dev.safetensors",
        "size_mb": 23800, "category": "Image Editing", "type": "comfyui-unet",
        "capability": "edit",
    },
    {
        "id": "qwen-image-edit", "name": "Qwen-Image-Edit",
        "desc": "Instruction-driven image editing. Strong on stylistic changes. Apache 2.0, ~20B class.",
        "url": "https://huggingface.co/Qwen/Qwen-Image-Edit/resolve/main/qwen-image-edit.safetensors",
        "filename": "qwen-image-edit.safetensors",
        "size_mb": 20000, "category": "Image Editing", "type": "comfyui-unet",
        "capability": "edit",
    },
```

- [ ] **Step 2.4: Run test to verify it passes**

Run:
```bash
cd ~/open-palette && pytest tests/test_model_catalog.py -v
```
Expected: `3 passed`.

- [ ] **Step 2.5: Commit**

```bash
cd ~/open-palette && git add model_catalog.py tests/test_model_catalog.py
git commit -m "feat: register FLUX.1 Kontext and Qwen-Image-Edit in model catalog"
```

---

## Task 3: Build FLUX.1 Kontext edit workflow

**Files:**
- Modify: `backends/comfyui.py` (add method `build_kontext_edit_workflow`)
- Create: `tests/test_comfyui_edit_workflows.py`

- [ ] **Step 3.1: Write failing test**

Create `tests/test_comfyui_edit_workflows.py`:
```python
"""Unit tests for edit workflow builders. No ComfyUI required."""

from backends.comfyui import ComfyUIBackend


def test_kontext_workflow_has_required_nodes():
    backend = ComfyUIBackend(url="http://example.invalid")
    wf = backend.build_kontext_edit_workflow(
        source_filename="src.png",
        mask_filename=None,
        prompt="flatten, solid colors, no gradient",
        params={"steps": 25, "cfg": 2.5, "seed": 42},
    )
    node_types = {n["class_type"] for n in wf.values()}
    assert "UNETLoader" in node_types
    assert "LoadImage" in node_types
    assert "KSampler" in node_types
    assert "VAEDecode" in node_types
    assert "SaveImage" in node_types


def test_kontext_workflow_injects_prompt_and_source():
    backend = ComfyUIBackend(url="http://example.invalid")
    wf = backend.build_kontext_edit_workflow(
        source_filename="logo.png",
        mask_filename=None,
        prompt="remove text",
        params={"steps": 25, "cfg": 2.5, "seed": 7},
    )
    prompt_nodes = [n for n in wf.values() if n["class_type"] == "CLIPTextEncode"]
    assert any(n["inputs"]["text"] == "remove text" for n in prompt_nodes)
    load_image_nodes = [n for n in wf.values() if n["class_type"] == "LoadImage"]
    assert any(n["inputs"]["image"] == "logo.png" for n in load_image_nodes)


def test_kontext_workflow_sets_seed():
    backend = ComfyUIBackend(url="http://example.invalid")
    wf = backend.build_kontext_edit_workflow(
        source_filename="src.png",
        mask_filename=None,
        prompt="edit",
        params={"steps": 25, "cfg": 2.5, "seed": 1234},
    )
    ksampler = next(n for n in wf.values() if n["class_type"] == "KSampler")
    assert ksampler["inputs"]["seed"] == 1234
```

- [ ] **Step 3.2: Run test to verify it fails**

Run:
```bash
cd ~/open-palette && pytest tests/test_comfyui_edit_workflows.py -v
```
Expected: FAIL — `build_kontext_edit_workflow` does not exist.

- [ ] **Step 3.3: Implement `build_kontext_edit_workflow`**

Open `backends/comfyui.py`. Locate the `ComfyUIBackend` class. Add the following method (place it near existing `build_*_workflow` style methods; the exact location follows the pattern of the main text-to-image builder):

```python
    def build_kontext_edit_workflow(
        self,
        source_filename: str,
        mask_filename: str | None,
        prompt: str,
        params: dict,
    ) -> dict:
        """Build a ComfyUI workflow for FLUX.1 Kontext [dev] image editing.

        Kontext takes a source image + text instruction and preserves identity
        while applying the edit. Uses ReferenceLatent to inject the source into
        conditioning. When mask_filename is provided, an inpaint path is used.
        """
        seed = int(params.get("seed", 0))
        steps = int(params.get("steps", 25))
        cfg = float(params.get("cfg", 2.5))

        workflow: dict = {
            "1": {
                "class_type": "UNETLoader",
                "inputs": {
                    "unet_name": "flux1-kontext-dev.safetensors",
                    "weight_dtype": "fp8_e4m3fn",
                },
            },
            "2": {
                "class_type": "DualCLIPLoader",
                "inputs": {
                    "clip_name1": "t5xxl_fp8_e4m3fn.safetensors",
                    "clip_name2": "clip_l.safetensors",
                    "type": "flux",
                },
            },
            "3": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "ae.safetensors"},
            },
            "4": {
                "class_type": "LoadImage",
                "inputs": {"image": source_filename},
            },
            "5": {
                "class_type": "VAEEncode",
                "inputs": {"pixels": ["4", 0], "vae": ["3", 0]},
            },
            "6": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": prompt, "clip": ["2", 0]},
            },
            "7": {
                "class_type": "ReferenceLatent",
                "inputs": {
                    "conditioning": ["6", 0],
                    "latent": ["5", 0],
                },
            },
            "8": {
                "class_type": "FluxGuidance",
                "inputs": {"conditioning": ["7", 0], "guidance": cfg},
            },
            "9": {
                "class_type": "CLIPTextEncode",
                "inputs": {"text": "", "clip": ["2", 0]},
            },
            "10": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": 1.0,
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "denoise": 1.0,
                    "model": ["1", 0],
                    "positive": ["8", 0],
                    "negative": ["9", 0],
                    "latent_image": ["5", 0],
                },
            },
            "11": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["10", 0], "vae": ["3", 0]},
            },
            "12": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "edit_kontext",
                    "images": ["11", 0],
                },
            },
        }

        if mask_filename:
            workflow["13"] = {
                "class_type": "LoadImageMask",
                "inputs": {"image": mask_filename, "channel": "alpha"},
            }
            workflow["14"] = {
                "class_type": "SetLatentNoiseMask",
                "inputs": {"samples": ["5", 0], "mask": ["13", 0]},
            }
            workflow["10"]["inputs"]["latent_image"] = ["14", 0]

        return workflow
```

- [ ] **Step 3.4: Run test to verify it passes**

Run:
```bash
cd ~/open-palette && pytest tests/test_comfyui_edit_workflows.py -v
```
Expected: `3 passed`.

- [ ] **Step 3.5: Add mask-path test**

Append to `tests/test_comfyui_edit_workflows.py`:
```python
def test_kontext_workflow_with_mask_adds_noise_mask():
    backend = ComfyUIBackend(url="http://example.invalid")
    wf = backend.build_kontext_edit_workflow(
        source_filename="src.png",
        mask_filename="mask.png",
        prompt="edit",
        params={"steps": 25, "cfg": 2.5, "seed": 1},
    )
    node_types = {n["class_type"] for n in wf.values()}
    assert "LoadImageMask" in node_types
    assert "SetLatentNoiseMask" in node_types
```

- [ ] **Step 3.6: Run mask test**

Run:
```bash
cd ~/open-palette && pytest tests/test_comfyui_edit_workflows.py -v
```
Expected: `4 passed`.

- [ ] **Step 3.7: Commit**

```bash
cd ~/open-palette && git add backends/comfyui.py tests/test_comfyui_edit_workflows.py
git commit -m "feat: add FLUX.1 Kontext edit workflow builder"
```

---

## Task 4: Build Qwen-Image-Edit workflow

**Files:**
- Modify: `backends/comfyui.py` (add method `build_qwen_edit_workflow`)
- Modify: `tests/test_comfyui_edit_workflows.py`

- [ ] **Step 4.1: Write failing test**

Append to `tests/test_comfyui_edit_workflows.py`:
```python
def test_qwen_workflow_has_required_nodes():
    backend = ComfyUIBackend(url="http://example.invalid")
    wf = backend.build_qwen_edit_workflow(
        source_filename="src.png",
        mask_filename=None,
        prompt="remove text",
        params={"steps": 20, "cfg": 4.0, "seed": 42},
    )
    node_types = {n["class_type"] for n in wf.values()}
    assert "UNETLoader" in node_types
    assert "TextEncodeQwenImageEdit" in node_types
    assert "LoadImage" in node_types
    assert "KSampler" in node_types
    assert "VAEDecode" in node_types
    assert "SaveImage" in node_types


def test_qwen_workflow_injects_prompt_and_source():
    backend = ComfyUIBackend(url="http://example.invalid")
    wf = backend.build_qwen_edit_workflow(
        source_filename="logo.png",
        mask_filename=None,
        prompt="make it flat",
        params={"steps": 20, "cfg": 4.0, "seed": 7},
    )
    qwen_enc = next(n for n in wf.values() if n["class_type"] == "TextEncodeQwenImageEdit")
    assert qwen_enc["inputs"]["prompt"] == "make it flat"
    load_image_nodes = [n for n in wf.values() if n["class_type"] == "LoadImage"]
    assert any(n["inputs"]["image"] == "logo.png" for n in load_image_nodes)
```

- [ ] **Step 4.2: Run test to verify it fails**

Run:
```bash
cd ~/open-palette && pytest tests/test_comfyui_edit_workflows.py -v
```
Expected: FAIL — `build_qwen_edit_workflow` does not exist.

- [ ] **Step 4.3: Implement `build_qwen_edit_workflow`**

Add the following method to `ComfyUIBackend` in `backends/comfyui.py`, immediately after `build_kontext_edit_workflow`:

```python
    def build_qwen_edit_workflow(
        self,
        source_filename: str,
        mask_filename: str | None,
        prompt: str,
        params: dict,
    ) -> dict:
        """Build a ComfyUI workflow for Qwen-Image-Edit.

        Qwen-Image-Edit uses TextEncodeQwenImageEdit which consumes both the
        source image and the prompt together to produce conditioning.
        """
        seed = int(params.get("seed", 0))
        steps = int(params.get("steps", 20))
        cfg = float(params.get("cfg", 4.0))

        workflow: dict = {
            "1": {
                "class_type": "UNETLoader",
                "inputs": {
                    "unet_name": "qwen-image-edit.safetensors",
                    "weight_dtype": "default",
                },
            },
            "2": {
                "class_type": "CLIPLoader",
                "inputs": {
                    "clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
                    "type": "qwen_image",
                },
            },
            "3": {
                "class_type": "VAELoader",
                "inputs": {"vae_name": "qwen_image_vae.safetensors"},
            },
            "4": {
                "class_type": "LoadImage",
                "inputs": {"image": source_filename},
            },
            "5": {
                "class_type": "VAEEncode",
                "inputs": {"pixels": ["4", 0], "vae": ["3", 0]},
            },
            "6": {
                "class_type": "TextEncodeQwenImageEdit",
                "inputs": {
                    "prompt": prompt,
                    "clip": ["2", 0],
                    "vae": ["3", 0],
                    "image": ["4", 0],
                },
            },
            "7": {
                "class_type": "TextEncodeQwenImageEdit",
                "inputs": {
                    "prompt": "",
                    "clip": ["2", 0],
                    "vae": ["3", 0],
                    "image": ["4", 0],
                },
            },
            "8": {
                "class_type": "KSampler",
                "inputs": {
                    "seed": seed,
                    "steps": steps,
                    "cfg": cfg,
                    "sampler_name": "euler",
                    "scheduler": "simple",
                    "denoise": 1.0,
                    "model": ["1", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0],
                },
            },
            "9": {
                "class_type": "VAEDecode",
                "inputs": {"samples": ["8", 0], "vae": ["3", 0]},
            },
            "10": {
                "class_type": "SaveImage",
                "inputs": {
                    "filename_prefix": "edit_qwen",
                    "images": ["9", 0],
                },
            },
        }

        if mask_filename:
            workflow["11"] = {
                "class_type": "LoadImageMask",
                "inputs": {"image": mask_filename, "channel": "alpha"},
            }
            workflow["12"] = {
                "class_type": "SetLatentNoiseMask",
                "inputs": {"samples": ["5", 0], "mask": ["11", 0]},
            }
            workflow["8"]["inputs"]["latent_image"] = ["12", 0]

        return workflow
```

- [ ] **Step 4.4: Run test to verify it passes**

Run:
```bash
cd ~/open-palette && pytest tests/test_comfyui_edit_workflows.py -v
```
Expected: `6 passed`.

- [ ] **Step 4.5: Commit**

```bash
cd ~/open-palette && git add backends/comfyui.py tests/test_comfyui_edit_workflows.py
git commit -m "feat: add Qwen-Image-Edit workflow builder"
```

---

## Task 5: Add `run_edit` dispatch method

**Files:**
- Modify: `backends/comfyui.py` (add `run_edit` method)
- Modify: `tests/test_comfyui_edit_workflows.py`

- [ ] **Step 5.1: Write failing test**

Append to `tests/test_comfyui_edit_workflows.py`:
```python
import pytest


def test_run_edit_rejects_unknown_model():
    backend = ComfyUIBackend(url="http://example.invalid")
    with pytest.raises(ValueError, match="unknown edit model"):
        backend.build_edit_workflow(
            model="nonexistent-model",
            source_filename="src.png",
            mask_filename=None,
            prompt="edit",
            params={},
        )


def test_run_edit_dispatches_to_kontext():
    backend = ComfyUIBackend(url="http://example.invalid")
    wf = backend.build_edit_workflow(
        model="flux-kontext-dev",
        source_filename="src.png",
        mask_filename=None,
        prompt="edit",
        params={"steps": 25, "cfg": 2.5, "seed": 1},
    )
    save_node = next(n for n in wf.values() if n["class_type"] == "SaveImage")
    assert save_node["inputs"]["filename_prefix"] == "edit_kontext"


def test_run_edit_dispatches_to_qwen():
    backend = ComfyUIBackend(url="http://example.invalid")
    wf = backend.build_edit_workflow(
        model="qwen-image-edit",
        source_filename="src.png",
        mask_filename=None,
        prompt="edit",
        params={},
    )
    save_node = next(n for n in wf.values() if n["class_type"] == "SaveImage")
    assert save_node["inputs"]["filename_prefix"] == "edit_qwen"
```

- [ ] **Step 5.2: Run test to verify it fails**

Run:
```bash
cd ~/open-palette && pytest tests/test_comfyui_edit_workflows.py -v
```
Expected: FAIL — `build_edit_workflow` does not exist.

- [ ] **Step 5.3: Implement `build_edit_workflow` dispatch**

Add method to `ComfyUIBackend` in `backends/comfyui.py`, immediately after `build_qwen_edit_workflow`:

```python
    def build_edit_workflow(
        self,
        model: str,
        source_filename: str,
        mask_filename: str | None,
        prompt: str,
        params: dict,
    ) -> dict:
        """Dispatch to the right edit workflow builder based on model id."""
        if model == "flux-kontext-dev":
            return self.build_kontext_edit_workflow(
                source_filename, mask_filename, prompt, params,
            )
        if model == "qwen-image-edit":
            return self.build_qwen_edit_workflow(
                source_filename, mask_filename, prompt, params,
            )
        raise ValueError(f"unknown edit model: {model}")
```

- [ ] **Step 5.4: Add `run_edit` async method that submits to ComfyUI**

Add immediately after `build_edit_workflow`:

```python
    async def run_edit(
        self,
        model: str,
        source_filename: str,
        mask_filename: str | None,
        prompt: str,
        params: dict,
    ) -> bytes:
        """Build an edit workflow and execute it on ComfyUI.

        Returns the raw PNG bytes of the edited result.
        Assumes source_filename and mask_filename (if given) have already been
        staged into ComfyUI's input directory by the caller.
        """
        workflow = self.build_edit_workflow(
            model, source_filename, mask_filename, prompt, params,
        )
        return await self._execute_workflow(workflow)
```

Note: `_execute_workflow` is the existing ComfyUI submission method used by the text-to-image path. If the codebase uses a different name (e.g., `_queue_prompt` + `_wait_for_image`), mirror the pattern used by the main generate method. Grep for how `build_*_workflow` callers submit and follow that pattern exactly.

- [ ] **Step 5.5: Run test to verify it passes**

Run:
```bash
cd ~/open-palette && pytest tests/test_comfyui_edit_workflows.py -v
```
Expected: `9 passed`.

- [ ] **Step 5.6: Commit**

```bash
cd ~/open-palette && git add backends/comfyui.py tests/test_comfyui_edit_workflows.py
git commit -m "feat: add build_edit_workflow dispatcher and run_edit async"
```

---

## Task 6: Add `/api/edit` route

**Files:**
- Modify: `server.py`
- Create: `tests/test_api_edit.py`

- [ ] **Step 6.1: Write failing tests**

Create `tests/test_api_edit.py`:
```python
"""Unit tests for POST /api/edit."""

import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from server import app


@pytest.fixture
def client():
    return TestClient(app)


def _make_png_bytes(size=(64, 64), color=(255, 0, 0)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def test_edit_rejects_missing_source(client):
    resp = client.post(
        "/api/edit",
        data={"prompt": "edit", "model": "flux-kontext-dev"},
    )
    assert resp.status_code == 422  # FastAPI multipart validation


def test_edit_rejects_bad_model(client):
    png = _make_png_bytes()
    resp = client.post(
        "/api/edit",
        data={"prompt": "edit", "model": "not-a-real-model"},
        files={"source": ("src.png", png, "image/png")},
    )
    assert resp.status_code == 400
    assert "model" in resp.json()["detail"].lower()


def test_edit_rejects_mismatched_mask_dims(client):
    png = _make_png_bytes(size=(64, 64))
    mask = _make_png_bytes(size=(32, 32))
    resp = client.post(
        "/api/edit",
        data={"prompt": "edit", "model": "flux-kontext-dev"},
        files={
            "source": ("src.png", png, "image/png"),
            "mask": ("mask.png", mask, "image/png"),
        },
    )
    assert resp.status_code == 400
    assert "mask" in resp.json()["detail"].lower()


def test_edit_happy_path_calls_run_edit(client):
    png = _make_png_bytes()
    result = _make_png_bytes(color=(0, 255, 0))
    with patch("server.comfyui_backend.run_edit", new=AsyncMock(return_value=result)) as m:
        resp = client.post(
            "/api/edit",
            data={
                "prompt": "make it green",
                "model": "flux-kontext-dev",
                "steps": "25",
                "cfg": "2.5",
                "seed": "42",
            },
            files={"source": ("src.png", png, "image/png")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert "filename" in body
    assert body["filename"].startswith("edits/")
    assert body["filename"].endswith(".png")
    assert "url" in body
    m.assert_awaited_once()
```

- [ ] **Step 6.2: Run test to verify it fails**

Run:
```bash
cd ~/open-palette && pytest tests/test_api_edit.py -v
```
Expected: FAIL — route not defined.

- [ ] **Step 6.3: Add `/api/edit` route to `server.py`**

Locate the block of image-generation routes near `@app.post("/api/generate")` (around line 847). Add immediately after it:

```python
import uuid as _uuid_edit  # local alias to avoid collision
from PIL import Image as _PILImage  # local alias


@app.post("/api/edit")
async def api_edit(
    source: UploadFile = File(...),
    prompt: str = Form(...),
    model: str = Form(...),
    mask: UploadFile | None = File(default=None),
    steps: int = Form(default=25),
    cfg: float = Form(default=2.5),
    seed: int = Form(default=0),
):
    """Run an image edit via ComfyUI and return the saved edit path."""
    # Validate model
    if model not in {"flux-kontext-dev", "qwen-image-edit"}:
        raise HTTPException(status_code=400, detail=f"Unknown edit model: {model}")

    # Read source, validate image
    source_bytes = await source.read()
    try:
        src_img = _PILImage.open(io.BytesIO(source_bytes))
        src_img.verify()
        src_img = _PILImage.open(io.BytesIO(source_bytes))  # reopen after verify
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid source image: {e}")

    # Read + validate mask if provided
    mask_bytes: bytes | None = None
    if mask is not None:
        mask_bytes = await mask.read()
        try:
            mask_img = _PILImage.open(io.BytesIO(mask_bytes))
            mask_img.verify()
            mask_img = _PILImage.open(io.BytesIO(mask_bytes))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid mask image: {e}")
        if mask_img.size != src_img.size:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Mask dimensions {mask_img.size} do not match source "
                    f"{src_img.size}"
                ),
            )

    # Stage source (and mask) to ComfyUI input dir
    # comfyui_backend.input_dir is assumed to be set in backend init.
    edit_id = _uuid_edit.uuid4().hex[:12]
    staged_source = f"wyltek_edit_{edit_id}_src.png"
    src_img.save(Path(comfyui_backend.input_dir) / staged_source, format="PNG")

    staged_mask: str | None = None
    if mask_bytes is not None:
        staged_mask = f"wyltek_edit_{edit_id}_mask.png"
        mask_img.save(Path(comfyui_backend.input_dir) / staged_mask, format="PNG")

    params = {"steps": steps, "cfg": cfg, "seed": seed}

    try:
        result_bytes = await comfyui_backend.run_edit(
            model=model,
            source_filename=staged_source,
            mask_filename=staged_mask,
            prompt=prompt,
            params=params,
        )
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"ComfyUI unreachable: {e}")
    except FileNotFoundError as e:
        raise HTTPException(status_code=424, detail=f"Model file missing: {e}")

    # Write to outputs/edits/
    edits_dir = Path("outputs") / "edits"
    edits_dir.mkdir(parents=True, exist_ok=True)
    out_name = f"edit_{edit_id}.png"
    out_path = edits_dir / out_name
    out_path.write_bytes(result_bytes)

    return {
        "filename": f"edits/{out_name}",
        "url": f"/outputs/edits/{out_name}",
    }
```

Note: `comfyui_backend` is assumed to be the module-level ComfyUI backend instance in `server.py`. If it has a different name, grep `server.py` for the existing ComfyUI backend variable and use that.

If `HTTPException`, `Path`, or `io` are not already imported at the top of `server.py`, add the needed imports.

- [ ] **Step 6.4: Run tests to verify they pass**

Run:
```bash
cd ~/open-palette && pytest tests/test_api_edit.py -v
```
Expected: `4 passed`.

- [ ] **Step 6.5: Commit**

```bash
cd ~/open-palette && git add server.py tests/test_api_edit.py
git commit -m "feat: add POST /api/edit route"
```

---

## Task 7: Create image edit page — HTML shell

**Files:**
- Create: `static/studio/image-edit.html`

- [ ] **Step 7.1: Create the page**

Write the file with this full content:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Wyltek Studio — Image Edit</title>
  <link rel="stylesheet" href="/static/css/style.css">
  <link rel="stylesheet" href="/static/css/nav.css">
  <script src="/static/js/nav.js"></script>
  <style>
    .edit-page { max-width: 1200px; margin: 0 auto; padding: 24px; }
    .edit-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
    .edit-layout { display: grid; grid-template-columns: 1fr 360px; gap: 20px; }
    @media (max-width: 900px) { .edit-layout { grid-template-columns: 1fr; } }

    .source-panel { position: relative; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; min-height: 400px; display: flex; align-items: center; justify-content: center; overflow: hidden; }
    #source-canvas-wrap { position: relative; max-width: 100%; max-height: 600px; }
    #source-img { display: block; max-width: 100%; max-height: 600px; }
    #mask-canvas { position: absolute; top: 0; left: 0; cursor: crosshair; opacity: 0.6; }

    .drop-zone { border: 2px dashed var(--border); border-radius: 12px; padding: 48px 24px; text-align: center; color: var(--text-dim); cursor: pointer; }
    .drop-zone:hover, .drop-zone.drag-over { border-color: var(--accent); color: var(--text); background: var(--accent-dim); }
    #file-input { display: none; }

    .tool-row { display: flex; gap: 8px; margin: 10px 0; flex-wrap: wrap; align-items: center; }
    .tool-row label { font-size: 12px; color: var(--text-dim); }

    .controls { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 18px; }
    .controls label { display: block; font-size: 12px; color: var(--text-dim); margin: 10px 0 4px; }
    .controls select, .controls input, .controls textarea { width: 100%; padding: 8px; background: var(--surface-2); border: 1px solid var(--border); border-radius: 6px; color: var(--text); font-size: 13px; }
    .controls textarea { min-height: 80px; resize: vertical; }
    .btn-edit { width: 100%; margin-top: 14px; padding: 12px; background: var(--accent); color: #fff; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; }
    .btn-edit:disabled { opacity: 0.5; cursor: not-allowed; }

    .gallery-strip { margin-top: 20px; display: flex; gap: 10px; overflow-x: auto; padding-bottom: 10px; }
    .gallery-item { position: relative; flex-shrink: 0; }
    .gallery-item img { width: 140px; height: 140px; object-fit: cover; border-radius: 8px; border: 1px solid var(--border); }
    .gallery-item .actions { position: absolute; bottom: 4px; left: 4px; right: 4px; display: flex; gap: 4px; background: rgba(0,0,0,0.6); border-radius: 4px; padding: 2px; }
    .gallery-item .actions button { flex: 1; font-size: 10px; padding: 2px; background: var(--surface-2); border: none; border-radius: 3px; color: var(--text); cursor: pointer; }
  </style>
</head>
<body>
  <div class="edit-page">
    <div class="edit-header">
      <h2>Image Edit</h2>
      <div class="subtitle" style="font-size:13px;color:var(--text-dim)">Instruction-driven editing via ComfyUI</div>
    </div>

    <div class="edit-layout">
      <!-- Left: source + mask -->
      <div class="source-panel">
        <div class="drop-zone" id="drop-zone">
          <div class="drop-icon">&#8613;</div>
          <p>Drop an image here or <u>click to browse</u></p>
          <small>PNG, JPG. Max 20MB.</small>
        </div>
        <input type="file" id="file-input" accept="image/png,image/jpeg">
        <div id="source-canvas-wrap" style="display:none">
          <img id="source-img" alt="Source">
          <canvas id="mask-canvas"></canvas>
        </div>
      </div>

      <!-- Right: controls -->
      <div class="controls">
        <label for="model-select">Model</label>
        <select id="model-select">
          <option value="flux-kontext-dev">FLUX.1 Kontext [dev]</option>
          <option value="qwen-image-edit">Qwen-Image-Edit</option>
        </select>

        <label for="prompt">Edit instruction</label>
        <textarea id="prompt" placeholder="e.g. flat version, solid colors, remove gradient"></textarea>

        <div class="tool-row">
          <label><input type="checkbox" id="mask-enable"> Paint mask</label>
          <label>Brush <input type="range" id="brush-size" min="5" max="100" value="30" style="width:80px"></label>
          <button id="mask-clear" class="btn">Clear</button>
          <button id="mask-undo" class="btn">Undo</button>
        </div>

        <details>
          <summary style="cursor:pointer;font-size:12px;color:var(--text-dim);margin-top:8px">Advanced</summary>
          <label>Steps</label>
          <input type="number" id="steps" value="25" min="1" max="100">
          <label>CFG</label>
          <input type="number" id="cfg" value="2.5" step="0.1" min="1" max="10">
          <label>Seed (0 = random)</label>
          <input type="number" id="seed" value="0">
        </details>

        <button class="btn-edit" id="btn-edit" disabled>Edit</button>
      </div>
    </div>

    <!-- Gallery of edits -->
    <div class="gallery-strip" id="edit-gallery"></div>

    <!-- Toast -->
    <div id="toast-msg" class="toast"></div>
  </div>

  <script src="/static/js/project-picker.js"></script>
  <script src="/static/studio/js/image-edit.js"></script>
</body>
</html>
```

- [ ] **Step 7.2: Verify page loads**

Start the server if not running:
```bash
cd ~/open-palette && python server.py &
```
Open http://localhost:8000/studio/image-edit.html in a browser. Confirm layout renders with drop zone and right-hand controls. Expected: no JS errors in console (image-edit.js doesn't exist yet — browser will 404 it; that's fine for this step).

- [ ] **Step 7.3: Commit**

```bash
cd ~/open-palette && git add static/studio/image-edit.html
git commit -m "feat: add image edit page HTML shell"
```

---

## Task 8: JS controller — `?asset=` handoff and source rendering

**Files:**
- Create: `static/studio/js/image-edit.js`

- [ ] **Step 8.1: Create the file with handoff-only logic**

Write `static/studio/js/image-edit.js`:

```javascript
/**
 * Image Edit page controller.
 *
 * Handles:
 *  - ?asset=<filename> handoff from the Generate page
 *  - Direct upload (Task 10)
 *  - Mask canvas (Task 9)
 *  - POST /api/edit submission (Task 11)
 *  - Gallery + actions (Task 12)
 */
(() => {
  const $ = (id) => document.getElementById(id);

  const state = {
    sourceBlob: null,    // File or Blob of the source image
    sourceUrl: null,     // object URL / server URL
    maskStrokes: [],     // array of stroke polylines
    editing: false,
    gallery: [],         // edit results
  };

  function showToast(msg) {
    const el = $('toast-msg');
    if (!el) return;
    el.textContent = msg;
    el.classList.add('show');
    setTimeout(() => el.classList.remove('show'), 3000);
  }

  function showSource(url) {
    state.sourceUrl = url;
    const img = $('source-img');
    img.src = url;
    img.onload = () => {
      $('drop-zone').style.display = 'none';
      $('source-canvas-wrap').style.display = 'block';
      initMaskCanvas(img.naturalWidth, img.naturalHeight);
      $('btn-edit').disabled = false;
    };
    img.onerror = () => {
      showToast('Could not load image — it may have been deleted.');
    };
  }

  function initMaskCanvas(w, h) {
    const c = $('mask-canvas');
    c.width = w;
    c.height = h;
    const img = $('source-img');
    c.style.width = img.clientWidth + 'px';
    c.style.height = img.clientHeight + 'px';
    const ctx = c.getContext('2d');
    ctx.clearRect(0, 0, w, h);
    state.maskStrokes = [];
  }

  function handleAssetHandoff() {
    const params = new URLSearchParams(window.location.search);
    const asset = params.get('asset');
    if (!asset) return;
    // Assets live under /outputs/<filename> — use existing static mount.
    showSource('/outputs/' + encodeURIComponent(asset));
    // Also fetch as blob so we can POST it back.
    fetch('/outputs/' + encodeURIComponent(asset))
      .then(r => {
        if (!r.ok) throw new Error('fetch failed');
        return r.blob();
      })
      .then(b => { state.sourceBlob = b; })
      .catch(() => { showToast('Could not load ' + asset); });
  }

  document.addEventListener('DOMContentLoaded', () => {
    if (typeof ProjectPicker !== 'undefined') ProjectPicker.init(showToast);
    handleAssetHandoff();
  });

  // Expose for subsequent tasks to extend
  window.ImageEditPage = { state, showToast, showSource, initMaskCanvas };
})();
```

- [ ] **Step 8.2: Manually verify handoff**

1. Start server if not running: `cd ~/open-palette && python server.py &`
2. Pick any existing output file in `outputs/` (e.g., `ls ~/open-palette/outputs/ | head -1`)
3. Open `http://localhost:8000/studio/image-edit.html?asset=<filename>` in a browser
4. Expected: source image appears in the left panel, drop zone hides, Edit button enables, no JS errors in console.

- [ ] **Step 8.3: Commit**

```bash
cd ~/open-palette && git add static/studio/js/image-edit.js
git commit -m "feat: add image-edit page controller with ?asset handoff"
```

---

## Task 9: Mask canvas painting (brush, clear, undo, export)

**Files:**
- Modify: `static/studio/js/image-edit.js`

- [ ] **Step 9.1: Add mask painting to the controller**

Replace the placeholder `initMaskCanvas` and add painting logic. Open `static/studio/js/image-edit.js` and replace the `initMaskCanvas` function and add new functions at the same IIFE scope level:

```javascript
  function initMaskCanvas(w, h) {
    const c = $('mask-canvas');
    c.width = w;
    c.height = h;
    const img = $('source-img');
    c.style.width = img.clientWidth + 'px';
    c.style.height = img.clientHeight + 'px';
    c.getContext('2d').clearRect(0, 0, w, h);
    state.maskStrokes = [];
    wireMaskHandlers(c);
  }

  function wireMaskHandlers(canvas) {
    let drawing = false;
    let stroke = null;

    function pointerPos(e) {
      const r = canvas.getBoundingClientRect();
      const sx = canvas.width / r.width;
      const sy = canvas.height / r.height;
      return { x: (e.clientX - r.left) * sx, y: (e.clientY - r.top) * sy };
    }

    function shouldDraw() {
      return $('mask-enable').checked;
    }

    canvas.addEventListener('pointerdown', (e) => {
      if (!shouldDraw()) return;
      drawing = true;
      const p = pointerPos(e);
      const size = parseInt($('brush-size').value, 10);
      stroke = { size, points: [p] };
      canvas.setPointerCapture(e.pointerId);
      redraw();
    });

    canvas.addEventListener('pointermove', (e) => {
      if (!drawing) return;
      stroke.points.push(pointerPos(e));
      redraw();
    });

    canvas.addEventListener('pointerup', (e) => {
      if (!drawing) return;
      drawing = false;
      if (stroke && stroke.points.length > 0) state.maskStrokes.push(stroke);
      stroke = null;
      redraw();
    });

    function redraw() {
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = 'rgba(255,255,255,1)';
      ctx.strokeStyle = 'rgba(255,255,255,1)';
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      const all = stroke ? state.maskStrokes.concat([stroke]) : state.maskStrokes;
      for (const s of all) {
        ctx.lineWidth = s.size;
        if (s.points.length === 1) {
          const p = s.points[0];
          ctx.beginPath();
          ctx.arc(p.x, p.y, s.size / 2, 0, Math.PI * 2);
          ctx.fill();
        } else {
          ctx.beginPath();
          ctx.moveTo(s.points[0].x, s.points[0].y);
          for (let i = 1; i < s.points.length; i++) {
            ctx.lineTo(s.points[i].x, s.points[i].y);
          }
          ctx.stroke();
        }
      }
    }

    $('mask-clear').addEventListener('click', () => {
      state.maskStrokes = [];
      redraw();
    });
    $('mask-undo').addEventListener('click', () => {
      state.maskStrokes.pop();
      redraw();
    });
    $('mask-enable').addEventListener('change', () => {
      canvas.style.pointerEvents = $('mask-enable').checked ? 'auto' : 'none';
    });
    canvas.style.pointerEvents = 'none'; // default off
  }

  function maskBlob() {
    // Returns a Promise<Blob|null> of the mask as a PNG. Null if no strokes.
    return new Promise((resolve) => {
      if (state.maskStrokes.length === 0) return resolve(null);
      const c = $('mask-canvas');
      // Convert to alpha mask: white-on-transparent already from redraw
      c.toBlob((b) => resolve(b), 'image/png');
    });
  }

  // Expose for Task 11
  window.ImageEditPage.maskBlob = maskBlob;
```

Also update the exposed API object at the bottom of the IIFE:
```javascript
  window.ImageEditPage = { state, showToast, showSource, initMaskCanvas, maskBlob };
```

- [ ] **Step 9.2: Manually verify masking**

1. Reload `http://localhost:8000/studio/image-edit.html?asset=<filename>` in a browser.
2. Tick "Paint mask", drag on the image. Strokes should appear in white.
3. Click Clear — strokes disappear.
4. Click Undo after multiple strokes — last one disappears.
5. Resize brush slider — new strokes use new size.

- [ ] **Step 9.3: Commit**

```bash
cd ~/open-palette && git add static/studio/js/image-edit.js
git commit -m "feat: add mask canvas painting to image edit page"
```

---

## Task 10: Direct upload (drag/drop + file picker)

**Files:**
- Modify: `static/studio/js/image-edit.js`

- [ ] **Step 10.1: Add direct upload handlers**

At the end of the IIFE, just before the `document.addEventListener('DOMContentLoaded', ...)` line, add:

```javascript
  function wireUpload() {
    const dz = $('drop-zone');
    const fi = $('file-input');
    dz.addEventListener('click', () => fi.click());
    fi.addEventListener('change', (e) => {
      const f = e.target.files[0];
      if (f) acceptFile(f);
    });
    dz.addEventListener('dragover', (e) => {
      e.preventDefault();
      dz.classList.add('drag-over');
    });
    dz.addEventListener('dragleave', () => dz.classList.remove('drag-over'));
    dz.addEventListener('drop', (e) => {
      e.preventDefault();
      dz.classList.remove('drag-over');
      const f = e.dataTransfer.files[0];
      if (f) acceptFile(f);
    });
  }

  function acceptFile(file) {
    if (!/^image\/(png|jpeg)$/.test(file.type)) {
      showToast('Only PNG or JPG accepted.');
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      showToast('File too large (max 20MB).');
      return;
    }
    state.sourceBlob = file;
    const url = URL.createObjectURL(file);
    showSource(url);
  }

  // Expose for tests
  window.ImageEditPage.acceptFile = acceptFile;
```

Update the DOM-ready handler to call `wireUpload()`:
```javascript
  document.addEventListener('DOMContentLoaded', () => {
    if (typeof ProjectPicker !== 'undefined') ProjectPicker.init(showToast);
    wireUpload();
    handleAssetHandoff();
  });
```

Also add `acceptFile` to the exposed API:
```javascript
  window.ImageEditPage = { state, showToast, showSource, initMaskCanvas, maskBlob, acceptFile };
```

- [ ] **Step 10.2: Manually verify upload**

1. Open `http://localhost:8000/studio/image-edit.html` (no ?asset).
2. Click the drop zone, pick a PNG/JPG. It should load.
3. Reload and drag/drop a PNG onto the drop zone. It should load.
4. Try a non-image — toast should say "Only PNG or JPG accepted".

- [ ] **Step 10.3: Commit**

```bash
cd ~/open-palette && git add static/studio/js/image-edit.js
git commit -m "feat: add direct upload to image edit page"
```

---

## Task 11: Edit submit + gallery rendering

**Files:**
- Modify: `static/studio/js/image-edit.js`

- [ ] **Step 11.1: Add edit submission and gallery rendering**

At the end of the IIFE before the DOM-ready handler, add:

```javascript
  async function submitEdit() {
    if (!state.sourceBlob) {
      showToast('No source image.');
      return;
    }
    if (state.editing) return;
    const prompt = $('prompt').value.trim();
    if (!prompt) {
      showToast('Enter an edit instruction.');
      return;
    }

    state.editing = true;
    $('btn-edit').disabled = true;
    $('btn-edit').textContent = 'Editing...';

    const fd = new FormData();
    fd.append('source', state.sourceBlob, 'source.png');
    fd.append('prompt', prompt);
    fd.append('model', $('model-select').value);
    fd.append('steps', $('steps').value);
    fd.append('cfg', $('cfg').value);
    fd.append('seed', $('seed').value);

    const mb = await maskBlob();
    if (mb) fd.append('mask', mb, 'mask.png');

    try {
      const resp = await fetch('/api/edit', { method: 'POST', body: fd });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.detail || 'Edit failed');
      }
      const data = await resp.json();
      addToGallery(data);
      showToast('Edit complete');
    } catch (e) {
      showToast('Edit failed: ' + e.message);
    } finally {
      state.editing = false;
      $('btn-edit').disabled = false;
      $('btn-edit').textContent = 'Edit';
    }
  }

  function addToGallery(item) {
    state.gallery.unshift(item);
    renderGallery();
  }

  function renderGallery() {
    const g = $('edit-gallery');
    g.textContent = '';
    for (const item of state.gallery) {
      const wrap = document.createElement('div');
      wrap.className = 'gallery-item';
      const img = document.createElement('img');
      img.src = item.url;
      wrap.appendChild(img);
      const actions = document.createElement('div');
      actions.className = 'actions';
      actions.appendChild(makeBtn('Save', () => window.open(item.url, '_blank')));
      actions.appendChild(makeBtn('URL', () => copyUrl(item.url)));
      actions.appendChild(makeBtn('Project', () => ProjectPicker.show(item.filename)));
      actions.appendChild(makeBtn('Re-edit', () => useAsSource(item.url)));
      wrap.appendChild(actions);
      g.appendChild(wrap);
    }
  }

  function makeBtn(label, fn) {
    const b = document.createElement('button');
    b.textContent = label;
    b.addEventListener('click', fn);
    return b;
  }

  async function copyUrl(url) {
    const abs = window.location.origin + url;
    await navigator.clipboard.writeText(abs);
    showToast('URL copied');
  }

  function useAsSource(url) {
    fetch(url)
      .then(r => r.blob())
      .then(b => {
        state.sourceBlob = b;
        state.maskStrokes = [];
        showSource(url);
      });
  }

  // Wire the Edit button in DOM-ready
  window.ImageEditPage.submitEdit = submitEdit;
```

Update the DOM-ready handler to wire the Edit button:
```javascript
  document.addEventListener('DOMContentLoaded', () => {
    if (typeof ProjectPicker !== 'undefined') ProjectPicker.init(showToast);
    wireUpload();
    handleAssetHandoff();
    $('btn-edit').addEventListener('click', submitEdit);
  });
```

- [ ] **Step 11.2: Manually verify submit path (error path only, no live ComfyUI)**

1. Reload page with an asset loaded.
2. Type an instruction, click Edit. Without ComfyUI + models installed, expect a toast like "Edit failed: ComfyUI unreachable" — this is correct error behavior.
3. Browser DevTools → Network tab: confirm a `POST /api/edit` multipart request with `source`, `prompt`, `model`, `steps`, `cfg`, `seed` fields.

- [ ] **Step 11.3: Commit**

```bash
cd ~/open-palette && git add static/studio/js/image-edit.js
git commit -m "feat: add edit submit and gallery rendering"
```

---

## Task 12: "Send to Editor" button on Generate page

**Files:**
- Modify: `static/index.html`
- Modify: `static/js/app.js`

- [ ] **Step 12.1: Add button to main viewer**

Open `static/index.html`. Locate the `.result-actions` block (around line 178):
```html
            <button class="btn" id="btn-send-project">Send to Project</button>
```

Add immediately after it:
```html
            <button class="btn" id="btn-send-editor">Send to Editor</button>
```

- [ ] **Step 12.2: Wire main-viewer button in app.js**

Open `static/js/app.js`. Locate lines 479-480:
```javascript
  document.getElementById('btn-use-as-ref').addEventListener('click', useAsRef);
  document.getElementById('btn-send-project').addEventListener('click', sendImageToProject);
```

Add immediately after:
```javascript
  document.getElementById('btn-send-editor').addEventListener('click', sendImageToEditor);
```

Add a new function near `sendImageToProject` (search for its definition):
```javascript
function sendImageToEditor() {
  const img = document.getElementById('result-image');
  if (!img || !img.src) return;
  // Extract filename from /outputs/<name>
  const m = img.src.match(/\/outputs\/([^?#]+)/);
  if (!m) return;
  window.location = '/studio/image-edit.html?asset=' + encodeURIComponent(m[1]);
}
```

- [ ] **Step 12.3: Add button to gallery thumbnails**

Grep for where gallery thumbnails are rendered:
```bash
cd ~/open-palette && grep -n "gallery-strip\|galleryStrip\|renderGallery" static/js/app.js | head -10
```

In the gallery thumbnail rendering function, each thumbnail gets an actions overlay or similar. Find where existing actions (e.g., "Send to Project", "Use as Reference") are added to thumbnails. Add a "Send to Editor" button there with:
```javascript
const sendEditorBtn = document.createElement('button');
sendEditorBtn.className = 'btn';
sendEditorBtn.textContent = 'Edit';
sendEditorBtn.addEventListener('click', () => {
  window.location = '/studio/image-edit.html?asset=' + encodeURIComponent(filename);
});
thumbActions.appendChild(sendEditorBtn);
```

Where `filename` is the existing variable holding the thumbnail's filename. If the gallery rendering pattern does not have per-thumbnail actions, add them following the pattern of the main viewer.

- [ ] **Step 12.4: Manually verify**

1. Reload `http://localhost:8000/`, generate any image (or trigger a mock).
2. Confirm "Send to Editor" button appears next to "Send to Project".
3. Click it. Browser navigates to `/studio/image-edit.html?asset=<filename>` and source image loads.
4. Check gallery thumbnails also have an Edit button and navigate the same way.

- [ ] **Step 12.5: Commit**

```bash
cd ~/open-palette && git add static/index.html static/js/app.js
git commit -m "feat: add 'Send to Editor' buttons on generate page"
```

---

## Task 13: Nav entry

**Files:**
- Modify: `static/js/nav.js`

- [ ] **Step 13.1: Add entry**

Open `static/js/nav.js`. Locate the nav entries array (around line 6). The existing entries look like:
```javascript
    { href: '/',           icon: '&#9998;',  label: 'Generate',    id: 'generate' },
```

Add a new entry after the existing Studio-family entries (locate where frames/image-tools/meme etc. are listed):
```javascript
    { href: '/studio/image-edit.html', icon: '&#9997;', label: 'Edit', id: 'edit' },
```

- [ ] **Step 13.2: Verify nav highlights correctly**

1. Visit `http://localhost:8000/studio/image-edit.html`
2. The "Edit" nav entry should be highlighted as active.
3. The entry exists in the nav and clicking it from other pages lands here.

If the nav's active-id detection is path-based and needs registration, also add to the `activeId` resolution logic. Grep for `activeId` in `nav.js` and mirror the pattern.

- [ ] **Step 13.3: Commit**

```bash
cd ~/open-palette && git add static/js/nav.js
git commit -m "feat: add Edit nav entry"
```

---

## Task 14: Playwright E2E bootstrap

**Files:**
- Create: `tests/e2e/package.json`
- Create: `tests/e2e/playwright.config.ts`
- Create: `tests/e2e/image-edit.spec.ts`

- [ ] **Step 14.1: Create `tests/e2e/package.json`**

```json
{
  "name": "wyltek-studio-e2e",
  "version": "1.0.0",
  "private": true,
  "devDependencies": {
    "@playwright/test": "^1.47.0",
    "typescript": "^5.4.0"
  },
  "scripts": {
    "test": "playwright test"
  }
}
```

- [ ] **Step 14.2: Install Playwright**

Run:
```bash
cd ~/open-palette/tests/e2e && npm install && npx playwright install chromium
```

- [ ] **Step 14.3: Create `tests/e2e/playwright.config.ts`**

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: '.',
  timeout: 30_000,
  use: {
    baseURL: 'http://localhost:8000',
    trace: 'on-first-retry',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: 'cd ../../ && python server.py',
    url: 'http://localhost:8000',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
```

- [ ] **Step 14.4: Create `tests/e2e/image-edit.spec.ts`**

```typescript
import { test, expect } from '@playwright/test';
import { readFileSync } from 'fs';
import { join } from 'path';

test('handoff from generate page loads source', async ({ page }) => {
  // Seed an output file so ?asset= works.
  // Uses any existing file in outputs/; if none exist, the test is skipped.
  const { existsSync, readdirSync } = await import('fs');
  const outputs = join(__dirname, '../../outputs');
  if (!existsSync(outputs)) test.skip();
  const files = readdirSync(outputs).filter(f => /\.(png|jpg|jpeg)$/i.test(f));
  if (files.length === 0) test.skip();

  const asset = files[0];
  await page.goto(`/studio/image-edit.html?asset=${encodeURIComponent(asset)}`);
  await expect(page.locator('#source-img')).toBeVisible();
  await expect(page.locator('#drop-zone')).toBeHidden();
  await expect(page.locator('#btn-edit')).toBeEnabled();
});

test('direct upload loads an image', async ({ page }) => {
  await page.goto('/studio/image-edit.html');
  await expect(page.locator('#drop-zone')).toBeVisible();

  // 1x1 transparent PNG
  const tinyPng = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9' +
    'awAAAABJRU5ErkJggg==',
    'base64',
  );
  await page.setInputFiles('#file-input', {
    name: 'tiny.png',
    mimeType: 'image/png',
    buffer: tinyPng,
  });
  await expect(page.locator('#source-img')).toBeVisible();
  await expect(page.locator('#btn-edit')).toBeEnabled();
});

test('rejects non-image upload', async ({ page }) => {
  await page.goto('/studio/image-edit.html');
  await page.setInputFiles('#file-input', {
    name: 'notes.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('hello'),
  });
  await expect(page.locator('#toast-msg')).toContainText('PNG or JPG');
});

test('edit submit posts to /api/edit', async ({ page }) => {
  await page.route('**/api/edit', async (route) => {
    const json = { filename: 'edits/fake.png', url: '/outputs/edits/fake.png' };
    await route.fulfill({ status: 200, body: JSON.stringify(json), contentType: 'application/json' });
  });
  await page.goto('/studio/image-edit.html');
  const tinyPng = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9' +
    'awAAAABJRU5ErkJggg==',
    'base64',
  );
  await page.setInputFiles('#file-input', {
    name: 'tiny.png',
    mimeType: 'image/png',
    buffer: tinyPng,
  });
  await page.fill('#prompt', 'flatten');
  await page.click('#btn-edit');
  await expect(page.locator('.gallery-item img')).toBeVisible();
});
```

- [ ] **Step 14.5: Run E2E**

Run:
```bash
cd ~/open-palette/tests/e2e && npx playwright test
```
Expected: 4 passed (or 1 skipped + 3 passed if outputs/ is empty).

- [ ] **Step 14.6: Commit**

```bash
cd ~/open-palette && git add tests/e2e/
git commit -m "test: add Playwright E2E for image edit page"
```

---

## Task 15: README / setup note

**Files:**
- Modify: `README.md`

- [ ] **Step 15.1: Append setup section**

Open `README.md`. Add a new section near the bottom (after any existing installation / usage blocks):

```markdown
## Image Editing (Kontext + Qwen-Image-Edit)

The editor at `/studio/image-edit.html` wires two local models through ComfyUI:

- **FLUX.1 Kontext [dev]** — instruction-driven editing, identity-preserving. Download via Settings → Models. ~24GB, non-commercial license.
- **Qwen-Image-Edit** — instruction-driven stylistic editing. Apache 2.0. ~20GB.

Neither model is downloaded by default. The page will surface a 424 error if the selected model is not installed in ComfyUI.

Source images can come from the Generate page's "Send to Editor" button or direct upload on the editor page. Edited results save to `outputs/edits/` and are shown in the editor's gallery strip. Each gallery item has Save, Copy URL, Send to Project, and Re-edit (use as source) actions.
```

- [ ] **Step 15.2: Commit**

```bash
cd ~/open-palette && git add README.md
git commit -m "docs: document image edit page setup"
```

---

## Final verification

- [ ] **Run full test suite**

```bash
cd ~/open-palette && pytest tests/ -v --ignore=tests/e2e
cd ~/open-palette/tests/e2e && npx playwright test
```
Expected: all backend tests pass. E2E tests pass or skip if outputs/ empty.

- [ ] **Manual smoke test (UI)**

1. `cd ~/open-palette && python server.py` (if not running).
2. Visit `/`, generate any image via existing flow.
3. Click "Send to Editor" → redirects to edit page with source loaded.
4. Type an instruction, click Edit. With Kontext installed in ComfyUI, confirm a real edit is produced.
5. Click "Re-edit" on a gallery item — source swaps to that edit.
6. Click "Send to Project" on a gallery item — confirm project picker appears.

- [ ] **Manual smoke test (against `cs_finalists`)**

Using `~/Downloads/cs_finalists/6ec17ebd.png`:
1. Upload to the editor directly.
2. Prompt: "flat vector style, solid colors, no gradient, no shadow".
3. Confirm edited output is visually flatter. If not, also try Qwen-Image-Edit.

---

## Spec coverage check

| Spec section | Task(s) |
|--------------|---------|
| Page at `/studio/image-edit.html` | 7, 8, 13 |
| Two models (Kontext + Qwen-Image-Edit) | 2, 3, 4, 5, 6 |
| Mask painting | 9 |
| URL-param handoff | 8 |
| Direct upload | 10 |
| Edits to `outputs/edits/` | 6 |
| Gallery + actions (Save/Copy/Project/Use-as-Source) | 11 |
| "Send to Editor" on generate page (viewer + thumbs) | 12 |
| Error handling — frontend cases | 8, 10, 11 |
| Error handling — backend cases | 6 |
| Pytest unit tests | 1, 2, 3, 4, 5, 6 |
| Playwright E2E | 14 |
| Setup docs | 15 |
| Model registration | 2 |
