# Factroll Plan — Web App (Follow-up Surface)

Follow-up to [`PLAN.md`](./PLAN.md) (MCP-first). Do **not** start until
MCP milestones 0–3 are complete and the core service layer is stable.

This is a second surface over the same engine, not a rewrite. The
retired pre-MCP web app plan lives in
[`archive/ARCHITECTURE_ASSESSMENT.md`](./archive/ARCHITECTURE_ASSESSMENT.md)
for reference.

---

## Goal

A standalone web app for users who don't have an MCP-capable agent, or
who prefer a focused single-purpose UI. Same Factroll mechanics, with
a chat-style UI on our side, powered by a user-supplied LLM API key
(BYOK).

## Relationship to the MCP server

```
┌─────────────────────────┐    ┌──────────────────────────┐
│  MCP server (PLAN.md)   │    │  Web app (this plan)     │
│   OAuth + transport +    │    │   chat UI + agent loop   │
│   thin protocol adapter │    │   + BYOK key vault       │
└────────────┬────────────┘    └─────────────┬────────────┘
             │                               │
             ▼                               ▼
        ┌────────────────────────────────────────┐
        │  factroll/core/  (shared engine)       │
        │  + Postgres                            │
        └────────────────────────────────────────┘
```

The web app **does not speak MCP** to its own backend. Both surfaces
call `factroll/core/` as plain in-process functions. The MCP server is
not on the critical path for the web app — no extra hop, no second
auth flow to itself.

Schemas for actions are defined once (e.g. JSON Schema or Pydantic /
TS types) and consumed by both adapters:

```
schemas/<action>.{py|ts}
   ├─> MCP tool definition (in MCP adapter)
   └─> Native LLM tool definition (in web BFF agent loop)
```

A CI test ensures the two adapters never drift.

## Why a separate surface (not a wider MCP)

- Non-developer users won't install and configure an MCP client.
- We control the UX, can run product experiments, can ship push
  notifications and onboarding flows.
- Multi-provider support (Anthropic, OpenAI, Gemini) is easier when we
  own the agent loop.

## What's shared with MCP

- All core service operations.
- Schemas (single source of truth for action signatures).
- Postgres + persistence layer.
- The same OAuth provider for user identity (web app uses session
  cookies on top of it).

## What's web-app-specific

- **No MCP protocol** anywhere on this surface.
- **BYO API key**: user pastes an LLM API key into settings; encrypted
  at rest with a KMS-backed key.
- **Server-side agent loop**: the BFF runs the loop, calling the user's
  chosen LLM with the action tool schemas exposed.
- **Streaming UI**: SSE/WebSocket from BFF to the browser.
- **Chat-style affordances**: button row of next actions, modal for
  free-text questions, EL slider, session summary, score dashboards.

## Layered architecture (web side)

- **Frontend (PWA)**: chat UI, topic picker, settings.
- **BFF**: cookie auth, key vault, agent loop, provider abstraction.
- **Core**: shared with MCP server.
- **DB**: shared with MCP server.

## API key strategy

- v1: server-side, encrypted at rest with a KMS-backed key. Masked
  display, last-4 only. Validated on save with a 1-token test call.
  Per-user per-session rate limit on top of the provider's own.
- Client-side keys (browser-only, never leave the user's machine) are
  in the backlog — they add CORS complexity and limit provider choice.

## Provider abstraction

- v1: Anthropic only.
- v2: OpenAI.
- v3: Gemini, only on real demand.

An internal adapter normalizes tool-call shapes across providers. The
schemas package is provider-agnostic; the adapter compiles them to each
provider's tool format.

## Agent loop

1. User message arrives over WS/SSE.
2. BFF assembles tool schemas + recent transcript.
3. Calls the user's chosen provider with the user's key.
4. If the response contains tool calls → dispatch each to core, append
   results, loop.
5. Stream tokens back to the browser.
6. Persist transcript.

Bounded at **max 5 tool rounds per user turn** to prevent runaways.

## Roadmap

### Milestone W1 — Static UI + read-only core integration
- Topic picker, profile view, no chat yet.
- Read from core via REST endpoints.
- Auth via the same OAuth provider, cookie session.

### Milestone W2 — BYO key + agent loop (Anthropic)
- Key vault (encrypted at rest, masked display, validate-on-save).
- Agent loop with Anthropic SDK + schemas.
- Single-topic walkthrough: start → next_fact → switch.

### Milestone W3 — Full action surface in UI
- Buttons mirror MCP action set.
- Free-text question modal (does not derail main flow).
- EL adjustment control.

### Milestone W4 — Quiz mechanic in UI
- Quiz launch button.
- Per-question UI with locked-answer reveal at scoring.
- Score display + per-fact accuracy view.

### Milestone W5 — Polish & launch
- Session history, summary, accuracy dashboards.
- Anonymous demo flow (limited free tier on our key — see open
  questions).
- Mobile PWA install flow.

## Backlog (web-app)

- Multi-provider (OpenAI, Gemini).
- Client-side keys (CORS proxying or native fetch where available).
- Native mobile wrapper (Capacitor) — only if PWA proves insufficient.
- Visual facts.
- Spaced repetition scheduling.
- Exam proximity mode.
- Push notifications.

---

## Open questions (web-app-specific)

General open questions from [`PLAN.md`](./PLAN.md) still apply.

1. **Frontend framework**: keep the existing React JSX scaffold
   (`backlog_20260415.jsx`) as a starting point, or rebuild on
   Next.js / Remix / SvelteKit?
2. **Anonymous demo**: do we offer any pre-BYOK trial on our LLM key
   (strict rate limit), or is "paste your key first" the only path?
3. **Cost visibility**: how prominently do we surface per-session token
   spend? Live counter, post-session only, or settings-page-only?
4. **Mobile**: PWA from day one, or web-first then PWA?
5. **Session continuity with MCP**: if a user uses both MCP and the web
   app, do we present a single unified history, or keep
   per-surface session histories (matching the MCP plan's per-surface
   session scoping)?
