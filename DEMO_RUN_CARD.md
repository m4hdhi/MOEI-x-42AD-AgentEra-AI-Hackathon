# DEMO RUN CARD — Agent42 Hackathon
## Laptop operator: print this, tape it next to the screen.

---

## PRE-SHOW CHECKLIST (do before 8:30 AM)

- [ ] `make infra-up` — Postgres + Redis running
- [ ] `make api` — API on :8000 (check: `curl localhost:8000/health`)
- [ ] `make web` — Next.js on :3000 (or ngrok URL if demoing WhatsApp externally)
- [ ] `uv run python scripts/import_dataset.py` — demo data loaded
- [ ] WhatsApp webhook live (ngrok tunnel pointing to `/whatsapp/inbound`)
- [ ] Browser tab pre-opened to `http://localhost:3000` (or ngrok URL)
- [ ] Phone with WhatsApp ready, MOEI test number saved
- [ ] Langfuse open in a second tab (bonus: shows live traces during demo)
- [ ] Disable all notifications on laptop (Focus mode ON)
- [ ] Font/zoom bumped to 125% in browser so judges can see text

---

## DEMO FLOW — TARGET 2 MIN 30 SEC

### STEP 1 — Web Chat  (45 sec)

**URL:** `localhost:3000`  or ngrok

1. Click **Sign in with UAE PASS** (mock)
2. Select **Fatima Al Mansouri** (ID: 784199011810004) from the demo identities toggle
3. Navigate to `/chat`
4. Type exactly:
   > *"I'm behind on my Sheikh Zayed housing payments after a medical emergency — what are my options?"*
5. **Wait** for the response — it will include:
   - A rescheduling plan with rule citations (SZHP-R3.x)
   - A case number (`MOEI-CASE-…`)
   - EN + AR response

**Presenter A says:** *"The SZHP rules engine ran in real time — deterministic policy, not a guess. A case was created."*

---

### STEP 2 — WhatsApp  (45 sec)  ← MONEY SHOT

1. Pick up the phone
2. Open WhatsApp, find the MOEI test number
3. Send:
   > *"What's the status of my request?"*
4. Wait for the reply — Agent42 responds with:
   - Fatima's name (no re-introduction)
   - The real case status + SLA timing
   - Her preferred channel recognized

**Presenter A says:** *"Different channel. Same brain. It already knows her — pulled her unified profile by Customer ID. She didn't say who she was. She never has to again."*

> **If WhatsApp is slow (> 10 sec):** Narrator says "WhatsApp's webhook runs async — reply arrives in a few seconds" — fills the gap naturally.

---

### STEP 3 — Proactive Update  (20 sec)

1. Navigate to `localhost:3000/admin`
2. Go to **Citizens** → search **Fatima**
3. Click **Send Status Update**
4. Show the green confirmation + the update logged to her timeline

**Presenter A says:** *"Her case is SLA-breached. We sent her an update before she had to ask. That's proactive engagement."*

---

### STEP 4 — Human Escalation + Co-pilot  (30 sec)

1. Stay in Admin → Citizens → Fatima
2. Point at the **escalation-risk badge** ("Repeat Escalator — 2 signals fired")
3. Navigate to **Agent Co-pilot**
4. Show: live transcript, sentiment indicator, next-best-action, cross-channel history on one screen

**Presenter A says:** *"She's a repeat escalator. Two dataset signals — reopened case plus history — fired before she complained. The human agent sees everything on one screen. Acts in one click."*

---

### OPTIONAL — Executive Dashboard  (if time allows, ~20 sec)

1. Navigate to `localhost:3000/admin` → **Executive Dashboard**
2. Point at: FCR, CSAT, deflection rate, sentiment trend, volume forecast

**Presenter A says:** *"Leadership asks a question in plain language and gets root-cause analysis grounded in real operations."*

---

## FALLBACK PLAN

| Problem | What to do |
|---|---|
| WhatsApp reply doesn't come | Screenshot of a pre-sent WhatsApp reply on phone; say "async webhook, reply is in flight — here's the exact same flow from our pre-run" |
| API returns an error | Say "let me switch to our backup environment" → have `ngrok` tunnel to a pre-warmed API on port 8001 |
| Web won't load | Have a screen recording of the full demo at `~/Desktop/hassan_demo_backup.mp4` — play it and narrate live |
| Case not showing in admin | Pre-load case `MOEI-CASE-DEMO-001` for Fatima in the dataset; this always exists |

---

## URL CHEAT SHEET

| What | URL |
|---|---|
| Homepage | `localhost:3000` |
| Chat | `localhost:3000/chat` |
| Admin | `localhost:3000/admin` |
| Citizens | `localhost:3000/admin/citizens` |
| Co-pilot | `localhost:3000/admin/copilot` |
| Exec Dashboard | `localhost:3000/admin/dashboard` |
| API health | `localhost:8000/health` |
| Langfuse | `localhost:3001` |

---

## TIMING GUIDE

```
0:00 — Presenter A opens on slide 1 (30 sec)
0:30 — Fatima story slide 2 (35 sec)
1:05 — Federal problem slide 3 (25 sec)
1:30 — Architecture slide 4 (20 sec)
1:50 — DEMO STARTS — slide 5 stays on screen
         Step 1 Web (45 sec) → 2:35
         Step 2 WhatsApp (45 sec) → 3:20
         Step 3 Proactive (20 sec) → 3:40
         Step 4 Co-pilot (30 sec) → 4:10
4:10 — Slide 10 Impact (30 sec)
4:40 — Slide 11 Pilot (30 sec)
5:10 — Slide 12 Close (15 sec)
─────────────────────────────────────────
5:25 total (5-sec buffer)
```
