# Infographic catalog port — `/studio/infographic`

**Date:** 2026-05-16
**Page:** `static/studio/infographic.html`
**Scope:** New backend modules + 3 endpoints + frontend tab UI. No new daemon, no new infra. Adds Ollama dependency for prompt expansion (already running on driveThree).

## Goal

Replace the freeform-textarea prompt composer on `/studio/infographic` with a catalog-driven flow ported from upstream [SenseNova-Skills](https://github.com/OpenSenseNova/SenseNova-Skills) `sn-infographic`. User picks a `data_type` and `tone/context` from two dropdowns; the system samples a layout (of 87) and a style (of 66) using sn-infographic's weighted-random algorithm, runs an Ollama-based prompt-expansion step against the picked layout/style markdown bodies, then renders via the existing SenseNova U1 / HiDream backends.

Preserves the existing freeform flow as a tab for power users.

## Why

`/studio/infographic` today is a freeform textarea — the user composes the entire prompt by hand. sn-infographic ships an opinionated catalog of 87 layouts × 66 styles as curated markdown reference files, plus a `data_type`/`context` → `layout`/`style` rule table with weighted-random sampling. Auditing the upstream skill (`/tmp/SenseNova-Skills`) showed that 90% of the catalog's value is the reference-file content and the selection rules — neither requires SenseNova-hosted infrastructure. Both port cleanly onto open-palette's local U1 + Ollama stack.

## Architecture

```
open-palette/
├─ static/studio/
│  ├─ catalogs/                           ← NEW
│  │  ├─ layouts/                         ← 87 .md (verbatim from upstream)
│  │  ├─ styles/                          ← 66 .md (verbatim from upstream)
│  │  ├─ layout-style-selection.md        ← upstream selection-rules doc
│  │  ├─ prompts-expand-system.md         ← upstream expander system prompt
│  │  └─ index.json                       ← BUILT — data_types, contexts, file index
│  └─ js/
│     ├─ infographic.js                   ← tab dispatcher
│     └─ infographic/
│        ├─ catalog-mode.js               ← NEW Catalog tab
│        └─ freeform-mode.js              ← lifted from current infographic.js
├─ studio/
│  ├─ infographic_catalog.py              ← NEW — load index, sample, read .md
│  └─ infographic_expander.py             ← NEW — Ollama HTTP, system prompt, fallback
├─ scripts/
│  └─ build_infographic_catalog.py        ← NEW — parses upstream MD → index.json
└─ server.py                              ← +3 endpoints
```

## Backend — catalog module

`studio/infographic_catalog.py` is a process-lifetime singleton. Loads `index.json` once at server start. Exposes the deterministic sampler that replicates sn-infographic's weighted pool exactly.

```python
class InfographicCatalog:
    def __init__(self, catalog_dir: Path):
        self.dir = catalog_dir
        self.index = json.loads((catalog_dir / "index.json").read_text())
        self._data_type_map = {dt["key"]: dt for dt in self.index["data_types"]}
        self._context_map   = {ctx["key"]: ctx for ctx in self.index["contexts"]}

    def list_data_types(self) -> list[str]
    def list_contexts(self)   -> list[str]
    def sample(self, data_type, context, *, seed=None) -> tuple[str, str]
    def read_markdown(self, kind, name) -> str   # kind ∈ {'layouts','styles'}
```

Sampling pool composition (per sn-infographic `references/layout-style-selection.md` Step 3):

- Primary candidate × **10**
- Each alternative × **9**
- 3 random outsiders (names outside the data_type/context's candidate set) × **1**
- `random.Random(seed).choice(pool)` → final pick

Unknown `data_type` or `context` → fallback `hub-spoke` / `corporate-memphis` (sn-infographic default).

`read_markdown` validates `name` against `index["all_layouts"]` / `index["all_styles"]` before reading — defends against path traversal.

## Backend — expander module

`studio/infographic_expander.py` builds the expansion request and posts to Ollama via its OpenAI-compatible `/v1/chat/completions` endpoint.

```python
DEFAULT_MODEL = os.environ.get("INFOGRAPHIC_EXPANDER_MODEL", "gpt-oss:20b")
OLLAMA_URL    = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
TIMEOUT_S     = 30.0

def expand(user_prompt: str, layout: str, style: str, *,
           catalog: InfographicCatalog) -> ExpansionResult:
    """Returns ExpansionResult(prompt, fallback_used: bool, elapsed_s, model)."""
```

Request shape:

```python
{
  "model": DEFAULT_MODEL,
  "messages": [
    {"role": "system", "content": <prompts-expand-system.md verbatim>},
    {"role": "user",   "content":
      f"## User prompt\n{user_prompt}\n\n"
      f"## Layout reference: {layout}\n{layout_md_body}\n\n"
      f"## Style reference: {style}\n{style_md_body}\n"
    },
  ],
  "stream": False,
  "options": {"temperature": 0.7, "num_predict": 1024},
}
```

**Fallback path.** If Ollama is unreachable, times out, or returns malformed JSON, `expand()` falls back to a deterministic template:

```python
def _template_fallback(user_prompt, layout_md, style_md) -> str:
    """Parses Structure / Visual Elements / Text Placement from layout.md and
    Color Palette / Visual Elements from style.md via section-header regex,
    concatenates into a ~200-word prompt. Always returns a usable string."""
```

`ExpansionResult.fallback_used` is surfaced in the render response so the UI can show an amber chip "Ollama unavailable — template prompt used". Render proceeds regardless.

## Backend — catalog build script

`scripts/build_infographic_catalog.py` — one-shot CLI. Idempotent.

```bash
python -m scripts.build_infographic_catalog \
    /tmp/SenseNova-Skills/skills/sn-infographic/references \
    static/studio/catalogs/
```

Steps:

1. Copy `layouts/`, `styles/`, `layout-style-selection.md`, `prompts-expand-system.md`, `prompts-critic-system.md` verbatim to `out_dir/`
2. Parse the two markdown tables in `layout-style-selection.md` (21 data_types, 21 contexts)
3. Enumerate `out_dir/layouts/*.md` (87) and `out_dir/styles/*.md` (66)
4. Validate every primary/alternative name in the tables has a corresponding `.md` file — fail loud on cross-ref errors
5. Write `out_dir/index.json`:

```json
{
  "version": "1",
  "built_at": "2026-05-16T02:53:00Z",
  "data_types": [
    {"key": "overview / summary",
     "primary": "bento-grid",
     "alternatives": ["periodic-table", "containerization", ...]},
    ...
  ],
  "contexts": [
    {"key": "Professional / Business",
     "primary": "corporate-memphis",
     "alternatives": ["swiss-style", "minimalism", ...]},
    ...
  ],
  "all_layouts": ["asymmetry", "axial-expansion", ...],
  "all_styles":  ["aged-academia", "art-deco", ...],
  "fallback": {"layout": "hub-spoke", "style": "corporate-memphis"}
}
```

Treat `static/studio/catalogs/` as vendored — committed to the repo as a snapshot. Upstream re-pull = re-run script + commit the diff.

## API contract

Three new endpoints under `/api/infographic/`. Pydantic models match the existing convention in `server.py`.

**Naming note.** The API request field is `tone` (UI-friendly), the catalog index field is `contexts` (preserved verbatim from upstream's `layout-style-selection.md` table). Same concept — `tone` is the user's pick, `contexts` is the list of all valid picks. Keep both names; don't unify.


### `GET /api/infographic/catalog`

Returns dropdown content. Cached at process start.

```json
{
  "version": "1",
  "data_types": ["timeline / history", "process / tutorial", ...],   // 21
  "contexts":   ["Technical / Engineering", "Software / Product / Tech brand", ...],   // 21
  "counts":     {"layouts": 87, "styles": 66}
}
```

### `POST /api/infographic/pick`

Samples a layout + style. Supports partial re-roll via `lock`.

Request:

```json
{
  "data_type": "overview / summary",
  "tone":      "Professional / Business",
  "lock":      null,                                          // null | "layout" | "style"
  "current":   null,                                          // required if lock != null
  "seed":      null
}
```

Response (200):

```json
{
  "layout":    "bento-grid",
  "style":     "corporate-memphis",
  "from_pool": {"layout": "primary", "style": "alternative"}  // primary|alternative|outsider|fallback
}
```

Errors:

- `400 unknown_data_type` / `400 unknown_tone` — body includes valid list
- `400 invalid_lock` — `lock` set but `current` missing or names not in catalog

Latency target: **<100ms p99**.

### `POST /api/infographic/render`

Expands the prompt via Ollama (inline, ~2s), then enqueues the render via the existing JobQueue. Returns the `job_id` the frontend already subscribes to.

Request:

```json
{
  "user_prompt": "Q4 capability matrix for the platform team",
  "data_type":   "overview / summary",
  "tone":        "Professional / Business",
  "layout":      "bento-grid",
  "style":       "corporate-memphis",
  "backend":     "sensenova",
  "steps":       50,
  "aspect_ratio": "9:16"
}
```

Response (202):

```json
{
  "job_id":          "ig_20260516_023014_a1b2",
  "expanded_prompt": "Modular bento-grid infographic with a hero cell...",
  "expansion": {
    "elapsed_s":     2.13,
    "model":         "qwen2.5:32b",
    "fallback_used": false
  }
}
```

Errors:

- `400 unknown_layout` / `400 unknown_style` — name not in catalog
- `400 unknown_data_type` / `400 unknown_tone` — kept for analytics + future feature-gating
- `503 backend_unavailable` — sensenova-worker or comfyui not responding (existing convention)

Expansion runs inline (not queued) — it's ~2s and the synchronous return lets the UI show what was sent to the model. Render proceeds via the existing `/api/sensenova/render` internals — this endpoint is effectively `expand → forward`.

### Why three endpoints, not one

Re-roll is a distinct verb. Merging pick + render means every re-roll triggers an 80s render. Splitting `/pick` from `/render` keeps re-roll at <100ms — the whole point of the two-phase UX.

## Frontend

Two tabs at the top of the page. Catalog default, Freeform preserved verbatim for power users.

```
┌─────────────────────────────────────────────────────────────┐
│  [ Catalog ]   ( Freeform )                                 │
├─────────────────────────────────────────────────────────────┤
│  What's this about?                                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Q4 capability matrix for the platform team          │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  Data type           Tone / Context                         │
│  [ overview ▾ ]      [ Professional / Business ▾ ]          │
│                                                             │
│  Layout: bento-grid              🎲 re-roll                 │
│  Style:  corporate-memphis       🎲 re-roll                 │
│  ▸ Show selection details                                   │
│                                                             │
│  Backend: [ SenseNova U1 ▾ ]   Steps: [ 50 ▾ ]              │
│                                                             │
│  [ Pick layout & style ]   [ Render ]                       │
└─────────────────────────────────────────────────────────────┘
```

### Module split

```
static/studio/js/
├─ infographic.js                 ← entry + tab dispatch (~200 LOC)
└─ infographic/
   ├─ catalog-mode.js             ← NEW catalog tab (~300 LOC)
   └─ freeform-mode.js            ← lifted from current infographic.js (~200 LOC)
```

Vanilla ES modules — matches existing `static/studio/js/` convention. No bundler.

### State machine (catalog mode)

| State | Trigger | UI |
|---|---|---|
| `EMPTY` | page load | Pick & Render disabled; dropdowns enabled |
| `READY_TO_PICK` | both dropdowns chosen | Pick enabled, Render disabled |
| `PICKED` | `/pick` returned | Picks shown, Render enabled, 🎲 enabled |
| `RENDERING` | Render clicked | Pick + Render disabled, progress bar visible |
| `RENDERED` | WS reports done | Image shown, Pick & Render re-enabled |

Single `state` object, explicit transition functions (`goToReadyToPick()`, `goToPicked(layout, style, fromPool)`, etc.). No framework.

### Re-roll

Per-axis 🎲 buttons POST `/pick` with `lock` set to the *other* axis:

```js
async function reRollLayout() {
  const r = await fetch('/api/infographic/pick', {
    method: 'POST',
    body: JSON.stringify({
      data_type: state.dataType, tone: state.tone,
      lock: "style", current: { layout: state.layout, style: state.style },
    }),
  });
  const { layout, from_pool } = await r.json();
  state.layout = layout;
  state.fromPool.layout = from_pool.layout;
  renderPickStrip();   // re-paint just the pick row, not the page
}
```

Optimistic UI: row dims briefly during the <100ms request, no spinner.

### Selection details (collapsible)

When expanded, shows:

- First paragraph of `layouts/<name>.md` — fetched on-demand from `/static/studio/catalogs/layouts/<name>.md`, cached in-memory per page session
- First paragraph of `styles/<name>.md` — same
- From-pool badges: `primary` (green), `alternative` (blue), `outsider` (amber wildcard), `fallback` (red)

### Render flow

```
Render clicked
  ├─ state → RENDERING; disable buttons; reset progress bar
  ├─ POST /api/infographic/render
  ├─ Receives 202 + { job_id, expanded_prompt, expansion }
  │   ├─ UI shows "Expanded via qwen2.5:32b (2.1s)"
  │   └─ UI shows expanded_prompt in a collapsible <details>
  ├─ Subscribe to existing WS channel for job_id
  ├─ Progress on `progress` frames (existing infrastructure)
  └─ On `done`: state → RENDERED, image rendered
```

`fallback_used === true` → amber chip "Ollama unavailable — template prompt used".

### Persistence (localStorage)

```js
infographic.activeTab = "catalog" | "freeform"
infographic.dataType  = "overview / summary"
infographic.tone      = "Professional / Business"
```

Picks themselves are not persisted — every page load starts at `EMPTY`. Dropdowns persist because they're the user's intent.

### Accessibility

- Native `<select>` for dropdowns — keyboard navigation built-in
- `<button aria-label="Re-roll layout">` for 🎲
- Tab strip `role="tablist"` with `aria-selected` on the active tab
- Pick strip `aria-live="polite"` so screen readers announce new picks

## Error handling

| Failure | Surface | UX |
|---|---|---|
| Catalog index missing/corrupt | Startup | `server.py` fails loud: "Catalog index not built — run `python -m scripts.build_infographic_catalog`" |
| Unknown data_type/tone at pick | `POST /pick` 400 | Frontend re-fetches `/api/infographic/catalog`, repopulates dropdowns, inline toast "Selection list was updated — please re-pick" |
| Ollama unavailable / slow | Caught in `expand()` | Template fallback; `fallback_used: true`; UI shows amber chip; render proceeds |
| Render backend down | Existing JobQueue path | Existing `503` flow — worker-status bar handles it |

Not errors:

- `from_pool: "fallback"` — successful sample from the safety net, surfaces as red badge
- `from_pool: "outsider"` — the ~10% wildcard the sampler is supposed to produce, amber badge

## Logging

Three log lines per render (`structlog`, matches existing `server.py` convention):

```python
log.info("infographic_pick",   data_type=..., tone=..., layout=..., style=..., lock=..., from_pool=...)
log.info("infographic_expand", model=..., elapsed_s=..., fallback_used=..., prompt_chars=...)
log.info("infographic_render", job_id=..., backend=..., layout=..., style=..., total_setup_s=...)
```

Query trail via `journalctl --user -u openpalette.service | grep infographic_`.

## Testing

### `tests/studio/test_infographic_catalog.py` (~150 LOC)

```
test_index_loads
test_list_data_types_returns_21_entries
test_list_contexts_returns_21_entries
test_sample_seeded_deterministic
test_sample_pool_weights_primary_10x         # statistical: 10k samples, primary ≥ 35%
test_sample_pool_weights_alternative_9x      # alternatives combined ≥ 50%
test_sample_pool_weights_outsider_10pct      # outsiders ≤ 15%
test_sample_unknown_data_type_returns_fallback_layout
test_sample_unknown_context_returns_fallback_style
test_read_markdown_rejects_path_traversal    # "../../etc/passwd" → FileNotFoundError
test_read_markdown_rejects_unknown_name
```

### `tests/studio/test_infographic_expander.py` (~120 LOC, mocks Ollama)

```
test_build_request_includes_layout_and_style_bodies
test_build_request_uses_env_model
test_expand_returns_ollama_response_on_success
test_expand_falls_back_on_http_error          # httpx.ConnectError → template
test_expand_falls_back_on_timeout             # httpx.TimeoutException → template
test_expand_falls_back_on_bad_response_shape  # missing choices[] → template
test_template_fallback_is_deterministic       # same input → same output
test_template_fallback_includes_layout_structure_section
test_template_fallback_includes_style_palette_section
```

### `tests/api/test_infographic_endpoints.py` (~200 LOC, FastAPI TestClient)

```
test_get_catalog_returns_expected_shape
test_post_pick_happy_path
test_post_pick_lock_layout_preserves_layout    # 10 calls, layout unchanged
test_post_pick_lock_style_preserves_style
test_post_pick_unknown_data_type_returns_400
test_post_pick_invalid_lock_returns_400
test_post_render_expansion_inline_then_enqueues   # mocks JobQueue + expander
test_post_render_unknown_layout_returns_400
test_post_render_propagates_fallback_used
```

Coverage target: **80%+** on the three new modules.

E2E (real Ollama + real sensenova-worker) is manual — see smoke test below.

## Deployment

No infra changes. Two pre-flight checks at startup, both fail-fast:

1. `static/studio/catalogs/index.json` exists and parses
2. Ollama is reachable (`GET /api/tags` → 200) — logs warning if not but doesn't crash (template fallback keeps the system usable)

The Ollama model itself must be installed beforehand — Ollama does not auto-pull on first chat request, it returns 404 `model not found`. Treat a missing model the same as "Ollama unavailable": expander logs a warning, falls back to template, render proceeds with `fallback_used: true`. Default model is `gpt-oss:20b` (already loaded on driveThree at spec time); alternatives that work for this kind of prose expansion: `qwen3:14b` (faster), `gemma4:31b` (higher quality), `mistral-small3.2:24b` (balanced). Add a one-line `README.md` note: `ollama pull gpt-oss:20b` for first-time setup.

## Manual smoke test (post-deploy)

~3 minutes:

1. `GET /api/infographic/catalog` returns 21 data_types + 21 contexts
2. Open `/studio/infographic`, switch to Catalog tab, pick "overview / summary" + "Professional / Business" → click Pick → see `bento-grid + corporate-memphis` (or similar primary pair)
3. 🎲 re-roll layout three times — style stays `corporate-memphis`
4. Click "Show selection details" → see layout + style descriptions populated
5. Render with default settings → image appears in ~80s, expanded_prompt visible in collapsible
6. Switch to Freeform tab → existing flow still works unchanged

## Out of scope

- VLM critic loop (move #2 from the audit) — multi-round generate-critique-retry. Separate spec.
- OpenAI↔Anthropic adapter abstraction (move #3) — env var to route the expander to Claude. Punted; current design hard-codes Ollama and is easy to extend later.
- `sn-image-imitate` layout blueprint — different feature, separate spec.
- Logo-slot detection (`/studio/infographic-fill`) — untouched by this work.
