# Hassan — 12-slide deck outline

> Build this as Keynote/Slides. **Do NOT pre-record slides** — judges can tell.
> Use the UAE flag palette: red `#EF3340`, green `#009639`, white, ink `#0C1B2A`.

> **Score to the official rubric (100 pts):** Agentic Depth 25 · Federal Impact 25 ·
> Technical Excellence 20 · Demo & Storytelling 15 · Feasibility & Execution 15. Slide map:
> 2/5 → Demo & Storytelling, 6 → Agentic Depth, 7/8/9 → Technical Excellence, 10/11 →
> Federal Impact + Feasibility. (The FAQ's older "Omnichannel 25 / CX 20 / Challenge
> Understanding 20" weighting is superseded by the rubric PDF.)
>
> **Scope framing:** the FAQ marks **Part C (agent co-pilot + leadership dashboard) as out of
> scope** — so we **lead with Parts A+B** (cross-channel continuity, unified profile, automation,
> proactive engagement). The co-pilot and dashboards stay in as *supporting* evidence for
> Technical Excellence + Demo, never as the headline.

---

### 1 · Title

- **Hassan**
- Hyper-Adaptive Smart Service Agent for the Nation
- MOEI × 42 Abu Dhabi · AgentEra · Challenge 3
- Team name + logos

### 2 · Citizen story (Fatima Al Mansouri)

- Photo of Ajman skyline
- Headline: *"4 months behind on her SZHP payments after a medical emergency — and a repeat
  escalator the system should have seen coming"*
- Today's reality: **5 days, 4 channels, 1 hour wait, re-explaining every time**
- Tomorrow with Hassan: **90 seconds, 1 conversation, every channel, never repeats**

### 3 · The federal problem

- 174 federal services
- 4 channels per service (web, voice, WhatsApp, mobile)
- Siloed CRMs at MOEI: housing, energy, infrastructure, maritime, transport
- The UAE National AI Strategy 2031 calls for citizen-facing transformation
- **No team here is solving the cross-channel hand-off. We are.**

### 4 · Architecture (1-page diagram)

- Channel Gateway → one LangGraph supervisor → specialist worker agents (housing/energy/
  transport/maritime/infrastructure)
- Knowledge layer (Postgres FTS) + human co-pilot + Langfuse tracing
- Callouts: "one brain, every channel" · "multi-agent specialist dispatch" · "tools-not-LLMs for policy"

### 5 · Live demo cue

- "Now we'll switch to the live demo. 90 seconds. Cross-channel. One citizen."
- 3-pane split: WhatsApp · Voice · Web

### 6 · Agentic depth

- Router · Sentiment · Memory · Guardrails · Dispatcher · Critic · Escalation · Composer
- Multi-agent specialist dispatch (housing live; energy/maritime/transport/infrastructure same pattern)
- **Dataset-grounded escalation**: fuses CRM/case signals (anger · SLA breach · reopen · repeat-escalator
  · critical · VIP) and escalates on ≥ 2 — *predicts* escalation before the citizen complains
- Every decision step persisted to Postgres → replayable PDPL audit trail
- Escalation → human co-pilot handoff with full cross-channel history

### 7 · Federal-grade

- **PDPL article-by-article mapping** (docs/pdpl-mapping.md)
- Audit trail UI (every decision clickable)
- Bias detector + PII redaction at gateway and composer
- Provider-agnostic cloud cascade — automatic LLM failover, no single-vendor lock-in
- UAE PASS verified identity (sandbox in pilot)

### 8 · Arabic-first

- Jais-Family-30B for Khaliji dialect
- Native RTL UI (not a translated English skin)
- Code-switching: Arabic + English in the same turn handled cleanly
- Translation fallback: Gemini 2.5 Flash for tool outputs

### 9 · Open standards, no lock-in

- LangGraph (orchestration) + Langfuse (tracing) — Apache-2.0 / MIT
- **Provider-agnostic LLM cascade**: Groq · OpenAI/Claude · Jais · Gemini behind one interface —
  swap any provider in one line, graph logic unchanged (e.g. Groq → Cerebras for the 5 demo minutes)
- **$0 RAG**: Postgres full-text search (bilingual EN/AR) today; pgvector when scale demands — no vector-DB lock-in
- **Graceful degradation everywhere**: LLM down → fallback model; model missing → heuristic; never hard-fails
- Containerised → deployable to UAE-region cloud or on-prem (data residency)

### 10 · Impact projections

- Projected deflection rate: **~60%** (industry baseline for vertical-sliced multi-agent CX)
- AHT reduction: **5+ minutes → < 90 seconds** for housing rescheduling triage
- Annual citizen-hours saved: **(MOEI volume × deflection × baseline AHT)**
- Tie back to UAE National AI Strategy 2031 (AED 335B contribution target)

### 11 · 90-day pilot

- **Days 1–30:** integrate Customer Happiness Centre · real UAE PASS sandbox · Azure UAE North / Core42
- **Days 31–60:** shadow mode against real traffic · measure deflection, accuracy, CSAT
- **Days 61–90:** limited GA on housing arrears + 2 more services with human-in-the-loop
- Named sponsors: **MOEI Customer Happiness Centre + Sheikh Zayed Housing Programme**

### 12 · Close

- *"حسن. خدمة حكومة الإمارات بذكاء يستحقه المواطن."*
- *"Hassan. UAE government service with the intelligence its citizens deserve."*
- Single closing line. Land the plane.
