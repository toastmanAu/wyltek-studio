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
