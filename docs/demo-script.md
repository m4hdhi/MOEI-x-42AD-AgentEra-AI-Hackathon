# Demo Script — MOEI Omnichannel AI Customer Engagement Agent

A tight 6–7 minute walkthrough that shows **one citizen carried across every channel**, the
**employee co-pilot**, and the **leadership view** — mapped to the evaluation rubric.

> Persona: **Fatima Al Blooshi**, a citizen with a Sheikh Zayed Housing Programme case.
> Pre-req: API on :8000, web on :3000, infra up. Sign in via UAE PASS mock when prompted.

---

## Act 1 — One citizen, every channel (Agentic Depth · 25)

1. **WhatsApp** — From the homepage, scan the "Try on WhatsApp" QR (or open `/chat`).
   Sign in with UAE PASS. Ask: *"I'm behind on my Sheikh Zayed housing loan, what can I do?"*
   → The assistant answers in your language, **creates a case**, and cites the official source.
2. **Voice** — Open `/call`, press the green button, say the same thing.
   → Watch the **live tone meter** react, the transcript build, and *"Logged as case MOEI-CASE-…"*
   appear. Hang up → the call is **recorded, transcribed, summarised and quality-scored**.
3. **Mobile** — Open `/mobile`. Ask *"what's the status of my request?"*
   → It already knows Fatima and her open case — **no repeating information**. This is the
   "same intelligent representative across the journey" the brief asks for.

**Say:** *"One profile, one memory, four channels — the citizen never re-explains anything."*

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

## One-line message for judges
> *We didn't build a chatbot. We built MOEI's unified digital brain — it knows the citizen,
> empowers the employee, and gives leadership real-time, explainable decision support.*
