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
