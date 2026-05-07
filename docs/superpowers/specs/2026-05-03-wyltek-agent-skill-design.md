# Wyltek Studio — Agent Skill (future work)

**Status:** parked — pick up after current image-tools / 3D polish wraps.
**Date:** 2026-05-03

## Question

Is Wyltek agent-usable today? Could a Claude Skill expose the full studio
to an autonomous agent?

## Verdict

Yes, already usable in principle. Three reasons:

1. **REST + JSON everywhere.** FastAPI on `:7860`, no DB / IPC / Electron.
2. **80 paths grouped into 25 coherent prefixes** (`/api/generate`,
   `/api/worldgen`, `/api/projects/...`, `/api/beats/...`, etc.).
3. **Uniform async-job pattern**: POST → `{job_id}` → poll `/api/job/{id}`
   until `status:done`. Covers 2D, 3D, music, video, TTS, remix.
   `/openapi.json` already published — an agent can introspect the routes
   without us writing wrapper docs.

## Gaps to close before shipping a polished skill

| Gap | Severity | Fix |
|---|---|---|
| ~25 POST routes use `dict = Body(...)` (untyped) | medium | Replace with Pydantic models — also fixes `/docs` UX |
| No auth — anyone on LAN can drive | medium remote / fine local | Add `X-API-Key` middleware, env-gated, skip when unset |
| 80 routes is a lot for an agent to crawl | low | Skill itself fixes this via curated verbs |

## Proposed skill shape

```
~/.claude/skills/wyltek/
├── SKILL.md                ← when to invoke + 8-10 high-value verbs
├── references/
│   ├── api-map.md          ← curated route table grouped by intent
│   ├── job-lifecycle.md    ← POST→poll→fetch w/ retry/timeout
│   └── storage-paths.md    ← /storage/, projects, gallery, assets
└── scripts/
    ├── wyltek_client.py    ← thin HTTP client + poll helper + auth header
    └── examples/
        ├── img_to_3d.py    ← end-to-end "photo → GLB"
        ├── remix.py
        └── enqueue_job.py
```

### Curated verbs (not all 80)

- `generate-image` → `/api/generate`
- `generate-3d` → `/api/generate` (mode_3d, with TRELLIS/Hy3D selection)
- `remix-image` → `/api/remix`
- `generate-music` / `generate-beats`
- `tts-speak`
- `worldgen` → `/api/worldgen`
- `bg-remove` / `object-remove` / `sam-segment`
- `transcode` / `frame-grab`
- `project-create` / `project-add-asset`
- `gallery-list` / `job-wait`

The skill teaches **patterns**, not routes. OpenAPI stays the source of truth.

## Recommended build order when picked up

1. **Backend chore (~1–2h):** add Pydantic models for the 25 untyped POSTs.
   Improves agent + human `/docs` simultaneously.
2. **Auth (~1h):** `WYLTEK_API_KEY` env + middleware checking `X-API-Key`.
   No-op when unset (preserves localhost dev flow). Required before
   exposing via Tailscale or any public hop.
3. **Skill scaffold (~2h):** `wyltek_client.py` + 3-4 example recipes.
   Validates the API surface end-to-end and surfaces remaining schema gaps.

Step 3 can also start first — the schema gaps will surface naturally as
the agent uses the API. Better to ship a thin skill against the current
surface than block on the Pydantic refactor.

## Out of scope for v1

- Streaming progress over WS (the skill polls `/api/job/{id}` initially)
- Auth scopes / per-key rate limits
- Long-running media uploads chunking (existing endpoints handle <100MB
  in a single multipart POST, sufficient for the agent recipes we have
  in mind)

## Related work to land before this

- **Image-tools Phase 1+** (active) — Mask & Fill / Edit headliner / Recolor
  endpoints will expand the skill's verb list.
- **TRELLIS heartbeat + Q8_0 default** (shipped 2026-05-03) — agent recipes
  for 3D will lean on these for sane defaults and progress visibility.
