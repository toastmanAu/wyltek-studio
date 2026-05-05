from pathlib import Path
from studio.infographics import assemble_prompt, load_templates

T = Path(__file__).resolve().parent.parent / "templates" / "infographics"

def test_loads_and_renders():
    tpl = load_templates(T)["hub_and_spoke"]
    r = assemble_prompt(tpl, {
        "title":"Wyltek Studio","hub_desc":"a friendly mascot",
        "spokes":[{"label":"Frames","tagline":"Text to Image","color":"#9be6c4"},
                  {"label":"Edit"},{"label":"Remix"},{"label":"Music"}]})
    assert "Wyltek Studio" in r.prompt and "Frames" in r.prompt
    assert r.image_paths == []

def test_with_hub_image():
    tpl = load_templates(T)["hub_and_spoke"]
    r = assemble_prompt(tpl, {
        "title":"Brand","hub_desc":"logo","hub_image":"/u/logo.png",
        "spokes":[{"label":"A"},{"label":"B"},{"label":"C"},{"label":"D"}]})
    assert "[Image 1]" in r.prompt
    assert r.image_paths == ["/u/logo.png"]
