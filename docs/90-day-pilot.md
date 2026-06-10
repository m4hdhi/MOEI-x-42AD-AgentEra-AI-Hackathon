# Agent42 — 90-day pilot plan with MOEI

> Detailed plan referenced from slide 11 of the deck. Bring printed copies; specificity moves judges.

## Sponsors (named)

| Role | Department | Why them |
| --- | --- | --- |
| Pilot owner | **MOEI Customer Happiness Centre** | Owns the CSAT KPIs Agent42 moves; budget authority for citizen-channel rollouts |
| Business sponsor | **Sheikh Zayed Housing Programme** | The vertical slice; provides anonymised arrears caseload for shadow-mode evaluation |
| Technical sponsor | **MOEI Digital Government / TDRA liaison** | UAE PASS sandbox access; data residency clearance on Core42 / Azure UAE North |
| Compliance sponsor | **MOEI Data Protection Officer** | PDPL DPIA sign-off; breach notification SOP |

## Phase 1 — Days 1–30: Production integration

| Workstream | Deliverable | KPI / sign-off |
| --- | --- | --- |
| UAE PASS integration | Replace synthetic identities with UAE PASS sandbox; verified `user_id` flow | DPO sign-off |
| Data residency | Deploy on **Azure UAE North** *or* **Core42 / G42 Cloud** (whichever has faster onboarding) | TDRA liaison sign-off |
| WhatsApp production | Migrate from Twilio Sandbox to **Meta WhatsApp Cloud API** under MOEI's Business Account | First 100 production-channel turns logged |
| Consent flow | Production consent screen + record (PDPL Art. 4) | DPO sign-off |
| Voice telephony | LiveKit Cloud → SIP into MOEI's contact-centre PBX | One real call routed end-to-end |
| Federal SSO | Co-pilot console behind MOEI staff SSO | Pen-test pass |

**Phase 1 exit criteria:** one live citizen completes a real housing rescheduling triage through Agent42, with a human co-pilot supervising. Zero PDPL incidents.

## Phase 2 — Days 31–60: Shadow mode

| Workstream | Deliverable | KPI |
| --- | --- | --- |
| Shadow routing | Agent42 handles **read-only** copies of every citizen turn in production; never replies | 100% volume parity |
| Accuracy evaluation | Daily compare Agent42's recommendation vs. human officer's actual decision | Agreement rate **≥ 80%** by D60 |
| Deflection projection | Compute deflection rate assuming Agent42 had replied | Baseline established |
| CSAT comparison | Citizens served by humans are surveyed; Agent42's draft is rated by 3 internal evaluators | Internal CSAT **≥ 4.4 / 5** |
| Bias / drift monitoring | Weekly review of bias detector flags + critic-rejected drafts | Zero high-severity bias incidents in week |
| Cost-per-conversation | Track Groq + Cerebras + ElevenLabs + LiveKit unit economics | Target **< AED 1.00 per conversation** |

**Phase 2 exit criteria:** ≥ 80% recommendation agreement on a 5,000-turn evaluation set. Bias detector flags trending to zero. Cost target met.

## Phase 3 — Days 61–90: Limited GA

| Workstream | Deliverable | KPI |
| --- | --- | --- |
| Live deployment | Agent42 handles **housing arrears triage** as the default first-touch agent, with human escalation for any case scored manual_review | **60%** deflection rate by D90 |
| Service expansion | Stand up `EnergyAgent` and `TransportAgent` workers; route their intents to those workers | 2 services live |
| Citizen audit-trail UI | Public "explain my answer" page citizens can open for any of their cases | First 100 citizen audit accesses |
| AHT reduction | Measure handle time for housing rescheduling vs. baseline | **5 minutes → ≤ 90 seconds** |
| First-response time | Time-to-first-meaningful-reply | **< 5 seconds** |
| CSAT | Per-channel CSAT post-conversation survey | **≥ 4.5 / 5** |

**Phase 3 exit criteria:** ready for full GA across all 174 services with budget approval.

## RACI (executive view)

|  | Pilot owner | SZHP | DPO | 42 AD / Vendor | Agent42 team |
| --- | --- | --- | --- | --- | --- |
| Approve scope | **R** | C | C | I | A |
| Provide UAE PASS sandbox | C | I | C | **R** | A |
| Anonymised data feed | I | **R** | C | I | A |
| PDPL DPIA | C | C | **R** | I | A |
| Build & deploy | I | I | C | I | **R/A** |
| Citizen comms | **R** | C | I | I | A |

## Risk register

| Risk | Likelihood | Mitigation |
| --- | --- | --- |
| UAE PASS sandbox access slow | High | Run Phase 1 with synthetic identities + UAE PASS in parallel; budget 4 weeks |
| Jais Khaliji quality variance | Medium | Native Emirati QA reviewer; fallback to Gemini 2.5 Pro for Arabic if Jais flagged |
| LLM cost overrun at scale | Medium | Provider tiering (Groq/Cerebras), response caching + batching; evaluate UAE-hosted/on-prem model for steady-state traffic post-pilot |
| Critic false positives blocking valid replies | Medium | Threshold tuning weekly; co-pilot review of every blocked draft for first 2 weeks |
| Data residency clarification | Low–Medium | Pre-validated: Azure UAE North + Core42 both meet TDRA criteria |

## Budget envelope (indicative)

- LLM inference (Groq + Cerebras): scales with volume; budgeted **< AED 1.00 / conversation**
- Voice (LiveKit + Deepgram + ElevenLabs): **AED 0.20 / minute** of voice
- Infrastructure (Azure UAE North): standard compute + Postgres + Redis; **AED 25k / month** at pilot volume
- People: 2 backend engineers + 1 frontend + 1 native Arabic QA reviewer + 0.25 FTE DPO

## Success metrics summary

| Metric | Baseline | Phase 2 target | Phase 3 target |
| --- | --- | --- | --- |
| Deflection rate | 0% | n/a (shadow) | **60%** |
| First response time | 40 min wait | <5s (shadow) | **<5s** |
| AHT (housing triage) | 5+ min | n/a | **≤90s** |
| CSAT | n/a | ≥4.4 internal | **≥4.5** |
| Recommendation agreement | n/a | **≥80%** | n/a |
| Cost / conversation | n/a | < AED 1.00 | **< AED 1.00** |
| Bias incidents | n/a | 0 high-severity | **0** |
