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

Migration tool: Alembic.

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

**Python.** MCP SDK (`mcp` package), FastAPI as the HTTP/SSE layer,
SQLAlchemy as the ORM, Alembic for migrations, Pydantic for schemas.
**Auth0** as the OAuth 2.1 provider (PKCE; third-party token flow for
MCP remote transport).

Initial choices locked down in Milestone 0:
- Language + MCP SDK: Python + `mcp`
- Web framework / HTTP layer: FastAPI
- ORM / migration tool: SQLAlchemy + Alembic
- Hosting target: VPS (resolved)
- OAuth provider: Auth0

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

1. ~~**Stack**: Python or TypeScript MCP SDK?~~ **Resolved: Python.**
   FastAPI + SQLAlchemy + Alembic + Pydantic.
2. ~~**Hosting**: Fly.io / Render / Cloud Run / VPS?~~ **Resolved: VPS.**
3. ~~**OAuth provider**: Auth0, Clerk, Supabase, or self-hosted (Hydra,
   Keycloak)?~~ **Resolved: Auth0.** Best-fit for MCP's third-party
   OAuth 2.1 + PKCE flow; migrate to self-hosted Hydra if MAU growth
   makes pricing a concern.
4. ~~**DB migration tool**: Alembic, Prisma, Sqitch, plain SQL?~~
   **Resolved: Alembic** (Python stack, SQLAlchemy integration).
5. ~~**Fact corpus seeding source**: export from past Claude
   conversations, manual curation, or both? Tooling needed?~~
   **Resolved: past Claude conversations. Tooling = parser →
   LLM structuring step → review CLI. See "Fact source strategy".**
6. ~~**Quiz state on disconnect**: if the user disconnects mid-quiz, do
   we time out the locked answer (and how long), or honor it
   indefinitely until they reconnect?~~ **Resolved: hold indefinitely;
   no timeout.**
7. ~~**Per-surface vs unified session**: confirm `(user_id, surface_id)`
   scoping vs a single active session per user.~~ **Resolved:
   per-surface.** Sessions keyed `(user_id, surface_id)`; profile and
   EL shared across surfaces.
8. ~~**"Switch topic" mid-quiz**: hard-block, soft-confirm via tool
   output, or quietly close the quiz?~~ **Resolved: quietly close the
   quiz, then switch.**
9. ~~**Free-text Q&A handling**: tool returns an instruction to the
   agent to answer using its own ability (v1 plan), or proxy through a
   server-side LLM for grounded QA (backlog)? When do we move?~~
   **Resolved: agent instruction for v1.** Move to server-side LLM
   when Q&A quality becomes a recurring complaint or a paid tier
   covers the per-question cost.
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
14. ~~**EL adjustment ergonomics**: keep `set_experience_level` as a
    direct action, or only expose it via the `/factroll-status` prompt
    and explicit user request?~~ **Resolved: direct action.**
    Include in `next_actions` when session context warrants it (e.g.
    after a fact is delivered), not on every response.

---

## Options Analysis

Detailed comparison for open questions that imply a choice among named
alternatives. Questions 2, 5, 6, 8, 10, 12, 13 are already resolved
above. Question 11 asks for a number, not a discrete option.

---

### Q1 — Stack: Python or TypeScript MCP SDK?

#### Option A — Python

Python MCP SDK (`mcp` package), FastAPI or Starlette as the HTTP layer,
SQLAlchemy as the ORM, Alembic for migrations, Pydantic for schemas.

**Pros**
- The seed pipeline (parser → LLM structuring step → review CLI) will
  naturally be Python; same language keeps the whole repo unified.
- SQLAlchemy + Alembic is the most battle-tested Postgres ORM/migration
  stack, and the strongest answer to Q4.
- Pydantic schemas map cleanly to the `schemas/<action>.py` shared-
  schema goal; validation is first-class.
- FastAPI handles SSE natively and is async-ready for the web BFF.
- Anthropic's Python SDK is the reference implementation; prompt
  caching, streaming, and tool use are first-class.
- Data tooling (corpus analysis, EL statistics, future analytics) is
  stronger in Python.

**Cons**
- If the web BFF ends up in TypeScript, schemas cannot be shared across
  surfaces — two separate definitions must stay in sync.
- Python's gradual typing means type errors surface at runtime more
  often than TypeScript's compile-time checks.
- Slightly more asyncio boilerplate compared to Node's native event loop
  for SSE-heavy workloads.

**Matches better when**
- The seed pipeline and any analytics tooling live in the same repo.
- Alembic is the chosen migration tool (Q4).
- The web BFF is also Python (FastAPI).
- Team is more fluent in Python than TypeScript.

**Matches worse when**
- The web BFF is Next.js/Remix — schema sharing across surfaces becomes
  a manual sync problem.
- Compile-time type safety across all layers is a hard requirement.

#### Option B — TypeScript

Official TypeScript MCP SDK (`@modelcontextprotocol/sdk`), Hono or
Express as the HTTP layer, Drizzle ORM or Prisma for Postgres, Zod for
schemas.

**Pros**
- If the web BFF is also TypeScript, the `schemas/<action>.ts` package
  is shared verbatim between the MCP adapter and the BFF agent loop —
  enforced at compile time, no drift possible.
- Zod schemas generate JSON Schema for tool definitions with minimal
  boilerplate.
- Node.js is native to SSE/WebSocket; no GIL, idiomatic async.
- MCP's broader tooling ecosystem (debugging, inspector tools) skews
  TypeScript-first.
- Prisma and Drizzle have strong DX and type inference.

**Cons**
- The seed pipeline will likely still be Python regardless, so the
  "single language" argument is weakened — two languages in the repo
  without the schema-sharing benefit.
- Prisma and Drizzle are newer with smaller communities than SQLAlchemy;
  migration edge cases (complex constraints, column renames) are less
  well-documented.
- Build tooling (tsconfig, bundlers) adds friction vs `python -m`-style
  execution.
- TypeScript is not the reference implementation; edge cases in the MCP
  SDK hit Python first.

**Matches better when**
- The web BFF is Next.js or Remix — schema sharing pays off immediately.
- Team is stronger in TypeScript than Python.
- Compile-time proof of no adapter drift is a hard requirement.

**Matches worse when**
- The seed pipeline ends up in Python anyway (likely) — two languages,
  no sharing benefit.
- DB admin, corpus analysis, or analytics work benefits from Python's
  data ecosystem.

**Recommendation: Python.** The seed pipeline is the deciding factor.
It will be Python regardless, and keeping the MCP server in the same
language unifies the repo, the CI pipeline, and the mental model. The
schema-sharing benefit of TypeScript is real but conditional on a
TypeScript BFF; that surface does not exist yet. Revisit if the web BFF
lands on Next.js.

---

### Q3 — OAuth provider: Auth0, Clerk, Supabase, or self-hosted?

#### Option A — Auth0

Hosted OAuth 2.1 authorization server. Industry standard, supports
PKCE, machine-to-machine (M2M) tokens, and all standard grant types.

**Pros**
- Best-in-class OAuth 2.1 + PKCE compliance; tested with MCP's
  third-party client flow (the pattern where Claude Desktop holds the
  token, not a browser session).
- Extensive SDKs for Python and TypeScript; well-documented PKCE
  integration guide.
- M2M tokens available for future server-to-server automation.
- GDPR tooling, audit logs, and MFA are built in.
- Fastest path to Milestone 0.

**Cons**
- Most expensive option at scale; pricing grows with monthly active
  users.
- Can be overkill for v1 scale; dashboard complexity is high for a
  simple scope set (`factroll.read`, `factroll.write`).
- Vendor lock-in: tenant config is not portable.

**Matches better when**
- MCP is the primary surface (Auth0's third-party OAuth flow is exactly
  what MCP remote transport requires).
- Speed to Milestone 0 is the priority.
- Enterprise or compliance requirements appear later.

**Matches worse when**
- Budget is tight long-term and MAU grows; Auth0 can become expensive
  quickly.
- Self-sovereignty of auth data is a requirement.

#### Option B — Clerk

Modern auth platform focused on developer experience. Drop-in UI
components, generous free tier, strong web-session story.

**Pros**
- Best DX of all hosted options; fastest to wire up for a web app.
- Generous free tier (10 000 MAU).
- Built-in user management dashboard, impersonation, and session
  management.

**Cons**
- Designed for first-party web sessions (user signs into your app), not
  third-party OAuth 2.1 flows. MCP requires an authorization server that
  issues tokens to external clients (Claude Desktop, Claude Code) — this
  is not Clerk's primary model.
- OAuth 2.1 PKCE for third-party clients is less mature and less
  documented in Clerk than Auth0.

**Matches better when**
- The web app is the primary surface and the auth flow is always
  browser-initiated.
- DX and onboarding speed for the web surface are the top priorities.

**Matches worse when**
- MCP is the primary surface — the third-party OAuth 2.1 dance is not
  where Clerk shines.

#### Option C — Supabase Auth

Auth bundled with Supabase's Postgres-as-a-service. Open-source,
self-hostable, free tier included.

**Pros**
- If Supabase is used for the Postgres instance, auth is bundled — one
  fewer service to configure.
- Open-source; self-hostable if needed later.
- Free tier is generous; no per-MAU pricing at small scale.

**Cons**
- Supabase Auth is designed for first-party auth (user signs into your
  app), not for acting as an OAuth 2.1 authorization server issuing
  tokens to external MCP clients. This use case is not natively
  supported.
- We are running on a VPS (Q2 resolved), not Supabase managed Postgres,
  so the "one service" bundling benefit disappears.
- Less battle-tested for the specific MCP OAuth 2.1 PKCE flow.

**Matches better when**
- The Postgres instance is on Supabase (which it isn't here).
- Auth needs are limited to first-party web sessions.

**Matches worse when**
- MCP's third-party OAuth 2.1 flow is the primary auth surface — this
  pattern is not Supabase Auth's design target.

#### Option D — Self-hosted (Ory Hydra or Keycloak)

Run an OAuth 2.1 authorization server on the same VPS.

- **Hydra** (Ory): lightweight, headless OAuth 2.1/OIDC server; no
  built-in login UI (must wire your own); excellent spec compliance.
- **Keycloak**: heavyweight, full-featured identity platform; built-in
  UI; complex to configure.

**Pros**
- Full control; no per-user pricing; data never leaves the VPS (GDPR
  data locality is simple).
- Hydra has exemplary OAuth 2.1 + PKCE compliance; arguably the
  strongest third-party token issuer for MCP.
- Zero vendor lock-in; can migrate config to another deployment.
- Long-term cost is the cheapest option (VPS already paid for).

**Cons**
- Significant ops burden: uptime, security patches, backup, key
  rotation are all on us.
- Hydra requires building a login/consent UI from scratch (not a drop-
  in).
- Keycloak is operationally complex; overkill for v1 scope set.
- Adds meaningful time to Milestone 0 before the first smoke run.

**Matches better when**
- Budget sensitivity matters long-term and MAU could grow large.
- GDPR data locality is a strict requirement.
- The team has ops capacity and wants zero vendor dependency.

**Matches worse when**
- Speed to Milestone 0 is the priority.
- Team is small and ops capacity is limited.

**Recommendation: Auth0 for v1.** It is the fastest path to a correct
OAuth 2.1 + PKCE setup for MCP's third-party token flow, which is the
pattern that neither Clerk nor Supabase Auth targets well. Document a
migration path to self-hosted Hydra in the backlog for when MAU growth
makes Auth0's pricing a concern. Clerk is fine if the web app launches
first but should not be the auth layer for the MCP server.

---

### Q4 — DB migration tool: Alembic, Prisma, Sqitch, or plain SQL?

#### Option A — Alembic

SQLAlchemy's migration companion. Generates versioned Python migration
scripts; can autogenerate diffs from model changes.

**Pros**
- Directly integrated with SQLAlchemy models; autogenerate saves time on
  routine column additions.
- Battle-tested; largest community of the options listed.
- Python-native — zero friction if the stack is Python (Q1 → Python).
- Migration scripts are plain Python; arbitrary logic (data migrations,
  conditional DDL) is easy to express.
- Excellent documentation and VPS deployment story.

**Cons**
- Python-only; if the stack shifts to TypeScript, Alembic is no longer
  available.
- Migration files are Python code rather than raw SQL, which some DBAs
  find less auditable.
- Autogenerate misses some complex cases (e.g. functional indexes,
  partial indexes) — always review before applying.

**Matches better when**
- Python is the chosen stack (Q1 → Python).
- SQLAlchemy is the ORM.
- Frequent schema iteration is expected during v1 development.

**Matches worse when**
- TypeScript is the stack.
- Pure-SQL auditing is a hard requirement.

#### Option B — Prisma

TypeScript-native schema-first ORM + migration tool. Schema defined in
Prisma Schema Language (PSL); migrations are generated SQL files.

**Pros**
- Best DX if the stack is TypeScript; type-safe queries included in the
  same package.
- Generated migrations are SQL files (auditable), not ORM code.
- Prisma Studio provides a GUI DB inspector.
- Active ecosystem and excellent getting-started documentation.

**Cons**
- TypeScript-only; not usable with a Python server.
- PSL is another schema language to learn; it doesn't map one-to-one
  to Postgres DDL.
- Production migrations involving column renames, complex constraints, or
  large table rewrites require manual intervention that Prisma's tooling
  sometimes obscures.
- Prisma ORM query performance has known overhead vs raw SQL on
  complex joins.

**Matches better when**
- TypeScript is the stack (Q1 → TypeScript).
- ORM and migration tool should be a single coherent package.

**Matches worse when**
- Python is the stack — Prisma is simply not applicable.
- Fine-grained migration control is needed on a live production table.

#### Option C — Sqitch

Language-agnostic, change-based migration tool. Migrations are pure SQL
files with dependency declarations; Sqitch tracks what has been applied.

**Pros**
- Pure SQL migrations: maximum auditability; a DBA can read and approve
  every change without knowing the ORM.
- Entirely language-agnostic — works equally well with Python or
  TypeScript stacks.
- Dependency-aware: migrations declare what they depend on; Sqitch
  reorders as needed.
- Stable and low-dependency; no framework to keep updated.

**Cons**
- No autogenerate: every migration is written by hand.
- Smaller community; less beginner documentation.
- No ORM integration; the schema in Sqitch files and the ORM models must
  be kept in sync manually.
- Higher initial time investment to set up correctly.

**Matches better when**
- The team includes a DBA or treats schema changes as high-stakes
  operations requiring SQL-level review.
- The stack could change language; you want migration tooling that is
  independent of that choice.
- Auditability and traceability of schema history are first-class
  requirements.

**Matches worse when**
- Fast schema iteration during v1 is a priority; writing every migration
  by hand slows the loop.
- The team is small and wants the migration tool to do the heavy lifting.

#### Option D — Plain SQL

Numbered or timestamped raw SQL files executed by a thin runner (a
simple shell script, a Makefile target, or a minimal library like
`golang-migrate` used purely as a runner).

**Pros**
- Zero framework dependency; completely transparent.
- Trivially auditable.
- Works with any language stack and any deployment environment.

**Cons**
- No autogenerate; every DDL statement written by hand.
- Manual version tracking is error-prone without a runner that records
  which migrations have been applied.
- Does not scale well as the schema grows and migration ordering becomes
  complex.

**Matches better when**
- The schema is very small and unlikely to change often.
- Zero external dependencies is a hard constraint.

**Matches worse when**
- Schema will evolve frequently across milestones (it will).
- A reliable record of applied migrations is needed in production.

**Recommendation: Alembic** (conditional on Q1 → Python, which is the
recommendation there). It is the most integrated, best-documented option
for the Python/SQLAlchemy stack and handles the schema evolution
expected across Milestones 0–5. If Q1 resolves to TypeScript, use
Prisma. Sqitch is a sound choice if SQL-level auditability becomes a
requirement later — it can replace Alembic without touching the ORM.

---

### Q7 — Per-surface vs unified session scoping

#### Option A — Per-surface: `(user_id, surface_id)` (current plan)

Each MCP connection identity (`surface_id`) gets its own active session.
Two connections from the same user run independent, non-colliding
sessions.

**Pros**
- Models the actual use case: the plan explicitly mentions Aleksei using
  both Claude Desktop and Claude Code simultaneously on different topics.
- Quiz lock is surface-scoped by construction — no cross-surface
  contention possible without any extra locking logic.
- Matches how MCP connections work natively (each connection has a
  distinct handshake and lifecycle).
- Profile and EL are still shared across surfaces, so progress is not
  siloed.

**Cons**
- More complex session-management queries (must filter by surface_id).
- User could accidentally start two sessions and not realize it; "resume"
  UX must make clear which surface the session is on.
- Session summary and history views must aggregate across surfaces to
  give a unified picture.

**Matches better when**
- Power users with multiple agents is a real early-adopter scenario (it
  is, per the plan).
- Quiz state must be isolated and collision-free without distributed
  locking.
- Sessions are meant to reflect distinct interaction contexts.

**Matches worse when**
- v1 simplicity is the top priority and parallel multi-client use is
  not yet observed in practice.
- The UX team wants a single "current session" concept across all
  surfaces.

#### Option B — Unified: single active session per user

Only one active session per user at any time. Starting a session on a
second client either takes over or is blocked until the first is ended.

**Pros**
- Simpler DB queries; no surface_id dimension.
- Single "resume" UX — no ambiguity about which session to resume.
- Easier to build unified session history.

**Cons**
- Blocks the explicitly mentioned real use case of two clients running
  simultaneously.
- Last-writer-wins on `start` from a second client would silently end
  the first client's session, which is surprising behavior.
- Blocking the second client requires the user to explicitly end the
  first session — friction on a power-user workflow.

**Matches better when**
- v1 user base is expected to have exactly one active MCP client at a
  time.
- Simplicity of session management outweighs the parallel-client use
  case.

**Matches worse when**
- The first user (and likely early adopters) uses both Claude Desktop
  and Claude Code — this is the stated scenario.

**Recommendation: Per-surface (Option A).** The use case is explicit in
the plan; Option B would require the first user to work around the
limitation immediately. The session table already has `surface_id` in
the schema, so the complexity cost is already paid.

---

### Q9 — Free-text Q&A handling

#### Option A — Agent instruction (v1 plan)

When the user asks a free-text question, the tool returns a structured
instruction telling the agent to answer using its own LLM abilities.
The server stores the question for analytics and future corpus
enrichment but does not call an LLM itself.

```jsonc
{
  "say": "(answer the user's question using the current fact and recent context, then offer 'next_fact' or 'switch_topic')",
  "next_actions": ["next_fact", "switch_topic"]
}
```

**Pros**
- No server-side LLM cost or API key management.
- No ToS exposure from relaying user content through our own model.
- The agent already has the full session context; its answer can be
  naturally grounded in the conversation history.
- Questions are stored for future corpus enrichment without needing a
  live generation step.
- Fastest to implement; unblocks Milestone 2 without additional
  infrastructure.

**Cons**
- Answer quality varies by agent and by how well the instruction
  prompt is written; Factroll has no control over what the agent says.
- If the agent hallucinates, the user may associate the bad answer with
  the Factroll session rather than the underlying LLM.
- Instruction fidelity depends on the agent following the returned
  `say` string — not all clients will handle it identically.

**Matches better when**
- v1 speed and cost are the priorities.
- Users are using capable agents (Claude Desktop, Claude Code) that
  follow tool instructions reliably.
- Q&A is a secondary feature, not a product differentiator.

**Matches worse when**
- Answer accuracy is a brand concern.
- Users are on weaker agents that ignore or misinterpret the instruction.
- Q&A becomes a primary feature with quality expectations.

#### Option B — Server-side LLM proxy (backlog)

Factroll forwards the user's question and the current fact/session
context to a server-controlled LLM call, returning a grounded answer
directly in the tool response.

**Pros**
- Consistent answer quality regardless of which agent the user is
  running.
- Factroll controls the prompt; answers can be grounded against the
  stored fact corpus.
- Enables richer features: citation of source facts, accuracy scoring
  of user understanding, structured Q&A history.

**Cons**
- Adds LLM API cost on Factroll's side; requires an API key and cost
  controls.
- Adds latency (an extra LLM call per question).
- ToS surface: we are now relaying user content through our own model.
- Significantly more complexity; needs a provider abstraction, error
  handling, and rate limiting on LLM calls.

**Matches better when**
- Q&A answer quality is a product differentiator (paid tier or premium
  feature).
- The fact corpus is dense enough to ground answers reliably.
- Budget for LLM API costs is available.

**Matches worse when**
- v1; no budget for server-side LLM calls.
- Moving fast is more important than answer consistency.

**Recommendation: Agent instruction (Option A) for v1**, as already
planned. Move to Option B when either: (a) Q&A answer quality becomes
a recurring user complaint, or (b) a paid tier is introduced whose
margin covers the per-question LLM cost. The switch does not require a
schema change — only the server-side handler for `ask_question` changes.

---

### Q14 — EL adjustment ergonomics

#### Option A — `set_experience_level` as a direct action

The action is part of the active session vocabulary and included in
`next_actions` when contextually appropriate, allowing the agent to
suggest or invoke it mid-session without the user breaking flow.

**Pros**
- Discoverable: the agent can proactively suggest EL adjustment when
  the user signals that facts feel too easy or too hard.
- No flow interruption: the user does not need to exit the session and
  invoke `/factroll-status` separately.
- Consistent with the rest of the action model — all session-modifying
  operations are available as actions.

**Cons**
- Adds a term to the `next_actions` vocabulary in every session turn
  where it is relevant; slight token cost.
- The agent must decide when to surface the suggestion; a poorly tuned
  agent might suggest EL changes too often or not at all.
- Risk of accidental EL changes if the agent misinterprets an offhand
  user comment ("this is too easy") as an intent to change EL.

**Matches better when**
- EL calibration is expected to happen frequently as users explore new
  topics and discover their actual level.
- The agent is capable of contextual judgment about when to surface the
  action.
- Smooth in-session UX is a priority.

**Matches worse when**
- EL is treated as a stable setting changed only at deliberate review
  points.
- Accidental EL drift would be confusing or hard to undo.

#### Option B — EL change only via `/factroll-status`

`set_experience_level` is removed from the in-session `next_actions`
set. EL can only be changed by the user explicitly invoking the
`/factroll-status` prompt, which presents a deliberate review-and-
adjust interface.

**Pros**
- Intentional change only: the user has to mean it, reducing accidental
  EL drift.
- Simpler session vocabulary; the in-session `next_actions` set is
  shorter.
- Clear UX boundary: session = content flow; status = profile
  management.

**Cons**
- Not discoverable mid-session: if the user realizes facts are too easy
  in fact 3, they must break flow, invoke `/factroll-status`, change
  EL, and then resume — or just tolerate the wrong level for the rest
  of the session.
- The agent cannot proactively help the user calibrate.
- Adds friction to what may be a frequent operation for new users still
  finding their level.

**Matches better when**
- EL is meant to be stable across sessions; users are expected to set
  it once and revisit deliberately.
- Session flow should never be interrupted by housekeeping actions.

**Matches worse when**
- New users are still discovering their level and need to adjust
  frequently mid-session.
- Agent-driven calibration (agent notices difficulty signals and
  suggests EL adjustment) is a desired feature.

**Recommendation: Direct action (Option A)**, with one implementation
note: include `set_experience_level` in `next_actions` only when the
session context warrants it (e.g., after a fact is delivered, not after
every single response), not as a permanent fixture in every response.
This preserves discoverability and agent-driven calibration while
minimising token bloat. Revisit and tighten the trigger condition in
the backlog if users report unwanted EL-change suggestions.
