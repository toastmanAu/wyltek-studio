"""Phase 1 integration test: loader → assembler → backend (mocked) pipeline."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backends import sensenova
from studio.infographics import assemble_prompt, load_templates


@pytest.mark.asyncio
async def test_pipeline_text_only(tmp_path):
    """Verify full pipeline: load template → assemble prompt → call backend."""
    # Load hub_and_spoke template
    tpl = load_templates(
        Path(__file__).resolve().parent.parent / "templates" / "infographics"
    )["hub_and_spoke"]

    # Assemble prompt with minimal valid values
    result = assemble_prompt(
        tpl,
        {
            "title": "Test",
            "hub_desc": "robot",
            "spokes": [{"label": str(i)} for i in range(4)],
        },
    )

    # Verify assembly produced expected prompt structure
    assert "Test" in result.prompt
    assert "robot" in result.prompt
    assert result.image_paths == []

    # Mock the backend and verify the call
    out_png = tmp_path / "out.png"
    out_png.write_bytes(b"")

    with patch.object(
        sensenova, "generate", new=AsyncMock(return_value=out_png)
    ) as m:
        backend_result = await sensenova.generate(
            prompt=result.prompt,
            image_paths=result.image_paths,
            aspect="1:1",
            seed=42,
            tier="draft",
            output_dir=tmp_path,
        )

    # Verify mock was called with correct signature
    assert backend_result == out_png
    assert "Test" in m.call_args.kwargs["prompt"]
    assert m.call_args.kwargs["aspect"] == "1:1"
    assert m.call_args.kwargs["seed"] == 42
    assert m.call_args.kwargs["tier"] == "draft"
    assert m.call_args.kwargs["output_dir"] == tmp_path
