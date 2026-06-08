# MOEI Omnichannel AI Customer Engagement Agent

> **MOEI × 42 Abu Dhabi · AgentEra AI Hackathon — Challenge 3**
> A unified, intelligent customer-engagement layer for the UAE Ministry of Energy and Infrastructure,
> operating consistently across **WhatsApp, the voice contact centre, the website, and the mobile app**.

Citizens see one assistant — the **MOEI Smart Assistant** — that remembers them across every channel,
answers in Arabic or English, creates and tracks cases, and hands off to a human when needed.
Leadership gets one real-time dashboard; contact-centre agents get an AI co-pilot.

---

## The problem (Challenge 3)

MOEI engages customers across WhatsApp, voice, web, and mobile — but each channel runs in isolation:
fragmented context, repeated customer effort, inconsistent quality, and no unified operational view.
This project is a single agentic AI layer that unifies all four channels.

## What it does

**A · Conversational intelligence (cross-channel)**
- Bilingual (Arabic / English) natural-language understanding with consistent intent classification.
- Retrieval-grounded answers (RAG) over a MOEI knowledge base — every reply can cite its source.
- Persistent citizen context: start on WhatsApp, continue on the app — the assistant remembers.
- Real-time voice tone & sentiment (calm / stressed / frustrated / satisfied) feeding the unified profile.

**B · Operational execution**
- Automated case creation, routing, tracking, and resolution (CRM).
- Smart search across services, policies, FAQs, and procedures — same results on web, mobile, and chat.
- Next-best-action recommendations and proactive WhatsApp follow-ups.

**C · Agent & leadership enablement**
- AI co-pilot for human agents (live transcript, sentiment, suggested next action).
- Executive dashboard: real-time KPIs, sentiment trends, channel performance, escalation risk, forecasting.
- Voice contact-centre analytics: every call recorded, transcribed, summarised, and quality-scored.
- PDPL Article 7 audit trail — replay exactly how any decision was reached.

## Success metrics (on the executive dashboard)
First-contact resolution · average handle time · customer effort score · CSAT · channel deflection.

---

## Architecture

```
        WhatsApp   ·   Voice   ·   Web   ·   Mobile
                          │
                          ▼
              Channel Gateway (FastAPI)         normalise · user_id · language · correlation_id
                          │
                          ▼
              LangGraph SUPERVISOR  (one brain, all channels)
        ┌───────────────────────────────────────────────┐
        │ Router          intent + service + language     │
        │ Sentiment       tone scoring                     │
        │ Memory Loader   cross-channel history (Redis)    │
        │ Guardrails      PII redaction · injection guard  │
        │ Dispatcher ───► service workers + Knowledge RAG  │
        │ Critic          quality self-check               │
        │ Escalation      sentiment × risk × confidence    │
        │ Composer        channel-aware reply + citations  │
        │ Next-Best-Action  co-pilot hint                  │
        │ Persist         case · activity · audit trail    │
        └───────────────────────────────────────────────┘
              │              │                │
              ▼              ▼                ▼
     Service workers   Knowledge base    Post-Call Analyst
   (housing, energy,   (Postgres FTS:    (summary, QA score,
    transport,          curated facts +   FCR, sentiment
    maritime, infra)    crawled pages)    trajectory)
```

## Tech stack

| Layer | Choice |
|---|---|
| Orchestration | **LangGraph** multi-node supervisor |
| Primary LLM | **OpenAI GPT-4o-mini** (quality) · **Groq Llama 3.3 70B** (fast fallback) |
| API | **FastAPI** (Python 3.12, `uv`) |
| Web | **Next.js 15** (App Router, Tailwind) |
| Database | **PostgreSQL 16** — cases, citizens, recordings, knowledge base (full-text search), audit log |
| Cache / memory | **Redis 7** — short-term cross-channel conversation buffer |
| Voice | Browser SpeechRecognition (STT) + **ElevenLabs** streaming TTS (browser TTS fallback) |
| Messaging | **Twilio** WhatsApp (sandbox) |
| Identity | **UAE PASS** (wire-compatible mock for the demo; one env-var switch to staging) |
| Observability | **Langfuse** (LLM traces — engineering only) |

No paid vector DB: the knowledge base uses Postgres full-text search (bilingual), so it runs at $0 and
swaps to pgvector later without changing agent code.

---

## Repository layout

```
apps/
  api/            FastAPI gateway + routes (auth, chat, voice, whatsapp, crm, recordings, …)
  web/            Next.js citizen site + admin console
agents/
  hassan/         LangGraph supervisor, service workers, knowledge + post-call agents, LLM clients
infra/
  docker-compose.yml      Postgres + Redis + Langfuse
  postgres/               init.sql … init_v6 (schema migrations)
scripts/
  crawl_moei.py           crawl moei.gov.ae → knowledge_documents (EN/AR)
  import_dataset.py       loads the official MOEI dataset (CRM, cases, channel logs)
  seed_omnichannel.py     synthetic demo data (cases, notifications, activity)
docs/                     PDPL mapping, 90-day pilot, deck outline
```

---

## Running it locally

**Prerequisites:** Docker, Node 20+, `pnpm`, and [`uv`](https://docs.astral.sh/uv/).

```bash
# 1. Infrastructure (Postgres + Redis + Langfuse)
make infra-up

# 2. Database schema (run each migration in order)
for f in infra/postgres/init.sql infra/postgres/init_v2.sql infra/postgres/init_v3.sql \
         infra/postgres/init_v4_knowledge.sql infra/postgres/init_v5_recordings.sql \
         infra/postgres/init_v6_citizens.sql infra/postgres/init_v7_geo.sql \
         infra/postgres/init_v8_dataset.sql; do
  docker exec -i hassan-postgres psql -U hassan -d hassan < "$f"
done

# 3. Secrets — copy the template and fill in your keys
cp .env.example .env
#   set OPENAI_API_KEY (or GROQ_API_KEY), ELEVENLABS_API_KEY,
#   TWILIO_* , HASSAN_SESSION_SECRET, DATABASE_URL, REDIS_URL

# 4. Python deps + API on :8000
make sync
make api

# 5. Web deps + frontend on :3000  (separate terminal)
make web-install
make web

# 6. Load the official MOEI Omnichannel dataset (200 CRM profiles, 250 cases,
#    300 WhatsApp + 400 voice + 350 web sessions — all linked by Customer ID)
uv run python scripts/import_dataset.py

# 6b. (optional) extra synthetic content + knowledge crawl
make synth                                       # synthetic cases + activity
uv run python scripts/crawl_moei.py --max 250    # crawl moei.gov.ae into the knowledge base
```

Open **http://localhost:3000**.

### Surfaces

| URL | Who | What |
|---|---|---|
| `/` | Citizen | MOEI-styled homepage + smart search + "Try on WhatsApp" |
| `/chat` | Citizen | Chat assistant *(UAE PASS sign-in required)* |
| `/call` | Citizen | Voice contact centre — live tone, recording, case creation |
| `/mobile` | Citizen | Mobile-app channel |
| `/csat` | Citizen | Post-case satisfaction survey |
| `/admin/login` | Staff | Console sign-in (demo password `admin`) |
| `/admin/exec` | Staff | Executive dashboard (KPIs, forecasting, live activity) |
| `/admin/citizens` | Staff | Citizen directory + 360° profile with next actions |
| `/admin/calls` | Staff | Call recordings, transcripts, AI summaries, QA scores |
| `/admin/copilot` | Staff | Live agent co-pilot |
| `/admin/audit` | Staff | PDPL audit trail (look up by case number) |

---

## Data & privacy

- The system runs on the **official MOEI Omnichannel hackathon dataset** — 200 unified CRM
  profiles, 250 service cases, and 1,050 channel interactions (300 WhatsApp + 400 voice +
  350 web/app), all linked by **Customer ID**. `scripts/import_dataset.py` loads every sheet
  into the live schema (`citizens`, `cases`, `interactions`). 186/200 customers span 2+ channels.
- **Cross-channel memory** (the challenge's #1 requirement): `GET /crm/identify?phone=…` resolves
  a caller to their unified profile from any channel — name, VIP tier, risk flag, open cases, and a
  ready-to-speak greeting — so they never repeat themselves. The 360° profile (`/admin/citizens`)
  shows the full WhatsApp→voice→web timeline on one screen.
- The moei.gov.ae service catalogue is public content; synthetic generators remain for stress-testing.
- Citizen interactions are gated behind **UAE PASS sign-in**, so requests are stored against a
  verified identity. PII is redacted in transit; every decision is logged for the right-to-explanation
  audit trail (PDPL Article 7). `.env` secrets are never committed.

---

## Notes for reviewers

- The **browser voice call** is a real recording → transcript → AI-analysis pipeline at $0.
  A physical line on **800 6634** would add Twilio Voice (telephony) — the intelligence layer behind it
  is already built.
- WhatsApp uses the Twilio sandbox (visitors send the join code shown on the homepage card);
  production needs a Meta-verified MOEI WhatsApp Business number — a configuration step, not a rebuild.

*Built for the MOEI × 42 Abu Dhabi AgentEra AI Hackathon.*
