# Memory Example: Aleksei's Profile & Learning Context

## Purpose & Context

Aleksei is an **ML/AI engineer** preparing for the **Claude Certified Architect (CCA) Foundations certification exam**. The goal is systematic, deep mastery across eight saved favorite topics that collectively span the full CCA exam syllabus:

1. Neural Network Architectures
2. MLOps & Model Deployment
3. System Design for AI
4. Training & Optimization
5. Data Engineering for AI
6. AI Safety & Governance
7. MCP & Tool Integration
8. Prompt Engineering & Structured Outputs

**Note:** MCP & Tool Integration and Prompt Engineering & Structured Outputs were added specifically to fill identified CCA coverage gaps (Domains 2 and 4).

Aleksei approaches learning **depth-first**: fully exploring a concept before moving on, frequently requesting concrete examples (e.g., annotated JSON structures) rather than abstract descriptions.

---

## Current State & Active Mechanics

**Expert Level (EL):**
- A parameter (expressed as a percentage) controlling how advanced or non-obvious presented facts should be
- Aleksei typically sets EL at 20% for new topic sessions
- EL started at 0 and was upgraded to 1 in early sessions based on demonstrated comprehension

**Category Rolls (A–D):**
- Facts are categorized as foundational (A), standard (B), interesting/non-obvious (C), or recent/discussion-based (D)
- Distribution follows: `ABChance = (1 - EL) × 0.95`
- **Critical rule:** Claude must never silently skew category weighting based on inferred expertise
- Claude may offer a higher starting EL suggestion before the first fact on a new topic, but only as an explicit suggestion

**Navigation Commands:**
- After each fact, Aleksei uses prompts like "Next fact," "Switch topic," "Expert level," or "Question" to navigate sessions

**Topic Randomization:**
- Sessions often begin with a random topic draw from the eight saved favorites

**Topics Covered to Date:**
- System Design for AI (scalability, feature stores, vector databases/HNSW)
- MCP & Tool Integration (architecture, primitives, JSON-RPC 2.0, sampling, security)
- AI Safety & Governance (Goodhart's Law, alignment proposals, long-term risk taxonomy, AI pause debate)

**Quiz Mechanic (Under Active Development):**
- Quiz questions anchor only to facts established within the current session
- Claude pre-commits to the correct answer before seeing the user's response (prevents sycophantic capitulation)
- Question types are restricted by EL band
- Per-fact performance tracking surfaces knowledge gaps over time

---

## Key Learnings & Principles

### No Silent Profile-Based Adjustments
Claude must not adapt fact category distribution based on Aleksei's inferred background without making the adjustment explicit. Transparency about mechanics is required.

### Depth Over Breadth
Aleksei prefers to fully understand a concept—including edge cases and concrete examples—before advancing to the next fact.

### Concrete Grounding
Abstract explanations should be accompanied by real examples (e.g., actual JSON-RPC message structures with field-level annotation).

### Reliability Analysis Matters
Aleksei proactively evaluates system failure modes (e.g., hallucinated answers, sycophantic acceptance of wrong responses) and expects Claude to surface risks and mitigations, not just execute mechanics.

### Collaborative System Design
When issues are found (e.g., the silent skew correction), Aleksei and Claude co-draft corrective instructions to be applied project-wide.

---

## Approach & Patterns

- Sessions are structured around the EL/category system with explicit navigation commands
- Aleksei asks technically precise clarifying questions, often probing the boundaries of specifications (e.g., what is MCP-defined vs. server-author-defined)
- Demonstrates strong ability to infer system behavior from first principles (e.g., correctly deducing that sampling requests must embed prompts in the JSON-RPC payload)
- Engages in meta-level system improvement: identifying bugs in the learning system itself and proposing fixes
