# SenseNova-U1 Capability Reference

> Source-of-truth reference for building a UI that exposes the **full**
> SenseNova-U1-8B-MoT capability surface (not just a single mode). All facts
> below are extracted from the local repo at `/home/phill/SenseNova-U1` and
> the HuggingFace model card. Prompt examples are quoted **verbatim** from
> the shipped JSONL files with their line indices so the UI's "starter
> templates" are reproducible against the actual reference inference scripts.
>
> Repo paths shown without a leading `/` are relative to
> `/home/phill/SenseNova-U1/`.

## Table of Contents

1. [Glossary & Special Tokens](#glossary--special-tokens)
2. [System Messages (the actual mode selectors)](#system-messages-the-actual-mode-selectors)
3. [Mode catalogue (one-line per mode)](#mode-catalogue)
4. [Cross-cutting: shared sampler & image-input conventions](#cross-cutting-shared-sampler--image-input-conventions)
5. [Mode: Text-to-Image (T2I) — General](#mode-text-to-image-t2i--general)
6. [Mode: Text-to-Image — Reasoning (Think)](#mode-text-to-image--reasoning-think)
7. [Mode: Text-to-Image — Infographic](#mode-text-to-image--infographic)
8. [Mode: Image Editing (it2i) — General](#mode-image-editing-it2i--general)
9. [Mode: Image Editing — Reasoning (Think)](#mode-image-editing--reasoning-think)
10. [Mode: Interleaved Generation — General (Think)](#mode-interleaved-generation--general-think)
11. [Mode: Interleaved Generation — Reasoning (Think + grounded)](#mode-interleaved-generation--reasoning-think--grounded)
12. [Mode: Visual Understanding (VQA)](#mode-visual-understanding-vqa)
13. [Distilled 8-step preview model](#distilled-8-step-preview-model)
14. [Prompt Enhancement workflow](#prompt-enhancement-workflow)
15. [Resolution buckets — full table per task](#resolution-buckets--full-table-per-task)
16. [Recommended sampler knobs (cheat sheet)](#recommended-sampler-knobs-cheat-sheet)
17. [VLA & World Modeling (out of API surface)](#vla--world-modeling-out-of-api-surface)
18. [Known Limitations / Open Questions](#known-limitations--open-questions)

---

## Glossary & Special Tokens

The model is **not** activated by free-text "trigger sentences" the way a chat
model is. The user's hypothesis that opening phrases switch modes is
**incorrect for the local-inference path** — mode selection is done by which
inference entry point you call (`t2i_generate`, `it2i_generate`,
`interleave_gen`, `chat`) plus a system-message and a few real special
tokens. The trigger-sentence pattern only shows up in the LightLLM/LightX2V
serving system message (see "GENERATION_SYSTEM_PROMPT" / "INTERLEAVE_SYSTEM_PROMPT"
quoted below).

| Token / phrase | Where it appears | What it does |
| :--- | :--- | :--- |
| `<image>` | User prompt body for **interleave** and **editing** when multiple inputs are passed | Placeholder for an input image. The interleave script accepts a prompt like `"<image>\n图文交错生成小猫游览故宫的场景"`; if you pass N images and the prompt has no `<image>` tag, the editing path **auto-prepends one per input image**. (`examples/editing/inference.py:248`, `examples/interleave/inference.py:226`) |
| `<think>...</think>` | Decoder output, T2I/edit/interleave think mode | Chain-of-thought block emitted by the model autoregressively before image tokens. T2I think mode returns `(image, think_text)`; the script writes `<output_stem>.think.txt`. (`examples/t2i/inference.py:92-97`) |
| `<image1>`, `<image2>`, … | Decoder output, **interleave think mode only** | Numbered tags the model emits inside `<think>...</think>` to refer to images it has just generated, then re-references in the final answer. **Mandatory inside the think block**, **forbidden outside** — this is enforced by the system prompt. (See `DEFAULT_SYSTEM_MESSAGE` quoted below.) |
| `think_mode=True` argument | Python API kwarg on `t2i_generate` / `it2i_generate` / `interleave_gen` | Boolean toggle that triggers reasoning. Behaves differently per mode: T2I thinks then renders one image; editing thinks then renders one edit; interleave **defaults to True** and may emit multiple intermediate images. |
| `chat_template_kwargs.enable_thinking` | OpenAI-compatible serving payload | Server-side equivalent of `think_mode`. (`examples/serving/client.py:107-109`) |
| `modalities: ["image"]` / `["text", "image"]` | OpenAI-compatible serving payload | Tells the server which output streams to allocate. T2I/it2i use `["image"]`; interleave uses `["text", "image"]`. |

There is **no `--prompt-prefix`-style mode selector** in the local examples.
The repo's mode selection is by *function call*, not by prompt text.

---

## System Messages (the actual mode selectors)

### Local-inference path: the **interleave** script ships one default system message and **the T2I, editing, and VQA scripts ship none**

The full default system message used by `examples/interleave/inference.py:54`
(also used verbatim as `INTERLEAVE_SYSTEM_PROMPT` in `examples/serving/client.py:17-29`):

```
You are a multimodal assistant capable of reasoning with both text and images. You support two modes:

Think Mode: When reasoning is needed, you MUST start with a <think></think> block and place all reasoning inside it. You MUST interleave text with generated images using tags like <image1>, <image2>. Images can ONLY be generated between <think> and </think>, and may be referenced in the final answer.

Non-Think Mode: When no reasoning is needed, directly provide the answer without reasoning. Do not use tags like <image1>, <image2>; present any images naturally alongside the text.

After the think block, always provide a concise, user-facing final answer. The answer may include text, images, or both. Match the user's language in both reasoning and the final answer.
```

This message is **overridable** via `--system_message` (interleave script) or
the `system_message` kwarg of `model.interleave_gen`.

### Serving path adds a second system message for T2I / it2i

`examples/serving/client.py:31-49` defines a separate
`GENERATION_SYSTEM_PROMPT` for the T2I and it2i HTTP endpoints. Verbatim:

```
You are an image generation and editing assistant that accurately understands and executes user intent.

You support two modes:

1. Think Mode:
If the task requires reasoning, you MUST start with a <think></think> block. Put all reasoning inside the block using plain text. DO NOT include any image tags. Keep it reasonable and directly useful for producing the final image.

2. Non-Think Mode:
If no reasoning is needed, directly produce the final image.

Task Types:

A. Text-to-Image Generation:
- Generate a high-quality image based on the user's description.
- Ensure visual clarity, semantic consistency, and completeness.
- DO NOT introduce elements that contradict or override the user's intent.

B. Image Editing:
- Use the provided image(s) as input or reference for modification or transformation.
- The result can be an edited image or a new image based on the reference(s).
- Preserve all unspecified attributes unless explicitly changed.

General Rules:
- For any visible text in the image, follow the language specified for the rendered text in the user's description, not the language of the prompt. If no language is specified, use the user's input language.
```

> **UI implication**: if you build a self-hosted UI on top of the local
> inference scripts, you do NOT need to send a system message for T2I,
> editing, or VQA — the model class handles it internally. If you build on
> top of the LightLLM/LightX2V HTTP server, you SHOULD send these two
> system messages because the official client does, and the model was
> served with them.

### VQA / chat: no system message in the local script

`examples/vqa/inference.py:61-69` calls `self.model.chat(...)` with no
`system_message` parameter; the question is the entire user content. The
serving client mirrors this — `run_vqa` posts only `[{"role": "user",
"content": ...}]` (`examples/serving/client.py:340-356`).

---

## Mode catalogue

8 distinct modes, mapped to 4 inference entry-points and 1 system-message
toggle:

| # | Mode | Entry point | Think? | Inputs | Output |
|---|------|-------------|--------|--------|--------|
| 1 | T2I — General | `t2i_generate` | off | text | 1 image |
| 2 | T2I — Reasoning | `t2i_generate(think_mode=True)` | on | text | 1 image + `.think.txt` |
| 3 | T2I — Infographic | `t2i_generate` | off (typically) | very long text | 1 image (info-dense) |
| 4 | Image Editing — General | `it2i_generate` | off | text + 1..N images | 1 image |
| 5 | Image Editing — Reasoning | `it2i_generate(think_mode=True)` | on | text + 1..N images | 1 image + reasoning |
| 6 | Interleaved — General | `interleave_gen(think_mode=True)` | on (default) | text + 0..N images | text + N images |
| 7 | Interleaved — Reasoning (grounded) | `interleave_gen(think_mode=True)` w/ first-frame image | on | text + 1 grounding image | text + N images |
| 8 | Visual Understanding (VQA) | `chat` | implicit (long-CoT in answer) | 1 image + question | text |

The "OCR / text-in-image" capability the user asked about is **not a
separate mode** — it is exercised by VQA (`chat`) when the question targets
text in the image. There is no dedicated entry-point or system prompt for
OCR; it shares mode #8.

---

## Cross-cutting: shared sampler & image-input conventions

### Common sampler defaults across T2I / it2i / interleave

| Knob | Default | Notes |
|------|---------|-------|
| `cfg_scale` | `4.0` | Text classifier-free guidance |
| `cfg_norm` | `"none"` | T2I also accepts `"global"`, `"channel"`, `"cfg_zero_star"`; **editing rejects `cfg_zero_star`** (`examples/editing/inference.py:336-344`) |
| `timestep_shift` | `3.0` | |
| `cfg_interval` | `[0.0, 1.0]` | LO HI |
| `num_steps` | `50` | Override to `8` for the distilled preview model |
| `seed` | `42` | `DEFAULT_SEED` constant in every script |
| `dtype` | `bfloat16` | bf16/fp16/fp32 selectable via `--dtype` |
| `attn_backend` | `"auto"` | `auto`/`flash`/`sdpa` — auto picks flash-attn if importable, else SDPA |

it2i adds `img_cfg_scale=1.0` (image CFG; 1.0 = disabled).

### Image input conventions

- **Format**: any PIL-loadable file (`.jpg`, `.jpeg`, `.png`, `.webp`).
  RGBA inputs are **flattened onto a white background** before being fed
  to the model (`examples/editing/inference.py:104-112`).
- **Count**:
  - Editing: `--image` is `nargs="+"`, JSONL `image` may be a string OR a
    list (`examples/editing/inference.py:262-265, 116-118`). Multi-input
    is for "subject + accessory + pose" style composition.
  - Interleave: `--image` is repeatable (`action="append"`) and JSONL
    `image` is a list of paths (`examples/interleave/inference.py:292-298, 254`).
  - VQA: exactly one image per question.
- **Pre-resize budget**: editing's `--input_max_pixels` defaults to `auto`,
  which keeps **up to 2 inputs at 2048×2048** and divides that pixel
  budget across more (`examples/editing/inference.py:37-42`). Override
  with an integer (e.g. `1048576` for 1024²) or set `--no-do-resize` to
  skip.
- **What the model literally does with reference images**:
  - Editing: literal pixel-aligned edit target (or composition source).
    Output resolution defaults to track the **first input** via
    `smart_resize` (aspect preserved, normalized to `--target_pixels`
    default `2048*2048`). (`examples/editing/inference.py:141-162`)
  - Interleave: same — first input image dictates output size; this is
    the only signal that the model is "grounding" rather than free-form
    illustrating. (`examples/interleave/inference.py:199-212`)
  - VQA: image is the visual evidence the answer reasons over.

### Output resolution rules

| Mode | Default | Override |
|------|---------|----------|
| T2I | 2048×2048 (1:1) | `--width / --height` per CLI; `width`/`height` per JSONL line |
| Editing | matches first input via `smart_resize` (target = 2048²) | Explicit `--width / --height` (must be multiples of 32) or `--target_pixels` |
| Interleave (no input) | 16:9 → 2048×1152 | `--resolution {bucket}` or `--width / --height` |
| Interleave (with input) | matches first input via `smart_resize` | Cannot override; CLI W/H is treated as no-input fallback |

Off-bucket resolutions are **allowed but warned** by the script and may
degrade quality (`examples/t2i/inference.py:40-47`).

---

## Mode: Text-to-Image (T2I) — General

**Entry point**: `model.t2i_generate(...)` (wrapped by
`examples/t2i/inference.py`).

**Trigger**: pass `--prompt` or `--jsonl` without `--think`. No mode
prefix needed.

**JSONL schema** (`examples/t2i/inference.py:170-175`):

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `prompt` | str | yes | — | Free-form text |
| `width` | int | no | CLI `--width` (2048) | Per-sample override |
| `height` | int | no | CLI `--height` (2048) | Per-sample override |
| `seed` | int | no | CLI `--seed` (42) | Per-sample override |
| `think` | bool | no | CLI `--think` flag | Per-sample think toggle |
| `type` | str | no | — | Tag injected into output filename (`{i:04d}_{type}_{w}x{h}.png`) |

**Resolution buckets supported (T2I)**:

```
1:1   2048 × 2048
16:9  2720 × 1536       9:16   1536 × 2720
3:2   2496 × 1664       2:3    1664 × 2496
4:3   2368 × 1760       3:4    1760 × 2368
2:1   2880 × 1440       1:2    1440 × 2880
3:1   3456 × 1152       1:3    1152 × 3456
```

**Think mode**: supported (`--think` or per-sample `"think": true`).

**Verbatim sample prompts** from `examples/t2i/data/samples.jsonl`:

- L1 (1536×2720): `"Close portrait of an elderly woman by a farmhouse window, textured skin, gentle smile, warm natural light, emotional documentary look. The portrait should feel polished and natural, with sharp eyes, realistic skin texture, accurate facial anatomy, and premium lighting that keeps the face as the main focus."`
- L2 (1536×2720, **CN text rendering**): `"A greeting card on a wooden desk with readable Chinese text \"生日快乐\", flowers beside it, simple celebratory styling. Any text in the image must be rendered exactly as written in quotation marks, with correct spelling, clean typography, and strong readability."`
- L3 (2720×1536, **EN text rendering**): `"A neon bar sign that clearly reads \"OPEN LATE\", dark interior, moody reflections, easy text rendering. Any text in the image must be rendered exactly as written in quotation marks, with correct spelling, clean typography, and strong readability."`
- L4 (2048×2048, portrait realism): `"Tight portrait of a surfer with saltwater droplets on tan skin, sunlit face, windblown hair, natural freckles, vivid blue eyes, coastal realism."`
- L13 (1536×2720, brand text): `"A cafe takeaway cup standing on a clean counter, with the sleeve text rendered clearly as \"SenseNova-U1\", realistic paper texture, morning light, cozy interior blur, and no additional readable menu boards."`

**Recommended pattern visible across L1, L10, L15**: append a
"polish-and-realism" tail sentence to portrait prompts:
> `"The portrait should feel polished and natural, with sharp eyes, realistic skin texture, accurate facial anatomy, and premium lighting that keeps the face as the main focus."`

…and for editorial/artistic compositions:
> `"The final image should feel intentional and refined, with a clear artistic mood, thoughtful composition, nuanced color control, and a gallery-like sense of visual storytelling."`

**Showcase output dir**: `docs/assets/showcases/t2i_general/` (filenames
encode the aspect ratio + style category, e.g. `9_16_dense_face_hd_10.webp`,
`16_9_dense_text_rendering_18.webp`).

**Recommended knobs**: defaults are documented as the production values:
`--cfg_scale 4.0 --cfg_norm none --timestep_shift 3.0 --num_steps 50`
(`examples/README.md` quick-start; `docs/base_vs_distill.md`).

**Known limitations** (`README.md` "Ongoing Improvements"):
- Fine human-body details degrade when people are small in the scene or
  in complex interactions.
- Text rendering may misspell or distort, especially in text-dense scenes
  — recommend prompt enhancement.
- 32K context cap on understanding side (does not directly limit T2I but
  caps how long an enhanced prompt can practically be).

---

## Mode: Text-to-Image — Reasoning (Think)

**Entry point**: same as T2I, with `think_mode=True`.

**Trigger**: pass `--think` (CLI) or `"think": true` in JSONL.

**What it does**: model autoregressively fills `<think>...</think>`,
expanding a short, ambiguous prompt into a structured visual brief, then
denoises the image. The reasoning text is saved to `<output_stem>.think.txt`
(or `--think_output PATH`); `--print_think` echoes it. (`examples/t2i/inference.py:271-291, 367-377`)

**JSONL schema**: same as general T2I.

**Resolution**: same buckets; the shipped reasoning samples all use 2048×2048.

**Verbatim sample prompts** from `examples/t2i/data/samples_reasoning.jsonl`
(all 5 lines, ALL 2048×2048):

- L1 — `"The playful craft that embodies Russian cultural charm"` → reasons "matryoshka" → renders matryoshka set. Output: `docs/assets/showcases/t2i_reasoning/1_reasoning.png`
- L2 — `"A typical dish from the country where Naples is located"` → reasons "Naples → Italy → Neapolitan pizza". Output: `docs/assets/showcases/t2i_reasoning/2_reasoning.png`
- L3 — `"A gigantic bubble in the immediate foreground with a small town barely visible inside"` → reasons about lensing/refraction. Output: `docs/assets/showcases/t2i_reasoning/3_reasoning.png`
- L4 — `"A chocolate bar left in direct sunlight, highlighting the state of the chocolate"` → reasons heat → melt → glossy puddle. Output: `docs/assets/showcases/t2i_reasoning/6_reasoning.png`
- L5 — `"A solution of calcium carbonate reacting with acetic acid"` → reasons CO₂ release → bubbles. Output: `docs/assets/showcases/t2i_reasoning/7_reasoning.png`

**Reasoning template the model converges to** (extracted from
`docs/showcases.md` think transcripts):
1. Instruction Understanding
2. Reasoning Process
3. Establish the frame
4. Build the environment (sometimes elided)
5. Set the lighting and color
6. Lock the style
7. **Explicit Prompt** (one final sentence — this is what actually
   conditions the diffusion stage)

**UI implication**: the "think" output is great content for an "AI
notes" / explainability panel. Always show step 7 prominently — that's
the prompt the model effectively rendered.

**Known limitations**: Think-mode RL has not been specifically trained
for visual editing/reasoning/interleave (`README.md` "Beta status"
callout) — quality is comparable to SFT models, not superior.

---

## Mode: Text-to-Image — Infographic

**Entry point**: same `t2i_generate`. There is **no dedicated argument or
system message** that puts the model in "infographic mode" — it is purely
a prompt style + (optionally) a wider canvas + (recommended)
`--enhance` for short user inputs.

**Trigger**: prompt explicitly *describes* an infographic, with title,
sections, color palette, typography, icons, bilingual text, etc. The
shipped reference prompts are 1500–4000 tokens long. There is no special
trigger sentence; what matters is information density.

**JSONL schema**: identical to general T2I.

**Resolution**: any T2I bucket. The 35 shipped infographic samples
(`examples/t2i/data/samples_infographic.jsonl`) use:
- 2048×2048 (1:1) — most common
- 1536×2720 (9:16) — long vertical
- 2496×1664 (3:2) — landscape
- 2368×1760 (4:3)
- 1760×2368 (3:4)
- 1664×2496 (2:3)

**Think mode**: supported but the shipped samples don't enable it —
infographic prompts are already dense enough that the think pass adds
little.

**Verbatim sample prompts** (selected for diversity; full set has 35
lines in `examples/t2i/data/samples_infographic.jsonl`):

- **L1 — Cyberpunk Win-95-style gaming dashboard, 2048×2048**:
  Opens `"This infographic, titled \"GAMER_INTEL // 游戏动态\", presents a stylized analysis of the mobile gaming landscape through a retro-futuristic, Windows 95-inspired interface…"` then specifies five layered windows, each with title/content/highlighted phrase. Mixed EN/JA/ZH text rendering.
- **L2 — Comic-book superhero compliance poster, 2048×2048, seed=42**:
  Opens `"The infographic, titled \"Foundational Principles for Fund Management Compliance,\" is presented in a vibrant, comic book style with bold colors, dynamic speech bubbles, and action words like \"POW!\", \"BANG!\", and \"ZAP!\"…"` Three horizontal sections, three panels each.
- **L3 — Biomedical+finance metaphor, **CN**, 1536×2720**:
  Opens `"该信息图以"理财产品配置机理：精准增值"为主题，采用生物医学与金融科技融合的视觉隐喻…"` Five-step left-to-right narrative.
- **L8 — French sepia historical pie chart, 2048×2048**:
  Opens `"Create an infographic in a historical archival style with sepia and parchment color tones and distressed edges. It features a title 'SOURCES D'INCENDIES DANS LES CENTRES INDUSTRIELS DU XIXE SIÈCLE' presented on two stacked horizontal banners at the top left."` Includes raw JSON data block for the chart values.
- **L9 — 8-bit arcade learn-to-code grid, 1536×2720**: 9-panel grid teaching programming primitives (CONDITIONALS, LOOPS, FUNCTIONS).
- **L25 — CN cyberpunk 6-chapter office-snack comic, 2368×1760**.
- **L27 — Oil-painting Baroque-frame EV chassis cutaway, 1760×2368**.

**Showcase outputs**: `docs/assets/showcases/t2i_infographic/0000.webp`
… `0033.webp` (35 renders aligned with 35 JSONL lines).

**Prompt structure that the shipped samples consistently follow**:
1. Open with `"This infographic, titled \"…\""` or
   `"The infographic titled \"…\""` (or CN equivalent
   `"该信息图以"…"为主题"`).
2. Declare visual style (e.g. "comic book style", "sepia archival",
   "blueprint", "chalkboard", "Baroque frame", "cyberpunk Win-95").
3. Declare layout (grid, sunburst, tree, triptych, radial, hub-and-spoke).
4. Declare color palette + typography rules.
5. Walk through each region top-to-bottom or left-to-right with **icons +
   labels + body text + highlighted phrases**.
6. Close with a "summary" sentence describing the overall visual logic
   and **the language used** for text rendering ("All textual content is
   in English…" / "所有文本均为简体中文…").

**Recommended for infographic mode**: enable `--enhance` for short user
inputs (see [Prompt Enhancement workflow](#prompt-enhancement-workflow)).
The default style fed into `PromptEnhancer.from_env(style="infographic")`
is hardcoded in `examples/t2i/inference.py:317`.

**Known limitations**: text rendering is most error-prone *here* (see
README "Text-based Generation" caveat). 8-step preview model shows
"grid artifacts" on some infographic shapes (`docs/base_vs_distill.md`).

---

## Mode: Image Editing (it2i) — General

**Entry point**: `model.it2i_generate(...)` via `examples/editing/inference.py`.

**Trigger**: provide `--prompt + --image` (CLI), or each JSONL line must
have `prompt + image`. No mode-selector text in the prompt.

**JSONL schema** (`examples/editing/inference.py:253-258`):

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `prompt` | str | yes | — | Edit instruction |
| `image` | str **or** list[str] | yes | — | Path(s); multi-image = composition |
| `width` | int | no | auto from input | Must be multiple of 32 |
| `height` | int | no | auto from input | Must be multiple of 32 |
| `seed` | int | no | CLI `--seed` (42) | |
| `type` | str | no | — | Filename tag |
| `input_max_pixels` | int \| `"auto"` | no | CLI default (`"auto"`) | Per-input pixel budget |
| `do_resize` | bool | no | CLI default (`True`) | Skip outer resize |

**Resolution**: editing has its own bucket table
(`examples/editing/inference.py:24-36`) — note these are **smaller** than
T2I buckets, because edits are pinned to ~1.5–2.5 MP rather than ~4 MP:

```
1:1   1536 × 1536
16:9  2048 × 1152      9:16   1152 × 2048
3:2   1888 × 1248      2:3    1248 × 1888
4:3   1760 × 1312      3:4    1312 × 1760
2:1   2144 × 1088      1:2    1088 × 2144
3:1   2592 × 864       1:3    864  × 2592
```

The default behaviour, however, is **NOT** to snap to a bucket — it is to
follow the input via `smart_resize` to `--target_pixels=2048*2048`.

**Multi-image behaviour**: pass multiple `--image` paths or a `list` in
JSONL. The model does subject + accessory + pose composition (showcase:
"Replace the man with a woman", "Add a bouquet of flowers", multi-ref
cases in `docs/showcases.md` Image Editing section).

**Verbatim sample prompts** from `examples/editing/data/samples.jsonl` (all 8 lines):

- L1 (`images/1.webp`) — `"Change the jacket of the person on the left to bright yellow."`
- L2 (`images/2.webp`) — `"Make the person in the image smile."`
- L3 (`images/3.webp`, **CN multi-edit**) — `"在小狗头上放一个花环，并且把图片变为吉卜力风格。"`
- L4 (`images/4.webp`) — `"Add a bouquet of flowers."`
- L5 (`images/5.webp`, **style transfer**) — `"Turn the image into an American comic style."`
- L6 (`images/6.webp`, **text replacement**) — `"Replace the text \"WARFIGHTER\" to \"BATTLEFIELD\" in the bold orange-red font."`
- L7 (`images/7.webp`, **object removal**) — `"Remove the person on the far right wearing a green skirt and a green top."`
- L8 (`images/8.webp`, **identity replace**) — `"Replace the man with a woman."`

These 8 lines neatly enumerate the "starter template" categories the UI
should expose for general editing: attribute change, expression edit,
style transfer + add accessory, add element, full-image style, in-image
text edit, object removal, identity replacement. Reference outputs:
`docs/assets/showcases/editing/{1..8}_out.webp`.

**Recommended knobs**: `--cfg_scale 4.0 --img_cfg_scale 1.0 --cfg_norm
none --timestep_shift 3.0 --num_steps 50`. Image-CFG is **off by default**
(scale=1.0); raise it if the edit is drifting too far from the input.

**Pre-resize input recommendation**: the README explicitly says
"Pre-resize inputs to ~2048×2048 resolution with original aspect ratio
before inference for best quality" and ships
`examples/editing/resize_inputs.py` as a helper.

**Known limitations**: distilled 8-step model exhibits **altered colour
tones** on edits (`docs/base_vs_distill.md` "Existing Issues" section).

---

## Mode: Image Editing — Reasoning (Think)

**Entry point**: `it2i_generate(think_mode=True)`.

**Trigger**: pass `--think`. Output adds `<output_stem>_think.txt`
(`examples/editing/inference.py:472-476`).

**What's different**: the model emits a 6-step reasoning block specific
to editing:
1. Source Image Analysis
2. Instruction Understanding
3. Reasoning Process
4. Expected Visual Changes
5. Elements to Preserve
6. **Explicit Edit Prompt** (the actual sentence the diffusion stage uses)

This lets users supply *intentful* but *vague* instructions like "draw
what it will look like one hour later" and have the model derive the
literal pixel-space change.

**JSONL schema**: same as general editing.

**Resolution**: same as general editing (auto from input is the typical path).

**Verbatim sample prompts** from `examples/editing/data/samples_reasoning.jsonl`
(all 7 lines):

- L1 (temporal) — `"Draw what it will look like one hour later."` on `034_temporal_reasoning_draw_what_it_will_look_like.png`
- L2 (causal) — `"Draw what it will look like immediately after someone stands up from sitting on it for a long time."` on `036_causal_reasoning_draw_what_it_will_look_like.png`
- L3 (spatial) — `"Draw an image showing the side view of the provided traffic cone."` on `039_spatial_reasoning_draw_an_image_showing_the_si.png`
- L4 (physics) — `"Change the water to high-concentration saltwater"` on `042_physics_change_the_water_to_high-con.jpg`
- L5 (biology) — `"What the fruit looks like when ripe in the picture"` on `044_biology_what_the_fruit_looks_like_wh.jpg`
- L6 (anomaly correction) — `"Correct the unreasonable part in the image."` on `046_anomaly_correction_correct_the_unreasonable_par.jpg`
- L7 (mathematics) — `"Modify the matrix in the image to an upper triangular matrix"` on `047_mathematics_modify_the_matrix_in_the_ima.jpg`

These 7 lines map cleanly to the **starter-template categories**:
temporal, causal, spatial, physics, biology, anomaly-correction,
mathematics. Reference outputs:
`docs/assets/showcases/editing/{stem}_result.jpeg`.

**UI implication**: showing the full think block under an "AI thinking"
disclosure is more valuable here than for T2I think — these edits would
otherwise look like the model "ignored" the input.

**Known limitations**: same Beta callout — RL has not been specifically
optimized for editing reasoning.

---

## Mode: Interleaved Generation — General (Think)

**Entry point**: `model.interleave_gen(...)` via
`examples/interleave/inference.py`. **`think_mode` defaults to `True`**.

**Trigger**: provide `--prompt` (and optionally one or more `--image` /
`<image>` placeholders). The system message is mandatory and is what
makes this an "interleaved" run rather than a one-shot T2I.

**JSONL schema** (`examples/interleave/inference.py:282-288`):

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `prompt` | str | yes (or `conversations`) | — | May contain `<image>` placeholders |
| `conversations` | list | alt | — | ShareGPT format: `[{"from":"human","value":"…"}]` |
| `image` | list[str] | no | `[]` | Resolved against `--image_root` |
| `images` | list[str] | no | — | Alternate alias for `image` |
| `width` / `height` | int | no | from `--resolution` | Used **only** when no input image |
| `seed` | int | no | CLI `--seed` (42) | |
| `think_mode` | bool | no | CLI `--think_mode` (True) | |

**Resolution buckets (interleave, no input image)**: same table as
editing (`1:1 → 1536×1536`, `16:9 → 2048×1152`, etc., 11 buckets total).
Default = `16:9 → 2048×1152` (`examples/interleave/inference.py:38-39`).

When an input image is given, **output size follows the input** via
`smart_resize` and the `--resolution`/`--width`/`--height` flags are
ignored (`examples/interleave/inference.py:199-212, 468-477`).

**Output files** (per sample):
- `<stem>.txt` — full text response (think + final answer)
- `<stem>_input_<i>.png` — saved copies of input images (one per input)
- `<stem>_image_<i>.png` — generated images (one per `<image1>`, `<image2>`, …)
- `results.jsonl` — manifest in JSONL mode

**Verbatim sample prompts** from `examples/interleave/data/samples.jsonl` (all 6 lines):

- L1 (text only, EN, multi-image promo) — `"Write a promotional copy for a beachfront villa. Interleave images of the villa's exterior, the infinity pool, and the ocean view from the master bedroom."`
- L2 (text only, **CN**, product promo) — `"香氛蜡烛的产品宣传图，多图"`
- L3 (text only, **CN**, illustrated storybook) — `"讲一下经典童话《卖火柴的小女孩》，但这次请给出一个温暖的平行宇宙改编版图文绘本。在最后一次擦亮火柴时，出现的不是幻象，而是一只拥有魔法的驯鹿，它载着小女孩飞向了有糖果和壁炉的城堡"`
- L4 (text + 1 image, mixed travel diary) — `"<image>\nDesign some travel diaries for my chubby orange cat,he strolled through a fragrant flower shop, took a break amidst the ink-black clouds of Huangshan Mountain, and finally gazed at the deep blue of the submarine."` + `examples/interleave/data/images/image1.png`
- L5 (text only, makeup variations) — `"Design three makeup looks suitable for Black women, each appropriate for a different occasion: work, banquet, and date."`
- L6 (text only, dense slide deck content) — long paragraph beginning `"Create a slide outlining our model for integrating beneficiary insights with long-term financial sustainability…"`

These 6 lines map to **6 starter-template categories**: marketing copy
+ multi-image, product promo, illustrated storybook, image-grounded
travel diary, multi-look variants, dense slide / poster.

**Showcase outputs** in `docs/assets/showcases/interleave/`:
- `case_0001_makeup_three_looks.webp` (matches L5)
- `case_0003_beachfront_villa.webp` (matches L1)
- `case_0004_scented_candle_promo.webp` (matches L2)
- `case_0005_matchgirl_warm_au.webp` (matches L3)
- `case_0006_orange_cat_travel.webp` (matches L4)
- `case_0007_bowie_slide_design.webp` (matches L6)

**Recommended sampler knobs**: `--cfg_scale 4.0 --img_cfg_scale 1.0
--timestep_shift 3.0 --num_steps 50` (same as editing). System message
must remain the default unless you know what you're doing — the model
relies on the `<image1>` tag protocol it teaches.

**Known limitations** (called out in README): "**experimental**, may not
yet match dedicated T2I quality"; "Beta — RL has not been specifically
optimized for visual editing, reasoning, and interleaved tasks".

---

## Mode: Interleaved Generation — Reasoning (Think + grounded)

Same entry point as general interleave; this is a **flavour** rather than
a separate API. The shipped samples demonstrate that this is the path for
**multi-step visual reasoning grounded in a starting frame**: pathfinding,
object tracking, ball-eating game logic, color-mixing puzzles.

**Verbatim sample prompts** from `examples/interleave/data/samples_reasoning.jsonl` (all 5 lines, all use `<image>` + a first-frame PNG from the puzzle generator):

- L1 (key-door matching maze) — `"<image>\nThe scene shows a maze with a green circular agent, colored diamond-shaped keys, and colored hollow rectangular doors. Find the Yellow key and then navigate to the matching Yellow door, showing the complete movement process step by step."`
- L2 (object tracking) — `"<image>\nThe pink rectangle marked with a green border is the only object that will move. It will move horizontally to align directly below the blue circle marked with a red star. Track the movement with the green border as the object moves."`
- L3 (ball-eating game) — `"<image>\nIn the scene, there is a black ball and several colored balls of different sizes. The black ball can eat balls that are smaller than itself. After eating a ball, the black ball grows larger. Find the correct sequence to eat all colored balls step by step."`
- L4 (move-to-target) — `"<image>\nIn the scene there are two objects and their corresponding target outlines; each outline matches its object in color and shape. Move each object to its matching outline via shortest path. Show the movement step by step."`
- L5 (subtractive color mixing) — `"<image>\nDemonstrate subtractive color mixing. The image shows two pigment colors. The center region is marked with a white rectangular outline. Predict and show what color appears in the marked mixing zone when these two pigments combine."`

**Pattern**: every prompt **starts with `<image>\n`**, then a precise
description of the puzzle's visual conventions, then the goal, then
"step by step". This is the closest thing in the repo to a "trigger
sentence" pattern and it is real for this sub-mode.

Reference output: `docs/assets/showcases/interleave/reasoning.png` (a
single composite of the 5 samples).

**UI implication**: this is a real, novel capability — exposing it as a
"Visual reasoning" mode with a file-upload widget is justified. Pre-fill
the prompt with `<image>\n` automatically when the user uploads.

---

## Mode: Visual Understanding (VQA)

**Entry point**: `model.chat(...)` via `examples/vqa/inference.py`.
Calls into the standard transformers `chat()` interface.

**Trigger**: provide `--image + --question`, or JSONL with `image +
question + (id?)`. **No system message, no mode prefix.**

**JSONL schema** (`examples/vqa/inference.py:84-87`):

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `image` | str | yes | Path to one image |
| `question` | str | yes | Free text |
| `id` | str | no | Carried into output `answers.jsonl` |

**Resolution**: VQA uses the model's native multimodal preprocessor
(`load_image_native`) — there are **no resolution buckets**; the
model accepts arbitrary image sizes and pages them through its hybrid-mask
attention. Context cap: 32K tokens (README "Visual Understanding"
limitation).

**Sampling defaults** (`examples/vqa/inference.py:38-43, 93-98`):

| Knob | Default | Recommended in README |
|------|---------|------------------------|
| `max_new_tokens` | 1024 | **8192** for long-form |
| `do_sample` | False (greedy) | **True** for nuanced answers |
| `temperature` | 0.7 | **0.6** |
| `top_p` | 0.9 | **0.95** |
| `top_k` | None | **20** |
| `repetition_penalty` | None | **1.05** |

**Verbatim sample prompts** from `examples/vqa/data/samples.jsonl` (all 3 lines):

- L1 (`image1.jpg`) — `"Describe the image content."` (general description)
- L2 (`image2.jpg`) — `"How many dogs are there in this image?"` (counting)
- L3 (`image3.jpg`) — `"Which pill do you choose?"` (knowledge + visual reasoning)

These 3 lines + the README's menu example
(`examples/vqa/data/images/menu.jpg` → "recommend a balanced meal for 2
people, budget-conscious") cover four "starter template" categories:
description, counting, choice/recommendation, OCR-grounded recommendation.

**Multi-turn**: `chat()` returns `(response, history)`; pass the history
back in via the `history=` kwarg for multi-turn (`examples/vqa/inference.py:61-69`).
The shipped batch script does **not** use multi-turn.

**Agentic / OCR variants**: the README and `docs/showcases.md`
distinguish "Visual Understanding (General)" and "Visual Understanding
(Agentic)" galleries. Both go through the same `chat` API — agentic just
means longer-CoT, multi-step reasoning answers. There is **no separate
agentic API**.

**Known limitations**: 32K context cap (README). No streaming in the
local script.

---

## Distilled 8-step preview model

`SenseNova-U1-8B-MoT-8step-preview` is a step-distilled (and CFG-distilled)
sibling that runs ~6× faster but with two known issues:

1. Grid artifacts in some renders.
2. Altered colour tones in image edits.

To use it, switch the sampler to `--cfg_scale 1.0 --num_steps 8`
(`docs/base_vs_distill.md`). Everything else (prompts, JSONL, modes) is
identical. Useful default for the UI as a "fast preview" toggle.

---

## Prompt Enhancement workflow

Configured entirely via env vars (`docs/prompt_enhancement.md`):

| Env var | Default | |
|---|---|---|
| `U1_ENHANCE_BACKEND` | `chat_completions` | or `anthropic` |
| `U1_ENHANCE_ENDPOINT` | Gemini OpenAI-compat URL | |
| `U1_ENHANCE_MODEL` | `gemini-3.1-pro` | |
| `U1_ENHANCE_API_KEY` | _unset_ | required |

Enable with `--enhance`; debug-print original + enhanced with
`--print_enhance`.

The enhancer is `PromptEnhancer.from_env(style="infographic")` —
hardcoded style is "infographic", so the prompt template is tuned for
dense layouts. **Only the T2I script uses it**; editing/interleave/VQA do
not call the enhancer.

Recommended backends per `docs/prompt_enhancement.md` table:
- **Gemini 3.1 Pro** — best overall (default)
- **SenseNova 6.7 Flash-Lite** — best for CN, lower cost (preferred for
  production)
- Claude (Sonnet/Opus) — strong typography
- Kimi 2.5 — good CN, weaker EN-dense
- Gemini 3.1 Flash-Lite (third-party) — fast
- Qwen3.6-Plus (third-party Aliyun gateway)

UI implication: surface as "Auto-improve prompt" toggle on the T2I and
infographic pages; keep it off by default (extra latency + key required).

---

## Resolution buckets — full table per task

| Aspect | T2I | Editing | Interleave |
|---|---|---|---|
| 1:1 | 2048×2048 | 1536×1536 | 1536×1536 |
| 16:9 | 2720×1536 | 2048×1152 | 2048×1152 |
| 9:16 | 1536×2720 | 1152×2048 | 1152×2048 |
| 3:2 | 2496×1664 | 1888×1248 | 1888×1248 |
| 2:3 | 1664×2496 | 1248×1888 | 1248×1888 |
| 4:3 | 2368×1760 | 1760×1312 | 1760×1312 |
| 3:4 | 1760×2368 | 1312×1760 | 1312×1760 |
| 2:1 | 2880×1440 | 2144×1088 | 2144×1088 |
| 1:2 | 1440×2880 | 1088×2144 | 1088×2144 |
| 3:1 | 3456×1152 | 2592×864 | 2592×864 |
| 1:3 | 1152×3456 | 864×2592 | 864×2592 |

Note the **T2I table is ~2× the pixel count of the editing/interleave
tables** for matching aspects. The serving client
(`examples/serving/client.py:51-63`) exposes both 1.5K and 2K size
presets per aspect — that comment is the cleanest summary of "trained
buckets".

**Aspect ratios actually shipped vs trained**: the shipped 35
infographic samples cover 1:1, 9:16, 3:2, 4:3, 3:4, 2:3 (6 of 11
buckets). The 14 general T2I samples cover 1:1, 16:9, 9:16. The 5
T2I-reasoning samples are all 1:1. **No shipped sample uses 1:2, 2:1,
1:3, or 3:1** — those wide/tall buckets exist in the table but the
project gallery does not exercise them, so quality there is somewhat
unverified.

---

## Recommended sampler knobs (cheat sheet)

| Mode | cfg_scale | img_cfg_scale | cfg_norm | timestep_shift | num_steps |
|---|---|---|---|---|---|
| T2I (base) | 4.0 | n/a | none | 3.0 | 50 |
| T2I (8-step preview) | 1.0 | n/a | none | 3.0 | 8 |
| Editing (base) | 4.0 | 1.0 | none | 3.0 | 50 |
| Interleave (base) | 4.0 | 1.0 | n/a (no `cfg_norm`) | 3.0 | 50 |
| VQA | greedy or `--do_sample --temperature 0.6 --top_p 0.95 --top_k 20 --repetition_penalty 1.05` | | | | `max_new_tokens 8192` |

`cfg_norm` choices:
- T2I: `none` (default), `global`, `channel`, `cfg_zero_star`
- Editing: `none` (default), `global`, `channel` — `cfg_zero_star` is **rejected**

---

## VLA & World Modeling (out of API surface)

The README mentions Vision-Language-Action (VLA) and World Modeling (WM)
under "Beyond Multimodality". The repo ships **3 YouTube demo links** in
`docs/assets/showcases/vla/` but **no inference script, no training
code, no prompt format**. There is also no LightLLM/LightX2V serving
mode for VLA. Treat as roadmap, not capability.

---

## Known Limitations / Open Questions

### Limitations explicitly flagged in the docs

1. **32K context cap** on visual understanding (README "Ongoing
   Improvements"). Affects long multi-image VQA and very long enhanced
   prompts.
2. **Small / interacting humans** render with degraded fine-detail
   (README).
3. **Text rendering** can misspell or distort, especially text-dense
   scenes — README explicitly redirects to prompt enhancement.
4. **Interleaved generation is experimental + Beta** — RL not yet
   optimized for editing/reasoning/interleave; current quality is
   comparable to SFT, not better (README).
5. **8-step preview** has grid artifacts and edit-time colour shifts
   (`docs/base_vs_distill.md`).

### Things the docs are silent or ambiguous on

1. **Per-mode max input image count for editing** — the script accepts
   any number, but the input-pixel auto-budget assumes 2 inputs are the
   "common case". No hard cap is documented; one practical cap is GPU
   memory.
2. **Multi-turn for `chat()`** — the `history` machinery exists in the
   wrapper but no shipped sample exercises it; multi-turn behaviour is
   undocumented.
3. **Whether interleave **without** the default system message degrades
   gracefully** — it almost certainly will (the model relies on
   `<image1>` token protocol), but no comparison is shipped.
4. **Whether the T2I infographic prompt enhancer can be reconfigured
   for non-infographic styles** — `style="infographic"` is hardcoded in
   the inference script; `PromptEnhancer.from_env` may accept other
   styles, but no other style strings are documented in the local repo.
5. **Distilled model + edit + think mode** — not benchmarked; the
   `base_vs_distill.md` only compares base/distill on T2I and edit
   (no-think).
6. **VLA prompt format** — entirely undocumented; only video links
   exist.
7. **Whether the 11-bucket trained set is actually fully covered by
   training** — the script *warns* on off-bucket, but doesn't enumerate
   which buckets have the most training data; the gallery suggests 1:1,
   16:9, 9:16, 3:2/2:3, 4:3/3:4 are the "well-trained" ones.
8. **OCR as a first-class capability** — the docs mention OCR appears
   in the VQA "general" gallery but ship no OCR-only sample, no special
   prompt prefix, no benchmark numbers. Practical answer: OCR works via
   plain VQA, expect generic VLM-quality OCR.

### Architectural notes worth surfacing in the UI

- **NEO-Unify** removes both the visual encoder and the VAE (`README.md`
  Key Pillars). Practical UI consequence: there is **no "encoder time"
  vs "decoder time" split** to expose; one model, one forward pass per
  step.
- **17.55B total params** (8.12B understanding + 8.19B generation +
  1.25B shared text I/O), 35.1 GB BF16 footprint
  (`docs/parameter_breakdown.md`). On 24 GB cards (e.g. driveThree's
  7900 XTX) you must use accelerate offload — the local fork already
  patches `device_map="auto" + low_cpu_mem_usage=True` and caps GPU at
  20 GiB for interleave to leave headroom for `lm_head`
  (`examples/interleave/inference.py:141-153`). T2I doesn't hit
  `lm_head`, so it doesn't need the cap.
- **Hybrid-mask attention**: text rows = causal, image rows = full text
  prefix + full image span. Triton + FA3 both implemented; FA3 gives
  2.4–3.2× prefill speedup (`docs/inference_infra.md`). Practical: if
  flash-attn isn't installed, expect 2-3× slower prefill but otherwise
  identical outputs.
- **Production stack**: LightLLM (understanding) + LightX2V (generation),
  disaggregated via pinned shared memory. Single-node H100 TP2+CFG2 ≈
  9 s for 2048², L40S ≈ 25 s, 5090 ≈ 23 s
  (`docs/inference_infra.md`).
