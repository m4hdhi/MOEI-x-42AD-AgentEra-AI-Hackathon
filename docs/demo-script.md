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

---

## Scripted CLI demo — `make smoke-demo` (Housing Maintenance journey)

A **deterministic 5-minute** version of Act 1 that runs entirely from the terminal — perfect as a
backup if the UI is flaky, or to show judges the cross-channel logic with nothing to hide. It walks
**one citizen across five channels/touches** and **asserts** continuity at every step.

> **Persona for this run:** **Ahmed Al Mansouri** — Customer ID **`DEMO-001`**, phone
> `+971501234567`, preferred channel **WhatsApp**, **VIP Silver**. He arrives with history: a
> *resolved* Housing Maintenance case from ~3 months ago and an *open* vehicle-registration renewal
> from last week. (Different persona from the Fatima UI walkthrough above — this one is purpose-built
> for the scripted run.)
>
> **Setup (once):** `make api` (API on :8000) in one terminal. Then in another:
> ```bash
> make smoke-demo        # seeds DEMO-001 (idempotent) then runs the 5 steps with assertions
> ```
> The target seeds the citizen for you. To re-run the script alone: `bash scripts/smoke_demo.sh`
> (honours `BASE_URL`). Each step prints PASS/PASS-FAIL and a final scoreboard.

**The journey:** `web → WhatsApp (AR) → proactive push → agent handoff → mobile closure`, keyed by
the single Customer ID the whole way.

| Presenter says | System shows |
|---|---|
| **Step 1 — Website intent.** *"Ahmed opens our website and reports a maintenance problem: 'I have a crack in the ceiling of my MOEI housing unit.' Watch — no menus, no forms."* | A `POST /chat/web` (channel `web`, EN). The supervisor classifies it as a **housing service request**, opens a case, and the response carries a real **`MOEI-CASE-…` number**. The script captures it as `$CASE_ID`. **Rubric:** Agentic Depth (25) — intent → action → case. **Wow:** a plain sentence became a tracked government case in one turn. |
| **Step 2 — WhatsApp follow-up, in Arabic.** *"Now Ahmed switches to WhatsApp and asks in Arabic: 'ما هو آخر تحديث على طلبي؟' — what's the latest on my request? He never tells us who he is."* | A `POST /chat/web` (channel `whatsapp`, AR). The agent resolves him by **Customer ID**, pulls his open case, and replies **in Arabic citing the same `$CASE_ID`** with its status — the script asserts the reply contains that case number. **Rubric:** Agentic Depth (25) — cross-channel continuity. **Wow:** *"Notice the agent knew exactly who Ahmed was on WhatsApp, in Arabic, and referenced the case he opened on the web — without asking him to identify himself again. That's the unified profile in action."* |
| **Step 3 — Proactive update.** *"We don't wait for Ahmed to chase us. The moment the case is assigned, MOEI reaches out to him first — on his preferred channel."* | A `POST /cases/$CASE_ID/trigger-update` pushes *"field visit scheduled for Thursday"* to his **preferred channel (WhatsApp)**, logs it as a **sent notification**, and drops it on the activity timeline (HTTP 200 asserted). **Rubric:** Federal Impact (25) — proactive engagement, fewer inbound contacts. **Wow:** the agency initiates the conversation, not the citizen. |
| **Step 4 — Agent handoff card.** *"Say a human needs to step in. Here's the single screen they get."* | A `GET /crm/agent-context?case_id=$CASE_ID` returns one card: **customer_name, case_summary, sentiment, recommended_action**, and the **full cross-channel interaction_history** (the web + WhatsApp turns — asserted ≥ 2, across both channels). **Rubric:** Agentic Depth (25) + Technical Excellence (20) — context-preserving handoff. **Wow:** the agent inherits the entire history and a recommended next step — zero repetition for the citizen. |
| **Step 5 — Mobile closure.** *"Finally Ahmed opens the mobile app: 'The technician came and fixed it, thank you.' Watch the case close itself."* | A `POST /chat/web` (channel `mobile`). The supervisor detects the **citizen-confirmed resolution**, closes the case end-to-end, and sets **`status=resolved`, `resolution_type=agent_resolved`** (asserted via `GET /crm/cases/$CASE_ID`). **Rubric:** Agentic Depth (25) + Federal Impact (25) — autonomous resolution, higher FCR. **Wow:** no agent, no form — a thank-you on a third channel closed the loop. |

**Close on the scoreboard the script prints:**
> ```
> Cross-channel context preserved: YES
> Case auto-resolved: YES
> ```
> *"One citizen, one Customer ID, four channels — web, WhatsApp, proactive push, mobile — and not
> once did he repeat himself. That's not a chatbot; that's a unified digital brain for MOEI."*

**If a step shows ✗ live:** the most likely cause is the LLM router classifying Step 1 as a
non-housing service or Step 2 not as a status check. Re-run — the assertions are deterministic given
a created case; only the upstream classification is model-driven. The seed and all five endpoints
are deterministic.
