# Architecture Assessment: Productizing Factroll

## Overview

You're proposing to turn the **conversation-based learning system** (currently running inside Claude conversations with EL mechanics, category rolls, and quiz guards) into a **standalone product** with web + mobile UI, BYOK LLM keys, and server-side persistence.

This assessment covers what's strong, what needs correction, and the major pitfalls to watch.

---

## Current State

- **System design:** Well-tested conversation-based mechanics (EL, A-D category rolls, anti-sycophancy quiz guard, spaced repetition ideas)
- **Implementation:** Entirely prompt-driven; no backend
- **UI mockup:** React backlog component exists (backlog_20260415.jsx)
- **Target user:** ML/AI engineers prepping for CCA certification (Aleksei as initial user)

---

## What's Strong About Your Proposal

### 1. BYOK Model Removes Major Operational Burden

**Why this matters:** You avoid billing infrastructure, margin management, rate-limit liability, and user support for "my bill is too high." Users pay their own LLM costs.

- No Stripe integration complexity
- No financial compliance (PCI, revenue recognition)
- Lower legal liability
- Scales with zero operational cost on your side

**Trade-off:** Users must have API keys, which adds onboarding friction. Acceptable for your target audience.

### 2. Button-First Navigation Maps Directly to Existing Design

Your existing commands ("Next fact", "Switch topic", "Quiz me", "Expert level") are already discrete actions. Converting them to tappable links is a natural translation, not a forced UI paradigm shift.

- Low impedance mismatch
- Mobile-friendly by design
- User already expects this flow from conversation sessions

### 3. Server-Side Fact Curation Builds Competitive Moat

If you store and curate LLM-generated facts, you build a growing corpus. Over time:

- You can serve cached facts without LLM calls (cheaper, faster)
- You can A/B test fact quality across users
- You can license the corpus later if it becomes valuable
- New users benefit from accumulated knowledge without re-generating

This is the hardest thing for competitors to copy.

---

## Corrections: Things to Rethink

### 1. "Agent" Needs a Precise Definition

Your current system prompt (PROJECT_INSTRUCTIONS.md) handles:
- EL tracking
- Category roll mechanics (`ABChance = (1 - EL) × 0.95`)
- Quiz pre-commitment and scoring
- Session flow control

When you move to a product, you have two architectural choices:

#### Option A: Thin Client, Fat Prompt
```
User → Client (state manager) → Server (stateless) → User's LLM API (runs system prompt)
```
- System prompt is the "agent"
- Server is a state manager and fact store
- **Problem:** You're paying tokens for arithmetic (rolling dice, calculating ABChance). The LLM might not follow deterministic rules reliably.

#### Option B: Server-Side Orchestrator (Recommended)
```
User → Client (UI) → Server (session logic, rolls, EL tracking, fact retrieval)
                 → User's LLM API (fact generation, Q&A, quiz distractor generation only)
```
- Server runs deterministic rules in code (the "agent" logic)
- LLM is a tool for creative generation only
- **Advantage:** Cheaper, more reliable, fully deterministic

**Recommendation:** Go with Option B. Your rules are deterministic; run them in code. Reserve LLM calls for:
- Fact generation
- Answering user questions
- Generating quiz distractors
- Evaluating open-ended quiz responses

This cuts LLM token usage by ~70% and guarantees ABChance formula compliance.

---

### 2. BYOK Model: The Right First Move (Consumer Subscriptions Won't Work)

You considered: *Could users instead use their existing Claude Free/Pro, ChatGPT Plus, Gemini Pro subscriptions?*

**Why consumer subscriptions don't work:**
- **No API access.** Claude.ai Free/Pro, ChatGPT Plus, Gemini Free are web-only. No programmatic access.
- **ToS violation.** All explicitly prohibit automation, bot access, and screen scraping.
- **Credential nightmare.** You'd need user passwords (much worse than API keys). Never worth it.
- **Rate limit hell.** After 5-10 automated requests, the user gets blocked.
- **Fragile.** UI changes break your scrapers constantly.

**Bottom line:** You must use **BYOK with API keys**. It's the only legal, scalable, reliable option.

---

#### API Key Storage: The Security Detail

This is critical. You will be handling user API keys—but minimally.

##### Problem: Traditional Approach (Don't Do This)
```
User sends key to server → Server stores (encrypted?) in DB → Server uses to call LLM
```
- Single breach exposes every user's API key
- You're liable for their API quota abuse
- Compliance nightmare (GDPR, data retention, etc.)

##### Solution: Client-Side Keys (Recommended for BYOK)
```
User pastes key into client (localStorage/Keychain) → Client calls LLM API directly
Server handles: session state, fact storage, scoring (no keys needed)
```

**Implementation:**
- Keys never leave the client
- Keys never traverse your server
- Client uses CORS-proxied LLM calls (or native mobile APIs)
- Your server is stateless regarding credentials

**If you must proxy keys** (e.g., to work around CORS):
1. Encrypt keys with a per-user ephemeral session key
2. Delete immediately after use
3. Never log or store
4. Document this heavily in your privacy policy

**For Anthropic API specifically:** The SDK supports client-side calls; you don't need to proxy.

---

#### Future: Freemium Tier (Post-Launch)

Once BYOK is working, consider a **freemium tier** to lower friction:

```
User gets 10 facts/day free (on your API key) → Beyond that: bring your own key
```

**Why this works:**
- New users can try the product without setup friction
- Sustainable upsell (power users/regular users bring their own key)
- You eat the cost, but it's small (~$0.01/day per free user)
- Clean separation: you don't touch free user credentials

**Timing:** Ship BYOK first. Add freemium tier after 50+ users prove product-market fit.

---

### 3. Multi-Model Support Is Harder Than It Looks

You said "subscriptions/API keys to LLM models" (plural). Supporting Claude, GPT-4, Gemini means:

| Problem | Impact |
|---|---|
| Different API formats | Different SDKs, different error codes, different streaming protocols |
| Different tool-use conventions | Your quiz mechanic relies on structured output; not all models support it equally |
| Different system prompt compliance | Your pre-commitment rule, roll procedure, category logic — weaker models will ignore or hallucinate |
| Different cost models | Token counting differs; you can't reliably warn users about costs |
| Quality variance | Generated facts will vary wildly by model |

**Recommendation:** 
- **Launch with Claude API only.** Your entire system was designed and battle-tested with Claude's behavior.
- Add other models only if you have:
  - 50+ active users requesting it
  - Proven model-agnostic fact curation pipeline
  - A/B testing infrastructure

Premature multi-model support is a classic time sink. Ship single-model first.

---

### 4. Think Hard About Session State Architecture

Your data lives in three places: device, server, LLM context.

```
┌─────────────────────────────────────────────┐
│ Server Database                             │
├─────────────────────────────────────────────┤
│ • User account + preferences                │
│ • Topics (8 favorites + custom)             │
│ • EL progress per topic                     │
│ • Curated fact corpus (indexed, reusable)   │
│ • Quiz score history (per-fact, per-user)   │
│ • Session metadata (created, last_accessed) │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Client (localStorage / memory)              │
├─────────────────────────────────────────────┤
│ • Active session state                      │
│   - current topic                           │
│   - current EL                              │
│   - facts shown in this session             │
│   - quiz answers (not yet submitted)        │
│ • API keys (encrypted, never sent to server)│
│ • UI state (scroll position, etc.)          │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│ Ephemeral (per LLM call, discard after)    │
├─────────────────────────────────────────────┤
│ • Free-text question context                │
│ • Recent facts (for QA grounding)           │
│ • Conversation transcript (if needed)       │
└─────────────────────────────────────────────┘
```

**Don't persist:**
- Raw LLM conversation turns (unless you're building analytics)
- Fact generation prompts (user doesn't need to see the sausage-making)
- Temporary quiz attempts (only store final scores)

---

### 5. Link-Buttons vs. Free-Text Creates Two UX Modes

**Buttons** (structured, predictable):
- "Next fact"
- "Switch topic"
- "Quiz me"
- "Expert level +20%"

**Free-text** (open-ended):
- "What's the difference between X and Y?"
- "Can you give an example of Z?"
- "Why does this matter for the CCA exam?"

**Design tension:** Button mode keeps session state clean and deterministic. Free-text requires full LLM context and can derail the flow (user asks a tangent question, now what?).

**Recommendation:** Make free-text a **modal overlay**, not inline.

```
Main flow (buttons):
Fact → [Next / Switch / Quiz / Expert level]

When user clicks "Ask a question":
→ Opens modal with chat input
→ LLM answers with context of current fact + session
→ Modal closes, returns to main flow
→ Session state unchanged
```

**Benefits:**
- Main session flow never gets disrupted
- Free-text still available for power users
- Modal can have its own timeout (30 min?); stale context doesn't poison the session

---

### 6. Web + Mobile Simultaneously Is a Trap

**Bad approach:** Build iOS and Android separately
- 2x codebase maintenance
- 2x QA
- 2x deployment pipeline
- You ship slower

**Approach A: React Native / Expo**
- One codebase for iOS + Android
- Trade: UI compromises on both platforms, native performance features are harder

**Approach B: PWA (Recommended first)**
- Responsive web app that works on all devices
- One codebase
- Works offline with Service Workers
- Mobile users can "install" it (web app manifest)
- No App Store friction

**Timeline suggestion:**
1. Launch PWA (responsive web)
2. If you need push notifications or background sync → Capacitor wrapper for iOS/Android
3. If you need native-specific features (complex animations, hardware access) → later

Ship web first. Mobile will work. Only build native after you have proof of product-market fit.

---

## Pitfalls to Watch

### 1. LLM Hallucinated Facts

**Risk:** Users learn incorrect information.

**Mitigation:**
- Implement a **fact review queue** on the server
- Only serve facts marked "reviewed"
- Flag facts that touch CCA exam topics (high stakes)
- Let users report inaccuracies with one click
- Track fact accuracy over time; deprioritize low-quality sources

### 2. API Key Exposure

**Risk:** Single breach leaks every user's API quota.

**Mitigation:**
- Client-side key storage (no server-side persistence)
- Clear documentation: "We never store your API keys"
- Implement a kill-switch: user can rotate keys without re-entering

### 3. Scope Creep Into Full LMS

**Risk:** You get distracted building "Visual Facts", "Spaced Repetition", "Exam Proximity Mode" before shipping the core loop.

**Current backlog:** 7 items, with only 1 marked "ready". You'll never ship if you try to build everything.

**Mitigation:**
- Define **MVP scope strictly:** fact → buttons → quiz → session summary
- Everything else (Visual Facts, Spaced Repetition, Exam Mode) is post-launch
- Measure before building: "Do users actually want this?"

### 4. Model-Dependent Prompt Behavior

**Risk:** Your system prompt relies on Claude-specific behavior (e.g., structured JSON output, instruction following). If you add GPT-4 and it doesn't follow rules, users see broken mechanics.

**Mitigation:**
- Test prompt compliance on new models before adding support
- Move deterministic rules to server code (don't rely on LLM for arithmetic)
- Document which models are "officially supported"

### 5. Cold Start Problem

**Risk:** New user lands, sees no facts, sees an empty topic list, leaves.

**Mitigation:**
- Seed the fact corpus from your own CCA prep sessions (you've done 30+ sessions)
- Pre-generate facts for the 8 core topics using Claude Batch API (cheap)
- New users see pre-curated facts immediately; the system feels populated

### 6. Cost Surprise for Users

**Risk:** User runs a 10-fact session, their API bill shows $5 in unexpected costs, they blame you and leave a bad review.

**Mitigation:**
- Show **estimated token usage** before each session
- Warn before expensive operations (e.g., "Quiz mode uses 3x tokens for distractors")
- Surface actual token counts in session summary
- Link to pricing calculators

### 7. Session Resumption Complexity

**Risk:** User closes the app mid-session, reopens it, and the session state is confusing (was I mid-question? Did that count toward my EL?).

**Mitigation:**
- Save session state aggressively to server after each action
- Resume exactly where they left off
- Clear session summary at the end (facts seen, EL reached, quiz scores)
- Don't auto-resume after 24h; user explicitly chooses to continue

---

## Suggested Priority Order

### Phase 1: Core Infrastructure
1. **Data model design**
   - User schema (id, email, password/SSO, api_key_salt, created_at)
   - Topic schema (id, name, user_favorites, default_EL)
   - Fact schema (id, topic_id, content, category, created_by, reviewed, accuracy_score)
   - Session schema (id, user_id, topic_id, facts_shown, el_reached, created_at)
   - Quiz result schema (id, session_id, fact_id, user_answer, correct, timestamp)

2. **Server API** (no LLM calls yet; use mock fact data)
   - POST /api/auth/login
   - GET /api/topics (user's favorites)
   - GET /api/topics/:id/facts (retrieve pre-curated facts)
   - POST /api/sessions (start new session)
   - POST /api/sessions/:id/next (get next fact or quiz question)
   - POST /api/sessions/:id/answer (submit quiz answer)
   - POST /api/sessions/:id/close (save session)

3. **Database schema** (PostgreSQL recommended)
   - Users table
   - Topics table
   - Facts table (with `reviewed` boolean)
   - Sessions table
   - Quiz results table

### Phase 2: Web Client (Responsive)
1. **Layout & navigation**
   - Header (topic, EL display)
   - Fact card (centered, readable)
   - Button row (Next / Switch / Quiz / Expert level / Ask question)
   - Optional modal for free-text questions

2. **Topic selection flow**
   - Show favorites
   - Show suggestions
   - Allow search/custom entry

3. **Button interactions**
   - Each button triggers a POST to server
   - Server returns next state
   - Client updates UI

### Phase 3: LLM Integration
1. **Fact generation**
   - Server-side job queue
   - Generate facts for new topics on demand
   - User's API key → Claude API → fact saved to DB
   - Review queue before serving to other users

2. **Free-text Q&A**
   - Modal for "Ask a question"
   - Client sends question + context (current fact, recent facts)
   - Server proxies to user's LLM API
   - Response shown in modal

3. **Quiz distractor generation**
   - When user requests quiz, generate 3 distractors
   - Use user's API key
   - Pre-commit correct answer before rendering

### Phase 4: Quiz Mechanic
1. **Question generation**
   - Per-fact, per-EL-band (recall vs. application vs. edge cases)
   - Source only from facts shown in session
   - Locked answer before rendering

2. **Scoring & tracking**
   - Submit answer → server compares to locked answer
   - Update session quiz_results
   - Surface per-fact accuracy over time

### Phase 5: Polish & Analytics
1. Session summary (facts seen, EL reached, quiz score)
2. Session history / progress dashboard
3. Anonymous usage metrics (which topics are popular?)
4. Fact accuracy feedback loop

### Phase 6+: Post-Launch
- Visual facts (diagrams for Neural Networks topic)
- Spaced repetition (suggest revisiting old facts)
- Exam proximity mode (shift toward D-category, quiz-heavy)
- Mobile native apps (if demand exists)

---

## Key Decisions Ahead

| Decision | Options | Recommendation |
|---|---|---|
| **LLM access model** | BYOK (user's API key) OR Consumer subscription scraping OR Freemium shared key | BYOK (legal, reliable, scalable). Freemium tier post-launch. Never scrape. |
| **Where does EL logic run?** | Server-side code OR LLM-in-prompt | Server-side code (cheaper, more reliable) |
| **Where do API keys live?** | Client-side only OR Server-proxied | Client-side only (simpler, more secure) |
| **Which LLM models?** | Claude + GPT-4 + others OR Claude only | Claude only (for now) |
| **Web first or native?** | React Native + Expo OR PWA + optional Capacitor | PWA first |
| **Session state?** | Fully server-managed OR Hybrid (server + client) | Hybrid (server owns truth; client caches) |
| **Free-text QA?** | Inline in main flow OR Modal overlay | Modal overlay |

---

## Next Steps

1. **Confirm architecture choice:** Do you agree with Option B (server-side orchestrator)?
2. **Sketch the data model:** User, Topic, Fact, Session, QuizResult
3. **Design the API contract:** What does POST /sessions/:id/next return?
4. **Prototype the web client:** Responsive layout with mock data
5. **Build server** (Go, Node, Python — pick your strongest)
6. **Integrate LLM** (fact generation, Q&A)

Want me to help you design the data model or API contract next?
