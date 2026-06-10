# 18-day build plan — May 22 to June 8, 2026

Adapted from the strategic playbook. **All build days complete. Day 18 = rest, then hackathon.**

## ✅ Foundation (Days 1–2)

- ✅ Monorepo: `apps/api`, `apps/web`, `agents/`, `infra/`
- ✅ docker-compose: Langfuse + Qdrant + Postgres + Redis
- ✅ `.env.example`, brand identity (Hassan, UAE palette)
- ✅ LangGraph supervisor hello-world

## ✅ Days 3–4 — Supervisor + Channel Gateway

- ✅ Role-based LLM cascade (Groq → OpenAI/Claude → Gemini; Jais for Arabic) with automatic fallback
- ✅ Pydantic structured output on Router and Composer
- ✅ Langfuse tracing callback wired into every graph invocation
- ✅ Gateway hardening: correlation-ID middleware, unified error envelope, gateway-side language detection
- ✅ Redis short-term buffer keyed by `user_id` (cross-channel primitive)

## ✅ Days 5–6 — HousingAgent + Tools

- ✅ `szhp_rules_engine` — deterministic Python with rule citations + EN/AR summaries
- ✅ `risk_score` — weighted scorecard with SHAP-style feature contributions
- ✅ `doc_ocr` — Docling integration with text-fallback for tests
- ✅ `uaepass_lookup` — synthetic identities for demo
- ✅ HousingAgent worker pulls case from text + UAE PASS, calls tools, returns drafts in both languages
- ✅ Synthetic dataset generator: 300 cases + 100 salary slips (`scripts/gen_synthetic_data.py`)

## ✅ Day 7 — Memory + RAG

- ✅ Mem0 episodic memory wired into Memory Loader (no-op when key absent)
- ✅ Qdrant knowledge store stub (rules-engine citations already cover the demo moment)
- ✅ Episodic memory writes user turns on every supervisor run

## ✅ Days 8–9 — Arabic + RTL

- ✅ Inter + Noto Sans Arabic via `next/font/google`
- ✅ Native RTL through `dir="rtl"` toggle per message
- ✅ Arabic turns routed to `LLMRole.ARABIC` (Jais → Gemini fallback → Groq 70B)

## ✅ Days 10–11 — Voice channel

- ✅ `/voice/turn` text-as-voice fallback (channel='voice', cross-channel memory works)
- ✅ `/voice/token` LiveKit access-token issuer (503 when LiveKit not configured)
- ✅ `agents/hassan/voice/livekit_worker.py` — LiveKit Agents entrypoint
  (lazy-imports voice extras; `uv pip install -e '.[voice]'` to enable)

## ✅ Day 12 — WhatsApp

- ✅ Twilio webhook at `/whatsapp/inbound` with signature validation
- ✅ WA-number → Emirates ID demo mapping (lights up cross-channel memory)
- ✅ TwiML response

## ✅ Day 13 — Reflection + Escalation

- ✅ Critic node calls `LLMRole.CRITIC` with `CriticVerdict` schema, scores accuracy / cultural / completeness
- ✅ Escalation routes on: explicit request, critic < 0.65, rules engine `manual_review`, or router confidence < 0.4

## ✅ Day 14 — Co-pilot + Exec dashboards

- ✅ `/copilot/sessions/{user_id}/transcript` — cross-channel turn feed
- ✅ `/copilot/audit/{correlation_id}` — Postgres-backed audit retrieval
- ✅ `/exec/kpis` + `/exec/trend` — demo dashboard data
- ✅ `apps/web/src/app/copilot/page.tsx` — sentiment, suggested replies, audit link
- ✅ `apps/web/src/app/exec/page.tsx` — Recharts dashboard with KPIs + trends + risk bands
- ✅ `apps/web/src/app/audit/page.tsx` — citizen audit trail UI

## ✅ Day 15 — Federal-grade polish

- ✅ `guardrails/pii.py` — Emirates ID / IBAN / mobile / email / card redaction
- ✅ `guardrails/bias.py` — nationality / gender / age / religion / disability stereotype detector
- ✅ `guardrails/prompt_injection.py` — gateway-side prompt-injection guard
- ✅ Gateway-side injection block + Composer-side PII redaction + bias rewrite
- ✅ `docs/pdpl-mapping.md` — article-by-article PDPL compliance map

## ✅ Days 16–17 — Demo + Deck + Pilot

- ✅ `README-Demo.md` — 5-minute stage script with Q&A crushers and pivot rules
- ✅ `docs/deck-outline.md` — 12-slide deck plan
- ✅ `docs/90-day-pilot.md` — named sponsors, RACI, phase exit criteria, budget envelope, success metrics

## Day 18 — Buffer + rest

> Tired teams lose hackathons. Use today.

## Hackathon (June 9–11)

- D1 booth setup, mentor feedback, identify MOEI vs 42 vs industry judges
- D2 integrate mentor feedback, final rehearsal
- D3 deliver — 5 minutes is everything

---

## Verification status

- ✅ `pytest agents/tests/` — 16 passed, 1 skipped (live Groq test, runs when key present)
- ✅ `make smoke` — health + English + Arabic + exec KPIs all return 200 with graceful fallbacks
- ✅ `from hassan.supervisor.graph import build_graph` — graph compiles with 8 nodes
- ⏳ Live Groq path — set `GROQ_API_KEY` to unlock
- ⏳ Live Langfuse traces — set `LANGFUSE_PUBLIC_KEY/SECRET_KEY` after `make infra-up`
- ⏳ Live voice channel — `uv pip install -e '.[voice]'` + LiveKit creds
- ⏳ Live WhatsApp — Twilio Sandbox webhook URL via ngrok

---

## Post-plan updates (hackathon week, aligned to the official docs)

- **WhatsApp → Meta WhatsApp Cloud API** (supersedes the Day 12 Twilio path) — see
  `README-WhatsApp-Meta.md`.
- **Escalation is now dataset-grounded** (supersedes the Day 13 logic): on top of the immediate
  triggers, `escalation_node` fuses the Service-Cases / CRM signals from the dataset — Anger Flag,
  Very-Negative sentiment, SLA breach, Reopen Count > 1, Repeat-Escalator risk, Critical priority,
  Gold/Platinum VIP — and escalates when **≥ 2** fire together (FAQ Q12/Q13). The reason + signals
  persist to the case for the co-pilot. Tests: `agents/tests/test_escalation_rules.py`.
- **Official MOEI service catalogue loaded** into the knowledge base (`scripts/import_services_catalog.py`,
  run by `make dataset`) — 129 services, Arabic, FTS-searchable for smart-search + grounding.
