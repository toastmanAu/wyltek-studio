import json
from pathlib import Path
import jsonschema, pytest

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "studio" / "infographics_schema.json"

@pytest.fixture
def schema():
    with SCHEMA_PATH.open() as f: return json.load(f)

def _minimal():
    return {"id":"minimal","name":"Minimal","description":"x",
            "slots":[{"id":"title","type":"text","required":True}],
            "prompt_template":"{{title}}"}

def test_minimal_validates(schema): jsonschema.validate(_minimal(), schema)
def test_missing_required_rejected(schema):
    bad = _minimal(); del bad["prompt_template"]
    with pytest.raises(jsonschema.ValidationError): jsonschema.validate(bad, schema)
def test_unknown_slot_type_rejected(schema):
    bad = _minimal(); bad["slots"][0]["type"] = "magic"
    with pytest.raises(jsonschema.ValidationError): jsonschema.validate(bad, schema)
def test_list_slot_validates(schema):
    tpl = _minimal()
    tpl["slots"].append({"id":"rows","type":"list","min":2,"max":5,
        "item_slots":[{"id":"label","type":"text","required":True},
                      {"id":"image","type":"image_ref","required":False}]})
    jsonschema.validate(tpl, schema)
