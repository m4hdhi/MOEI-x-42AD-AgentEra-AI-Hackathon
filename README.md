# Hassan — Hyper-Adaptive Smart Service Agent for the Nation

> MOEI × 42 Abu Dhabi AgentEra AI Hackathon · Challenge 3 — Omnichannel AI Customer Engagement Agent
>
> Vertical-sliced through the **Sheikh Zayed Housing Programme**, architected to extend to all 174 UAE federal services.

---

## What this is

A multi-agent fabric that lets one Emirati citizen carry a single conversation across
**WhatsApp → voice → web → mobile** with persistent memory, Arabic+English (Khaliji-aware),
real-time sentiment, auto-escalation to human co-pilots, and a **live PDPL-aligned audit trail**.

The 5-minute demo: *Mariam from Sharjah, 4 months behind on her SZHP loan, gets a 12-month rescheduling
plan in 90 seconds, jumping from WhatsApp to voice to web — Hassan greets her by name on every channel.*

## Architecture

```
WhatsApp · Voice · Web · Mobile
            │
            ▼
   Channel Gateway (FastAPI)        normalize · user_id · language · correlation_id
            │
            ▼
     LangGraph SUPERVISOR           durable checkpoints → Postgres
   ┌────────────────────────┐
   │ Router                 │  intent + service classification
   │ Memory Loader (Mem0)   │  past interactions, preferences, open cases
   │ Policy Guardrails      │  PII redaction (Presidio) · bias · policy
   │ Service Dispatcher     │  parallel sub-agent dispatch
   │ Reflection / Critic    │  separate LLM critiques the draft
   │ Escalation Decider     │  sentiment × risk × confidence → co-pilot
   │ Response Composer      │  SSML / WhatsApp blocks / JSX cards
   └────────────────────────┘
        │       │       │
        ▼       ▼       ▼
   HousingAgent  EnergyAgent  MaritimeAgent  …  (Agno workers, ~1.7µs instantiation)
        │
        ▼
   Knowledge Layer        Human Co-pilot Console
   · Qdrant (RAG)         · live transcript
   · LightRAG (rules)     · sentiment meter
   · Docling-parsed       · suggested replies
   · Mem0 user memory     · audit trail link
                  │
                  ▼
        Langfuse (every span) · Postgres (audit) · Redis (short-term)
```

## Monorepo layout

```
apps/
  api/        FastAPI Channel Gateway — single ingress, normalizes payloads
  web/        Next.js 15 — citizen chat, co-pilot console, exec dashboard
agents/
  hassan/
    supervisor/   LangGraph state machine (Router → Composer)
    workers/      Agno per-domain workers (HousingAgent first)
    tools/        federal-grade tools (szhp_rules_engine, doc_ocr, …)
    memory/       Mem0 + Qdrant glue
infra/
  docker-compose.yml   Langfuse · Qdrant · Postgres · Redis
  postgres/init.sql    audit table, pgvector
data/                  synthetic SZHP rescheduling cases + PDFs (not committed)
docs/                  PDPL mapping · 90-day pilot deck · demo script
```

## Quick start (local)

```bash
# 1. Bring up infra (Postgres + Redis + Qdrant + Langfuse)
make infra-up

# 2. Python deps (uv)
make sync                      # uv sync + uv pip install -e agents

# 3. Copy env template
cp .env.example .env
cp apps/web/.env.example apps/web/.env.local
# Minimum: set GROQ_API_KEY for the live LLM path.
# Everything else is optional — graceful fallbacks keep the demo running.

# 4. Generate synthetic data (300 SZHP cases + 100 salary slips)
make synth

# 5. Run API
make api

# 6. Run web (separate terminal)
make web-install && make web

# 7. Verify end-to-end
make smoke
make test                      # 16 passed, 1 skipped (Groq-live test runs with key)
```

Open <http://localhost:3000> — landing page with citizen, co-pilot, executive, auditor entrypoints.

| URL | Surface |
| --- | --- |
| `/`         | Brand landing — 4 personas |
| `/chat`     | Citizen web chat (auto-RTL on Arabic) |
| `/copilot`  | Human co-pilot console (live transcript, sentiment, suggested replies) |
| `/exec`     | Executive dashboard (KPIs, trends, risk bands) |
| `/audit`    | Auditor: PDPL Art. 7 right-to-explanation by correlation_id |

Langfuse UI: <http://localhost:3001> (dev login in `infra/docker-compose.yml`).

## Tech stack — locked Day 1

| Layer            | Choice                                                                  |
| ---------------- | ----------------------------------------------------------------------- |
| Orchestrator     | **LangGraph** (durable checkpoints, time-travel debug, HITL interrupts) |
| Worker runtime   | **Agno** (~1.7µs instantiation per their GitHub bench)                  |
| Primary LLM      | Groq `llama-3.3-70b-versatile` (6k TPM / 30 RPM free)                   |
| Long-context     | Google Gemini 2.5 Flash                                                 |
| Arabic specialist| Jais-Family-30B-chat via HF Inference                                   |
| Speed-burst      | Cerebras Inference (~2,100 tps Llama-3.3-70B)                           |
| Local fallback   | Ollama `qwen2.5:7b` (fast path) · `qwen2.5:32b-instruct` (reasoner)     |
| Voice            | LiveKit Agents + Deepgram (EN) + Whisper (AR) + ElevenLabs (AR TTS)     |
| Memory           | Mem0 + Qdrant + Redis                                                   |
| RAG              | Docling → Qdrant · LightRAG for governance rules                        |
| WhatsApp         | Twilio Sandbox (dev) → Meta Cloud API (prod)                            |
| Observability    | Langfuse self-hosted — *this is the audit trail demo*                   |
| Frontend         | Next.js 15 · shadcn/ui · Tailwind · Recharts · native RTL               |
| Backend          | FastAPI · Python 3.12 · Pydantic v2                                     |
| DB               | Postgres 16 + pgvector                                                  |

## Federal-grade differentiators

1. **Cross-channel persistent memory in 90 seconds.** Same `user_id` across WhatsApp/voice/web — most teams skip this entirely.
2. **Genuine multi-agent supervisor with live Langfuse trace on screen.** Click any node, see the actual LLM call.
3. **Real-time voice sentiment + Khaliji-aware Arabic.**
4. **Reflection/critic loop that catches and fixes a bad output live.** Scripted demo moment.
5. **Local Ollama fallback unplugged from Wi-Fi.** Sovereignty point judges love.
6. **PDPL mapping doc, audit UI, bias detector, PII redaction, on-prem story.**
7. **A named agent.** "Hassan" beats "AI Agent v1.2" in judges' memory.

## What's built

All 17 working days are shipped. See [docs/build-plan.md](docs/build-plan.md) for the day-by-day completion table. Highlights:

- **8-node LangGraph supervisor** with structured-output Router/Composer, separate-LLM Critic, escalation routing, and durable checkpoints
- **Role-based LLM cascade** — Groq Llama 3.3 70B (primary) · Jais 30B (Arabic) · Gemini 2.5 Flash (long-ctx) · Ollama qwen2.5:7b (offline fallback). Automatic fall-back with `with_fallbacks()`
- **HousingAgent worker** calling deterministic `szhp_rules_engine`, `risk_score` (with SHAP-style contributions), `doc_ocr` (Docling), `uaepass_lookup`
- **Four channel ingresses**: `/chat/web`, `/voice/turn` + `/voice/token`, `/whatsapp/inbound` (Twilio with signature validation), all sharing the same supervisor
- **Cross-channel memory** via Redis last-20-turns buffer keyed by `user_id` + optional Mem0 episodic memory
- **Three operator UIs**: Citizen chat, Co-pilot console (sentiment, suggested replies, audit), Executive dashboard (Recharts: volumes, deflection, CSAT, risk bands)
- **Federal-grade guardrails**: Emirates ID/IBAN/mobile/email PII redaction at gateway and composer, bias detector with auto-rewrite, prompt-injection guard, PDPL article-by-article mapping in [docs/pdpl-mapping.md](docs/pdpl-mapping.md)
- **Audit trail UI** at `/audit?correlation_id=...` (PDPL Art. 7 right-to-explanation)
- **Synthetic data generator**: 300 SZHP cases + 100 salary slips, PDPL-safe
- **Demo deliverables**: 5-minute stage script ([README-Demo.md](README-Demo.md)), 12-slide deck outline ([docs/deck-outline.md](docs/deck-outline.md)), 90-day pilot plan with named MOEI sponsors and RACI ([docs/90-day-pilot.md](docs/90-day-pilot.md))

## Verification

```bash
make test         # 16 passed, 1 skipped (live Groq path skips without key)
make smoke        # Health + English + Arabic supervisor turns + exec KPIs
```

Live providers light up when their keys are set in `.env`; the demo runs end-to-end without any of them via the Ollama+Redis-no-op cascade.

## Compliance

- Federal Decree-Law No. 45/2021 (UAE PDPL) — synthetic demo data only; consent screen mockup; right-to-explanation via the audit trail UI.
- Data residency target: Microsoft Azure UAE North · AWS Middle East (UAE) · Core42 / G42 Cloud.
- All policy decisions encoded as deterministic Python (`szhp_rules_engine`) — the LLM never invents policy.

## License

Apache-2.0. See [LICENSE](LICENSE).
