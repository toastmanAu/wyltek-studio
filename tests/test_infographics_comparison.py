from pathlib import Path
from studio.infographics import assemble_prompt, load_templates
T = Path(__file__).resolve().parent.parent / "templates" / "infographics"


def test_comparison_assembles():
    tpl = load_templates(T)["comparison"]
    r = assemble_prompt(tpl, {
        "title": "Coffee vs Tea",
        "left": [{"heading": "Coffee", "bullets": [{"text": "bold"}, {"text": "rich"}, {"text": "warm"}]}],
        "right": [{"heading": "Tea", "bullets": [{"text": "light"}, {"text": "clean"}, {"text": "warm"}]}],
    })
    assert "Coffee" in r.prompt and "Tea" in r.prompt
