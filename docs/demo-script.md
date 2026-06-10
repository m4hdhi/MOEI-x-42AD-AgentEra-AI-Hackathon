# Demo Script — MOEI Omnichannel AI Customer Engagement Agent

A tight 6–7 minute walkthrough that shows **one citizen carried across every channel**, the
**employee co-pilot**, and the **leadership view** — mapped to the evaluation rubric.

> Persona: **Fatima Al Mansouri** — an Emirati citizen in **Ajman**, flagged **Repeat Escalator**,
> who has already reached MOEI across WhatsApp, voice, and web (8 / 11 / 3 interactions) about her
> **Sheikh Zayed Housing Programme** case. Sign in via the UAE PASS mock and pick **Fatima Al
> Mansouri (784199011810004)** from the "demo identities" toggle on the login screen.
> Pre-req: `make up` (API :8000, web :3000, infra up, dataset **and** the official service
> catalogue loaded — `make dataset` does both).

---

## Act 1 — One citizen across every channel, never repeating (Agentic Depth · 25)

This is the heart of the challenge (FAQ Q7/Q8): start on the **website**, follow up on
**WhatsApp**, hand off to a **human** — the citizen never re-explains, the AI never loses context.

1. **Website — open a request.** From the homepage `/`, sign in with UAE PASS (Fatima), then open
   `/chat` and type *"I'm behind on my Sheikh Zayed housing payments after a medical emergency —
   what are my options?"*
   → The assistant detects the intent, runs the **SZHP rules engine** (deterministic, not an LLM
   guess), proposes a rescheduling plan, **creates a case** (`MOEI-CASE-…`), and cites the official
   MOEI service. *(Q7: web intent → case · Housing Assistance is FAQ Q4's #1 service)*
2. **WhatsApp — check status, no re-introduction.** Open the WhatsApp surface (scan the homepage
   QR, or reopen `/chat`) and ask *"What's the status of my request?"*
   → It **already knows Fatima** — it pulls her unified profile by Customer ID and returns the real
   case status with SLA timing, **without asking who she is.** *(Q7: cross-channel continuity)*
   > Voice (`/call`) and mobile (`/mobile`) ride the same brain — the live tone meter, transcript,
   > and case logging all read and write the one profile.
3. **Proactive update — before she has to chase.** Her SLA-breached case triggers a **proactive
   status update on her preferred channel** (show it via Admin → Citizens → Fatima → *Send status
   update*, logged to her timeline). *(Q7: proactive engagement)*
4. **Predicted escalation → human with full history.** Fatima is flagged **Repeat Escalator** with
   a reopened case. On a perfectly **calm** status turn, the system **predicts the escalation before
   she complains** — two dataset signals fire (*repeat_escalator + reopened*, per FAQ Q12/Q13) — and
   routes her to a human, who opens the co-pilot to her **entire cross-channel history on one screen.**
   *(Q7: human handoff · Innovation: predictive complaint prevention)*

**Say:** *"One profile, one memory — she switched channels and repeated nothing. And we didn't wait
for her to get angry: the unified profile told us she was about to escalate, so we acted first."*

## Act 2 — The employee co-pilot (Agent enablement)

4. Go to **Admin → Agent Co-pilot**. Show the live transcript, sentiment, **next-best-action**,
   open cases, and the **ML escalation-risk** score.
5. Open **Admin → Citizens → Fatima**. Show the **Digital Twin**: preferred channel, frequent
   services, satisfaction trend, and **predicted next need**. Click **Resolve** / **Send status
   update** → the button turns green and it's logged to the timeline (a real WhatsApp message
   if the citizen is reachable).

**Say:** *"The agent sees everything and acts in one click — and the system predicts who's about
to escalate before they complain."*

## Act 3 — Leadership & intelligence (Federal Impact · 25)

6. Go to **Admin → Executive Dashboard**. Point at FCR, AHT, CES, CSAT, channel deflection,
   sentiment trend, volume forecast, and the workforce heatmap.
7. In the **AI Leadership Advisor**, type: *"Why might satisfaction be at risk this week and what
   should we prioritise?"* → It returns a **root-cause analysis + recommended actions** from live data.
8. Open **Admin → Agent Network** to show the **master agent + specialist agents** architecture,
   then **Admin → Call Recordings** for the contact-centre analytics, and **Admin → Audit Trail**
   (paste a case number) for the **PDPL Article 7** step-by-step explanation.

**Say:** *"Leadership asks a question in plain language and gets an answer grounded in real
operations — with a full audit trail behind every decision."*

## Act 4 — Differentiators (Innovation bonus)

- **Document OCR** — on `/chat`, upload an Emirates ID / salary slip photo → fields extracted by
  vision AI, no typing.
- **Accessibility** — toggle high-contrast and larger-text from the header (♿ icon); voice input
  on chat and call.
- **Predictive complaint prevention** — the escalation-risk model flags at-risk citizens on the
  dashboard before they churn.

---

## Rubric coverage cheat-sheet

| Rubric criterion | Shown in |
|---|---|
| Agentic Depth (25) | Acts 1 & 2 — unified profile, cross-channel context, automation, escalation prediction, NBA |
| Federal Impact (25) | Act 3 — FCR/AHT/CES/CSAT/deflection, proactive updates, faster resolution |
| Technical Excellence (20) | Whole demo — CRM + WhatsApp + voice + mobile + co-pilot + real-time analytics + ML + CV |
| Demo & Storytelling (15) | This script — one journey across channels + employee + leadership |
| Feasibility & Execution (15) | See `docs/feasibility-roadmap.md` |

> **Scope note:** the FAQ marks Part C (co-pilot + leadership dashboard) as *out of scope*, so
> **Act 1 (Parts A+B) is the headline** — Acts 2–3 are supporting evidence for Technical
> Excellence + Demo, not the main act. Open and close on cross-channel continuity.

## One-line message for judges
> *We didn't build a chatbot. We built MOEI's unified digital brain — it knows the citizen,
> empowers the employee, and gives leadership real-time, explainable decision support.*
