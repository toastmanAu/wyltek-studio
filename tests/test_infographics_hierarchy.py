from pathlib import Path
from studio.infographics import assemble_prompt, load_templates
T = Path(__file__).resolve().parent.parent / "templates" / "infographics"


def test_hierarchy_assembles():
    tpl = load_templates(T)["hierarchy"]
    r = assemble_prompt(tpl, {
        "title": "Company structure", "root": "CEO",
        "levels": [
            {"label": "C-suite", "nodes": [{"label": "CTO"}, {"label": "CFO"}]},
            {"label": "Directors", "nodes": [{"label": "Eng"}, {"label": "Ops"}, {"label": "Sales"}]},
        ],
    })
    assert "CEO" in r.prompt and "CTO" in r.prompt
