# Agent42 — 5-minute demo script

> Read this on stage. The single demo asset is the 90-second cross-channel hand-off.
> Everything else exists to make those 90 seconds work flawlessly.

## Setup (10 minutes before)

- [ ] Bring own router · 4G hotspot warmed up
- [ ] Pre-warm Groq + Deepgram credits — burn 5 calls so the first demo turn isn't a cold start
- [ ] Load test against Groq's **6,000 TPM / 30 RPM free-tier ceiling**
- [ ] Langfuse trace panel open in tab 2
- [ ] Exec dashboard pre-rendered in tab 3
- [ ] Phone with WhatsApp + LiveKit QR ready
- [ ] Backup 90-second video queued (do **not** pre-record slides)

## 0:00–0:30 — Hook

> "Fatima Al Mansouri, an Emirati citizen in Ajman, is 4 months behind on her Sheikh Zayed Housing
> Programme payments after a medical emergency. Today she calls the contact center — 40 minute
> wait. Gets redirected. Sends WhatsApp. Sends email. Visits a branch. Five days minimum.
> *That's the problem.*"

## 0:30–1:30 — Live cross-channel demo (3-pane split)

1. **WhatsApp:** Fatima sends `أحتاج تأجيل قسط السكن`. Agent42 replies in Arabic, asks for her salary slip.
2. **PDF upload:** Agent42 OCRs (Docling) → risk scorer → SZHP rules engine → proposes 12-month plan.
3. **Voice switch:** scan QR → joins the voice channel (LiveKit when configured; text-as-voice
   fallback keeps the demo bulletproof). Fatima speaks in Arabic. Agent42 greets her by name:
   > "أهلًا فاطمة، أرى أنك بدأت طلب إعادة جدولة"
   **This is the wow moment.** Sentiment overlay shows stress in her voice; Agent42 adjusts tone.

## 1:30–2:30 — The brain

Switch to architecture screen. Walk the actual Langfuse trace:

> Router → Memory → HousingAgent → tools → Critic → Composer

Click a node. Show the reasoning.

> "Agent42 isn't pretending — here's his actual thought process, captured for audit."

## 2:30–3:15 — Federal-grade differentiators

- Audit trail panel (PDPL-aligned) — every decision step replayable
- Bias detector flags a sample biased output; system rejects it
- **Kill the primary LLM key. Redo a turn. Still answers.** Provider-agnostic cloud cascade
  (Groq → OpenAI/Claude → Gemini) fails over automatically; rules/heuristics degrade gracefully.
- Co-pilot view: human agent sees live sentiment, suggested replies, full context — handling 3× cases.

## 3:15–4:00 — Scale + impact

Executive dashboard.

> "174 services siloed today. Agent42 unifies them with one architecture. We've vertical-sliced
> Housing — the same supervisor extends to Energy, Transport, Maritime."

Projected: ~60% deflection, AHT reduction, citizen-hours saved. Tie back to **UAE National AI Strategy 2031**.

## 4:00–4:45 — 90-day pilot plan

One slide:
- **Days 1–30:** integrate one MOEI service line (Customer Happiness team) · real UAE PASS sandbox · Azure UAE North / Core42
- **Days 31–60:** shadow mode against real traffic · measure deflection, accuracy, CSAT
- **Days 61–90:** limited GA on housing arrears + 2 more services with human-in-the-loop

Named sponsors: **MOEI Customer Happiness Centre + Sheikh Zayed Housing Programme**.

## 4:45–5:00 — Close

> "حسن. خدمة حكومة الإمارات بذكاء يستحقه المواطن."
> "Agent42. UAE government service with the intelligence its citizens deserve."

Land the plane.

---

## Q&A crushers — rehearsed

| Question                          | Answer                                                                                                |
| --------------------------------- | ----------------------------------------------------------------------------------------------------- |
| PDPL compliance?                  | Synthetic demo data; article-by-article mapping in repo; minimization; right-to-explanation via audit |
| Why Jais, not GPT-4?              | Sovereignty + UAE-aligned, on-prem-capable in production. Jais for Arabic, frontier for reasoning     |
| Hallucination on policy?          | Tools, not LLMs, encode policy. Agent calls `szhp_rules_engine`. Show the code                        |
| Cost at scale?                    | Per-conversation cost well under AED 1 (Groq/Cerebras free→paid tiers; cache + batch at scale)        |
| Khaliji vs MSA vs expat?          | Jais handles MSA + Khaliji; gateway language detect; Hindi/Urdu/Tagalog fallback via Gemini           |
| Supervisor LLM down?              | Auto-failover across cloud providers (Groq→OpenAI/Claude→Gemini); heuristics if all are down          |
| Multi-agent or single-agent?      | Genuine multi-agent: each worker has own context, tools, system prompt, parallel — show parallel trace|

## Pivot rules

- **Day 7** no working web→supervisor→HousingAgent→tool flow with Langfuse traces → drop Reflection + SenseVoice, keep voice + WhatsApp
- **Day 11** Arabic voice quality poor → drop live voice, pre-record clip, double down on WhatsApp + web
- **Native AR speaker flags Jais Khaliji as embarrassing** → switch Arabic to Gemini 2.5 Pro for demo, cite Jais as on-prem prod target
- **Teammate burnt out by Day 14** → cut exec dashboard to static Figma; protect demo flow
