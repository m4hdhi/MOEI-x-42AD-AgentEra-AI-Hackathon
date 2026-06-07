"""Supervisor nodes.

Day 3: Router and Composer are LLM-backed with structured output + graceful keyword fallback.
Memory Loader, Guardrails, Dispatcher, Critic, Escalation remain stubs scheduled for later days
but the graph shape is locked so Langfuse traces look correct from now on.
"""

from __future__ import annotations

import uuid

from loguru import logger

from ..guardrails import check_bias, looks_like_injection, redact_pii
from ..llm import LLMRole, get_llm_with_fallback
from ..memory.episodic import get_episodic_memory
from ..memory.short_term import get_short_term_buffer
from ..workers import (
    run_complaints_agent,
    run_energy_agent,
    run_general_agent,
    run_housing_agent,
    run_infrastructure_agent,
    run_maritime_agent,
    run_transport_agent,
)
from .prompts import COMPOSER_SYSTEM, CRITIC_SYSTEM, ROUTER_SYSTEM
from .schemas import ComposerOutput, CriticVerdict, RouterDecision, Service
from .state import SupervisorState

# ----- Keyword priors (used as fast-path on all channels + LLM hint) -------------
#
# IMPORTANT: the `housing` bucket only triggers the HousingAgent (rules engine + plan math)
# when the user is talking about an actual payment problem (loan, arrears, reschedule,
# behind on payments, mortgage). General informational questions about housing services
# ("what is the housing assistance program?") fall through to the General worker, which
# answers from the scraped MOEI catalog.

_SERVICE_KEYWORDS: dict[Service, dict[str, set[str]]] = {
    "housing": {
        "en": {"loan", "szhp", "arrears", "rescheduling", "reschedule",
               "installment", "instalment", "mortgage", "behind on my",
               "behind on payments", "missed payment", "late payment"},
        "ar": {"قرض", "تأجيل", "قسط", "متأخرات", "إعادة جدولة"},
    },
    "energy": {
        "en": {"power", "electricity", "outage", "blackout", "water bill", "tariff",
               "dewa", "fewa", "sewa", "aadc", "kahramaa", "petrol", "petroleum", "gas"},
        "ar": {"كهرباء", "ماء", "تعرفة", "انقطاع", "وقود", "بترول", "غاز"},
    },
    "maritime": {
        "en": {"boat", "vessel", "ship", "marine", "maritime", "port", "harbor", "harbour",
               "seafarer", "pleasure boat"},
        "ar": {"قارب", "سفينة", "بحري", "ميناء", "بحار"},
    },
    "transport": {
        "en": {"transportation permit", "transport permit", "vehicle permit", "national transportation",
               "truck", "driver license", "driver licence", "fleet"},
        "ar": {"تصريح نقل", "نقل وطني", "مركبة", "رخصة قيادة", "شاحنة"},
    },
    "infrastructure": {
        "en": {"infrastructure", "construction permit", "geological", "road permit",
               "public works", "survey"},
        "ar": {"بنية تحتية", "تصريح بناء", "جيولوجيا", "أعمال عامة", "مسح"},
    },
}


def _detect_language(text: str) -> str:
    arabic_chars = sum(1 for c in text if "؀" <= c <= "ۿ")
    return "ar" if arabic_chars > len(text) * 0.2 else "en"


def _citations_from_hits(hits: list[dict]) -> list[dict]:
    """Keep at most the top 2 unique-URL hits worth citing."""
    out: list[dict] = []
    seen: set[str] = set()
    for h in hits or []:
        url = (h.get("url") or "").strip()
        if not url or url in seen:
            continue
        seen.add(url)
        out.append({"title": h.get("title") or url, "url": url, "source": h.get("source", "kb")})
        if len(out) >= 2:
            break
    return out


def _format_citations_footer(citations: list[dict], language: str, channel: str) -> str:
    if not citations:
        return ""
    if channel == "whatsapp":
        # WhatsApp renders links inline; keep short and plain.
        head = "\n\nأكثر:" if language == "ar" else "\n\nMore info:"
        body = "\n".join(f"• {c['title']}: {c['url']}" for c in citations)
        return f"{head}\n{body}"
    if channel == "voice":
        # Voice TTS reads out loud — skip URLs, just name the sources.
        head = "\n\n(للمزيد:" if language == "ar" else "\n\n(More info from:"
        body = ", ".join(c['title'] for c in citations)
        return f"{head} {body})"
    # Web + mobile: markdown links rendered as clickable pills by the UI.
    head = "\n\n**أكثر:**" if language == "ar" else "\n\n**More info:**"
    body = " · ".join(f"[{c['title']}]({c['url']})" for c in citations)
    return f"{head} {body}"


def _keyword_intent(text: str) -> str | None:
    """Strong, unambiguous intent signals that should override service-based routing.

    Returns an intent only when confident; otherwise None (let the LLM/heuristics decide).
    Ensures complaints always reach the Complaints Agent regardless of which service it's about.
    """
    tl = text.lower()
    if any(k in tl for k in ("complaint", "unacceptable", "horrible", "terrible", "disappointed",
                              "ridiculous", "furious", "angry", "useless", "worst", "no one replies",
                              "nobody replies", "still waiting", "fed up")) \
       or any(k in text for k in ("شكوى", "غير مقبول", "سيئ", "غاضب", "محبط")):
        return "complaint"
    if any(k in tl for k in ("thank", "appreciate", "excellent", "great service", "well done")) \
       or any(k in text for k in ("شكرا", "ممتاز", "أحسنتم")):
        return "appreciation"
    if any(k in tl for k in ("i suggest", "you should", "why don't you", "i recommend", "it would be better")) \
       or "اقترح" in text:
        return "suggestion"
    if any(k in tl for k in ("status of", "where is my", "track my", "any update", "has my", "is my application",
                             "my request", "my application", "approved yet")) \
       or any(k in text for k in ("حالة طلبي", "أين طلبي", "تتبع")):
        return "status_check"
    return None


def _keyword_router(text: str) -> tuple[Service, float, str]:
    """Cheap deterministic prior. Scans for service-specific keywords. Most confident wins.

    Returns (service, confidence, reasoning). Confidence 0.8 when ≥1 keyword matched;
    bumps to 0.9 if ≥2 matched in the same domain.
    """
    lower = text.lower()
    scores: dict[Service, int] = {}
    for svc, by_lang in _SERVICE_KEYWORDS.items():
        en_hits = sum(1 for kw in by_lang["en"] if kw in lower)
        ar_hits = sum(1 for kw in by_lang["ar"] if kw in text)
        total = en_hits + ar_hits
        if total > 0:
            scores[svc] = total

    if not scores:
        return "unknown", 0.3, "no service keywords matched"

    best_svc, best_hits = max(scores.items(), key=lambda kv: kv[1])
    confidence = 0.9 if best_hits >= 2 else 0.8
    reasoning = f"matched {best_hits} {best_svc} keyword(s)"
    return best_svc, confidence, reasoning


# ----- Nodes -------------------------------------------------------------------

async def router_node(state: SupervisorState) -> dict:
    """LLM-backed intent + service classifier with structured output and keyword fallback.

    For WhatsApp we skip the LLM call entirely when the keyword prior is confident enough —
    saves ~25s per turn. The keyword router is right ~90% of the time on housing/energy/etc.,
    and the worker draft is still grounded in tools so a wrong service hint isn't catastrophic.
    """
    text = state.get("text", "")
    channel = state.get("channel", "web")
    hinted_lang = state.get("language") or "auto"

    # Always compute the keyword prior — used both as backstop and as context to the LLM.
    kw_service, kw_conf, kw_reason = _keyword_router(text)
    detected_lang = _detect_language(text) if hinted_lang == "auto" else hinted_lang

    # Strong intent signals (complaint/appreciation/suggestion) override service routing so
    # grievances always reach the Complaints Agent, even with no service keyword.
    forced_intent = _keyword_intent(text)
    if forced_intent:
        logger.info(f"router(intent-override): intent={forced_intent} service={kw_service} lang={detected_lang}")
        return {
            "intent": forced_intent,
            "service": kw_service,
            "language": detected_lang,
            "confidence": max(kw_conf, 0.85),
        }

    # Fast-path on ALL channels when keyword router is confident.
    # Skipping the LLM Router saves ~10s per turn. The keyword router covers all 5 MOEI domains.
    if kw_conf >= 0.8:
        logger.info(
            f"router(kw-fast): service={kw_service} conf={kw_conf} lang={detected_lang} (LLM skipped)"
        )
        tl = text.lower()
        if any(k in tl for k in ("thank", "appreciate", "excellent", "great service")) or any(k in text for k in ("شكرا", "ممتاز")):
            intent = "appreciation"
        elif any(k in tl for k in ("suggest", "you should", "why don't you", "recommend")) or "اقترح" in text:
            intent = "suggestion"
        elif any(k in tl for k in ("complaint", "unacceptable", "horrible", "disappointed", "broken")) or any(k in text for k in ("شكوى", "غير مقبول")):
            intent = "complaint"
        elif any(k in tl for k in ("behind", "arrears", "late", "status", "where is", "track")) or any(k in text for k in ("متأخر", "تأخر", "حالة")):
            intent = "status_check"
        else:
            intent = "service_request"
        return {
            "intent": intent,
            "service": kw_service,
            "language": detected_lang,
            "confidence": kw_conf,
        }

    try:
        llm = get_llm_with_fallback(LLMRole.ROUTER, temperature=0.0)
        structured = llm.with_structured_output(RouterDecision)
        decision: RouterDecision = await structured.ainvoke(
            [
                ("system", ROUTER_SYSTEM),
                (
                    "human",
                    f"Channel: {channel}\n"
                    f"Keyword prior: service={kw_service} (conf={kw_conf:.2f})\n"
                    f"Detected language hint: {detected_lang}\n"
                    f"Citizen message:\n{text}",
                ),
            ]
        )
        logger.info(
            f"router(llm): intent={decision.intent} service={decision.service} "
            f"lang={decision.language} conf={decision.confidence:.2f}"
        )
        return {
            "intent": decision.intent,
            "service": decision.service,
            "language": decision.language,
            "confidence": decision.confidence,
        }
    except Exception as e:
        logger.warning(f"Router LLM failed ({type(e).__name__}: {e}); using keyword fallback")
        # Floor confidence at 0.5 so a merely-ambiguous query isn't auto-escalated (<0.4).
        return {
            "intent": "service_request",
            "service": kw_service,
            "language": detected_lang,
            "confidence": max(kw_conf, 0.5),
        }


async def memory_loader_node(state: SupervisorState) -> dict:
    """Load Redis short-term buffer + Mem0 episodic memory.

    Both are no-ops if their stores aren't reachable, so this never blocks the graph.
    """
    user_id = state.get("user_id", "")
    text = state.get("text", "")
    if not user_id:
        return {"memory_snippets": []}

    buf = get_short_term_buffer()
    turns = await buf.recent(user_id, n=10)
    snippets = [f"[{t['channel']}] {t['role']}: {t['text']}" for t in turns]

    ep = get_episodic_memory()
    facts = await ep.search(user_id=user_id, query=text, limit=5)
    snippets += [f"[memory] {f}" for f in facts]

    if snippets:
        logger.info(
            f"memory: loaded {len(turns)} turns + {len(facts)} facts for user_id={user_id[:10]}…"
        )
    return {"memory_snippets": snippets}


def policy_guardrails_node(state: SupervisorState) -> dict:
    """PII redaction + prompt-injection guard.

    Bias check runs on the draft (post-dispatch), not here. PII redaction here only normalises
    the citizen's message for downstream logging; the original text remains available to the
    worker (which legitimately needs the Emirates ID to do its job).
    """
    text = state.get("text", "")
    if looks_like_injection(text):
        return {
            "pii_redacted": False,
            "policy_blocked": True,
            "block_reason": "prompt_injection_attempt",
        }
    _, redactions = redact_pii(text)
    return {
        "pii_redacted": bool(redactions),
        "policy_blocked": False,
        "block_reason": None,
    }


async def dispatcher_node(state: SupervisorState) -> dict:
    """Invoke worker agent(s).

    Day 5-6: housing branch calls the real HousingAgent (rules + risk + OCR).
    Other services have stub responses showing the extensibility narrative — same
    pattern, just unstubbed in the 90-day pilot.
    """
    service = state.get("service", "unknown")
    intent = state.get("intent", "service_request")
    language = state.get("language", "en")
    text = state.get("text", "")
    user_id = state.get("user_id", "")

    if intent == "escalate_to_human":
        draft = "Connecting you with a human agent now. They'll have your full context."
        return {"worker_draft": draft, "tool_calls": [{"tool": "escalate", "args": {"reason": "explicit_request"}}],
                "handled_by": "Escalation Agent"}

    memory = state.get("memory_snippets", [])

    # Retrieve grounding facts from the MOEI knowledge base (curated facts + crawled pages).
    # Cheap FTS lookup, run unconditionally — the composer decides whether to surface them.
    knowledge_hits: list[dict] = []
    try:
        from ..workers.knowledge import search as kb_search
        knowledge_hits = kb_search(text, lang=language, top_k=3)
    except Exception as e:
        logger.debug(f"knowledge: skipped ({e})")

    # Complaints go to the dedicated Complaints Agent (multi-agent ecosystem), regardless of service.
    if intent == "complaint":
        result_c = await run_complaints_agent(text=text, language=language, memory_snippets=memory)
        draft = result_c.draft_ar if language == "ar" else result_c.draft_en
        return {"worker_draft": draft, "tool_calls": result_c.tool_calls,
                "knowledge_hits": knowledge_hits, "handled_by": "Complaints Agent"}

    if service == "housing":
        # The HousingAgent's full rules-engine flow is meant for actual payment problems.
        # Informational housing questions ("how do I apply for SZHP?") should answer from
        # the catalog instead of asking the citizen for Emirates ID + salary + balance.
        payment_words = (
            "behind", "arrears", "late", "reschedul", "missed", "can't pay", "cannot pay",
            "loan", "installment", "instalment", "mortgage",
            "متأخر", "تأخر", "قسط", "قرض", "تأجيل",
        )
        is_payment_problem = any(k in text.lower() for k in payment_words if k.isascii()) or \
                             any(k in text for k in payment_words if not k.isascii())

        if is_payment_problem:
            result_h = await run_housing_agent(
                text=text, user_id=user_id, language=language, memory_snippets=memory
            )
            draft = result_h.draft_ar if language == "ar" else result_h.draft_en
            return {
                "worker_draft": draft,
                "tool_calls": result_h.tool_calls,
                "housing_decision": result_h.decision.as_dict() if result_h.decision else None,
                "knowledge_hits": knowledge_hits,
                "handled_by": "Housing Agent",
            }
        # Informational housing query → general worker with catalog grounding (fast path)
        result_g = await run_general_agent(text=text, language=language)
        draft = result_g.draft_ar if language == "ar" else result_g.draft_en
        return {"worker_draft": draft, "tool_calls": result_g.tool_calls, "knowledge_hits": knowledge_hits,
                "handled_by": "Housing Agent"}

    # Domain-specific workers — all real responders grounded in the MOEI catalog
    worker_map = {
        "energy": run_energy_agent,
        "transport": run_transport_agent,
        "maritime": run_maritime_agent,
        "infrastructure": run_infrastructure_agent,
    }
    if service in worker_map:
        result = await worker_map[service](text=text, language=language, memory_snippets=memory)
        draft = result.draft_ar if language == "ar" else result.draft_en
        return {"worker_draft": draft, "tool_calls": result.tool_calls, "knowledge_hits": knowledge_hits,
                "handled_by": f"{service.capitalize()} Agent"}

    # service == "unknown" or anything else → General MOEI worker handles it
    # (in-scope = answers from catalog; out-of-scope = polite refusal + redirect to MOEI topics)
    result_g = await run_general_agent(text=text, language=language, memory_snippets=memory)
    draft = result_g.draft_ar if language == "ar" else result_g.draft_en
    return {"worker_draft": draft, "tool_calls": result_g.tool_calls, "knowledge_hits": knowledge_hits,
            "handled_by": "General Service Agent"}


async def critic_node(state: SupervisorState) -> dict:
    """Reflection / Critic — separate LLM call critiques the worker draft.

    On score < 0.7, the supervisor flags it; the Composer is instructed to soften / re-ground.
    The scripted demo moment: a deliberately biased draft → critic catches it → re-plan.
    """
    draft = state.get("worker_draft", "")
    if not draft:
        return {"critic_score": 0.0, "critic_notes": "no draft to critique"}

    try:
        llm = get_llm_with_fallback(LLMRole.CRITIC, temperature=0.0)
        structured = llm.with_structured_output(CriticVerdict)
        verdict: CriticVerdict = await structured.ainvoke(
            [
                ("system", CRITIC_SYSTEM),
                (
                    "human",
                    f"Citizen message:\n{state.get('text', '')}\n\n"
                    f"Worker draft:\n{draft}\n\n"
                    f"Rate accuracy, cultural appropriateness, completeness.",
                ),
            ]
        )
        notes_parts = []
        if not verdict.accurate:
            notes_parts.append("accuracy")
        if not verdict.culturally_appropriate:
            notes_parts.append("cultural register")
        if not verdict.complete:
            notes_parts.append("completeness")
        notes = ", ".join(notes_parts) if notes_parts else "ok"
        if verdict.issues:
            notes += f" | issues: {'; '.join(verdict.issues[:2])}"
        logger.info(f"critic: score={verdict.score:.2f} notes={notes}")
        return {"critic_score": verdict.score, "critic_notes": notes}
    except Exception as e:
        logger.warning(f"Critic LLM failed ({e}); pass-through with score=0.85")
        return {"critic_score": 0.85, "critic_notes": "critic unavailable; pass-through"}


def escalation_node(state: SupervisorState) -> dict:
    """Decide co-pilot escalation. Function of intent, critic score, confidence, recommendation.

    Escalate when:
    - citizen explicitly asks for human
    - critic score below 0.65
    - rules engine recommended manual_review
    - router confidence is very low (<0.4)
    """
    if state.get("intent") == "escalate_to_human":
        return {"escalated": True, "escalation_reason": "explicit citizen request"}
    # Emotion-aware: a high-urgency citizen (emergency, vulnerable person) is fast-tracked.
    if state.get("urgency") == "high":
        emo = state.get("emotion", "neutral")
        return {"escalated": True, "escalation_reason": f"high urgency ({emo}) — priority human handoff"}
    if state.get("critic_score", 1.0) < 0.65:
        return {"escalated": True, "escalation_reason": f"critic flagged ({state.get('critic_notes', '')})"}
    housing = state.get("housing_decision") or {}
    if housing.get("recommendation") == "manual_review":
        return {"escalated": True, "escalation_reason": "rules engine: manual review"}
    if state.get("confidence", 1.0) < 0.4:
        return {"escalated": True, "escalation_reason": "low router confidence"}
    return {"escalated": False, "escalation_reason": None}


async def composer_node(state: SupervisorState) -> dict:
    """LLM-backed final composer. Channel-aware. Structured output. PII + bias safeguarded."""
    channel = state.get("channel", "web")
    language = state.get("language", "en")
    draft = state.get("worker_draft", "")
    service = state.get("service", "unknown")
    escalated = state.get("escalated", False)

    # Only inject memory for housing — it's the only multi-turn flow.
    # For energy/maritime/etc., memory injection causes bleed-through (Composer rewrites
    # the new service's worker draft using stale housing context).
    memory = state.get("memory_snippets", []) if service == "housing" else []

    if state.get("policy_blocked"):
        block_reason = state.get("block_reason", "policy")
        msg_en = (
            "I can't process that request as written. If this was a genuine question, "
            "please rephrase or ask me about your housing, energy, infrastructure, "
            "maritime, or transport needs."
        )
        msg_ar = (
            "لا يمكنني معالجة هذا الطلب كما هو. إذا كان سؤالًا حقيقيًا، يرجى إعادة الصياغة "
            "أو اسألني عن خدمات السكن، الطاقة، البنية التحتية، البحرية أو النقل."
        )
        return {
            "reply": msg_ar if language == "ar" else msg_en,
            "suggested_replies": [],
            "block_reason": block_reason,
        }

    # Route Arabic turns through Jais role; everything else through the primary cascade.
    role = LLMRole.ARABIC if language == "ar" else LLMRole.COMPOSER

    try:
        llm = get_llm_with_fallback(role, temperature=0.4)
        structured = llm.with_structured_output(ComposerOutput)
        memory_block = "\n".join(memory[-5:]) if memory else "(no prior turns)"
        result: ComposerOutput = await structured.ainvoke(
            [
                ("system", COMPOSER_SYSTEM),
                (
                    "human",
                    f"Channel: {channel}\n"
                    f"Language: {language}\n"
                    f"Escalated: {escalated}\n"
                    f"Recent turns:\n{memory_block}\n\n"
                    f"Worker draft to polish:\n{draft}",
                ),
            ]
        )

        # Outbound guardrails: redact any PII the model might have echoed; reject biased output.
        reply, _ = redact_pii(result.reply)
        bias = check_bias(reply)
        hits = state.get("knowledge_hits", []) or []
        citations = _citations_from_hits(hits)
        footer = _format_citations_footer(citations, language, channel)
        if bias:
            logger.warning(f"composer: bias detected, rewriting ({[f.category for f in bias]})")
            safe_en = (
                "I want to be careful with my wording. Let me restate: "
                f"{state.get('worker_draft', '')[:300]}"
            )
            safe_ar = (
                "أحرص على دقة الصياغة. أعيد الصياغة: "
                f"{state.get('worker_draft', '')[:300]}"
            )
            return {
                "reply": (safe_ar if language == "ar" else safe_en) + footer,
                "suggested_replies": [],
                "citations": citations,
            }
        return {"reply": reply + footer, "suggested_replies": result.suggested_replies, "citations": citations}
    except Exception as e:
        logger.warning(f"Composer LLM failed ({type(e).__name__}: {e}); using worker draft verbatim")
        hits = state.get("knowledge_hits", []) or []
        citations = _citations_from_hits(hits)
        footer = _format_citations_footer(citations, language, channel)
        return {
            "reply": draft + footer,
            "suggested_replies": [
                "Tell me about SZHP rescheduling",
                "I want to upload my salary slip",
                "Connect me with a human agent",
            ],
            "citations": citations,
        }


async def fast_compose_node(state: SupervisorState) -> dict:
    """Channel-aware shortcut: skip the Composer LLM call.

    The worker drafts are already grounded in the rules engine / MOEI catalog, so they're
    factually correct. We just need basic channel hygiene:
      - WhatsApp: strip ** bold markers (WhatsApp uses *single asterisks*) + trim to 1500 chars
      - Web/voice/mobile: keep markdown, pass through untouched
      - Generate cheap suggested-reply hints from the service the Router picked
    """
    draft = state.get("worker_draft", "")
    language = state.get("language", "en")
    service = state.get("service", "unknown")
    channel = state.get("channel", "web")

    hits = state.get("knowledge_hits", []) or []
    citations = _citations_from_hits(hits)
    footer = _format_citations_footer(citations, language, channel)
    if footer:
        draft = draft.rstrip() + footer

    if channel == "whatsapp":
        cleaned = draft.replace("**", "*")
        if len(cleaned) > 1500:
            cleaned = cleaned[:1480] + "…"
    else:
        cleaned = draft

    suggestions_en = {
        "housing": ["Show the 24-month plan", "I want to upload a salary slip", "Speak to a human"],
        "energy":  ["Report another issue", "Check tariff slabs", "Speak to a human"],
        "maritime":["List required documents", "What is the fee?", "Speak to a human"],
        "transport":["List required documents", "Check renewal status", "Speak to a human"],
        "infrastructure":["List required documents", "What is the SLA?", "Speak to a human"],
    }
    suggestions_ar = {
        "housing": ["اعرض خطة ٢٤ شهرًا", "أريد رفع كشف الراتب", "أحتاج موظف بشري"],
        "energy":  ["الإبلاغ عن مشكلة أخرى", "تحقق من شرائح التعرفة", "أحتاج موظف بشري"],
        "maritime":["الوثائق المطلوبة", "ما هي الرسوم؟", "أحتاج موظف بشري"],
        "transport":["الوثائق المطلوبة", "تحقق من حالة التجديد", "أحتاج موظف بشري"],
        "infrastructure":["الوثائق المطلوبة", "ما هي مدة المعالجة؟", "أحتاج موظف بشري"],
    }
    suggestions = (suggestions_ar if language == "ar" else suggestions_en).get(service, [])

    return {"reply": cleaned, "suggested_replies": suggestions[:3], "citations": citations}


_VOICE_SENTIMENT_CACHE: dict[str, float] = {}


def _keyword_sentiment(text: str) -> float:
    """Cheap lexicon score. Fast baseline used for all channels + as voice fallback."""
    t = text.lower()
    neg_kw = (
        "behind", "arrears", "late", "lost", "fired", "can't pay", "cannot pay", "stressed",
        "worried", "angry", "frustrated", "unacceptable", "horrible", "disappointed", "delayed",
        "broken", "complaint", "stuck", "ignored", "rude", "useless",
        "متأخر", "تأخر", "غاضب", "محبط", "شكوى", "غير مقبول", "فظيع",
    )
    pos_kw = (
        "thank", "thanks", "appreciate", "great", "excellent", "amazing", "fantastic",
        "helpful", "wonderful", "smooth", "easy", "perfect",
        "شكرا", "ممتاز", "رائع",
    )
    neg = sum(1 for k in neg_kw if k in t)
    pos = sum(1 for k in pos_kw if k in t)
    if neg == 0 and pos == 0:
        return 0.6
    return max(0.05, min(0.98, 0.5 + 0.15 * (pos - neg)))


async def _llm_sentiment(text: str) -> float | None:
    """One-shot OpenAI sentiment classifier. Returns float in [0,1] or None on error.

    Used for the voice channel — STT transcripts often miss the emotional cues
    (capitalisation, punctuation) that lexicon scoring relies on, so a small LLM
    pass improves accuracy materially on the voice path.
    """
    cache_key = text[:200]
    if cache_key in _VOICE_SENTIMENT_CACHE:
        return _VOICE_SENTIMENT_CACHE[cache_key]
    try:
        llm = get_llm_with_fallback(LLMRole.ROUTER, temperature=0.0)
        msg = await llm.ainvoke([
            ("system",
             "Rate the emotional sentiment of a UAE citizen's message on a 0..1 scale. "
             "0.0 = furious/distressed. 0.5 = neutral. 1.0 = delighted. "
             "Respond ONLY with the number, e.g. '0.32'."),
            ("human", text[:400]),
        ])
        raw = (getattr(msg, "content", str(msg)) or "").strip()
        if isinstance(raw, list):
            raw = " ".join(str(p) for p in raw)
        # Pull the first float from the response
        import re
        m = re.search(r"\d+(\.\d+)?", raw)
        if not m:
            return None
        score = max(0.0, min(1.0, float(m.group())))
        _VOICE_SENTIMENT_CACHE[cache_key] = score
        return round(score, 2)
    except Exception as e:
        logger.debug(f"llm-sentiment failed (non-fatal): {e}")
        return None


_URGENCY_KW = (
    "urgent", "emergency", "immediately", "right now", "asap", "today", "can't wait",
    "cannot wait", "elderly", "mother", "father", "child", "baby", "medical", "hospital",
    "no power", "no water", "unsafe", "danger", "leak", "deadline", "evicted",
    "عاجل", "طارئ", "فورا", "حالا", "اليوم", "خطر", "مستشفى", "والدتي", "والدي",
)


def _emotion_label(text: str, sentiment: float) -> str:
    """Map sentiment + cues to an emotion (Emotion-Aware Government, challenge Idea #2)."""
    tl = text.lower()
    if any(k in tl for k in ("furious", "angry", "unacceptable", "outrageous", "ridiculous")) or any(k in text for k in ("غاضب", "غير مقبول")):
        return "angry"
    if any(k in tl for k in ("worried", "anxious", "scared", "afraid", "stressed", "nervous")) or any(k in text for k in ("قلق", "خائف", "متوتر")):
        return "anxious"
    if sentiment < 0.4:
        return "frustrated"
    if sentiment >= 0.75:
        return "satisfied"
    return "neutral"


def _urgency_level(text: str, sentiment: float) -> str:
    tl = text.lower()
    hits = sum(1 for k in _URGENCY_KW if (k in tl if k.isascii() else k in text))
    if hits >= 2 or (hits >= 1 and sentiment < 0.35):
        return "high"
    if hits >= 1:
        return "medium"
    return "low"


# Life Event Detection Engine (challenge Idea #3): infer significant life events and the
# MOEI services they unlock, so the agent can proactively recommend them.
_LIFE_EVENTS = {
    "marriage": (("married", "marriage", "wedding", "getting married", "زواج", "تزوجت"),
                 "Newly married — may qualify for Sheikh Zayed Housing Programme support"),
    "new_home": (("new home", "building a house", "build a house", "new villa", "moved house",
                  "بناء منزل", "منزل جديد", "بيت جديد"),
                 "Building/owning a home — housing grants, connections, and permits apply"),
    "new_baby": (("new baby", "newborn", "had a baby", "expecting", "مولود", "طفل جديد"),
                 "Growing family — review housing eligibility and family services"),
    "retirement": (("retired", "retirement", "pension", "تقاعد", "تقاعدت"),
                   "Retirement — revisit housing instalments and support options"),
    "new_business": (("started a business", "new company", "trade licence", "investor", "شركة جديدة", "رخصة تجارية"),
                     "New business — maritime/transport/energy commercial services may apply"),
    "job_loss": (("lost my job", "unemployed", "laid off", "fired", "فقدت وظيفتي", "عاطل"),
                 "Income change — proactively offer SZHP hardship rescheduling"),
}


def _detect_life_events(text: str) -> list[str]:
    tl = text.lower()
    out = []
    for _, (kws, message) in _LIFE_EVENTS.items():
        if any((k in tl) if k.isascii() else (k in text) for k in kws):
            out.append(message)
    return out[:2]


async def sentiment_node(state: SupervisorState) -> dict:
    """Sentiment + emotion + urgency scoring (Emotion-Aware Government).

    Voice STT loses prosody, so a 1-line LLM call materially helps for voice. We then
    derive an emotion label (angry/anxious/frustrated/satisfied/neutral) and an urgency
    level, which downstream nodes use to adapt tone and prioritise.
    """
    text = state.get("text") or ""
    channel = state.get("channel", "web")
    score = None
    if channel == "voice":
        score = await _llm_sentiment(text)
    if score is None:
        score = _keyword_sentiment(text)
    score = round(score, 2)

    emotion = _emotion_label(text, score)
    urgency = _urgency_level(text, score)
    logger.info(f"sentiment={score:.2f} emotion={emotion} urgency={urgency}")
    return {"sentiment": score, "emotion": emotion, "urgency": urgency}


def next_best_action_node(state: SupervisorState) -> dict:
    """Compute a one-line action hint for the human co-pilot.

    Deterministic — picks from a small playbook based on intent/service/sentiment/escalation.
    The co-pilot UI renders this prominently so the agent knows what to do next.
    """
    intent = state.get("intent", "service_request")
    service = state.get("service", "general")
    escalated = bool(state.get("escalated"))
    sentiment = state.get("sentiment", 0.6) or 0.6
    housing = state.get("housing_decision") or {}

    if escalated and sentiment < 0.35:
        nba = "Acknowledge stress immediately, offer hardship pathway, schedule callback in <24h"
    elif intent == "complaint":
        nba = "Apologize, confirm complaint logged, set 48h follow-up commitment"
    elif intent == "appreciation":
        nba = "Thank the citizen warmly; flag for monthly satisfaction newsletter feature"
    elif intent == "suggestion":
        nba = "Acknowledge suggestion, log to Innovation Box, send Tawasul reference number"
    elif service == "housing" and housing.get("recommendation") == "approve_with_conditions":
        nba = f"Send {housing.get('proposed_plan_months','12')}-month plan e-signature link; flag for officer review of salary docs"
    elif service == "housing" and housing.get("recommendation") == "manual_review":
        nba = "Open case for Customer Happiness officer; commit 3-working-day SLA"
    elif intent == "status_check":
        nba = "Look up case status; if older than SLA, escalate to service owner"
    elif intent == "document_upload":
        nba = "Confirm receipt, run OCR via Docling, route to verification queue"
    elif service in ("energy", "maritime", "transport", "infrastructure"):
        nba = f"Share {service}-service web link, offer Customer Happiness Centre callback"
    else:
        nba = "Confirm citizen need, route to most-relevant MOEI service line"

    # Predictive Complaint Prevention: ML model scores how likely this turn ends escalated.
    risk: dict = {}
    try:
        from ..workers.escalation_model import predict_escalation
        risk = predict_escalation(
            intent=intent, service=service, channel=state.get("channel", "web"),
            sentiment=sentiment, msg_len=len(state.get("text", "")),
        )
    except Exception as e:
        logger.debug(f"escalation risk skipped: {e}")

    life_events = _detect_life_events(state.get("text", ""))

    # Autonomous Resolution (challenge Idea #5): the agent fully resolves simple, low-risk,
    # informational turns end-to-end — no human, no follow-up needed. Status lookups and
    # appreciations are inherently safe to auto-close; other intents must also be low-risk.
    autonomous = (
        not escalated
        and intent in ("status_check", "appreciation")
    ) or (
        not escalated
        and intent == "service_request"
        and risk.get("band") == "low"
        and not (state.get("housing_decision") or {}).get("recommendation") == "manual_review"
    )
    return {
        "next_best_action": nba,
        "escalation_risk": risk,
        "life_events": life_events,
        "autonomous": bool(autonomous),
    }


async def persist_turn_node(state: SupervisorState) -> dict:
    """Side-effect node: Redis + Mem0 + CRM case + activity event. All best-effort."""
    user_id = state.get("user_id", "")
    channel = state.get("channel", "web")
    text = state.get("text", "")
    if not user_id:
        return {}

    buf = get_short_term_buffer()
    await buf.append(user_id, "user", text, channel)
    await buf.append(user_id, "assistant", state.get("reply", ""), channel)

    ep = get_episodic_memory()
    await ep.add(
        user_id=user_id,
        text=f"User on {channel}: {text}",
        metadata={"channel": channel, "service": state.get("service", "unknown")},
    )

    # Stable per-turn reference used for both the case and the audit trail.
    correlation_id = state.get("correlation_id") or state.get("session_id") or uuid.uuid4().hex

    try:
        from ..workers.crm import emit_activity, upsert_case, write_audit_trail

        sentiment = state.get("sentiment")
        case = upsert_case(
            user_id=user_id,
            user_name=state.get("user_name") or None,
            channel=channel,
            intent=state.get("intent", "service_request"),
            service=state.get("service", "general"),
            user_text=text,
            sentiment=sentiment,
            escalated=bool(state.get("escalated")),
            correlation_id=correlation_id,
        )

        # Record the decision trail (one row per node) for the Audit Trail / right-to-explanation.
        citations = state.get("citations") or []
        audit_events: list[tuple[str, dict]] = [
            ("Request", {"channel": channel, "language": state.get("language"),
                         "message": text[:500], "case_number": case.get("case_number") if case else None}),
            ("Router", {"service": state.get("service"), "intent": state.get("intent"),
                        "confidence": state.get("confidence")}),
            ("Sentiment", {"score": sentiment, "emotion": state.get("emotion"), "urgency": state.get("urgency")}),
            ("Guardrails", {"pii_redacted": state.get("pii_redacted", False),
                            "policy_blocked": state.get("policy_blocked", False),
                            "block_reason": state.get("block_reason")}),
            ("Knowledge", {"sources": [{"title": c.get("title"), "url": c.get("url")} for c in citations]}),
            ("Worker", {"handled_by": state.get("handled_by", "General Service Agent"),
                        "tool_calls": state.get("tool_calls", []),
                        "housing_decision": state.get("housing_decision")}),
        ]
        if state.get("critic_score") is not None:
            audit_events.append(("Critic", {"score": state.get("critic_score"), "notes": state.get("critic_notes")}))
        audit_events.append(("Escalation", {"escalated": bool(state.get("escalated")),
                                            "reason": state.get("escalation_reason")}))
        audit_events.append(("Reply", {"text": state.get("reply", "")[:800],
                                       "next_best_action": state.get("next_best_action")}))
        write_audit_trail(correlation_id=correlation_id, user_id=user_id, channel=channel, events=audit_events)

        if case:
            emit_activity(
                event_type="case_created" if state.get("intent") != "status_check" else "turn",
                summary=f"{case['case_number']} · {state.get('intent','?')} · {state.get('service','?')} · {channel}",
                user_id=user_id, user_name=state.get("user_name"), channel=channel,
                payload={"case_id": str(case["id"]), "case_number": case["case_number"],
                          "service": state.get("service"), "intent": state.get("intent"),
                          "priority": case.get("priority"), "sentiment": sentiment},
            )
        if state.get("escalated"):
            emit_activity(
                event_type="escalation",
                summary=f"Escalated to co-pilot · {state.get('escalation_reason','')}",
                user_id=user_id, user_name=state.get("user_name"), channel=channel,
            )

        # Autonomous resolution: close pure-information turns end-to-end, no human needed.
        if case and state.get("autonomous") and state.get("intent") == "status_check":
            try:
                from ..workers.crm import resolve_case_autonomously
                resolve_case_autonomously(case["case_number"])
                emit_activity(
                    event_type="autonomous_resolution",
                    summary=f"🤖 {case['case_number']} resolved autonomously · no human needed",
                    user_id=user_id, user_name=state.get("user_name"), channel=channel,
                    payload={"case_number": case["case_number"]},
                )
            except Exception as e:
                logger.debug(f"autonomous resolve skipped: {e}")

        # Life-event signals → proactive recommendation logged for the co-pilot.
        for ev in state.get("life_events", []) or []:
            emit_activity(
                event_type="life_event",
                summary=f"🎯 Life-event detected · {ev}",
                user_id=user_id, user_name=state.get("user_name"), channel=channel,
                payload={"recommendation": ev},
            )

        if case:
            return {"case_number": case.get("case_number")}
    except Exception as e:
        logger.debug(f"crm/activity wiring failed (non-fatal): {e}")

    return {}
