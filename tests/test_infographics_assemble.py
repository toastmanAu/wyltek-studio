"""Assembly tests for studio.infographics.assemble_prompt.

Image-ref slot type was dropped from the infographic builder; these tests
cover the remaining text/list slot assembly and validation paths.
"""
import pytest
from studio.infographics import AssemblyResult, SlotValidationError, assemble_prompt

HUB = {
    "id": "hub", "name": "Hub", "description": "t",
    "slots": [
        {"id": "title", "type": "text", "required": True, "max_len": 30},
        {"id": "spokes", "type": "list", "min": 2, "max": 4,
         "item_slots": [
            {"id": "label", "type": "text", "required": True, "max_len": 20}]},
    ],
    "prompt_template": "Title: {{title}}. Spokes: {{#spokes}}[{{label}}] {{/spokes}}",
}


def test_text_slot():
    r = assemble_prompt(HUB, {"title": "Hello", "spokes": [{"label": "A"}, {"label": "B"}]})
    assert "Title: Hello." in r.prompt and "[A] [B]" in r.prompt
    assert r.image_paths == []


def test_required_missing():
    with pytest.raises(SlotValidationError):
        assemble_prompt(HUB, {"spokes": [{"label": "A"}, {"label": "B"}]})


def test_max_len():
    with pytest.raises(SlotValidationError):
        assemble_prompt(HUB, {"title": "x" * 31, "spokes": [{"label": "A"}, {"label": "B"}]})


def test_list_min():
    with pytest.raises(SlotValidationError):
        assemble_prompt(HUB, {"title": "T", "spokes": [{"label": "A"}]})


def test_result_dataclass():
    r = assemble_prompt(HUB, {"title": "T", "spokes": [{"label": "A"}, {"label": "B"}]})
    assert isinstance(r, AssemblyResult)
    assert hasattr(r, "prompt") and hasattr(r, "image_paths")


def test_image_paths_always_empty():
    """image_paths is preserved on the return type for back-compat
    but always [] now that image refs were dropped."""
    r = assemble_prompt(HUB, {"title": "T", "spokes": [{"label": "A"}, {"label": "B"}]})
    assert r.image_paths == []
