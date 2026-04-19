# Style Remix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a single-purpose Style Remix page at `/studio/remix` that takes an existing gallery image as a character base, applies a style reference (user upload or crypto logo) via img2img + IP-Adapter, and returns a batch of remixes. Replaces `/studio/sprites`.

**Architecture:** One new ComfyUI workflow template (`BASIC_IMG2IMG`) + one new backend method (`ComfyUIBackend.generate_remix`). New FastAPI endpoint `POST /api/remix` that resolves base-image and style-ref inputs (gallery id, upload, or crypto logo slug), then enqueues one job per batch slot via a small `remix: True` branch in `_run_job`. Frontend is a single-tab page that reuses existing nav, WS progress, and gallery patterns.

**Tech Stack:** Python 3.10 / FastAPI / pytest, vanilla HTML+JS frontend, ComfyUI (already running as a systemctl --user service), ComfyUI_IPAdapter_plus custom node pack.

---

## Task 1: Scaffold tests directory and add BASIC_IMG2IMG workflow template

**Files:**
- Create: `tests/__init__.py` (empty)
- Create: `tests/conftest.py`
- Create: `tests/test_remix_workflows.py`
- Modify: `backends/comfyui.py` (add `BASIC_IMG2IMG` constant near `BASIC_TXT2IMG` at line 274)

- [ ] **Step 1: Create tests directory and conftest**

```bash
mkdir -p tests
touch tests/__init__.py
```

Write `tests/conftest.py`:

```python
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
```

- [ ] **Step 2: Write failing test for BASIC_IMG2IMG shape**

Write `tests/test_remix_workflows.py`:

```python
"""Unit tests for the img2img remix workflow template. No ComfyUI required."""

import json

import pytest


def test_basic_img2img_has_required_node_types():
    from backends.comfyui import BASIC_IMG2IMG

    node_types = {n["class_type"] for n in BASIC_IMG2IMG.values()}
    assert "LoadImage" in node_types
    assert "VAEEncode" in node_types
    assert "KSampler" in node_types
    assert "CheckpointLoaderSimple" in node_types
    assert "CLIPTextEncode" in node_types
    assert "VAEDecode" in node_types
    assert "SaveImage" in node_types
    assert "EmptyLatentImage" not in node_types


def test_basic_img2img_ksampler_reads_encoded_latent():
    from backends.comfyui import BASIC_IMG2IMG

    ksampler = next(n for n in BASIC_IMG2IMG.values() if n["class_type"] == "KSampler")
    latent_ref = ksampler["inputs"]["latent_image"]
    src_id, _ = latent_ref
    src_class = BASIC_IMG2IMG[src_id]["class_type"]
    assert src_class == "VAEEncode"


def test_basic_img2img_vaencode_reads_loadimage():
    from backends.comfyui import BASIC_IMG2IMG

    vae_enc = next(n for n in BASIC_IMG2IMG.values() if n["class_type"] == "VAEEncode")
    pixels_ref = vae_enc["inputs"]["pixels"]
    src_id, _ = pixels_ref
    assert BASIC_IMG2IMG[src_id]["class_type"] == "LoadImage"


def test_basic_img2img_is_json_serializable():
    from backends.comfyui import BASIC_IMG2IMG

    serialized = json.dumps(BASIC_IMG2IMG)
    assert json.loads(serialized) == BASIC_IMG2IMG
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_remix_workflows.py -v`
Expected: FAIL with `ImportError: cannot import name 'BASIC_IMG2IMG' from 'backends.comfyui'`

- [ ] **Step 4: Add the BASIC_IMG2IMG template**

In `backends/comfyui.py`, find the closing `}` of `BASIC_TXT2IMG` (at line 308). Insert immediately after it:

```python


# Img2img workflow template for Style Remix.
# Differs from BASIC_TXT2IMG by replacing EmptyLatentImage with a
# LoadImage -> VAEEncode pair. KSampler starts from a partially-denoised
# version of the source image rather than random noise.
BASIC_IMG2IMG = {
    "1": {
        "class_type": "LoadImage",
        "inputs": {"image": ""},
    },
    "2": {
        "class_type": "VAEEncode",
        "inputs": {"pixels": ["1", 0], "vae": ["4", 2]},
    },
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 0, "steps": 30, "cfg": 7.0,
            "sampler_name": "dpmpp_2m", "scheduler": "karras",
            "denoise": 0.55,
            "model": ["4", 0], "positive": ["6", 0],
            "negative": ["7", 0], "latent_image": ["2", 0],
        },
    },
    "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "sd_xl_base_1.0.safetensors"},
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "", "clip": ["4", 1]},
    },
    "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {"text": "", "clip": ["4", 1]},
    },
    "8": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["3", 0], "vae": ["4", 2]},
    },
    "9": {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "wyltek-remix", "images": ["8", 0]},
    },
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_remix_workflows.py -v`
Expected: 4 tests pass.

- [ ] **Step 6: Commit**

```bash
git add tests/__init__.py tests/conftest.py tests/test_remix_workflows.py backends/comfyui.py
git commit -m "feat: add BASIC_IMG2IMG workflow template for Style Remix"
```

---

## Task 2: Add `generate_remix()` method to ComfyUIBackend

**Files:**
- Modify: `backends/comfyui.py` (add method on `ComfyUIBackend`, reuse `_add_ip_adapter`)
- Modify: `tests/test_remix_workflows.py` (add tests)

- [ ] **Step 1: Write failing tests for workflow assembly**

Append to `tests/test_remix_workflows.py`:

```python
def _make_backend():
    from backends.comfyui import ComfyUIBackend
    return ComfyUIBackend(config={"url": "http://example.invalid"})


def _assembled_workflow(overrides=None):
    base_params = {
        "base_filename": "base.png",
        "style_ref_filename": "style.png",
        "model": "juggernautXL_v9.safetensors",
        "lora_model": "pixel-art-xl.safetensors",
        "lora_strength": 0.55,
        "preserve_character": 0.45,
        "style_strength": 0.75,
        "ip_start": 0.0,
        "ip_end": 0.8,
        "blend_mode": "style transfer",
        "steps": 20,
        "cfg": 6.0,
        "seed": 42,
        "hint": "",
        "width": 1024,
        "height": 1024,
    }
    if overrides:
        base_params.update(overrides)
    return _make_backend()._build_remix_workflow(base_params)


def test_remix_sets_denoise_from_preserve_character():
    wf = _assembled_workflow({"preserve_character": 0.40})
    assert abs(wf["3"]["inputs"]["denoise"] - 0.60) < 1e-6


def test_remix_loads_base_into_node_1():
    wf = _assembled_workflow({"base_filename": "character.png"})
    assert wf["1"]["class_type"] == "LoadImage"
    assert wf["1"]["inputs"]["image"] == "character.png"


def test_remix_sets_checkpoint():
    wf = _assembled_workflow({"model": "realvisxl-v4.safetensors"})
    assert wf["4"]["inputs"]["ckpt_name"] == "realvisxl-v4.safetensors"


def test_remix_injects_lora_and_rewires_ksampler():
    wf = _assembled_workflow({"lora_model": "pixel-art-xl.safetensors", "lora_strength": 0.6})
    assert "20" in wf
    assert wf["20"]["class_type"] == "LoraLoader"
    assert wf["20"]["inputs"]["lora_name"] == "pixel-art-xl.safetensors"
    assert wf["20"]["inputs"]["strength_model"] == 0.6
    assert wf["3"]["inputs"]["model"] == ["13", 0]


def test_remix_ipadapter_batch_has_required_keys():
    wf = _assembled_workflow()
    ipadapter = wf["13"]
    assert ipadapter["class_type"] == "IPAdapterBatch"
    assert "embeds_scaling" in ipadapter["inputs"]
    assert "encode_batch_size" in ipadapter["inputs"]
    assert ipadapter["inputs"]["embeds_scaling"] == "V only"
    assert ipadapter["inputs"]["encode_batch_size"] == 0


def test_remix_hint_goes_to_positive_clip_encoder():
    wf = _assembled_workflow({"hint": "glowing eyes"})
    assert wf["6"]["inputs"]["text"] == "glowing eyes"


def test_remix_empty_hint_stays_empty():
    wf = _assembled_workflow({"hint": ""})
    assert wf["6"]["inputs"]["text"] == ""


def test_remix_sets_seed_and_steps_and_cfg():
    wf = _assembled_workflow({"seed": 12345, "steps": 25, "cfg": 5.5})
    assert wf["3"]["inputs"]["seed"] == 12345
    assert wf["3"]["inputs"]["steps"] == 25
    assert wf["3"]["inputs"]["cfg"] == 5.5


def test_remix_without_lora_skips_node_20_but_still_has_ipadapter():
    wf = _assembled_workflow({"lora_model": ""})
    assert "20" not in wf
    assert wf["13"]["class_type"] == "IPAdapterBatch"
    assert wf["3"]["inputs"]["model"] == ["13", 0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_remix_workflows.py -v`
Expected: 8 new tests FAIL with `AttributeError: 'ComfyUIBackend' object has no attribute '_build_remix_workflow'`.

- [ ] **Step 3: Implement `_build_remix_workflow` and `generate_remix`**

In `backends/comfyui.py`, append to the `ComfyUIBackend` class after `_add_ip_adapter` (before `_poll_history` at line 1450):

```python
    def _build_remix_workflow(self, params: dict) -> dict:
        """Build an img2img + IPAdapter workflow for Style Remix.

        Mirrors generate() but uses BASIC_IMG2IMG as the base. SDXL-only
        for v1 (no GGUF / Flux / PixArt / Klein paths).

        `params` must already be resolved — filenames refer to files
        already copied into the ComfyUI input directory.
        """
        import json as _json

        workflow = _json.loads(_json.dumps(BASIC_IMG2IMG))

        workflow["1"]["inputs"]["image"] = params["base_filename"]

        model_name = params.get("model", "")
        if model_name:
            workflow["4"]["inputs"]["ckpt_name"] = model_name

        workflow["3"]["inputs"]["seed"] = int(params["seed"])
        workflow["3"]["inputs"]["steps"] = int(params["steps"])
        workflow["3"]["inputs"]["cfg"] = float(params["cfg"])
        preserve = float(params["preserve_character"])
        workflow["3"]["inputs"]["denoise"] = round(1.0 - preserve, 4)

        workflow["6"]["inputs"]["text"] = params.get("hint", "") or ""
        workflow["7"]["inputs"]["text"] = params.get("negative_prompt", "") or ""

        lora_name = params.get("lora_model", "")
        if lora_name:
            lora_strength = float(params.get("lora_strength", 0.55))
            lora_strength_clip = float(params.get("lora_strength_clip", lora_strength * 0.6))
            model_source = workflow["3"]["inputs"]["model"]
            clip_source = workflow["6"]["inputs"]["clip"]
            workflow["20"] = {
                "class_type": "LoraLoader",
                "inputs": {
                    "lora_name": lora_name,
                    "strength_model": lora_strength,
                    "strength_clip": lora_strength_clip,
                    "model": model_source,
                    "clip": clip_source,
                },
            }
            workflow["3"]["inputs"]["model"] = ["20", 0]
            workflow["6"]["inputs"]["clip"] = ["20", 1]
            workflow["7"]["inputs"]["clip"] = ["20", 1]

        style_filename = params.get("style_ref_filename", "")
        if style_filename:
            ip_params = {
                "ip_adapter_model": params.get("ip_adapter_model", "sdxl_models/ip-adapter_sdxl_vit-h.safetensors"),
                "ip_adapter_strength": float(params.get("style_strength", 0.75)),
                "ip_adapter_weight_type": params.get("blend_mode", "style transfer"),
                "ip_adapter_start": float(params.get("ip_start", 0.0)),
                "ip_adapter_end": float(params.get("ip_end", 0.8)),
            }
            workflow = self._add_ip_adapter(workflow, [style_filename], ip_params)

        return workflow

    async def generate_remix(self, params: dict, output_path: str, on_progress) -> dict:
        """Run a single remix job through ComfyUI.

        `params` keys (server.py resolves filenames before calling):
          base_filename, style_ref_filename, model, lora_model, lora_strength,
          preserve_character, style_strength, ip_start, ip_end, blend_mode,
          steps, cfg, seed, hint, width, height.
        """
        import aiohttp

        workflow = self._build_remix_workflow(params)

        url = self.url.rstrip("/")
        client_id = str(uuid.uuid4())

        await on_progress(5, "Submitting to ComfyUI...")

        async with aiohttp.ClientSession() as session:
            async with session.post(f"{url}/prompt",
                                    json={"prompt": workflow, "client_id": client_id}) as resp:
                data = await resp.json()
                if "error" in data:
                    err = data.get("error")
                    node_errors = data.get("node_errors", {})
                    raise RuntimeError(f"ComfyUI rejected workflow: {err} {node_errors}")
                prompt_id = data["prompt_id"]

            for i in range(300):
                await asyncio.sleep(1)
                async with session.get(f"{url}/history/{prompt_id}") as resp:
                    history = await resp.json()
                if prompt_id in history:
                    break
                if i % 5 == 0:
                    await on_progress(min(10 + i, 85), "Remixing...")
            else:
                raise RuntimeError("ComfyUI remix timed out")

            record = history[prompt_id]
            outputs = record.get("outputs", {})
            save_node = outputs.get("9", {})
            images = save_node.get("images", [])
            if not images:
                raise RuntimeError("ComfyUI finished but produced no images")
            img = images[0]
            filename = img["filename"]
            subfolder = img.get("subfolder", "")
            view_url = f"{url}/view"
            qs = {"filename": filename, "subfolder": subfolder, "type": img.get("type", "output")}
            async with session.get(view_url, params=qs) as resp:
                data = await resp.read()

        with open(output_path, "wb") as f:
            f.write(data)

        await on_progress(100, "Done")
        return {"filename": Path(output_path).name}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_remix_workflows.py -v`
Expected: 12 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backends/comfyui.py tests/test_remix_workflows.py
git commit -m "feat: add ComfyUIBackend.generate_remix for img2img style transfer"
```

---

## Task 3: Gallery-id and crypto-logo-id resolution helpers

**Files:**
- Create: `tests/test_remix_resolvers.py`
- Modify: `server.py` (add resolvers above the music-engine block at line 1592)

- [ ] **Step 1: Write failing tests**

Write `tests/test_remix_resolvers.py`:

```python
"""Unit tests for remix input resolvers."""

from pathlib import Path

import pytest


def _make_storage(tmp_path: Path) -> Path:
    storage = tmp_path / "storage"
    (storage / "crypto-logos").mkdir(parents=True)
    (storage / "unsorted" / "2026-04-19" / "images").mkdir(parents=True)
    (storage / "crypto-logos" / "bitcoin-btc.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (storage / "unsorted" / "2026-04-19" / "images" / "abc12345.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    return storage


def test_resolve_crypto_logo_hits_storage_subdir(tmp_path, monkeypatch):
    _make_storage(tmp_path)
    monkeypatch.chdir(tmp_path)
    from server import resolve_crypto_logo
    path = resolve_crypto_logo("bitcoin-btc")
    assert path is not None
    assert path.name == "bitcoin-btc.png"


def test_resolve_crypto_logo_missing_returns_none(tmp_path, monkeypatch):
    _make_storage(tmp_path)
    monkeypatch.chdir(tmp_path)
    from server import resolve_crypto_logo
    assert resolve_crypto_logo("ripple-xrp") is None


def test_resolve_crypto_logo_rejects_path_traversal(tmp_path, monkeypatch):
    _make_storage(tmp_path)
    monkeypatch.chdir(tmp_path)
    from server import resolve_crypto_logo
    assert resolve_crypto_logo("../unsorted/2026-04-19/images/abc12345") is None
    assert resolve_crypto_logo("..") is None
    assert resolve_crypto_logo("a/b") is None


def test_resolve_gallery_image_hits_unsorted(tmp_path, monkeypatch):
    _make_storage(tmp_path)
    monkeypatch.chdir(tmp_path)
    from server import resolve_gallery_image
    path = resolve_gallery_image("abc12345.png")
    assert path is not None
    assert path.name == "abc12345.png"


def test_resolve_gallery_image_missing_returns_none(tmp_path, monkeypatch):
    _make_storage(tmp_path)
    monkeypatch.chdir(tmp_path)
    from server import resolve_gallery_image
    assert resolve_gallery_image("does_not_exist.png") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_remix_resolvers.py -v`
Expected: 5 tests FAIL with `ImportError: cannot import name 'resolve_crypto_logo' from 'server'`.

- [ ] **Step 3: Add resolvers to server.py**

In `server.py`, immediately BEFORE the `# --- Music Generation API ---` comment at line 1592, insert:

```python
# --- Style Remix resolvers ---

def resolve_crypto_logo(slug: str) -> Path | None:
    """Resolve a crypto logo slug like 'bitcoin-btc' to storage/crypto-logos/<slug>.png.

    Rejects slugs containing path separators, '..', or empty values.
    """
    if not slug or "/" in slug or "\\" in slug or ".." in slug:
        return None
    candidate = Path("storage") / "crypto-logos" / f"{slug}.png"
    return candidate if candidate.exists() else None


def resolve_gallery_image(filename: str) -> Path | None:
    """Resolve a gallery image filename via storage.resolve_asset."""
    import storage as store
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        return None
    return store.resolve_asset(filename)

```

Verify `Path` is already imported at the top of `server.py` (`from pathlib import Path`). If not, add it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_remix_resolvers.py -v`
Expected: 5 tests pass.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_remix_resolvers.py
git commit -m "feat: add gallery + crypto-logo resolvers for Style Remix"
```

---

## Task 4: `/api/remix` endpoint with validation

**Files:**
- Create: `tests/test_api_remix.py`
- Modify: `server.py` (add endpoint next to `/api/compare` at line 2159, plus a one-line dispatch branch in `_run_job`)

- [ ] **Step 1: Write failing validation tests**

Write `tests/test_api_remix.py`:

```python
"""Validation tests for POST /api/remix. Uses FastAPI TestClient; no ComfyUI required."""

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    (storage / "crypto-logos").mkdir(parents=True)
    (storage / "unsorted" / "2026-04-19" / "images").mkdir(parents=True)
    (storage / "crypto-logos" / "bitcoin-btc.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (storage / "unsorted" / "2026-04-19" / "images" / "abc12345.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    (tmp_path / "uploads").mkdir()
    monkeypatch.chdir(tmp_path)

    import importlib
    import server as server_mod
    importlib.reload(server_mod)
    return TestClient(server_mod.app)


def _valid_form(**overrides):
    base = {
        "base_gallery_id": "abc12345.png",
        "crypto_logo_id": "bitcoin-btc",
        "preserve_character": "0.45",
        "style_strength": "0.75",
        "ip_start": "0.0",
        "ip_end": "0.8",
        "blend_mode": "style transfer",
        "lora_model": "",
        "lora_strength": "0.55",
        "model": "juggernautXL_v9.safetensors",
        "steps": "20",
        "cfg": "6.0",
        "seed": "-1",
        "batch_size": "2",
        "hint": "",
    }
    base.update({k: str(v) for k, v in overrides.items()})
    return base


def test_remix_rejects_missing_base(client):
    form = _valid_form()
    del form["base_gallery_id"]
    resp = client.post("/api/remix", data=form)
    assert resp.status_code == 400
    assert "base" in resp.json()["error"].lower()


def test_remix_rejects_missing_style_ref(client):
    form = _valid_form()
    del form["crypto_logo_id"]
    resp = client.post("/api/remix", data=form)
    assert resp.status_code == 400
    assert "style" in resp.json()["error"].lower()


def test_remix_rejects_unknown_gallery_id(client):
    resp = client.post("/api/remix", data=_valid_form(base_gallery_id="nothing.png"))
    assert resp.status_code == 404


def test_remix_rejects_unknown_crypto_logo(client):
    resp = client.post("/api/remix", data=_valid_form(crypto_logo_id="ripple-xrp"))
    assert resp.status_code == 404


def test_remix_rejects_out_of_range_preserve_character(client):
    resp_low = client.post("/api/remix", data=_valid_form(preserve_character=0.1))
    resp_high = client.post("/api/remix", data=_valid_form(preserve_character=0.95))
    assert resp_low.status_code == 400
    assert resp_high.status_code == 400


def test_remix_rejects_out_of_range_batch_size(client):
    resp_zero = client.post("/api/remix", data=_valid_form(batch_size=0))
    resp_big = client.post("/api/remix", data=_valid_form(batch_size=20))
    assert resp_zero.status_code == 400
    assert resp_big.status_code == 400


def test_remix_accepts_valid_submission_and_returns_jobs(client):
    resp = client.post("/api/remix", data=_valid_form(batch_size=3))
    assert resp.status_code == 200
    body = resp.json()
    assert "remix_id" in body
    assert len(body["jobs"]) == 3
    for j in body["jobs"]:
        assert "job_id" in j


def test_remix_seed_expansion_deterministic(client):
    resp = client.post("/api/remix", data=_valid_form(batch_size=3, seed=100))
    assert resp.status_code == 200
    import server as server_mod
    seeds = sorted(server_mod.jobs[j["job_id"]]["params"]["seed"] for j in resp.json()["jobs"])
    assert seeds == [100, 101, 102]


def test_remix_seed_minus_one_picks_random_base(client):
    resp = client.post("/api/remix", data=_valid_form(batch_size=2, seed=-1))
    assert resp.status_code == 200
    import server as server_mod
    seeds = [server_mod.jobs[j["job_id"]]["params"]["seed"] for j in resp.json()["jobs"]]
    assert all(s >= 0 for s in seeds)
    assert abs(seeds[1] - seeds[0]) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_api_remix.py -v`
Expected: all 9 tests FAIL — endpoint not defined yet.

- [ ] **Step 3: Implement the endpoint**

In `server.py`, find the `@app.post("/api/compare")` route (line 2159). Immediately after the `compare()` function body (after line 2220, before `# --- WebSocket`), insert:

```python
# --- Style Remix API ---

_BLEND_MODE_VALUES = {"style transfer", "standard", "prompt is more important"}


@app.post("/api/remix")
async def remix(
    base_image: UploadFile | None = File(default=None),
    base_gallery_id: str = Form(""),
    style_ref: UploadFile | None = File(default=None),
    crypto_logo_id: str = Form(""),
    preserve_character: float = Form(0.45),
    style_strength: float = Form(0.75),
    ip_start: float = Form(0.0),
    ip_end: float = Form(0.8),
    blend_mode: str = Form("style transfer"),
    lora_model: str = Form(""),
    lora_strength: float = Form(0.55),
    model: str = Form("juggernautXL_v9.safetensors"),
    steps: int = Form(20),
    cfg: float = Form(6.0),
    seed: int = Form(-1),
    batch_size: int = Form(4),
    hint: str = Form(""),
):
    """Enqueue a batch of Style Remix jobs. One ComfyUI job per batch slot."""
    import random as _random
    import shutil as _shutil

    base_source_path: Path | None = None
    base_kind = ""
    base_ref = ""
    if base_image is not None and base_image.filename:
        upload_id = str(uuid.uuid4())[:8]
        ext = Path(base_image.filename).suffix or ".png"
        dest = Path("uploads") / f"remix_base_{upload_id}{ext}"
        async with aiofiles.open(dest, "wb") as f:
            await f.write(await base_image.read())
        base_source_path = dest
        base_kind = "upload"
        base_ref = dest.name
    elif base_gallery_id:
        resolved = resolve_gallery_image(base_gallery_id)
        if resolved is None:
            return JSONResponse({"error": f"Gallery image '{base_gallery_id}' not found"}, status_code=404)
        base_source_path = resolved
        base_kind = "gallery"
        base_ref = base_gallery_id
    else:
        return JSONResponse({"error": "base_image or base_gallery_id is required"}, status_code=400)

    style_source_path: Path | None = None
    style_kind = ""
    style_ref_id = ""
    if style_ref is not None and style_ref.filename:
        upload_id = str(uuid.uuid4())[:8]
        ext = Path(style_ref.filename).suffix or ".png"
        dest = Path("uploads") / f"remix_style_{upload_id}{ext}"
        async with aiofiles.open(dest, "wb") as f:
            await f.write(await style_ref.read())
        style_source_path = dest
        style_kind = "upload"
        style_ref_id = dest.name
    elif crypto_logo_id:
        resolved = resolve_crypto_logo(crypto_logo_id)
        if resolved is None:
            return JSONResponse({"error": f"Crypto logo '{crypto_logo_id}' not found"}, status_code=404)
        style_source_path = resolved
        style_kind = "crypto"
        style_ref_id = crypto_logo_id
    else:
        return JSONResponse({"error": "style_ref or crypto_logo_id is required"}, status_code=400)

    if not (0.2 <= preserve_character <= 0.9):
        return JSONResponse({"error": "preserve_character must be in [0.2, 0.9]"}, status_code=400)
    if not (1 <= batch_size <= 8):
        return JSONResponse({"error": "batch_size must be in [1, 8]"}, status_code=400)
    if blend_mode not in _BLEND_MODE_VALUES:
        return JSONResponse({"error": f"blend_mode must be one of {sorted(_BLEND_MODE_VALUES)}"}, status_code=400)

    comfy_input_dir = Path("/home/phill/ComfyUI/input")
    base_filename = f"remix_base_{uuid.uuid4().hex[:8]}{base_source_path.suffix}"
    style_filename = f"remix_style_{uuid.uuid4().hex[:8]}{style_source_path.suffix}"
    _shutil.copy2(base_source_path, comfy_input_dir / base_filename)
    _shutil.copy2(style_source_path, comfy_input_dir / style_filename)

    base_seed = _random.randint(0, 2**32 - 1 - batch_size) if seed == -1 else seed

    remix_id = str(uuid.uuid4())[:8]
    job_ids: list[dict] = []
    for i in range(batch_size):
        job_id = str(uuid.uuid4())[:8]
        slot_seed = base_seed + i
        params = {
            "remix": True,
            "backend": "comfyui",
            "base_filename": base_filename,
            "style_ref_filename": style_filename,
            "base_from_kind": base_kind,
            "base_from": base_ref,
            "style_ref_kind": style_kind,
            "style_ref": style_ref_id,
            "model": model,
            "lora_model": lora_model,
            "lora_strength": lora_strength,
            "preserve_character": preserve_character,
            "style_strength": style_strength,
            "ip_start": ip_start,
            "ip_end": ip_end,
            "blend_mode": blend_mode,
            "steps": steps,
            "cfg": cfg,
            "seed": slot_seed,
            "batch_size": batch_size,
            "slot_index": i,
            "hint": hint,
            "width": 1024,
            "height": 1024,
        }
        jobs[job_id] = {"status": "queued", "params": params, "progress": 0, "remix_id": remix_id}
        job_queue.submit_background(_run_job(job_id, params), lane="gpu", job_id=job_id)
        job_ids.append({"job_id": job_id})

    return {"remix_id": remix_id, "jobs": job_ids}

```

- [ ] **Step 4: Add the `remix:True` dispatch branch in `_run_job`**

In `server.py`, find the line `await backend.generate(params, str(output_path), on_progress)` (around line 2280). Replace with:

```python
        if params.get("remix"):
            await backend.generate_remix(params, str(output_path), on_progress)
        else:
            await backend.generate(params, str(output_path), on_progress)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_api_remix.py -v`
Expected: all 9 tests pass.

Also run: `pytest tests/ -v` to confirm no regression. Expected: previously-green tests still green.

- [ ] **Step 6: Commit**

```bash
git add server.py tests/test_api_remix.py
git commit -m "feat: add POST /api/remix endpoint with validation"
```

---

## Task 5: Build `remix.html` page scaffold + route

**Files:**
- Create: `static/studio/remix.html`
- Modify: `server.py` (add `/studio/remix` route near other studio page routes)

- [ ] **Step 1: Find the existing studio-route pattern**

Run: `grep -n "studio/" /home/phill/open-palette/server.py`

Expected: routes like `@app.get("/studio/music")` returning `FileResponse("static/studio/music.html")`. Match that pattern.

- [ ] **Step 2: Add the `/studio/remix` route**

In `server.py`, immediately next to an existing studio route (e.g. after `/studio/music`), add:

```python
@app.get("/studio/remix")
async def studio_remix():
    return FileResponse("static/studio/remix.html")
```

- [ ] **Step 3: Create `remix.html`**

Write `static/studio/remix.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Wyltek Studio — Style Remix</title>
  <link rel="stylesheet" href="/static/css/style.css">
  <link rel="stylesheet" href="/static/css/nav.css">
  <script src="/static/js/nav.js"></script>
  <style>
    .studio-page { max-width: 1400px; margin: 0 auto; padding: 32px 24px; }
    .studio-header h2 { margin: 0 0 4px; }
    .studio-header .subtitle { font-size: 13px; color: var(--text-dim); margin-bottom: 20px; }
    .ref-row { display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
    .ref-tile {
      width: 180px; height: 180px; border: 2px dashed var(--border); border-radius: 8px;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      cursor: pointer; position: relative; overflow: hidden; background: var(--surface);
    }
    .ref-tile.has-image { border-style: solid; }
    .ref-tile img { width: 100%; height: 100%; object-fit: contain; }
    .ref-tile .label { font-size: 12px; color: var(--text-dim); text-align: center; }
    .ref-tile .clear {
      position: absolute; top: 6px; right: 6px; width: 22px; height: 22px;
      background: rgba(0,0,0,0.7); color: #fff; border: none; border-radius: 50%;
      cursor: pointer; font-size: 13px; display: none;
    }
    .ref-tile.has-image .clear { display: block; }
    .ref-label { font-size: 11px; color: var(--text-dim); text-transform: uppercase; margin-bottom: 6px; }
    .crypto-picker { width: 180px; display: flex; flex-direction: column; gap: 6px; position: relative; }
    .crypto-picker input {
      padding: 6px 8px; background: var(--surface); border: 1px solid var(--border);
      border-radius: 6px; color: var(--text); font-size: 12px;
    }
    .crypto-picker .dropdown {
      display: none; position: absolute; top: 100%; left: 0; background: var(--surface);
      border: 1px solid var(--border); border-radius: 6px; max-height: 260px;
      overflow-y: auto; z-index: 20; min-width: 180px;
    }
    .crypto-picker .dropdown .item { padding: 6px 10px; font-size: 12px; cursor: pointer; }
    .crypto-picker .dropdown .item:hover { background: var(--surface-2); }
    .sublabel { font-size: 10px; color: var(--text-dim); text-align: center; }
    .controls { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px; margin-bottom: 16px; }
    .controls label { display: block; font-size: 10px; color: var(--text-dim); text-transform: uppercase; margin-bottom: 3px; }
    .controls input, .controls select {
      width: 100%; padding: 7px; background: var(--surface); border: 1px solid var(--border);
      border-radius: 6px; color: var(--text); font-size: 12px;
    }
    .range-val { font-size: 10px; color: var(--text-dim); text-align: center; }
    .hint-row { margin-bottom: 16px; }
    .hint-row input {
      width: 100%; padding: 10px; background: var(--surface); border: 1px solid var(--border);
      border-radius: 6px; color: var(--text); font-size: 13px;
    }
    .progress-bar { height: 6px; background: var(--surface-2); border-radius: 3px; overflow: hidden; margin: 12px 0; display: none; }
    .progress-fill { height: 100%; background: var(--accent); width: 0%; transition: width 0.3s; }
    .result-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; margin-top: 20px; }
    .result-tile { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; overflow: hidden; }
    .result-tile .image-wrap { width: 100%; aspect-ratio: 1/1; background: var(--surface-2); display: flex; align-items: center; justify-content: center; }
    .result-tile .image-wrap img { width: 100%; height: 100%; object-fit: contain; }
    .result-tile .placeholder { font-size: 11px; color: var(--text-dim); }
    .result-tile .actions { display: flex; gap: 4px; padding: 8px; }
    .result-tile .actions button { flex: 1; font-size: 11px; padding: 5px; }
    .modal-bg { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 100; }
    .modal-bg.active { display: flex; align-items: center; justify-content: center; }
    .modal { background: var(--surface); border-radius: 12px; padding: 24px; max-width: 900px; width: 90vw; max-height: 85vh; display: flex; flex-direction: column; }
    .modal h3 { margin: 0 0 12px; }
    .gallery-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 8px; overflow-y: auto; flex: 1; }
    .gallery-item { background: var(--surface-2); border-radius: 6px; cursor: pointer; overflow: hidden; aspect-ratio: 1/1; }
    .gallery-item img { width: 100%; height: 100%; object-fit: contain; }
    .gallery-item:hover { outline: 2px solid var(--accent); }
  </style>
</head>
<body>
  <div class="studio-page">
    <div class="studio-header">
      <h2>Style Remix</h2>
      <div class="subtitle">Pick a character from your gallery, apply a style reference.</div>
    </div>

    <div class="ref-row">
      <div>
        <div class="ref-label">Base Character</div>
        <div class="ref-tile" id="base-tile" onclick="onBaseTileClick()">
          <span class="label">Click to pick from gallery<br>or drop an image</span>
          <button class="clear" onclick="clearBase(event)">&times;</button>
        </div>
      </div>

      <div>
        <div class="ref-label">Style Reference</div>
        <div class="ref-tile" id="style-tile" onclick="onStyleTileClick()">
          <span class="label">Upload image</span>
          <button class="clear" onclick="clearStyle(event)">&times;</button>
        </div>
      </div>

      <div class="crypto-picker">
        <div class="ref-label">— or — Crypto Logo</div>
        <input type="text" id="crypto-search" placeholder="Search coin..." autocomplete="off"
               oninput="onCryptoSearch()" onfocus="onCryptoSearch()">
        <div class="dropdown" id="crypto-dropdown"></div>
        <div class="sublabel" id="crypto-status"></div>
      </div>

      <input type="file" id="hidden-upload" accept="image/*" style="display:none">
    </div>

    <div class="hint-row">
      <input type="text" id="hint" placeholder="Optional style hint (e.g. 'more golden', 'glowing eyes')">
    </div>

    <div class="controls">
      <div>
        <label>Preserve Character</label>
        <input type="range" id="preserve" min="0.2" max="0.9" step="0.05" value="0.45">
        <div class="range-val" id="preserve-val">0.45</div>
      </div>
      <div>
        <label>Style Intensity</label>
        <input type="range" id="strength" min="0" max="1.5" step="0.05" value="0.75">
        <div class="range-val" id="strength-val">0.75</div>
      </div>
      <div>
        <label>Style Start</label>
        <input type="range" id="ip-start" min="0" max="1" step="0.05" value="0.0">
        <div class="range-val" id="ip-start-val">0.00</div>
      </div>
      <div>
        <label>Style End</label>
        <input type="range" id="ip-end" min="0" max="1" step="0.05" value="0.8">
        <div class="range-val" id="ip-end-val">0.80</div>
      </div>
      <div>
        <label>Blend Mode</label>
        <select id="blend-mode">
          <option value="style transfer" selected>Style Transfer</option>
          <option value="standard">Standard</option>
          <option value="prompt is more important">Prompt Priority</option>
        </select>
      </div>
      <div>
        <label>Model</label>
        <select id="model"></select>
      </div>
      <div>
        <label>LoRA</label>
        <select id="lora"></select>
      </div>
      <div>
        <label>LoRA Strength</label>
        <input type="range" id="lora-strength" min="0" max="1" step="0.05" value="0.55">
        <div class="range-val" id="lora-strength-val">0.55</div>
      </div>
      <div>
        <label>Batch Size</label>
        <select id="batch">
          <option value="2">2</option>
          <option value="4" selected>4</option>
          <option value="6">6</option>
          <option value="8">8</option>
        </select>
      </div>
      <div>
        <label>Steps</label>
        <input type="number" id="steps" min="10" max="40" value="20">
      </div>
      <div>
        <label>CFG</label>
        <input type="number" id="cfg" min="1" max="20" step="0.5" value="6.0">
      </div>
      <div>
        <label>Seed</label>
        <input type="number" id="seed" value="-1" title="-1 = random">
      </div>
    </div>

    <button class="btn-primary" id="btn-gen" onclick="submitRemix()">Generate Remix</button>

    <div class="progress-bar" id="progress"><div class="progress-fill" id="progress-fill"></div></div>

    <div class="result-grid" id="results"></div>
  </div>

  <div class="modal-bg" id="gallery-modal" onclick="closeGalleryModal(event)">
    <div class="modal" onclick="event.stopPropagation()">
      <h3>Pick Base Character</h3>
      <div class="gallery-grid" id="gallery-grid"></div>
    </div>
  </div>

  <script src="/static/studio/js/remix.js"></script>
</body>
</html>
```

- [ ] **Step 4: Verify the page loads**

Run: `systemctl --user restart open-palette.service && sleep 3`
Visit: `http://localhost:7860/studio/remix`
Expected: page renders. Buttons don't work yet (JS file not created until Task 6). No critical JS errors beyond `submitRemix is not defined`.

- [ ] **Step 5: Commit**

```bash
git add static/studio/remix.html server.py
git commit -m "feat: scaffold Style Remix page markup and route"
```

---

## Task 6: Implement `remix.js` controller + `/api/crypto-logos` listing

**Files:**
- Create: `static/studio/js/remix.js`
- Modify: `server.py` (add `/api/crypto-logos` listing endpoint)

- [ ] **Step 1: Add a listing endpoint for crypto logos**

In `server.py`, just below the `resolve_crypto_logo` helper added in Task 3, add:

```python
@app.get("/api/crypto-logos")
async def list_crypto_logos():
    """List all crypto logos available for Style Remix."""
    logos_dir = Path("storage") / "crypto-logos"
    if not logos_dir.exists():
        return []
    items = []
    for png in sorted(logos_dir.glob("*.png")):
        slug = png.stem
        parts = slug.rsplit("-", 1)
        if len(parts) == 2 and parts[1].isalpha():
            name = f"{parts[0].replace('-', ' ').title()} ({parts[1].upper()})"
        else:
            name = slug.replace("-", " ").title()
        items.append({"slug": slug, "name": name})
    return items
```

- [ ] **Step 2: Write the controller**

Write `static/studio/js/remix.js`:

```javascript
/* Style Remix page controller. */

const state = {
  baseKind: '',
  baseGalleryId: '',
  baseUploadFile: null,
  styleKind: '',
  styleUploadFile: null,
  cryptoLogoId: '',
  jobs: {},
  models: [],
  loras: [],
  cryptoLogos: [],
};

const $ = (id) => document.getElementById(id);

async function loadCatalog() {
  try {
    const backends = await fetch('/api/backends').then(r => r.json());
    const comfy = backends.comfyui || {};
    state.models = (comfy.models || []).filter(m => /\.safetensors$|\.ckpt$/i.test(m));
    const modelSel = $('model');
    state.models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m; opt.textContent = m;
      modelSel.appendChild(opt);
    });
    const preferred = state.models.find(m => /juggernaut/i.test(m));
    if (preferred) modelSel.value = preferred;

    state.loras = comfy.loras || [];
    const loraSel = $('lora');
    const none = document.createElement('option');
    none.value = ''; none.textContent = '(none)';
    loraSel.appendChild(none);
    state.loras.forEach(l => {
      const opt = document.createElement('option');
      opt.value = l; opt.textContent = l;
      loraSel.appendChild(opt);
    });
    const pixelLora = state.loras.find(l => /pixel/i.test(l));
    if (pixelLora) loraSel.value = pixelLora;
  } catch (e) {
    console.warn('loadCatalog failed', e);
  }
}

async function loadCryptoLogos() {
  try {
    const resp = await fetch('/api/crypto-logos');
    if (!resp.ok) throw new Error('no endpoint');
    state.cryptoLogos = await resp.json();
    $('crypto-status').textContent = `${state.cryptoLogos.length} logos available`;
  } catch (e) {
    state.cryptoLogos = [];
    $('crypto-status').textContent = 'Logo list unavailable';
  }
}

function bindRangeLabel(inputId, labelId, digits = 2) {
  const inp = $(inputId); const lbl = $(labelId);
  const update = () => { lbl.textContent = Number(inp.value).toFixed(digits); };
  inp.addEventListener('input', update);
  update();
}

function onBaseTileClick() {
  openGalleryModal();
}

function clearBase(event) {
  event.stopPropagation();
  state.baseKind = '';
  state.baseGalleryId = '';
  state.baseUploadFile = null;
  const tile = $('base-tile');
  tile.classList.remove('has-image');
  tile.innerHTML = '<span class="label">Click to pick from gallery<br>or drop an image</span>'
    + '<button class="clear" onclick="clearBase(event)">&times;</button>';
}

function setBaseImagePreview(src) {
  const tile = $('base-tile');
  tile.classList.add('has-image');
  tile.innerHTML = `<img src="${src}" alt="Base character">`
    + '<button class="clear" onclick="clearBase(event)">&times;</button>';
}

function bindBaseDrop() {
  const tile = $('base-tile');
  tile.addEventListener('dragover', e => { e.preventDefault(); });
  tile.addEventListener('drop', e => {
    e.preventDefault();
    const f = e.dataTransfer.files[0];
    if (!f) return;
    state.baseKind = 'upload';
    state.baseUploadFile = f;
    state.baseGalleryId = '';
    setBaseImagePreview(URL.createObjectURL(f));
  });
}

async function openGalleryModal() {
  const modal = $('gallery-modal');
  const grid = $('gallery-grid');
  grid.innerHTML = '<div style="padding:20px;color:var(--text-dim)">Loading...</div>';
  modal.classList.add('active');
  try {
    const items = await fetch('/api/gallery').then(r => r.json());
    grid.innerHTML = '';
    items.forEach(item => {
      const el = document.createElement('div');
      el.className = 'gallery-item';
      el.innerHTML = `<img src="${item.url}" alt="">`;
      el.onclick = () => pickGalleryImage(item);
      grid.appendChild(el);
    });
  } catch (e) {
    grid.innerHTML = `<div style="padding:20px;color:var(--text-dim)">Failed to load gallery: ${e.message}</div>`;
  }
}

function closeGalleryModal(event) {
  if (event && event.target.id !== 'gallery-modal') return;
  $('gallery-modal').classList.remove('active');
}

function pickGalleryImage(item) {
  state.baseKind = 'gallery';
  state.baseGalleryId = item.filename || item.url.split('/').pop();
  state.baseUploadFile = null;
  setBaseImagePreview(item.url);
  closeGalleryModal();
}

function onStyleTileClick() {
  $('hidden-upload').onchange = (e) => {
    const f = e.target.files[0];
    if (!f) return;
    state.styleKind = 'upload';
    state.styleUploadFile = f;
    state.cryptoLogoId = '';
    const tile = $('style-tile');
    tile.classList.add('has-image');
    tile.innerHTML = `<img src="${URL.createObjectURL(f)}" alt="Style">`
      + '<button class="clear" onclick="clearStyle(event)">&times;</button>';
  };
  $('hidden-upload').click();
}

function clearStyle(event) {
  event.stopPropagation();
  state.styleKind = '';
  state.styleUploadFile = null;
  state.cryptoLogoId = '';
  const tile = $('style-tile');
  tile.classList.remove('has-image');
  tile.innerHTML = '<span class="label">Upload image</span>'
    + '<button class="clear" onclick="clearStyle(event)">&times;</button>';
}

function onCryptoSearch() {
  const q = $('crypto-search').value.trim().toLowerCase();
  const dd = $('crypto-dropdown');
  const matches = state.cryptoLogos.filter(l => l.slug.includes(q) || l.name.toLowerCase().includes(q)).slice(0, 30);
  if (!matches.length) { dd.style.display = 'none'; return; }
  dd.innerHTML = matches.map(l =>
    `<div class="item" onclick="pickCryptoLogo('${l.slug}','${l.name.replace(/'/g,"\\'")}')">${l.name}</div>`
  ).join('');
  dd.style.display = 'block';
}

function pickCryptoLogo(slug, name) {
  state.styleKind = 'crypto';
  state.cryptoLogoId = slug;
  state.styleUploadFile = null;
  $('crypto-dropdown').style.display = 'none';
  $('crypto-search').value = name;
  const tile = $('style-tile');
  tile.classList.add('has-image');
  tile.innerHTML = `<img src="/storage/crypto-logos/${slug}.png" alt="${name}">`
    + '<button class="clear" onclick="clearStyle(event)">&times;</button>';
}

async function submitRemix() {
  if (!state.baseKind) {
    alert('Pick a base character first.');
    return;
  }
  if (!state.styleKind) {
    alert('Pick a style reference (upload or crypto logo).');
    return;
  }

  const form = new FormData();
  if (state.baseKind === 'upload') {
    form.append('base_image', state.baseUploadFile);
  } else {
    form.append('base_gallery_id', state.baseGalleryId);
  }
  if (state.styleKind === 'upload') {
    form.append('style_ref', state.styleUploadFile);
  } else {
    form.append('crypto_logo_id', state.cryptoLogoId);
  }
  form.append('preserve_character', $('preserve').value);
  form.append('style_strength', $('strength').value);
  form.append('ip_start', $('ip-start').value);
  form.append('ip_end', $('ip-end').value);
  form.append('blend_mode', $('blend-mode').value);
  form.append('model', $('model').value);
  form.append('lora_model', $('lora').value);
  form.append('lora_strength', $('lora-strength').value);
  form.append('batch_size', $('batch').value);
  form.append('steps', $('steps').value);
  form.append('cfg', $('cfg').value);
  form.append('seed', $('seed').value);
  form.append('hint', $('hint').value);

  $('btn-gen').disabled = true;
  $('progress').style.display = 'block';
  $('progress-fill').style.width = '2%';
  $('results').innerHTML = '';
  state.jobs = {};

  let body;
  try {
    const resp = await fetch('/api/remix', { method: 'POST', body: form });
    body = await resp.json();
    if (!resp.ok) {
      throw new Error(body.error || `HTTP ${resp.status}`);
    }
  } catch (e) {
    $('btn-gen').disabled = false;
    $('progress').style.display = 'none';
    alert(`Submit failed: ${e.message}`);
    return;
  }

  body.jobs.forEach(j => {
    const tile = document.createElement('div');
    tile.className = 'result-tile';
    tile.innerHTML = `
      <div class="image-wrap"><span class="placeholder">Queued...</span></div>
      <div class="actions">
        <button disabled>Use as new base</button>
      </div>`;
    $('results').appendChild(tile);
    state.jobs[j.job_id] = tile;
  });
}

function openWebSocket() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type !== 'job_update') return;
    const tile = state.jobs[msg.job_id];
    if (!tile) return;
    const wrap = tile.querySelector('.image-wrap');
    if (msg.status === 'running') {
      const plc = wrap.querySelector('.placeholder');
      if (plc) plc.textContent = `${msg.progress}%`;
      const all = Object.values(state.jobs);
      let sum = 0;
      all.forEach(t => {
        const p = t.querySelector('.placeholder');
        if (p) {
          const m = /([\d.]+)%/.exec(p.textContent);
          if (m) sum += parseFloat(m[1]);
        } else {
          sum += 100;
        }
      });
      const pct = all.length ? (sum / all.length) : 0;
      $('progress-fill').style.width = `${pct}%`;
    } else if (msg.status === 'complete') {
      fetch(`/api/job/${msg.job_id}`).then(r => r.json()).then(jr => {
        const url = jr.output_url || `/storage/${msg.job_id}.png`;
        const filename = url.split('/').pop();
        wrap.innerHTML = `<img src="${url}" alt="Remix result">`;
        const btn = tile.querySelector('.actions button');
        btn.disabled = false;
        btn.textContent = 'Use as new base';
        btn.onclick = () => useAsNewBase(filename, url);
      });
    } else if (msg.status === 'error') {
      wrap.innerHTML = `<span class="placeholder" style="color:tomato">Error</span>`;
      const btn = tile.querySelector('.actions button');
      btn.disabled = true;
      btn.textContent = msg.message || 'Failed';
      btn.title = msg.message || '';
    }
    const allDone = Object.keys(state.jobs).every(id => {
      const t = state.jobs[id];
      const plc = t.querySelector('.placeholder');
      return !plc || /Error|Failed/.test(plc.textContent);
    });
    if (allDone) {
      $('btn-gen').disabled = false;
    }
  };
  ws.onclose = () => setTimeout(openWebSocket, 2000);
}

function useAsNewBase(filename, url) {
  state.baseKind = 'gallery';
  state.baseGalleryId = filename;
  state.baseUploadFile = null;
  setBaseImagePreview(url);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

document.addEventListener('DOMContentLoaded', () => {
  bindRangeLabel('preserve', 'preserve-val');
  bindRangeLabel('strength', 'strength-val');
  bindRangeLabel('ip-start', 'ip-start-val');
  bindRangeLabel('ip-end', 'ip-end-val');
  bindRangeLabel('lora-strength', 'lora-strength-val');
  bindBaseDrop();
  loadCatalog();
  loadCryptoLogos();
  openWebSocket();
});
```

- [ ] **Step 3: Restart server and manually verify**

Run: `systemctl --user restart open-palette.service && sleep 3`
Visit: `http://localhost:7860/studio/remix`

Manual verification:
1. Click Base Character tile → gallery modal opens → click an image → preview appears on tile.
2. Type "bit" into Crypto Logo search → "Bitcoin (BTC)" appears in dropdown → click → style tile shows the logo.
3. Click Generate Remix → placeholder tiles appear → tiles fill with results as jobs complete.
4. Click "Use as new base" on one of the results → base tile updates with that image.

If all four work, the page is functionally complete.

- [ ] **Step 4: Commit**

```bash
git add static/studio/js/remix.js server.py
git commit -m "feat: wire Style Remix frontend controller and crypto-logo list endpoint"
```

---

## Task 7: Add Remix to the sidebar nav and update AI copilot map

**Files:**
- Modify: `static/js/nav.js`
- Modify: `static/js/ai-copilot.js`

- [ ] **Step 1: Add Remix to NAV_ITEMS**

In `static/js/nav.js`, find the line for Image Tools:

```javascript
    { href: '/studio/image-tools', icon: '&#9986;', label: 'Image Tools', id: 'image-tools' },
```

Insert IMMEDIATELY BEFORE it (so Remix sits just above Image Tools):

```javascript
    { href: '/studio/remix',       icon: '&#127912;', label: 'Style Remix',  id: 'remix' },
```

- [ ] **Step 2: Add activeId detection**

In the same file, find the activeId detection chain (around line 26). Insert AT THE TOP of the chain (above the existing meme branch):

```javascript
  if (path.startsWith('/studio/remix')) activeId = 'remix';
  else if (path.startsWith('/studio/meme')) activeId = 'meme';
```

The existing `else if (path.startsWith('/studio/meme'))` line stays — you're just prefixing a new line.

- [ ] **Step 3: Update AI copilot page description**

In `static/js/ai-copilot.js`, find:

```javascript
    '/studio/sprites': 'Sprite Forge — game sprite editor and AI sprite generation.',
```

Replace with:

```javascript
    '/studio/remix': 'Style Remix — take a generated character image and apply a style reference (upload or crypto logo) to create themed variants.',
```

Then find the comment around line 60 listing pages. Replace any `Sprite Forge (/studio/sprites)` substring with `Style Remix (/studio/remix)`.

- [ ] **Step 4: Restart and verify**

Run: `systemctl --user restart open-palette.service && sleep 3`
Visit any Wyltek Studio page. The sidebar should include "Style Remix" under Create. Clicking it goes to `/studio/remix` and highlights the link.

- [ ] **Step 5: Commit**

```bash
git add static/js/nav.js static/js/ai-copilot.js
git commit -m "feat: add Style Remix to sidebar nav and copilot page map"
```

---

## Task 8: End-to-end integration test

**Files:**
- Create: `tests/test_remix_e2e.py`

- [ ] **Step 1: Write the integration test**

This test actually runs a remix through ComfyUI. Requires services up; skips gracefully otherwise.

Write `tests/test_remix_e2e.py`:

```python
"""End-to-end Style Remix integration test. Requires open-palette + ComfyUI running."""

import json
import time

import pytest
import requests

OP = "http://localhost:7860"
COMFY = "http://localhost:8188"


def _service_up(url: str, timeout: float = 1.0) -> bool:
    try:
        requests.get(url, timeout=timeout)
        return True
    except Exception:
        return False


@pytest.fixture(autouse=True)
def skip_if_services_down():
    if not _service_up(OP) or not _service_up(COMFY):
        pytest.skip("open-palette or ComfyUI not running on expected ports")


def _pick_existing_gallery_image() -> str:
    resp = requests.get(f"{OP}/api/gallery")
    resp.raise_for_status()
    items = resp.json()
    assert items, "No gallery images — add at least one before running this test."
    return items[0].get("filename") or items[0]["url"].split("/")[-1]


def _pick_existing_crypto_logo() -> str:
    resp = requests.get(f"{OP}/api/crypto-logos")
    resp.raise_for_status()
    items = resp.json()
    assert items, "No crypto logos — seed storage/crypto-logos/ with at least one .png."
    return items[0]["slug"]


def test_remix_end_to_end_with_gallery_and_crypto_logo():
    gallery_id = _pick_existing_gallery_image()
    logo_slug = _pick_existing_crypto_logo()

    form = {
        "base_gallery_id": gallery_id,
        "crypto_logo_id": logo_slug,
        "preserve_character": "0.50",
        "style_strength": "0.75",
        "ip_start": "0.0",
        "ip_end": "0.8",
        "blend_mode": "style transfer",
        "model": "juggernautXL_v9.safetensors",
        "lora_model": "",
        "lora_strength": "0.55",
        "steps": "15",
        "cfg": "6.0",
        "seed": "7",
        "batch_size": "1",
        "hint": "",
    }
    submit = requests.post(f"{OP}/api/remix", data=form, timeout=10)
    assert submit.status_code == 200, submit.text
    body = submit.json()
    assert len(body["jobs"]) == 1
    job_id = body["jobs"][0]["job_id"]

    deadline = time.time() + 180
    while time.time() < deadline:
        j = requests.get(f"{OP}/api/job/{job_id}", timeout=5).json()
        if j.get("status") in ("complete", "error"):
            break
        time.sleep(2)

    assert j["status"] == "complete", f"Job ended with status {j['status']}, error={j.get('error')}"

    import storage as store
    result_path = store.resolve_asset(f"{job_id}.png")
    assert result_path is not None and result_path.exists()
    meta_path = result_path.with_suffix(".json")
    assert meta_path.exists()
    meta = json.loads(meta_path.read_text())
    assert meta["base_from_kind"] == "gallery"
    assert meta["base_from"] == gallery_id
    assert meta["style_ref_kind"] == "crypto"
    assert meta["style_ref"] == logo_slug
    assert meta["preserve_character"] == 0.50
    assert meta["seed"] == 7
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/test_remix_e2e.py -v`

With both services up, gallery populated, and at least one crypto logo, expected: PASS (may take up to 3 minutes).
Without services: SKIPPED.

If the test fails on missing lineage metadata fields, `_run_job` isn't preserving the new param keys in the JSON sidecar. Check `storage/unsorted/<date>/images/<id>.json` — all fields from the remix `params` dict should flow through because `_run_job` writes `{**params, ...}` to the sidecar.

- [ ] **Step 3: Commit**

```bash
git add tests/test_remix_e2e.py
git commit -m "test: add end-to-end Style Remix integration test"
```

---

## Task 9: Remove the old Sprite Forge page

**Files:**
- Delete: `static/studio/sprites.html`
- Modify: `server.py` (remove `/studio/sprites` route if it exists)

- [ ] **Step 1: Confirm no live links remain**

Run: `grep -rn 'studio/sprites\|sprites.html' /home/phill/open-palette --include='*.html' --include='*.js' --include='*.py' --include='*.md'`

Expected: only matches in `docs/superpowers/` (historical references — OK). No matches in `static/js/` or `server.py` (they were updated in Task 7).

If a live reference remains in `static/` or `server.py`, fix it before proceeding.

- [ ] **Step 2: Remove the `/studio/sprites` route if present**

Run: `grep -n '/studio/sprites' /home/phill/open-palette/server.py`

If a `@app.get("/studio/sprites")` route exists, remove it plus its 2-3 line handler body.

- [ ] **Step 3: Delete the old page**

```bash
rm static/studio/sprites.html
```

- [ ] **Step 4: Restart and sanity-check**

Run: `systemctl --user restart open-palette.service && sleep 3`

Visit `http://localhost:7860/studio/remix` — still works.
Visit `http://localhost:7860/studio/sprites` — 404 (or SPA fallback — not important, page is intentionally gone).
Visit `http://localhost:7860/` — main Generate page still works.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: remove old Sprite Forge page (replaced by Style Remix)"
```

---

## Final verification

- [ ] Run the full test suite: `pytest tests/ -v`. All of `test_remix_workflows.py`, `test_remix_resolvers.py`, `test_api_remix.py` must pass. `test_remix_e2e.py` passes or skips gracefully.
- [ ] Walk the full user flow in a browser: pick a gallery base, pick a crypto logo, generate a batch of 4, all four results appear, click "Use as new base" on one, re-generate with a different style.
- [ ] Open one of the result files' JSON sidecar and confirm it contains `base_from_kind`, `base_from`, `style_ref_kind`, `style_ref`, `preserve_character`, `style_strength`, and `seed`.
- [ ] Confirm the IPAdapter regression guard passes: `pytest tests/test_remix_workflows.py::test_remix_ipadapter_batch_has_required_keys -v`. This prevents the 2026-04-19 "Required input is missing" bug from recurring on the remix code path.
