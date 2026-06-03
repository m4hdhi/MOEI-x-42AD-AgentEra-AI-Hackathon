"""Post-Call Analyst agent.

Runs after a voice call ends. Takes the full transcript and produces contact-centre
grade analytics that a real QA team would otherwise do by hand:

  - one-line summary + key topics
  - action items / follow-ups
  - first-contact-resolution (resolved?) judgement
  - sentiment trajectory (start vs end)
  - a 0-100 service-quality (QA) score
  - the dominant intent + MOEI service area

LLM-backed with a deterministic keyword fallback so the demo never shows an empty card
even if no API key is configured.
"""

from __future__ import annotations

import json
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from ..llm import LLMRole, get_llm_with_fallback


class CallAnalysis(BaseModel):
    summary: str = Field(description="One or two sentence neutral summary of the call.")
    topics: list[str] = Field(default_factory=list, description="2-4 short topic tags.")
    action_items: list[str] = Field(default_factory=list, description="Concrete follow-ups for staff.")
    intent: str = Field(default="service_request", description="Dominant intent.")
    service: str = Field(default="unknown", description="MOEI service area: housing/energy/transport/maritime/infrastructure/unknown.")
    resolved: bool = Field(default=False, description="True if the citizen's need was fully resolved in this call.")
    escalated: bool = Field(default=False, description="True if the call needed or requested a human agent / escalation.")
    qa_score: int = Field(default=70, description="Service-quality score 0-100.")
    sentiment_start: float = Field(default=0.5, description="Citizen sentiment at start, 0=very negative 1=very positive.")
    sentiment_end: float = Field(default=0.5, description="Citizen sentiment at end, 0=very negative 1=very positive.")


_SYSTEM = (
    "You are a contact-centre quality analyst for the UAE Ministry of Energy and Infrastructure. "
    "You review the transcript of a citizen call handled by the MOEI Smart Assistant and produce "
    "structured analytics. Be objective and concise. Service areas are exactly one of: "
    "housing, energy, transport, maritime, infrastructure, unknown. "
    "qa_score reflects clarity, empathy, accuracy and whether the citizen left satisfied."
)


def _transcript_text(transcript: list[dict[str, Any]]) -> str:
    lines = []
    for t in transcript:
        role = "Citizen" if t.get("role") == "citizen" else "Agent"
        lines.append(f"{role}: {t.get('text','')}")
    return "\n".join(lines)


_NEG = ("angry", "frustrated", "unacceptable", "terrible", "useless", "complaint", "still not",
        "no power", "outage", "stuck", "late", "behind", "can't", "cannot", "worried", "stressed",
        "غاضب", "مشكلة", "متأخر", "غير مقبول")
_POS = ("thank", "thanks", "great", "perfect", "appreciate", "helpful", "resolved", "happy", "good",
        "شكرا", "ممتاز", "رائع")
_RESOLVED = ("thank", "thanks", "that helps", "resolved", "got it", "perfect", "appreciate", "شكرا", "تم")


def _keyword_fallback(transcript: list[dict[str, Any]]) -> CallAnalysis:
    citizen_text = " ".join(t.get("text", "") for t in transcript if t.get("role") == "citizen").lower()
    neg = sum(1 for k in _NEG if k in citizen_text)
    pos = sum(1 for k in _POS if k in citizen_text)
    start = 0.4 if neg else 0.6
    end = min(1.0, 0.5 + 0.15 * pos - 0.1 * neg)
    resolved = any(k in citizen_text for k in _RESOLVED)
    service = "unknown"
    for svc, kws in {
        "housing": ("housing", "loan", "szhp", "reschedul", "sheikh zayed"),
        "energy": ("power", "outage", "electric", "tariff", "bill", "energy"),
        "transport": ("vehicle", "driver", "transport", "licence", "license"),
        "maritime": ("vessel", "boat", "port", "seafarer", "maritime"),
        "infrastructure": ("road", "construction", "infrastructure", "permit"),
    }.items():
        if any(k in citizen_text for k in kws):
            service = svc
            break
    summary = "Citizen contacted the call centre for assistance."
    if transcript:
        first_citizen = next((t.get("text", "") for t in transcript if t.get("role") == "citizen"), "")
        if first_citizen:
            summary = f"Citizen called regarding: {first_citizen[:140]}"
    return CallAnalysis(
        summary=summary,
        topics=[service] if service != "unknown" else ["general enquiry"],
        action_items=[] if resolved else ["Follow up to confirm the citizen's issue is resolved."],
        intent="complaint" if neg > pos else "service_request",
        service=service,
        resolved=resolved,
        qa_score=max(40, min(95, 70 + 8 * pos - 10 * neg)),
        sentiment_start=round(start, 2),
        sentiment_end=round(max(0.0, min(1.0, end)), 2),
    )


async def analyse_call(transcript: list[dict[str, Any]], language: str = "en") -> CallAnalysis:
    """Return structured analysis for a finished call transcript."""
    if not transcript:
        return CallAnalysis(summary="Empty call — no conversation recorded.", qa_score=0)

    convo = _transcript_text(transcript)
    try:
        llm = get_llm_with_fallback(LLMRole.REASONER, temperature=0.2)
        structured = llm.with_structured_output(CallAnalysis)
        result: CallAnalysis = await structured.ainvoke([
            ("system", _SYSTEM),
            ("human", f"Call language: {language}\n\nTranscript:\n{convo}\n\nProduce the analysis."),
        ])
        # Clamp + sanity
        result.qa_score = max(0, min(100, int(result.qa_score)))
        result.sentiment_start = round(max(0.0, min(1.0, float(result.sentiment_start))), 2)
        result.sentiment_end = round(max(0.0, min(1.0, float(result.sentiment_end))), 2)
        if result.service not in ("housing", "energy", "transport", "maritime", "infrastructure", "unknown"):
            result.service = "unknown"
        logger.info(f"postcall: analysed {len(transcript)} turns → service={result.service} resolved={result.resolved} qa={result.qa_score}")
        return result
    except Exception as e:
        logger.warning(f"postcall LLM failed ({type(e).__name__}: {e}); using keyword fallback")
        return _keyword_fallback(transcript)
