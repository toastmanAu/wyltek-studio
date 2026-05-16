# LLM/VLM provider adapter — `studio/llm_provider/`

**Date:** 2026-05-17
**Move:** #3 of the SenseNova-Skills audit (Move #1 catalog port shipped 2026-05-16; Move #2 VLM critic deferred and will consume this adapter).
**Scope:** New `studio/llm_provider/` package + migration of `studio/infographic_expander.py` and `studio/hidream_prompt_agent.py` to use it.

## Goal

Abstract the four LLM/VLM provider wire formats (Ollama native, OpenAI / OpenAI-compat, Anthropic Claude) behind a single async `chat()` function. Two existing consumers — the infographic prompt expander and the SCALIST prompt rewriter — migrate to the adapter. Configuration moves to `config.yaml` with env-var overrides, matching the existing project convention. API keys come from environment variables only and never appear in `config.yaml`.

## Why

`studio/infographic_expander.py` and `studio/hidream_prompt_agent.py` both hard-code Ollama. The original SenseNova-Skills audit identified provider-pluggability as a recurring pattern across upstream skills (`--vlm-type`, `--llm-type` flags with hierarchical auth fallback). Move #1's spec out-of-scope section explicitly punted this: *"OpenAI↔Anthropic adapter abstraction (move #3) — env var to route the expander to Claude. Punted; current design hard-codes Ollama and is easy to extend later."* The deferred Move #2 (VLM critic loop with 9-rule veto JSON) wants vision-capable LLMs and will be its third consumer.

Routing prompt-engineering work to Claude or GPT-5 when those models do a noticeably better job than the local Ollama model — and falling back to Ollama on a quota/auth error or for offline / self-host operation — is the immediate operational value.

## Architecture

```
┌────────────────────────────────────────────────────────────────┐
│ Consumers                                                       │
│                                                                 │
│  infographic_expander.expand()    hidream_prompt_agent          │
│       │                                  │                      │
│       └────────────┐         ┌───────────┘                      │
│                    ▼         ▼                                  │
│        ┌─────────────────────────────────┐                      │
│        │ studio/llm_provider/__init__.py │                      │
│        │  async chat(req: ChatRequest)   │                      │
│        │  → ChatResult                   │                      │
│        │  raises ProviderError           │                      │
│        └────────────┬────────────────────┘                      │
│                     │ dispatch on req.provider                  │
│        ┌────────────┼────────────┬──────────────┐               │
│        ▼            ▼            ▼              ▼               │
│   _ollama.py   _anthropic.py  _openai.py   _openai.py           │
│   /api/chat    /v1/messages   (OpenAI)     (compat)             │
└────────────────────────────────────────────────────────────────┘
                     │
                     ▼
              ┌──────────────┐
              │ _config.py   │  config.yaml + env-var resolution
              │ load_config()│  CONSUMER → ResolvedConsumerConfig
              └──────────────┘
```

The adapter exposes one async `chat()` function, four named providers, and a config loader. Each consumer asks the loader "what config for `infographic_expander`?" and gets back a fully-resolved `ResolvedConsumerConfig`, then passes it into `chat()`.

The four providers reduce to **two wire formats**:

- **OpenAI-compat shape** — used by `openai` and `openai-compat` providers. Same code, different default base_url + env-var-for-key.
- **Anthropic shape** — used by `claude`. Different message-content shape for vision; `max_tokens` is required; `system` is a top-level field.
- **Ollama native** — variant of OpenAI-compat with `images:[]` field on user messages and `extra` knobs (e.g., `think:false`) supported.

## Public API

`studio/llm_provider/__init__.py` exposes:

```python
from dataclasses import dataclass, field
from typing import Literal

ProviderName = Literal["ollama", "claude", "openai", "openai-compat"]
Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class TextBlock:
    text: str


@dataclass(frozen=True)
class ImageBlock:
    """Raw image bytes + MIME type. Adapter handles base64 encoding +
    provider-specific shape (Claude vs. OpenAI vs. Ollama-native)."""
    data: bytes
    media_type: Literal["image/png", "image/jpeg", "image/webp", "image/gif"]


Block = TextBlock | ImageBlock


@dataclass(frozen=True)
class Message:
    role: Role
    content: str | list[Block]


@dataclass(frozen=True)
class ChatRequest:
    provider: ProviderName
    model: str
    messages: list[Message]
    system: str | None = None
    temperature: float = 0.7
    max_tokens: int | None = None
    timeout_s: float = 30.0
    base_url: str | None = None
    api_key: str | None = None
    extra: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ChatResult:
    text: str
    model: str
    provider: ProviderName
    elapsed_s: float
    usage: dict[str, int] | None = None
    raw: dict | None = None


class ProviderError(Exception):
    def __init__(self, provider: ProviderName, *, reason: str,
                 status_code: int | None = None, original: Exception | None = None):
        self.provider = provider
        self.reason = reason
        self.status_code = status_code
        self.original = original
        super().__init__(f"[{provider}] {reason}")


class ProviderUnreachable(ProviderError): ...     # network/DNS/timeout
class ProviderAuthError(ProviderError): ...       # 401/403
class ProviderBadResponse(ProviderError): ...     # malformed JSON, empty content
class ProviderConfigError(ProviderError): ...     # missing key, unknown provider
class VisionNotSupported(ProviderError): ...      # ImageBlock to text-only model


async def chat(req: ChatRequest) -> ChatResult:
    """Dispatch to the configured provider. Raises ProviderError on failure."""
```

**Notes:**

- `extra: dict` is the escape hatch for provider-specific knobs. Documented per provider:
  - **Ollama:** `think: bool` (suppresses thinking on qwen3-style models), `num_predict: int`
  - **OpenAI:** `reasoning_effort: "low" | "medium" | "high"` (for o-series models), `seed: int`
  - **Anthropic:** no provider-specific knobs currently exposed
- `Message.content` accepts a plain `str` for the common text-only case — no forcing callers to wrap in `[TextBlock("hi")]`.
- `system` is lifted out of `messages` because Anthropic puts it in a top-level field while OpenAI/Ollama put it as a system-role message. The adapter handles the translation.
- All result + request types are `frozen=True` dataclasses, matching project immutability convention.

## Data flow per provider

### Ollama (native `/api/chat`)

```
POST {base_url}/api/chat
{
  "model": req.model,
  "messages": [
    {"role": "system", "content": req.system},          # if set
    {"role": "user",   "content": "...text..."},        # plain TextBlock
    {"role": "user",   "content": "...text...",         # mixed Block list
                       "images": ["base64data"]},
  ],
  "stream": false,
  "options": {"temperature": req.temperature, "num_predict": req.max_tokens},
  **req.extra,                                          # → "think": false lands here
}

Response:
{
  "model": "...",
  "message": {"role": "assistant", "content": "<text>"},
  "prompt_eval_count": N, "eval_count": M,              # → usage dict
  "done": true
}
```

**Why native instead of Ollama's OpenAI-compat:** the `think:false` knob (suppresses thinking on qwen3-style models) only exists on the native endpoint. SCALIST relies on this. The infographic expander could equally well use the OpenAI-compat endpoint, but using the same `_ollama.py` for both consumers keeps the code path uniform.

### Claude (`/v1/messages`)

```
POST {base_url}/v1/messages           # default base_url = https://api.anthropic.com
Headers: x-api-key, anthropic-version: 2023-06-01
{
  "model": req.model,
  "max_tokens": req.max_tokens or 1024,         # REQUIRED by Anthropic
  "system": req.system,                         # top-level, not a message
  "messages": [
    {"role": "user", "content": "...text..."},                 # plain
    {"role": "user", "content": [                              # mixed
      {"type": "text", "text": "..."},
      {"type": "image", "source": {
        "type": "base64", "media_type": "image/png", "data": "..."}},
    ]},
  ],
  "temperature": req.temperature,
}

Response:
{
  "id": "...", "model": "...",
  "content": [{"type": "text", "text": "<reply>"}],
  "usage": {"input_tokens": N, "output_tokens": M},
}
```

### OpenAI + OpenAI-compat (`/v1/chat/completions`)

```
POST {base_url}/v1/chat/completions
Headers: Authorization: Bearer {api_key}
{
  "model": req.model,
  "messages": [
    {"role": "system", "content": req.system},
    {"role": "user", "content": "...text..."},                 # plain
    {"role": "user", "content": [                              # mixed
      {"type": "text", "text": "..."},
      {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}},
    ]},
  ],
  "temperature": req.temperature,
  "max_tokens": req.max_tokens,
  "stream": false,
}

Response:
{
  "id": "...", "model": "...",
  "choices": [{"message": {"content": "<reply>"}}],
  "usage": {"prompt_tokens": N, "completion_tokens": M},
}
```

The `openai` and `openai-compat` providers share the same `_openai.py` module — they differ only in:

| Field | `openai` | `openai-compat` |
|---|---|---|
| Default base_url | `https://api.openai.com` | none (required from config) |
| API key env var | `OPENAI_API_KEY` | `OPENAI_COMPAT_API_KEY` |

### Vision-not-supported handling

If `ChatRequest.messages` contains an `ImageBlock` and the configured model can't accept it, the provider raises `VisionNotSupported(provider=..., reason="...")`. The adapter does NOT try to silently downgrade to text-only.

We don't maintain a model→capabilities database. Instead:

- **Ollama:** pass `images:[]` and let the model server reject it if not vision-capable. The provider catches the upstream 400 and re-raises as `VisionNotSupported`.
- **Claude:** all current Claude models are vision-capable; pass through.
- **OpenAI:** pass through; OpenAI rejects with 400 if the model isn't vision-capable. Provider catches and re-raises.

## Config schema

### config.yaml additions

```yaml
# NEW: top-level `llm_providers` block
llm_providers:
  ollama:
    enabled: true
    base_url: http://[::1]:11434
  claude:
    enabled: false
    base_url: https://api.anthropic.com   # optional; default if omitted
    # api_key: NEVER here — read from ANTHROPIC_API_KEY env
  openai:
    enabled: false
    base_url: https://api.openai.com      # optional
    # api_key: read from OPENAI_API_KEY env
  openai-compat:
    enabled: false
    base_url: ''                          # REQUIRED if enabled
    # api_key: read from OPENAI_COMPAT_API_KEY env

# NEW: per-consumer defaults
llm_consumers:
  infographic_expander:
    provider: ollama
    model: gpt-oss:20b
    timeout_s: 30
  scalist_rewriter:
    provider: ollama
    model: gemma4:26b
    timeout_s: 30
    extra:
      think: false                        # Ollama-native knob
```

The existing `prompt_optimizer:` block (used today for SCALIST) stays for one release with a deprecation warning. After Move #3 lands, it's superseded by `llm_consumers.scalist_rewriter`.

### Resolution: `load_consumer_config(name)`

```python
@dataclass(frozen=True)
class ResolvedConsumerConfig:
    provider: ProviderName
    model: str
    base_url: str
    api_key: str | None
    timeout_s: float
    extra: dict


def load_consumer_config(consumer: str) -> ResolvedConsumerConfig:
    """Resolve a consumer's config: config.yaml → env overrides → frozen result.

    Raises ProviderConfigError if any of:
    - the resolved provider is unknown
    - the resolved provider is disabled (`llm_providers.<name>.enabled: false`)
    - the model isn't set
    - a required API key is missing (everything except `ollama`)
    - `base_url` is required but missing (only `openai-compat`)
    """
```

**Resolution order, highest wins:**

1. **Env var** for the field (per consumer):
   - `INFOGRAPHIC_EXPANDER_PROVIDER`, `INFOGRAPHIC_EXPANDER_MODEL`, `INFOGRAPHIC_EXPANDER_TIMEOUT_S`
   - `SCALIST_REWRITER_PROVIDER`, `SCALIST_REWRITER_MODEL`, `SCALIST_REWRITER_TIMEOUT_S`
2. **config.yaml** `llm_consumers.<name>.<field>`
3. **Hard default** (used only if nothing else resolves)

**API key resolution** (separate from the rest):

1. `<CONSUMER>_API_KEY` env var (e.g. `INFOGRAPHIC_EXPANDER_API_KEY`) — lets two consumers use different keys for the same provider
2. Provider's standard env var (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENAI_COMPAT_API_KEY`)
3. Empty for `ollama` (no auth needed locally)

If neither resolves and the provider isn't `ollama`, raises `ProviderConfigError`.

### Existing env-var compat

| Old | Mapped to | Status |
|---|---|---|
| `INFOGRAPHIC_EXPANDER_MODEL` | `INFOGRAPHIC_EXPANDER_MODEL` | unchanged |
| `OLLAMA_BASE_URL` | `llm_providers.ollama.base_url` | unchanged; env wins over config when both set |
| `HIDREAM_PROMPT_MODEL` | `SCALIST_REWRITER_MODEL` | renamed; old accepted with deprecation warning for one release |
| `HIDREAM_OLLAMA_URL` | `OLLAMA_BASE_URL` | merged; old accepted with deprecation warning |

## Consumer migration

### `studio/infographic_expander.py`

**Before**: sync `expand()` using `httpx.Client`, wrapped in `run_in_executor` by the FastAPI handler.

**After**: async `expand()`, no executor wrap needed.

```python
async def expand(user_prompt, layout, style, *, catalog) -> ExpansionResult:
    cfg = load_consumer_config("infographic_expander")
    req = ChatRequest(
        provider=cfg.provider, model=cfg.model,
        system=catalog.expander_system_prompt(),
        messages=[Message(role="user", content=_build_user_message(...))],
        temperature=0.7, timeout_s=cfg.timeout_s,
        base_url=cfg.base_url, api_key=cfg.api_key, extra=cfg.extra,
    )
    start = time.monotonic()
    try:
        result = await chat(req)
        return ExpansionResult(prompt=result.text, fallback_used=False,
                                elapsed_s=result.elapsed_s, model=result.model)
    except ProviderError as exc:
        log.warning("expand fallback reason=%r", exc)
        return ExpansionResult(prompt=template_fallback(...), fallback_used=True,
                                elapsed_s=time.monotonic()-start, model=cfg.model)
```

**FastAPI handler change** (`server.py:infographic_render`): drop the `loop.run_in_executor(...)` wrap and just `await expand(...)`. The handler is already `async def`.

**Removed kwargs:** `model=`, `ollama_url=`, `timeout_s=` — now config-driven. Backward compat: the old kwargs are accepted with a deprecation warning for one release.

**Test migration:** existing tests patch `_build_client` with `httpx.MockTransport`. Migrated tests patch `studio.llm_provider.chat` directly. Same coverage target (97%).

### `studio/hidream_prompt_agent.py`

Same pattern. The 30-line LLM call body shrinks to a `ChatRequest` construction + `await chat(req)`. JSON-extraction and bbox-sanitisation downstream are untouched. When `cfg.provider != "ollama"`, the `think:false` extra is silently dropped (other providers don't have it) — documented behaviour, not an error.

This module previously had no tests; the migration adds a new `tests/test_hidream_prompt_agent.py` (~80 LOC) covering the migrated call path.

## Error handling

Five typed errors, all inheriting from `ProviderError`:

| Error | Trigger | Caller usually does |
|---|---|---|
| `ProviderUnreachable` | network/DNS/timeout | retry or fall back |
| `ProviderAuthError` | 401/403 | surface to operator; don't retry |
| `ProviderBadResponse` | non-2xx, malformed JSON, empty content | retry or fall back |
| `ProviderConfigError` | missing key, unknown provider, disabled | surface at startup; don't retry |
| `VisionNotSupported` | `ImageBlock` to text-only model | choose a different model or strip images |

Per provider, the exchange is wrapped:

```python
try:
    async with httpx.AsyncClient(timeout=req.timeout_s) as client:
        r = await client.post(url, json=body, headers=headers)
    if r.status_code in (401, 403):
        raise ProviderAuthError(provider, reason=f"HTTP {r.status_code}: {r.text[:200]}")
    if r.status_code == 400 and _is_vision_complaint(r):
        raise VisionNotSupported(provider, reason="model rejected image input")
    if r.status_code >= 400:
        raise ProviderBadResponse(provider, reason=f"HTTP {r.status_code}: {r.text[:200]}",
                                   status_code=r.status_code)
    return _parse_response(r.json())
except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
    raise ProviderUnreachable(provider, reason=str(exc), original=exc) from exc
except (KeyError, IndexError, ValueError) as exc:
    raise ProviderBadResponse(provider, reason=f"malformed response: {exc!r}", original=exc) from exc
```

Callers handle these the way they want. The expander catches `ProviderError` (the base class) and falls back to its template; SCALIST surfaces the error to its caller; Move #2's VLM critic might retry on `ProviderUnreachable` but propagate on `VisionNotSupported`.

## Testing

### Provider unit tests (4 files, ~120 LOC each)

`tests/test_llm_provider_<name>.py` for `ollama`, `anthropic`, `openai` (covers both `openai` and `openai-compat`).

```
test_text_only_request_shape          # request body field-by-field match
test_vision_request_shape             # ImageBlock → provider-specific image shape
test_system_message_placement         # ollama/openai: in messages; anthropic: top-level
test_extra_kwargs_passthrough         # extra={"think": False} hits the wire
test_connect_error_raises_unreachable
test_timeout_raises_unreachable
test_400_raises_bad_response
test_401_raises_auth_error
test_malformed_json_raises_bad_response
test_empty_content_raises_bad_response
test_response_usage_parsed            # usage dict normalised across providers
test_400_vision_complaint_raises_vision_not_supported
```

All HTTP mocked via `httpx.MockTransport`. Fast, offline.

### Config tests (~150 LOC)

`tests/test_llm_provider_config.py`:

```
test_yaml_only
test_env_overrides_yaml
test_consumer_specific_api_key_wins   # INFOGRAPHIC_EXPANDER_API_KEY > OPENAI_API_KEY
test_disabled_provider_raises_config_error
test_missing_api_key_for_remote_provider_raises
test_ollama_with_no_api_key_is_fine
test_legacy_env_vars_honoured         # OLLAMA_BASE_URL, INFOGRAPHIC_EXPANDER_MODEL
test_deprecated_hidream_prompt_model_warns_and_works
test_unknown_consumer_raises
test_unknown_provider_raises
```

### Consumer integration tests

- `tests/test_infographic_expander.py` — updated to patch `studio.llm_provider.chat` instead of `_build_client`. Coverage stays at ~97%.
- `tests/test_hidream_prompt_agent.py` — new file (~80 LOC). Mocks `chat`, asserts `_wrap_result` consumes the result correctly.

### Manual E2E smoke

CLI runner script `scripts/llm-provider-smoke.py`:

- One text-only invocation per provider (4 calls)
- One vision invocation per provider that supports it (3 calls — Ollama vision-model, Claude, OpenAI gpt-4o)
- Skipped in CI; run locally when API keys are available

Coverage target: **85%+** on `studio/llm_provider/*` (higher than 80% — this is infrastructure many things will lean on).

## Files & rough sizing

```
studio/llm_provider/
├─ __init__.py          ~180 LOC  (types, chat() dispatcher, registry, exceptions)
├─ _ollama.py            ~120 LOC
├─ _anthropic.py         ~140 LOC
├─ _openai.py            ~130 LOC  (used by both "openai" and "openai-compat")
└─ _config.py            ~150 LOC
                        ─────────
                        ~720 LOC

tests/
├─ test_llm_provider_ollama.py          ~120 LOC
├─ test_llm_provider_anthropic.py       ~120 LOC
├─ test_llm_provider_openai.py          ~130 LOC  (covers both providers)
├─ test_llm_provider_config.py          ~150 LOC
└─ test_hidream_prompt_agent.py         ~80 LOC   (new; existing module had none)
                                       ─────────
                                       ~600 LOC

scripts/
└─ llm-provider-smoke.py                ~80 LOC

Modified:
├─ studio/infographic_expander.py       -30 LOC  (less wire code)
├─ studio/hidream_prompt_agent.py       -30 LOC  (less wire code)
├─ tests/test_infographic_expander.py   ~unchanged LOC, different mocking surface
├─ server.py                            -3 LOC   (drop run_in_executor wrap)
├─ config.yaml                          +25 LOC  (new blocks)
└─ config.example.yaml                  +25 LOC
```

## Deployment

No infra changes. Two pre-flight checks at startup:

1. Each enabled provider's required API key resolves from env, or the startup logs a loud warning and the provider is implicitly disabled.
2. Each consumer's resolved config validates — if `provider=claude` but `ANTHROPIC_API_KEY` is unset, `load_consumer_config("infographic_expander")` raises `ProviderConfigError` at first use.

A new operator wanting to route the expander to Claude does:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export INFOGRAPHIC_EXPANDER_PROVIDER=claude
export INFOGRAPHIC_EXPANDER_MODEL=claude-opus-4-5
systemctl --user restart open-palette.service
```

No config-file edit required. The defaults stay Ollama for offline/self-host use.

## Out of scope (explicit)

- **Streaming responses** — current consumers all use `stream:false`. Adapter API leaves room (could be added as `chat_stream()` later) but isn't built now.
- **Tool/function calling** — none of the current consumers need it. Adding it is a self-contained extension.
- **Multi-turn conversation memory** — adapter is stateless, single round-trip per call.
- **Provider chain fallback** (try claude → ollama → template) — caller's responsibility. Each consumer composes its own fallback.
- **Image-gen providers** — `backends/openai_dalle.py` etc. are a different abstraction (image-in/image-out vs. text-in/text-out). Stay as they are.
- **Local VLM workers** (`studio/minicpm_worker.py`) — these are HTTP servers hosting local models, not provider clients. Not adapter consumers.
- **Cost/usage accounting** — the adapter returns `usage` when the provider supplies it, but doesn't aggregate, persist, or rate-limit. Add later as a separate layer.

## Related security cleanup (out of scope but recommended)

The current `config.yaml` has hardcoded API keys in two backend blocks (`gemini.api_key`, `huggingface.api_key`). These predate this work and aren't introduced by Move #3. The same env-var-only pattern this spec establishes should be applied to those backends as a follow-on cleanup, and the exposed keys rotated.

## Future moves enabled by this spec

- **Move #2 — VLM critic loop** (deferred from the SenseNova audit). With this adapter, the critic's nine-rule veto JSON evaluation reduces to:
  ```python
  cfg = load_consumer_config("vlm_critic")
  result = await chat(ChatRequest(
      provider=cfg.provider, model=cfg.model, system=CRITIC_SYSTEM,
      messages=[Message(role="user", content=[
          TextBlock(text=critique_prompt),
          ImageBlock(data=png_bytes, media_type="image/png"),
      ])],
  ))
  ```
- **Adding a new provider** (e.g., Gemini, Mistral hosted) — one new `_gemini.py` + one registry entry + one config-schema entry. ~140 LOC.
- **A/B prompt-engineering experiments** — env-var override lets a single render be routed to a different provider without redeploy.
