from pathlib import Path
from studio.infographics import assemble_prompt, load_templates
T = Path(__file__).resolve().parent.parent / "templates" / "infographics"


def test_stats_assembles():
    tpl = load_templates(T)["stats"]
    r = assemble_prompt(tpl, {
        "title": "By the numbers",
        "cells": [
            {"value": "1M+", "label": "users"},
            {"value": "99.9%", "label": "uptime"},
            {"value": "5x", "label": "faster"},
        ],
    })
    assert "1M+" in r.prompt and "99.9%" in r.prompt
