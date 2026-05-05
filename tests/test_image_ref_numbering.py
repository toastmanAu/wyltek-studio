"""Numbering contract for image refs in the prompt assembler:

1. image_ref-typed slots produce [Image 1..K] in declaration order.
2. External refs (chip-inserted [Image N] tokens) consume N=K+1, K+2…
   and are passed through as the user typed them.

The server endpoint (test_api_infographic_render.test_render_merges_external_image_refs)
locks the path-list merge contract. THIS test locks the assembler's
numbering invariant.
"""

from studio.infographics import assemble_prompt


def test_slot_refs_number_first_then_inline():
    tpl = {
        "id": "x",
        "name": "x",
        "description": "x",
        "slots": [
            {"id": "hub", "type": "image_ref"},
            {"id": "body", "type": "text", "required": True},
            {"id": "foot", "type": "image_ref"},
        ],
        "prompt_template": "{{hub}} body={{body}} foot={{foot}}",
    }
    r = assemble_prompt(tpl, {
        "hub": "/u/hub.png",
        "foot": "/u/foot.png",
        "body": "compare with [Image 3] and [Image 4]",
    })
    # hub -> Image 1, foot -> Image 2 (declaration order)
    assert "[Image 1]" in r.prompt
    assert "[Image 2]" in r.prompt
    # Inline tokens preserved as-is
    assert "[Image 3]" in r.prompt
    assert "[Image 4]" in r.prompt
    # Slot-derived paths only (server merges externals — see Task 21 tests)
    assert r.image_paths == ["/u/hub.png", "/u/foot.png"]


def test_nested_list_slot_refs_get_numbered_in_walk_order():
    """A list slot with image_ref item_slots should produce [Image N] in
    the order: outer slots first, then list items in array order."""
    tpl = {
        "id": "x",
        "name": "x",
        "description": "x",
        "slots": [
            {"id": "hero", "type": "image_ref"},
            {"id": "rows", "type": "list", "min": 1, "max": 3,
             "item_slots": [
                 {"id": "icon", "type": "image_ref"},
             ]},
        ],
        "prompt_template": "{{hero}};{{#rows}}row={{icon}};{{/rows}}",
    }
    r = assemble_prompt(tpl, {
        "hero": "/u/h.png",
        "rows": [
            {"icon": "/u/r1.png"},
            {"icon": "/u/r2.png"},
        ],
    })
    assert "[Image 1]" in r.prompt    # hero
    assert "[Image 2]" in r.prompt    # rows[0].icon
    assert "[Image 3]" in r.prompt    # rows[1].icon
    assert r.image_paths == ["/u/h.png", "/u/r1.png", "/u/r2.png"]
