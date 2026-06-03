# Hassan — 12-slide deck outline

> Build this as Keynote/Slides. **Do NOT pre-record slides** — judges can tell.
> Use the UAE flag palette: red `#EF3340`, green `#009639`, white, ink `#0C1B2A`.

---

### 1 · Title

- **Hassan**
- Hyper-Adaptive Smart Service Agent for the Nation
- MOEI × 42 Abu Dhabi · AgentEra · Challenge 3
- Team name + logos

### 2 · Citizen story (Mariam)

- Photo of Sharjah skyline
- Headline: *"4 months behind on her SZHP loan after a medical emergency"*
- Today's reality: **5 days, 4 channels, 1 hour wait**
- Tomorrow with Hassan: **90 seconds, 1 conversation, 3 channels**

### 3 · The federal problem

- 174 federal services
- 4 channels per service (web, voice, WhatsApp, mobile)
- Siloed CRMs at MOEI: housing, energy, infrastructure, maritime, transport
- The UAE National AI Strategy 2031 calls for citizen-facing transformation
- **No team here is solving the cross-channel hand-off. We are.**

### 4 · Architecture (1-page diagram)

- Channel Gateway → LangGraph Supervisor → Agno worker agents
- Knowledge layer + Human co-pilot + Langfuse audit
- Callouts: "durable checkpoints" · "parallel sub-agent dispatch" · "tools-not-LLMs for policy"

### 5 · Live demo cue

- "Now we'll switch to the live demo. 90 seconds. Cross-channel. One citizen."
- 3-pane split: WhatsApp · LiveKit (voice) · Web

### 6 · Agentic depth

- Router · Memory · Guardrails · Dispatcher · Reflection · Escalation · Composer
- Parallel sub-agent dispatch (housing now; energy/maritime/transport next pilot)
- Durable checkpoints → Postgres (time-travel debugging on demo day)
- Human-in-the-loop interrupts → co-pilot console

### 7 · Federal-grade

- **PDPL article-by-article mapping** (docs/pdpl-mapping.md)
- Audit trail UI (every decision clickable)
- Bias detector + PII redaction at gateway and composer
- On-prem Ollama fallback (demoed by unplugging Wi-Fi)
- UAE PASS verified identity (sandbox in pilot)

### 8 · Arabic-first

- Jais-Family-30B for Khaliji dialect
- Native RTL UI (not a translated English skin)
- Code-switching: Arabic + English in the same turn handled cleanly
- Translation fallback: Gemini 2.5 Flash for tool outputs

### 9 · Open-source + local fallback

- LangGraph · Agno · LiveKit · Mem0 · Qdrant · Langfuse — all Apache-2.0 or MIT
- Full local stack: Ollama qwen2.5 · Whisper · Kokoro TTS
- *"Unplug the demo laptop's Wi-Fi. It still works."*

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
