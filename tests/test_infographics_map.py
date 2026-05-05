from pathlib import Path
from studio.infographics import assemble_prompt, load_templates
T = Path(__file__).resolve().parent.parent / "templates" / "infographics"


def test_map_assembles():
    tpl = load_templates(T)["map"]
    r = assemble_prompt(tpl, {
        "title": "User distribution", "region": "world",
        "overlays": [
            {"location": "US", "label": "40%", "value": "120k users"},
            {"location": "EU", "label": "25%", "value": "75k users"},
            {"location": "APAC", "label": "20%", "value": "60k users"},
        ],
    })
    assert "User distribution" in r.prompt and "world" in r.prompt
