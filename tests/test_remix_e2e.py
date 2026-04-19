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
