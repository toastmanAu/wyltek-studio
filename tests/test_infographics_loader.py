import json
from pathlib import Path
import pytest
from studio.infographics import load_templates, TemplateLoadError

def _write(p: Path, doc: dict): (p / f"{doc['id']}.json").write_text(json.dumps(doc))
def _good(id_="hub"):
    return {"id": id_, "name": "T", "description": "x",
            "slots": [{"id":"title","type":"text","required":True}],
            "prompt_template": "{{title}}"}

def test_loads_valid(tmp_path):
    _write(tmp_path, _good("a")); _write(tmp_path, _good("b"))
    out = load_templates(tmp_path)
    assert set(out.keys()) == {"a","b"}

def test_skips_invalid(tmp_path, caplog):
    _write(tmp_path, _good("ok"))
    bad = _good("bad"); del bad["prompt_template"]
    _write(tmp_path, bad)
    out = load_templates(tmp_path)
    assert set(out.keys()) == {"ok"}
    assert "bad" in caplog.text

def test_empty_dir_returns_empty(tmp_path):
    assert load_templates(tmp_path) == {}

def test_missing_dir_raises(tmp_path):
    with pytest.raises(TemplateLoadError):
        load_templates(tmp_path / "no")
