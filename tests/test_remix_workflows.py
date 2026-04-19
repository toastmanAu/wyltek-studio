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
