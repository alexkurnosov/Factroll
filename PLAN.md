# Factroll Plan — MCP-First

Primary implementation roadmap. The web app is a follow-up surface; see
[`PLAN_WEB_APP.md`](./PLAN_WEB_APP.md).

The previous "web app with BYOK" plan has been retired and moved to
[`archive/ARCHITECTURE_ASSESSMENT.md`](./archive/ARCHITECTURE_ASSESSMENT.md).

---

## Goal

Ship Factroll as a remote **MCP server**. Users connect their own agent
(Claude Desktop, Claude Code, Cursor, …), authenticate via OAuth, and run
fact-rolling sessions using their own LLM subscription. Factroll provides
the engine — session state, EL math, category rolls, quiz logic, fact
corpus — and the agent provides the conversational surface and the
inference.

## Why MCP first

- **Self-validation.** The first user (Aleksei) can run it end-to-end in
  his own agent without us building a UI.
- **No LLM cost or ToS risk on our side.** The agent is the user's; we
  never relay model calls.
- **Provider-agnostic.** Any MCP-capable agent works.
- **The engine is the moat.** Building the core service first means the
  later web app is a thin shell over the same code.

## Architecture overview

```
┌──────────────────────────────────────────────────────────────┐
│  MCP server (this plan)                                       │
│   - Remote HTTP/SSE transport                                 │
│   - OAuth 2.1 (PKCE)                                          │
│   - 1 bootstrap tool + a few prompts + a few resources        │
└────────────────────────────┬─────────────────────────────────┘
                             │ (in-process function calls)
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  factroll/core/  (pure domain, protocol-agnostic)             │
│   start_session, next_fact, switch_topic, set_el,             │
│   submit_question, start_quiz, submit_quiz_answer, …          │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│  Postgres                                                     │
│   users, profiles, topics, facts, sessions, quiz_attempts, …  │
└──────────────────────────────────────────────────────────────┘
```

Layering rules:
- The **core** has no awareness of MCP, HTTP, or auth. It takes a
  `user_id` and returns plain data.
- The **MCP adapter** is the thinnest possible wrapper: parse tool args,
  call core, format response.
- The **web app** (later) will be a second adapter on the same core.
  Nothing in core may depend on either surface.

## Context-budget design (Option A: single bootstrap tool)

The MCP "always-on tax" — tokens spent in every conversation turn just
because the server is connected — is kept tight by exposing only one
tool plus a tiny prompt/resource catalog.

Target always-on cost: **~130 tokens.**

- **1 tool**: `factroll(action, params?)`
  Description (~25 words): "Factroll: guided fact-rolling sessions. Call
  with `action='start'` and `{topic}` to begin. Subsequent valid actions
  are returned in each response."
- **2–3 prompts** (catalog listing only; bodies fetched on invoke):
  `/factroll <topic>`, `/factroll-resume`, `/factroll-status`.
- **2–3 resources** (catalog listing only; contents fetched on read):
  `factroll://profile/me`, `factroll://topics`,
  `factroll://session/current`.

The action vocabulary (`next_fact`, `switch_topic`, …) is **not** in the
system prompt. It lives in conversation context only for the active
session, injected via the tool's response payload (`next_actions` field
below). When the session ends, the vocabulary scrolls out of context
naturally.

**Option B** (dynamic tool list via `notifications/tools/list_changed`)
is documented in the backlog. Not implemented in v1; revisit once major
clients reliably refresh on the notification and we have appetite for
the added complexity.

## The single tool

```
factroll(action: string, params?: object) -> ToolResult
```

Standard response shape (returned as the tool's text/structured content):

```jsonc
{
  "say": "<text the agent should present to the user>",
  "next_actions": ["next_fact", "switch_topic", "set_experience_level", "start_quiz"],
  "state": { /* compact session state hint, optional */ }
}
```

Conventions:
- The agent reads `say` and shows it to the user.
- `next_actions` teaches the agent which `action` strings are valid
  *right now*. The set is small and changes per state (e.g. mid-quiz it
  shrinks to `submit_quiz_answer` and `end_quiz`).
- `state` is optional and intentionally minimal (current topic, EL,
  fact count). Anything bigger goes behind a Resource.

Action enum (server-internal; communicated via responses, not advertised
in system prompt):

- `start` — initialize a session (`params: {topic}`)
- `next_fact`
- `switch_topic` (`params: {topic}`)
- `set_experience_level` (`params: {topic, level}`)
- `ask_question` (`params: {question}`) — see "Free-text Q&A" below
- `start_quiz`
- `submit_quiz_answer` (`params: {answer}`)
- `end_session`

## Prompts (entry points)

User-invokable slash-commands that expand into a starter message:

- `/factroll <topic>` — start a new session on a topic
- `/factroll-resume` — resume the most recent session
- `/factroll-status` — show EL across topics

Each is ~30 tokens in the listing; bodies fetched only on invoke.

## Resources

Read-on-demand state surfaces:

- `factroll://profile/me` — user profile, interests, EL per topic
- `factroll://topics` — topic catalog (favorites + suggestions)
- `factroll://session/current` — live session state

## Core service operations

Maps directly to the existing Factroll mechanics in
`PROJECT_INSTRUCTIONS.md`. All deterministic logic — EL math, category
rolls (`ABChance = (1 - EL) × 0.95`), repetition probability, quiz
pre-commitment — runs **server-side** so it can't be silently bent by an
LLM.

- `start_session(user_id, topic) -> Session`
- `next_fact(user_id) -> Fact` (runs the roll, picks a category, returns
  a fact from corpus matching topic + category + EL)
- `switch_topic(user_id, new_topic) -> Session`
- `set_experience_level(user_id, topic, level) -> Profile`
- `submit_user_question(user_id, question) -> AgentInstruction`
  (see "Free-text Q&A" below)
- `start_quiz(user_id) -> QuizQuestion` (locks the answer in DB before
  returning)
- `submit_quiz_answer(user_id, answer) -> QuizVerdict`
- `end_session(user_id) -> SessionSummary`

## Free-text Q&A

Open question (see end of doc), but the v1 plan:

When the user asks a free-text question, the tool returns an
**instruction to the agent**, e.g.:

```
{
  "say": "(answer the user's question using the current fact and recent context, then offer 'next_fact' or 'switch_topic')",
  "next_actions": ["next_fact", "switch_topic"]
}
```

The agent uses its own LLM to answer. The Factroll server stores the
question for analytics and future fact-corpus enrichment but does not
itself call an LLM in v1.

## Fact source strategy

- **v1**: pre-curated corpus seeded from Aleksei's existing CCA prep
  sessions. Exported from past Claude conversation logs via an extraction
  pipeline (parser → LLM structuring step → review CLI), loaded with
  `reviewed = false`, promoted to live after admin approval.
- **v1.5**: when the corpus is sparse for a topic, the tool returns a
  *generation instruction* to the agent ("Generate one [B]-category fact
  about $topic at EL $el, in this format: …"). The agent generates with
  its own credits; the response is stored immediately (see "User-generated
  content" below); if the user has opted in to contributing, the fact
  enters the review queue; once approved it joins the shared corpus.
- **Backlog**: server-side fact generation using our own LLM key for
  bulk seeding. Out of scope for v1 because of cost and ToS surface.

This sidesteps the "agent is the LLM" tension cleanly: mechanics stay
deterministic on the server, creative generation falls back to the
user's agent.

### User-generated content

All facts and quiz questions generated during a session are **stored
unconditionally** for service operation, analytics, and corpus seeding.
They are **never surfaced to other users** unless the generating user has
opted in via the `contribute_to_corpus` profile flag.

- `contribute_to_corpus = false` (default): content is stored, used only
  for that user's own sessions and internal analytics.
- `contribute_to_corpus = true`: content enters the review queue
  (`reviewed = false`); admin approval is required before it joins the
  shared corpus.

Attribution: `contributed_by_user_id` is stored internally (for
accountability and de-duplication) but is never exposed to other users.
Contribution counts may be shown on the contributor's own profile.

Corpus entries are labeled `source = 'community'` or `source =
'official'` so provenance is always clear.

Privacy posture: the Privacy Policy must disclose that generated content
is stored. Users may request deletion of their generated content (GDPR
right to erasure); deletion removes the content from the shared corpus
and from their own session history.

## Persistence

- **Postgres** as the system of record.
- Initial tables:
  - `users` — id, email, oauth_subject, created_at
  - `profiles` — user_id, topic, el, last_seen, contribute_to_corpus (bool, default false), …
  - `topics` — id, name, default_el, public/private
  - `facts` — id, topic_id, category (A/B/C/D), content, why_it_matters,
    reviewed, accuracy_score, source ('official'|'community'),
    contributed_by_user_id (nullable)
  - `sessions` — id, user_id, surface_id, topic_id, started_at,
    ended_at, status
  - `fact_events` — session_id, fact_id, shown_at, was_repeat
  - `quiz_attempts` — session_id, fact_id, locked_answer, user_answer,
    verdict, created_at

Migration tool: see open questions.

## Auth

- **OAuth 2.1 with PKCE.** Required for remote MCP.
- v1: lean on a hosted provider (Auth0 / Clerk / Supabase — open
  question) to avoid building a provider ourselves.
- Scopes start coarse: `factroll.read`, `factroll.write`. Refine later.
- The MCP adapter validates the token, resolves `user_id`, passes
  `user_id` into core. Auth concepts stop at the adapter boundary.

## Multi-conversation handling

Same user, two agents at once (e.g. Claude Desktop + Claude Code) is a
real case. v1 approach:

- Sessions are keyed `(user_id, surface_id)` where `surface_id` derives
  from the MCP connection identity.
- Profile (topics, EL per topic, history) is **shared** across surfaces.
- Active session is **per surface**. Two surfaces can be mid-session on
  different topics without colliding.
- Quiz lock is bound to a specific session, so cross-surface contention
  is impossible by construction.

## Stack

Open question on language (Python vs TypeScript); both have official
MCP SDKs. Decision drivers: deployment story, type system preference,
ecosystem fit for Postgres + OAuth libs.

Initial choices to lock down in Milestone 0:
- Language + MCP SDK
- Web framework / HTTP layer
- ORM / migration tool
- Hosting target
- OAuth provider

## Roadmap

### Milestone 0 — Skeleton (week 1)
- Repo structure: `core/`, `mcp/`, `db/`, `schemas/`.
- Postgres schema + migrations.
- Stub core methods (in-memory or trivial fixtures).
- MCP server boots; advertises `factroll(action, params?)`; returns a
  hello-world payload.
- OAuth wired against the chosen provider (verification only; no UX
  polish).
- Local "smoke run" against Claude Desktop.

### Milestone 1 — Walkthrough loop (week 2)
- Real `start_session` and `next_fact` against a seeded corpus (~10
  facts on one topic).
- Deterministic EL math + category rolls implemented and unit-tested.
- Tool response carries `next_actions`.
- End-to-end demo: connect, start a topic, walk five facts.

### Milestone 2 — Full action surface (week 3–4)
- `switch_topic`, `set_experience_level`, `ask_question`,
  `end_session`.
- Resources: profile, topics, current session.
- Prompts: `/factroll`, `/factroll-resume`, `/factroll-status`.
- Fact repetition logic (~20% revisit rate per existing spec).

### Milestone 3 — Quiz mechanic (week 5)
- Server-side locked-answer state machine.
- `start_quiz`, `submit_quiz_answer`.
- Per-fact quiz history; weighted re-quiz toward previously-missed
  facts.
- Score-summary surface every five attempts.

### Milestone 4 — Fact corpus expansion (week 6)
- Seed corpus from past CCA sessions (export pipeline).
- Generation-instruction fallback path with review queue.
- Basic admin tooling to approve/reject corpus entries.

### Milestone 5 — Production deploy (week 7)
- Deploy to chosen host.
- OAuth UX hardening (consent screen, scope display, revoke flow).
- Per-user rate limits.
- Logging + observability.
- Documentation: install link, OAuth flow, supported clients.

## Backlog (not v1)

- **Option B**: dynamic tool list via
  `notifications/tools/list_changed`. Adopt once major-client refresh is
  reliable and the always-on budget proves tight.
- Visual facts (diagrams attached to facts).
- Spaced repetition scheduling.
- Exam proximity mode.
- "Predict my questions" feature.
- Joke mode.
- Server-side LLM fact generation (premium path).
- Public/shared fact corpus.
- Server-side grounded QA (call our own LLM for free-text answers
  instead of bouncing back to the agent).

## Web app follow-up

When MCP is stable through Milestone 3, work begins on the web app —
see [`PLAN_WEB_APP.md`](./PLAN_WEB_APP.md). It is a **second surface
over the same core**, not a rewrite. The web app does not speak MCP to
its own backend; it calls `factroll/core/` in-process.

---

## Open questions

1. **Stack**: Python or TypeScript MCP SDK?
2. ~~**Hosting**: Fly.io / Render / Cloud Run / VPS?~~ **Resolved: VPS.**
3. **OAuth provider**: Auth0, Clerk, Supabase, or self-hosted (Hydra,
   Keycloak)?
4. **DB migration tool**: Alembic, Prisma, Sqitch, plain SQL?
5. ~~**Fact corpus seeding source**: export from past Claude
   conversations, manual curation, or both? Tooling needed?~~
   **Resolved: past Claude conversations. Tooling = parser →
   LLM structuring step → review CLI. See "Fact source strategy".**
6. ~~**Quiz state on disconnect**: if the user disconnects mid-quiz, do
   we time out the locked answer (and how long), or honor it
   indefinitely until they reconnect?~~ **Resolved: hold indefinitely;
   no timeout.**
7. **Per-surface vs unified session**: confirm `(user_id, surface_id)`
   scoping vs a single active session per user.
8. ~~**"Switch topic" mid-quiz**: hard-block, soft-confirm via tool
   output, or quietly close the quiz?~~ **Resolved: quietly close the
   quiz, then switch.**
9. **Free-text Q&A handling**: tool returns an instruction to the
   agent to answer using its own ability (v1 plan), or proxy through a
   server-side LLM for grounded QA (backlog)? When do we move?
10. ~~**Anonymous trial**: any pre-OAuth demo (e.g. a single read-only
    topic) to lower onboarding friction, or is OAuth gate from day one
    fine?~~ **Resolved: anonymous trial allowed; OAuth/registration
    required to save state (EL, history, profile).**
11. **Rate limits**: starting per-user request cap?
12. ~~**Telemetry**: what to log, with what retention, under what
    privacy posture? GDPR-conscious defaults from day one.~~
    **Resolved: log topics picked, facts per topic, questions per
    topic, quiz pass/fail rate per fact, EL progression, category
    distribution, session drop-off action, anonymous→registered
    conversion rate, free-text questions asked. All user-generated
    content stored unconditionally; shared corpus gated on
    `contribute_to_corpus` opt-in. See "User-generated content".**
13. ~~**Action surface**: is the v1 action enum above the right shape,
    or should we split / merge any actions (e.g. is
    `set_experience_level` distinct from a `start` param)?~~
    **Resolved: leave as-is for v1; revisit later.**
14. **EL adjustment ergonomics**: keep `set_experience_level` as a
    direct action, or only expose it via the `/factroll-status` prompt
    and explicit user request?
