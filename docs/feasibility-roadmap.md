# Feasibility & Execution Roadmap

How this prototype becomes a production MOEI platform — integration, scalability, security,
and a phased deployment plan. (Targets the rubric's Feasibility & Execution Readiness, 15 pts.)

---

## 1. Integration approach (drop into MOEI's real systems)

The prototype is built on clean seams so MOEI's real data sources replace synthetic ones with
**no agent-code changes** — every source maps to an existing table or adapter:

| MOEI source | Integration point | Status today |
|---|---|---|
| **CRM records / customer profiles** | `citizens` + `cases` tables via a thin sync adapter | synthetic → swap to CRM API/DB |
| **WhatsApp** | Twilio webhook → `/whatsapp/inbound` | sandbox → Meta-verified WABA number |
| **Contact centre (NICE) + call recordings** | `call_recordings` + Post-Call Analyst | browser capture → NICE CTI / SIP feed |
| **Knowledge: FAQs, policies, procedures, catalogue** | `knowledge_documents` + `knowledge_facts` (FTS) | crawl → MOEI CMS export + pgvector |
| **Website / mobile / search analytics** | `activity_events` ingestion | demo events → real event stream |
| **Feedback / surveys** | `case_feedback` | live CSAT/CES loop |
| **Identity** | UAE PASS OIDC (`/auth/uaepass/*`) | wire-compatible mock → `id.uaepass.ae` (one env var) |

**Channels** all funnel through one Channel Gateway → one LangGraph supervisor, so adding a
channel is a new adapter, not a new brain.

## 2. Scalability

- **Stateless API** (FastAPI) behind a load balancer — scale horizontally.
- **Postgres** as system of record (managed/HA in production); **Redis** for short-term memory.
- **Knowledge retrieval**: Postgres full-text search today; swap to **pgvector**/managed vector DB
  for semantic search at scale — the retriever is behind one interface.
- **LLM**: provider-agnostic with automatic fallback (OpenAI → Groq). Cache + batch for cost.
- **Async background workers** (notifications dispatcher, post-call analysis) decouple slow work
  from the request path.
- **New specialist agent = one module** under the supervisor — extends to all 174 federal services.

## 3. Security, privacy & governance

- **UAE PASS**-gated citizen interactions; signed HttpOnly session cookies.
- **PII redaction** in transit; **PDPL Article 7 audit trail** records every decision step.
- **Policy in tools, not the LLM** — deterministic rules engines decide eligibility, so answers
  are explainable and consistent.
- Role separation: citizen surface vs. staff console (federated SSO in production).
- Data residency: deployable to UAE-region cloud or on-prem (all components are containerised).

## 4. ML / model operations

- **Escalation-risk model** (scikit-learn) is retrained from `cases` via
  `scripts/train_escalation_model.py`; ships as a versioned artifact, with a transparent
  heuristic fallback if absent. Production: scheduled retraining + drift monitoring.
- **Vision OCR** uses a hosted vision model; can move to an on-prem model for sensitive documents.
- All AI calls are traced (Langfuse) for quality, latency, and cost monitoring.

## 5. Phased deployment plan

| Phase | Duration | Scope |
|---|---|---|
| **0 — Pilot (now)** | built | One programme (SZHP) across 4 channels, synthetic data, full agent + dashboards |
| **1 — Integrate** | ~4 weeks | Connect CRM, NICE, UAE PASS staging, MOEI knowledge export; shadow-mode |
| **2 — Live (limited)** | ~6 weeks | Go live on WhatsApp + web for 2–3 services; human-in-the-loop on escalations |
| **3 — Scale** | ~90 days | All high-volume services, voice line on 800 6634, pgvector, autonomous resolution for simple cases |
| **4 — Federate** | ongoing | Reusable pattern offered to other federal entities; multi-agent ecosystem grows |

## 6. Operational readiness

- One-command local bring-up (`make infra-up`, `make api`, `make web`); migrations in `infra/postgres`.
- Health checks, structured logging, correlation IDs end-to-end.
- Graceful degradation everywhere: LLM down → fallback model; model missing → heuristic; Twilio
  absent → dry-run; vision absent → manual entry. The platform never hard-fails in a demo or in prod.

## 7. Measurable impact targets (pilot KPIs)

- First-Contact Resolution **+15–25%**, Average Handle Time **−30%**, repeated-contact rate **−40%**
  (cross-channel memory), self-service deflection **50%+**, CSAT **+1 point**, and proactive
  complaint prevention reducing escalations **15–20%**. All tracked live on the executive dashboard.
