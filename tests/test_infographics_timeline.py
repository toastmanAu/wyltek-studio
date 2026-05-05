from pathlib import Path
from studio.infographics import assemble_prompt, load_templates
T = Path(__file__).resolve().parent.parent / "templates" / "infographics"


def test_timeline_assembles():
    tpl = load_templates(T)["timeline"]
    r = assemble_prompt(tpl, {
        "title": "From idea to ship",
        "steps": [
            {"label": "Idea", "description": "the spark"},
            {"label": "Plan", "description": "the spec"},
            {"label": "Build", "description": "the code"},
            {"label": "Ship", "description": "the world"},
        ],
    })
    assert "Idea" in r.prompt and "Ship" in r.prompt
