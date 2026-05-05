from pathlib import Path
from studio.infographics import assemble_prompt, load_templates
T = Path(__file__).resolve().parent.parent / "templates" / "infographics"


def test_list_assembles():
    tpl = load_templates(T)["list"]
    r = assemble_prompt(tpl, {
        "title": "5 reasons to ship",
        "rows": [
            {"label": "Speed", "description": "faster"},
            {"label": "Quality", "description": "less rework"},
            {"label": "Focus", "description": "tight scope"},
            {"label": "Joy", "description": "morale"},
            {"label": "Trust", "description": "we deliver"},
        ],
    })
    assert "5 reasons to ship" in r.prompt
