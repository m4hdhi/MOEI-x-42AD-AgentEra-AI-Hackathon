"""Global Country Intelligence — a strategic advisor for MOEI leadership.

Not a search engine or a dashboard: it turns trusted country data into decision-ready,
executive output in seconds. "Prepare me for a meeting with Germany's Energy Minister" →
an executive briefing with talking points, opportunities, risks, and recommended actions,
grounded only in the country profile (no hallucinated facts).

Endpoints:
  GET  /intel/countries                  list of country cards
  GET  /intel/country/{code}             full profile
  POST /intel/brief                      AI executive briefing for a meeting context
  POST /intel/compare                    side-by-side comparison across dimensions
  POST /intel/ask                        grounded strategic Q&A
  GET  /intel/briefs                      recently generated briefings
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from ..core.db import db_cursor

_AGENTS = Path(__file__).resolve().parents[3] / "agents"
if str(_AGENTS) not in sys.path:
    sys.path.insert(0, str(_AGENTS))

router = APIRouter(prefix="/intel", tags=["country-intelligence"])


def _profile(code: str) -> dict | None:
    with db_cursor() as cur:
        cur.execute("SELECT profile FROM countries WHERE code = %s", (code.upper(),))
        row = cur.fetchone()
        return row["profile"] if row else None


@router.get("/countries")
def list_countries() -> dict:
    with db_cursor() as cur:
        cur.execute(
            """SELECT code, flag, name, name_ar, region, capital, population_m, gdp_usd_b,
                      gdp_per_capita_usd, gdp_growth_pct, uae_trade_usd_b
               FROM countries ORDER BY gdp_usd_b DESC"""
        )
        rows = cur.fetchall()
    return {"count": len(rows), "countries": [_num(r) for r in rows]}


@router.get("/country/{code}")
def get_country(code: str) -> dict:
    p = _profile(code)
    if not p:
        raise HTTPException(404, "country not found")
    return p


# ── AI executive briefing ────────────────────────────────────────────────────
class ExecBrief(BaseModel):
    summary: list[str]              # 3-5 punchy executive bullets
    talking_points: list[str]       # what leadership should say / raise
    opportunities: list[str]        # strategic opportunities for the UAE
    risks: list[str]                # risks / sensitivities to manage
    recommended_actions: list[str]  # concrete next steps
    questions: list[str]            # smart questions to ask the counterpart


class BriefBody(BaseModel):
    code: str
    meeting_context: str | None = None    # e.g. "Energy Minister meeting on green hydrogen"
    language: str = "en"


_SYS = (
    "You are the strategic intelligence advisor to the UAE Ministry of Energy & Infrastructure (MOEI) "
    "leadership. Produce a crisp, decision-ready executive briefing for an international meeting. "
    "Be specific and quantitative, focused on energy, infrastructure, trade, and UAE bilateral cooperation. "
    "Ground EVERYTHING strictly in the provided country profile — never invent figures or agreements. "
    "Write for ministers: short, sharp, actionable. If language is 'ar', write in Arabic."
)


async def _ai_brief(profile: dict, context: str, language: str) -> tuple[ExecBrief | None, str]:
    try:
        from hassan.llm import LLMRole, get_llm_with_fallback  # type: ignore

        llm = get_llm_with_fallback(LLMRole.REASONER, temperature=0.3)
        structured = llm.with_structured_output(ExecBrief)
        prompt = (
            f"Meeting context: {context or 'general leadership readiness'}\n"
            f"Language: {language}\n\n"
            f"Country profile (the only source of truth):\n{json.dumps(profile, ensure_ascii=False)}"
        )
        brief: ExecBrief = await structured.ainvoke([("system", _SYS), ("human", prompt)])
        return brief, "ai"
    except Exception:
        return None, "fallback"


def _fallback_brief(p: dict, context: str, language: str) -> ExecBrief:
    """Deterministic, fully-grounded briefing from the structured profile — always works."""
    ar = language == "ar"
    uae = p.get("uae", {})
    en = p.get("energy", {})
    name = p.get("name")
    summary = [
        f"{name}: GDP ${p.get('gdp_usd_b', 0):,.0f}bn, ${p.get('gdp_per_capita_usd', 0):,.0f}/capita, "
        f"growth {p.get('gdp_growth_pct', 0)}%; population {p.get('population_m', 0)}m.",
        f"Energy: {en.get('renewable_share_pct', '—')}% renewable electricity, target {en.get('renewable_target', '—')}.",
        f"UAE bilateral: {uae.get('trade_trend', '—')}",
        f"Strategic positioning: {uae.get('positioning', '—')}",
    ]
    talking_points = [a.get("title") + " — " + a.get("detail", "") for a in uae.get("agreements", [])][:4]
    opportunities = [f"{o.get('sector')}: {o.get('title')} — {o.get('detail')}" for o in p.get("opportunities", [])]
    risks = p.get("risks", [])
    recommended_actions = [
        f"Advance {o.get('title')}" for o in p.get("opportunities", [])[:3]
    ] or ["Reaffirm bilateral cooperation and identify a flagship energy/infrastructure project."]
    questions = [
        f"What are {name}'s near-term priorities in {en.get('renewable_target', 'clean energy')}?",
        f"Where can the UAE add most value — investment, technology, or offtake?",
        "What would success from this engagement look like in 12 months?",
    ]
    return ExecBrief(summary=summary, talking_points=talking_points or ["Reaffirm strategic partnership."],
                     opportunities=opportunities, risks=risks,
                     recommended_actions=recommended_actions, questions=questions)


@router.post("/brief")
async def brief(body: BriefBody) -> dict:
    p = _profile(body.code)
    if not p:
        raise HTTPException(404, "country not found")
    brief, mode = await _ai_brief(p, body.meeting_context or "", body.language)
    if brief is None:
        brief = _fallback_brief(p, body.meeting_context or "", body.language)

    year = datetime.now(timezone.utc).year
    with db_cursor() as cur:
        cur.execute("SELECT COUNT(*) AS n FROM country_briefs WHERE reference LIKE %s", (f"BRIEF-{year}-%",))
        ref = f"BRIEF-{year}-{((cur.fetchone() or {}).get('n', 0) + 1):04d}"
        cur.execute(
            """INSERT INTO country_briefs (reference, code, country_name, meeting_context, language,
                 summary, talking_points, opportunities, risks, recommended_actions, questions, generated_by)
               VALUES (%(ref)s,%(code)s,%(name)s,%(ctx)s,%(lang)s,%(sum)s,%(tp)s,%(opp)s,%(risk)s,%(act)s,%(q)s,%(by)s)""",
            {
                "ref": ref, "code": body.code.upper(), "name": p.get("name"),
                "ctx": body.meeting_context, "lang": body.language,
                "sum": "\n".join(brief.summary), "tp": json.dumps(brief.talking_points, ensure_ascii=False),
                "opp": json.dumps(brief.opportunities, ensure_ascii=False),
                "risk": json.dumps(brief.risks, ensure_ascii=False),
                "act": json.dumps(brief.recommended_actions, ensure_ascii=False),
                "q": json.dumps(brief.questions, ensure_ascii=False), "by": mode,
            },
        )
        cur.execute(
            """INSERT INTO activity_events (user_id, user_name, channel, event_type, summary, payload)
               VALUES (NULL,'Leadership','web','country_brief',%s,%s)""",
            (f"{ref} · briefing for {p.get('name')} · {mode}", json.dumps({"reference": ref, "code": body.code})),
        )
    return {"reference": ref, "country": {"code": p.get("code"), "name": p.get("name"), "flag": p.get("flag")},
            "meeting_context": body.meeting_context, "generated_by": mode, "brief": brief.model_dump()}


# ── comparison ───────────────────────────────────────────────────────────────
@router.post("/compare")
def compare(payload: dict = Body(...)) -> dict:
    codes = [c.upper() for c in (payload.get("codes") or [])][:4]
    if len(codes) < 2:
        raise HTTPException(400, "provide at least 2 country codes")
    profs = [p for c in codes if (p := _profile(c))]
    if len(profs) < 2:
        raise HTTPException(404, "countries not found")

    def row(label, fn):
        return {"metric": label, "values": [fn(p) for p in profs]}

    rows = [
        row("GDP (US$ bn)", lambda p: p.get("gdp_usd_b")),
        row("GDP per capita (US$)", lambda p: p.get("gdp_per_capita_usd")),
        row("Real GDP growth (%)", lambda p: p.get("gdp_growth_pct")),
        row("Population (m)", lambda p: p.get("population_m")),
        row("Renewable electricity (%)", lambda p: (p.get("energy") or {}).get("renewable_share_pct")),
        row("Electricity per capita (kWh)", lambda p: (p.get("energy") or {}).get("per_capita_kwh")),
        row("Logistics index", lambda p: (p.get("infrastructure") or {}).get("logistics_index")),
        row("Competitiveness rank", lambda p: (p.get("competitiveness") or {}).get("global_competitiveness_rank")),
        row("UAE non-oil trade (US$ bn)", lambda p: (p.get("uae") or {}).get("non_oil_trade_usd_b")),
    ]
    return {
        "countries": [{"code": p.get("code"), "flag": p.get("flag"), "name": p.get("name")} for p in profs],
        "rows": rows,
    }


# ── grounded strategic Q&A ───────────────────────────────────────────────────
@router.post("/ask")
async def ask(payload: dict = Body(...)) -> dict:
    question = (payload.get("question") or "").strip()
    code = payload.get("code")
    language = payload.get("language", "en")
    if not question:
        raise HTTPException(400, "question required")

    # Ground on a specific country if given, else on all profiles (for comparisons).
    if code:
        profs = [_profile(code)] if _profile(code) else []
    else:
        with db_cursor() as cur:
            cur.execute("SELECT profile FROM countries")
            profs = [r["profile"] for r in cur.fetchall()]
    if not profs:
        raise HTTPException(404, "no country data")

    try:
        from hassan.llm import LLMRole, get_llm_with_fallback  # type: ignore

        llm = get_llm_with_fallback(LLMRole.REASONER, temperature=0.3)
        ctx = json.dumps(profs, ensure_ascii=False)[:14000]
        sys = (
            "You are MOEI leadership's strategic intelligence advisor. Answer concisely and "
            "specifically using ONLY the country data provided. Focus on energy, infrastructure, "
            "trade, and UAE bilateral strategy. If language is 'ar', answer in Arabic."
        )
        msg = await llm.ainvoke([("system", sys), ("human", f"Language: {language}\nData:\n{ctx}\n\nQuestion: {question}")])
        answer = getattr(msg, "content", str(msg))
        if isinstance(answer, list):
            answer = " ".join(str(p) for p in answer)
        return {"answer": answer, "grounded_on": [p.get("code") for p in profs], "mode": "ai"}
    except Exception:
        # Deterministic fallback: surface the most relevant country's headline facts.
        p = profs[0]
        uae = p.get("uae", {})
        return {
            "answer": (f"{p.get('name')}: GDP ${p.get('gdp_usd_b'):,.0f}bn, growth {p.get('gdp_growth_pct')}%. "
                       f"UAE: {uae.get('trade_trend', '—')} {uae.get('positioning', '')}"),
            "grounded_on": [p.get("code") for p in profs], "mode": "fallback",
        }


@router.get("/briefs")
def recent_briefs(limit: int = 20) -> dict:
    with db_cursor() as cur:
        cur.execute(
            """SELECT reference, code, country_name, meeting_context, generated_by, created_at
               FROM country_briefs ORDER BY created_at DESC LIMIT %s""",
            (limit,))
        rows = cur.fetchall()
    return {"items": [_ser(r) for r in rows]}


def _num(row: dict) -> dict:
    out = {}
    for k, v in dict(row).items():
        if hasattr(v, "__float__") and not isinstance(v, (bool, int)):
            try:
                out[k] = float(v)
            except Exception:
                out[k] = v
        else:
            out[k] = v
    return out


def _ser(row: dict) -> dict:
    out = {}
    for k, v in dict(row).items():
        out[k] = v.isoformat() if isinstance(v, datetime) else v
    return out
