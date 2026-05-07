from pathlib import Path
from studio.infographics import assemble_prompt, load_templates
T = Path(__file__).resolve().parent.parent / "templates" / "infographics"


def test_quadrant_assembles():
    tpl = load_templates(T)["quadrant"]
    r = assemble_prompt(tpl, {
        "title": "Strategy 2x2",
        "x_axis_low": "low cost", "x_axis_high": "high cost",
        "y_axis_low": "low value", "y_axis_high": "high value",
        "quadrants": [
            {"label": "do later"}, {"label": "do now"},
            {"label": "drop"}, {"label": "delegate"},
        ],
    })
    assert "Strategy 2x2" in r.prompt
