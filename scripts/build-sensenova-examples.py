#!/usr/bin/env python3
"""Build the gallery corpus from the SenseNova-U1 repo + local Wyltek renders.

Reads JSONL prompt files and webp showcase images from a local clone of the
SenseNova-U1 repository, pairs them by index where the dev's layout supports
it, and writes:

  static/studio/sensenova-examples/<category>/<id>.webp     # copied images
  static/studio/sensenova-examples.json                     # corpus index
  static/studio/sensenova-examples/LICENSE-NOTICE.md        # Apache 2.0 note

The corpus JSON is what the gallery UI fetches on load. Re-run this script
whenever the upstream repo ships new showcases.

The script is intentionally deterministic — same inputs always produce the
same output JSON ordering and the same titles.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from pathlib import Path

from PIL import Image

REPO_DEFAULT = Path.home() / "SenseNova-U1"
SKILLS_REPO_DEFAULT = Path.home() / "SenseNova-Skills"
HERE = Path(__file__).resolve().parent.parent
STATIC_DIR = HERE / "static" / "studio" / "sensenova-examples"
CORPUS_JSON = HERE / "static" / "studio" / "sensenova-examples.json"


def derive_title(prompt: str, max_len: int = 60) -> str:
    """Pull a short, human-readable title out of a long prompt.

    Strategy (highest priority first):
      1. Text inside the first pair of double quotes (ASCII or Chinese
         smart quotes “…”) — these are usually the literal poster/title
         text the model is asked to render.
      2. First clause before the first ASCII or full-width punctuation mark.
      3. First max_len chars, trimmed at the last word boundary.
    """
    m = re.search(r'[“"]([^“”"]{3,80})[”"]', prompt)
    if m:
        return m.group(1).strip()

    # Split on ASCII (.,;:) and full-width Chinese punctuation (。，；：).
    head = re.split(r"[.,;:。，；：]", prompt, maxsplit=1)[0].strip()
    if 3 <= len(head) <= max_len:
        return head

    if len(prompt) <= max_len:
        return prompt.strip()

    # Chinese has no whitespace so rsplit(" ") would no-op; fall back to a
    # hard truncate when no space exists in the window.
    window = prompt[:max_len]
    if " " in window:
        return window.rsplit(" ", 1)[0].strip() + "…"
    return window.strip() + "…"


_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


def clean_prompt_html(raw: str) -> str:
    """Normalise an HTML-embedded prompt to plain text with real newlines.

    The Skills doc stores prompts inside <details> blocks with <br><br>
    used for paragraph breaks. The freeform editor expects clean text in
    its textarea — same format as a chatbot paste-target.
    """
    text = _BR_RE.sub("\n", raw)
    text = html.unescape(text)
    # Collapse runs of 3+ newlines to a paragraph break; strip per-line whitespace.
    lines = [ln.strip() for ln in text.splitlines()]
    out: list[str] = []
    blank = False
    for ln in lines:
        if ln:
            out.append(ln)
            blank = False
        elif not blank:
            out.append("")
            blank = True
    return "\n".join(out).strip()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def build_infographic(repo: Path) -> list[dict]:
    """35 prompts ↔ 35 webp images, paired by index 0000…0033 + u1-case2."""
    prompts = load_jsonl(repo / "examples/t2i/data/samples_infographic.jsonl")
    img_dir = repo / "docs/assets/showcases/t2i_infographic"
    images = sorted(img_dir.glob("*.webp"))  # 0000.webp ... 0033.webp, u1-case2.webp last

    if len(prompts) != len(images):
        raise SystemExit(
            f"infographic count mismatch: {len(prompts)} prompts vs {len(images)} images"
        )

    dest = STATIC_DIR / "infographic"
    dest.mkdir(parents=True, exist_ok=True)

    entries = []
    for i, (img, p) in enumerate(zip(images, prompts)):
        ent_id = f"infographic-{i:04d}"
        target = dest / f"{i:04d}.webp"
        shutil.copy2(img, target)
        entries.append({
            "id": ent_id,
            "category": "infographic",
            "title": derive_title(p["prompt"]),
            "prompt": p["prompt"],
            "width": p["width"],
            "height": p["height"],
            "thumbnail": f"/static/studio/sensenova-examples/infographic/{i:04d}.webp",
            "source": "sensenova-u1-repo",
        })
    return entries


_SKILLS_EXAMPLE_RE = re.compile(
    r"<b>(\d+)\.\s*([^<]+?)</b>"
    r".*?<img\s+src=\"(images/infographics/info_\d+\.webp)\""
    r".*?title=\"Click to select all\"[^>]*>(.+?)</div></details>",
    re.DOTALL,
)


def build_skills_examples(skills_repo: Path) -> list[dict]:
    """Parse SenseNova-Skills/docs/sn-infographic-examples.md for ~96 entries.

    The upstream doc is a single HTML-in-Markdown table with one cell per
    example: title in <b>, thumbnail under images/infographics/info_NNN.webp,
    and the long expanded prompt nested inside a <details><summary>...
    block. Width/height come from the actual webp on disk (PIL).
    """
    md = skills_repo / "docs" / "sn-infographic-examples.md"
    img_root = skills_repo / "docs"

    if not md.exists():
        print(f"  [skills] skip — no sn-infographic-examples.md at {md}")
        return []

    text = md.read_text()
    matches = _SKILLS_EXAMPLE_RE.findall(text)
    if not matches:
        print("  [skills] skip — regex matched 0 examples (doc format changed?)")
        return []

    dest = STATIC_DIR / "skills-infographic"
    dest.mkdir(parents=True, exist_ok=True)

    entries = []
    for idx_str, raw_title, img_rel, raw_prompt in matches:
        src_img = img_root / img_rel
        if not src_img.exists():
            print(f"  [skills] skip #{idx_str} — image not found: {src_img}")
            continue

        idx = int(idx_str)
        target_name = Path(img_rel).name  # info_NNN.webp
        target = dest / target_name
        shutil.copy2(src_img, target)

        with Image.open(target) as im:
            w, h = im.size

        prompt = clean_prompt_html(raw_prompt)
        # Title derived from the prompt (same pipeline as U1 entries).
        # derive_title() now handles Chinese smart quotes + punctuation, so
        # it finds the quoted poster-title inside each Chinese prompt.
        title = derive_title(prompt)

        entries.append({
            "id": f"skills-infographic-{idx:03d}",
            "category": "skills-infographic",
            "title": title,
            "prompt": prompt,
            "width": w,
            "height": h,
            "thumbnail": f"/static/studio/sensenova-examples/skills-infographic/{target_name}",
            "source": "sensenova-skills-repo",
        })
    return entries


def build_reasoning(repo: Path) -> list[dict]:
    """5 prompts ↔ 5 images (paired 1→1 … 5→5). Images 6 and 7 have no
    reproducible prompt in the repo and are skipped."""
    prompts = load_jsonl(repo / "examples/t2i/data/samples_reasoning.jsonl")
    img_dir = repo / "docs/assets/showcases/t2i_reasoning"

    dest = STATIC_DIR / "reasoning"
    dest.mkdir(parents=True, exist_ok=True)

    entries = []
    for i, p in enumerate(prompts, start=1):
        src = img_dir / f"{i}_reasoning.png"
        if not src.exists():
            print(f"  [reasoning] skip — no image for prompt {i}")
            continue
        target = dest / f"{i}_reasoning.png"
        shutil.copy2(src, target)
        entries.append({
            "id": f"reasoning-{i:02d}",
            "category": "reasoning",
            "title": derive_title(p["prompt"]),
            "prompt": p["prompt"],
            "width": p["width"],
            "height": p["height"],
            "thumbnail": f"/static/studio/sensenova-examples/reasoning/{i}_reasoning.png",
            "source": "sensenova-u1-repo",
        })
    return entries


WYLTEK_V1_PROMPT = (
    'The theme of the infographic is "Wyltek Studio", executed in a playful, '
    "modern flat illustration style inspired by children's science books and "
    "editorial Notion cover art. The overall layout is a symmetrical hub-and-"
    "spoke configuration, featuring a central focal point with six equidistant "
    "radiating spokes at 12, 2, 4, 6, 8, and 10 o'clock positions. The "
    "background is a crisp, soft cream paper texture with a subtle, delicate "
    "dotted grid overlay. The title \"Wyltek Studio\" is prominently displayed "
    "in a bold, rounded sans-serif font within the center hub, which contains "
    "a friendly, multi-colored cartoon robot mascot smiling broadly, grasping "
    "a painter's brush in its right mechanical hand and a vintage microphone "
    "in its left. The six radiating spokes are arranged clockwise: At 12 "
    "o'clock, a mint green circular icon contains a smiling picture frame "
    "holding a paintbrush. Above the icon, the text \"Frames\" is written in "
    "a clean, rounded font, with the tagline \"Text to Image\" placed directly "
    "underneath in a smaller, monospaced typeface. At 2 o'clock, a sky blue "
    "circular icon features a cartoon magic eraser actively rubbing away a "
    "blurred section of a photograph. Above it, the text \"Image Edit\" is "
    "displayed, with the tagline \"Remove and Fill\" positioned below. At 4 "
    "o'clock, a sunshine yellow circular icon shows three cartoon dice, each "
    "face displaying a different photographic texture, captured in a mid-air "
    "shuffle. Above the icon is the text \"Remix\", with the tagline \"Image "
    "Variations\" below. At 6 o'clock, a lavender purple circular icon depicts "
    "a pair of sleek headphones surrounded by floating musical notes and "
    "vibrant, rhythmic sound waves. Above the icon is the text \"Music\", "
    "with the tagline \"Text to Music\" beneath it. At 8 o'clock, a coral pink "
    "circular icon features a cartoon dynamic microphone with a large, "
    "expressive speech bubble extending from its mesh head. Above the icon is "
    "the text \"Voice\", with the tagline \"Text to Speech\" situated below. "
    "At 10 o'clock, a peach orange circular icon showcases a floating, "
    "glowing wireframe planet with a tiny, stylized spaceship orbiting its "
    "equator. Above the icon is the text \"WorldGen\", with the tagline "
    "\"Text to 3D\" centered beneath it. All elements utilize thick, "
    "consistent black outlines. Each spoke maintains a specific, harmonious "
    "pastel color palette (mint green, sky blue, sunshine yellow, lavender "
    "purple, coral pink, and peach orange) to delineate categories. Gentle, "
    "soft drop shadows are applied to the hub and spokes to create a sense of "
    "depth against the cream background. The composition is highly balanced, "
    "emphasizing abundant white space to ensure maximum readability and a "
    "professional, approachable visual flow."
)


def build_local() -> list[dict]:
    """Wyltek studio examples — renders produced by this Studio."""
    dest = STATIC_DIR / "local"
    dest.mkdir(parents=True, exist_ok=True)

    src = HERE / "outputs/sensenova/wyltek-v1-50step-2048-20260512-220205.png"
    if not src.exists():
        print(f"  [local] skip — no Wyltek reference image at {src}")
        return []
    target = dest / "wyltek-v1-50step-2048.png"
    shutil.copy2(src, target)
    return [{
        "id": "local-wyltek-v1",
        "category": "local",
        "title": "Wyltek Studio (hub-and-spoke)",
        "prompt": WYLTEK_V1_PROMPT,
        "width": 2048,
        "height": 2048,
        "thumbnail": "/static/studio/sensenova-examples/local/wyltek-v1-50step-2048.png",
        "source": "local",
    }]


CATEGORIES = [
    {"id": "infographic", "label": "Infographics",
     "description": "Dense structured visuals — diagrams, posters, hub-and-spoke layouts. SenseNova-U1's strongest area."},
    {"id": "skills-infographic", "label": "Skills gallery",
     "description": "Long-form prompts ported from OpenSenseNova/SenseNova-Skills. Chinese source prompts, English titles derived; paste into a chatbot to translate or remix before rendering."},
    {"id": "reasoning", "label": "Reasoning",
     "description": "Short prompts that produce stepped, physically- or logically-reasoned visuals."},
    {"id": "local", "label": "Studio examples",
     "description": "Renders produced by this Studio on local hardware."},
]


def write_license_notice() -> None:
    (STATIC_DIR / "LICENSE-NOTICE.md").write_text(
        "# License Notice\n\n"
        "Images under `infographic/` and `reasoning/` and their associated\n"
        "prompts are redistributed from the\n"
        "[sensenova/SenseNova-U1](https://github.com/sensenova/SenseNova-U1)\n"
        "repository, under the Apache License 2.0.\n\n"
        "Source paths in the upstream repo:\n"
        "- `docs/assets/showcases/t2i_infographic/`\n"
        "- `docs/assets/showcases/t2i_reasoning/`\n"
        "- `examples/t2i/data/samples_infographic.jsonl`\n"
        "- `examples/t2i/data/samples_reasoning.jsonl`\n\n"
        "Images under `skills-infographic/` and their associated prompts are\n"
        "redistributed from the\n"
        "[OpenSenseNova/SenseNova-Skills](https://github.com/OpenSenseNova/SenseNova-Skills)\n"
        "repository, under the Apache License 2.0.\n\n"
        "Source paths in the upstream repo:\n"
        "- `docs/images/infographics/`\n"
        "- `docs/sn-infographic-examples.md`\n\n"
        "Images under `local/` are produced by this Studio.\n"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, default=REPO_DEFAULT,
                    help="Path to a local clone of sensenova/SenseNova-U1")
    ap.add_argument("--skills-repo", type=Path, default=SKILLS_REPO_DEFAULT,
                    help="Path to a local clone of OpenSenseNova/SenseNova-Skills")
    args = ap.parse_args()

    if not args.repo.exists():
        raise SystemExit(f"SenseNova-U1 repo not found at {args.repo}")

    STATIC_DIR.mkdir(parents=True, exist_ok=True)

    entries = []
    print("[build] infographic")
    entries.extend(build_infographic(args.repo))
    print(f"  → {len(entries)} entries")
    print("[build] skills-infographic")
    pre = len(entries)
    if args.skills_repo.exists():
        entries.extend(build_skills_examples(args.skills_repo))
        print(f"  → +{len(entries) - pre} entries")
    else:
        print(f"  → skip (no skills repo at {args.skills_repo})")
    print("[build] reasoning")
    pre = len(entries)
    entries.extend(build_reasoning(args.repo))
    print(f"  → +{len(entries) - pre} entries")
    print("[build] local")
    pre = len(entries)
    entries.extend(build_local())
    print(f"  → +{len(entries) - pre} entries")

    write_license_notice()

    corpus = {
        "schema_version": 1,
        "license_notice_url": "/static/studio/sensenova-examples/LICENSE-NOTICE.md",
        "categories": CATEGORIES,
        "entries": entries,
    }
    CORPUS_JSON.write_text(json.dumps(corpus, indent=2, ensure_ascii=False))
    print(f"\n[build] wrote {len(entries)} entries → {CORPUS_JSON}")
    print(f"[build] static assets → {STATIC_DIR}")


if __name__ == "__main__":
    main()
