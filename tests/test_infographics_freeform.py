from pathlib import Path
from studio.infographics import assemble_prompt, load_templates

T = Path(__file__).resolve().parent.parent / "templates" / "infographics"


def test_freeform_assembles_passthrough():
    tpl = load_templates(T)["freeform"]
    r = assemble_prompt(tpl, {"prompt": "A cat astronaut on Mars, oil painting"})
    assert r.prompt == "A cat astronaut on Mars, oil painting"
    assert r.image_paths == []


def test_freeform_passes_inline_image_tokens_unchanged():
    tpl = load_templates(T)["freeform"]
    r = assemble_prompt(tpl, {"prompt": "Compare [Image 1] and [Image 2]."})
    assert "[Image 1]" in r.prompt and "[Image 2]" in r.prompt
    assert r.image_paths == []  # chip-inserted refs come from external image_refs[]
