"""Predictive analytics + workforce planning for the executive dashboard.

Includes:
  - /analytics/volume-forecast  : 7-day demand forecast (seasonal-naive)
  - /analytics/sentiment-trend  : daily sentiment over the last 30 days
  - /analytics/escalation-risk  : top-N users currently at risk of escalation
  - /analytics/heatmap          : day-of-week × hour-of-day demand heatmap + headcount rec
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta

from fastapi import APIRouter, Body, Query

from ..core.db import db_cursor

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Empirical: each agent handles ~6 chats / hr or ~4 calls / hr → use 5 as a middle
CASES_PER_AGENT_HOUR = 5.0


@router.get("/volume-forecast")
def volume_forecast(days: int = Query(7, ge=1, le=30)) -> dict:
    """Seasonal-naive forecast: predicted demand for the next N days = same weekday last week.

    Falls back to the median when there isn't enough history.
    """
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT created_at::date AS day, COUNT(*) AS n
            FROM cases WHERE created_at > NOW() - INTERVAL '60 days'
            GROUP BY day ORDER BY day
            """
        )
        history = cur.fetchall()
    history_by_day = {r["day"]: int(r["n"]) for r in history}
    if not history:
        history_by_day = {}

    # Median for fallback
    counts = list(history_by_day.values())
    median = int(sorted(counts)[len(counts) // 2]) if counts else 50

    today = datetime.utcnow().date()
    actual = []
    for i in range(14, 0, -1):
        d = today - timedelta(days=i)
        actual.append({"day": d.isoformat(), "value": history_by_day.get(d, 0), "kind": "actual"})

    forecast = []
    for i in range(1, days + 1):
        d = today + timedelta(days=i)
        # Look 7 days back
        ref = d - timedelta(days=7)
        if ref in history_by_day:
            base = history_by_day[ref]
        else:
            base = median
        # Add a small 5% upward trend bias
        forecast.append({"day": d.isoformat(), "value": int(round(base * 1.05)), "kind": "forecast"})

    return {
        "as_of": today.isoformat(),
        "method": "seasonal-naive (lag-7) + 5% trend",
        "history": actual,
        "forecast": forecast,
    }


@router.get("/sentiment-trend")
def sentiment_trend(days: int = Query(14, ge=1, le=60)) -> dict:
    # `days` is server-validated via Query(ge=1, le=60), so safe to interpolate
    safe_days = int(days)
    with db_cursor() as cur:
        cur.execute(
            f"""
            SELECT created_at::date AS day,
                   AVG(sentiment) FILTER (WHERE sentiment IS NOT NULL) AS avg,
                   COUNT(*) FILTER (WHERE sentiment < 0.4) AS negative,
                   COUNT(*) AS total
            FROM cases
            WHERE created_at > NOW() - INTERVAL '{safe_days} days'
            GROUP BY day ORDER BY day
            """
        )
        rows = cur.fetchall()
    return {
        "days": days,
        "series": [
            {
                "day": r["day"].isoformat(),
                "avg": round(float(r["avg"]), 2) if r["avg"] is not None else None,
                "negative_count": int(r["negative"] or 0),
                "total": int(r["total"] or 0),
            }
            for r in rows
        ],
    }


@router.get("/escalation-risk")
def escalation_risk(limit: int = Query(10, ge=1, le=50)) -> dict:
    """Top users at risk: many open cases + low sentiment + high-priority cases."""
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT user_id, MAX(user_name) AS user_name,
                   COUNT(*) FILTER (WHERE status IN ('open','in_progress','escalated')) AS open_cases,
                   AVG(sentiment) FILTER (WHERE sentiment IS NOT NULL) AS avg_sentiment,
                   COUNT(*) FILTER (WHERE priority IN ('high','critical')) AS high_priority,
                   MAX(updated_at) AS last_touched
            FROM cases
            WHERE created_at > NOW() - INTERVAL '14 days'
            GROUP BY user_id
            HAVING COUNT(*) FILTER (WHERE status IN ('open','in_progress','escalated')) > 0
            ORDER BY (
                COUNT(*) FILTER (WHERE priority IN ('high','critical')) * 3
                + COUNT(*) FILTER (WHERE status IN ('open','in_progress','escalated')) * 1
                + COALESCE((1 - AVG(sentiment)) * 4, 1)
            ) DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()

    # ML model: probability this citizen escalates, from their profile signals.
    try:
        from hassan.workers.escalation_model import predict_escalation
    except Exception:
        predict_escalation = None  # type: ignore

    items = []
    for r in rows:
        avg_sent = float(r["avg_sentiment"]) if r["avg_sentiment"] is not None else 0.5
        ml = {}
        if predict_escalation is not None:
            # Use the citizen's signal: complaint-leaning if they have high-priority open cases.
            intent = "complaint" if int(r["high_priority"] or 0) > 0 else "service_request"
            ml = predict_escalation(intent=intent, service="unknown", channel="web",
                                    sentiment=avg_sent, msg_len=200)
        items.append({
            "user_id": r["user_id"],
            "user_name": r["user_name"] or "(unknown)",
            "open_cases": int(r["open_cases"] or 0),
            "high_priority": int(r["high_priority"] or 0),
            "avg_sentiment": round(avg_sent, 2) if r["avg_sentiment"] is not None else None,
            "last_touched": r["last_touched"].isoformat() if r["last_touched"] else None,
            "ml_risk": ml.get("risk"),
            "ml_band": ml.get("band"),
            "risk_score": round(
                (int(r["high_priority"] or 0) * 3
                 + int(r["open_cases"] or 0)
                 + (1.0 - avg_sent) * 4),
                1,
            ),
        })
    return {"items": items}


@router.get("/heatmap")
def heatmap() -> dict:
    """Demand heatmap: hour-of-day × day-of-week, plus recommended headcount per slot."""
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT
                EXTRACT(DOW FROM created_at)::int AS dow,
                EXTRACT(HOUR FROM created_at)::int AS hour,
                COUNT(*) AS n
            FROM cases
            WHERE created_at > NOW() - INTERVAL '28 days'
            GROUP BY dow, hour
            ORDER BY dow, hour
            """
        )
        rows = cur.fetchall()

    # PG DOW: 0=Sun..6=Sat
    day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    cell_avg: dict[tuple[int, int], float] = {}
    for r in rows:
        # cases over 4 weeks → avg per weekday occurrence is /4
        cell_avg[(int(r["dow"]), int(r["hour"]))] = float(r["n"]) / 4.0

    cells = []
    for dow in range(7):
        for hour in range(24):
            avg = cell_avg.get((dow, hour), 0.0)
            headcount = max(1, math.ceil(avg / CASES_PER_AGENT_HOUR))
            cells.append({
                "day": day_names[dow],
                "dow": dow,
                "hour": hour,
                "avg_cases": round(avg, 1),
                "recommended_agents": headcount,
            })

    # Workforce summary: agents needed at peak hour
    peak = max(cells, key=lambda c: c["avg_cases"]) if cells else None

    return {
        "cells": cells,
        "peak": peak,
        "model": "avg over last 28d, threshold 5 cases/agent/hr (configurable)",
    }


# ============================ AI LEADERSHIP ADVISOR ============================
# Leadership asks a question in plain language ("Why did satisfaction drop in housing
# this week?"); we assemble the live operational snapshot and an LLM produces a
# root-cause analysis with recommended actions. (Challenge guide Idea #4.)

def _ops_snapshot() -> dict:
    """Compact, structured picture of current operations for the advisor LLM."""
    snap: dict = {}
    try:
        with db_cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) total,
                       COUNT(*) FILTER (WHERE status='open') open,
                       COUNT(*) FILTER (WHERE status='escalated') escalated,
                       COUNT(*) FILTER (WHERE status='resolved') resolved,
                       COUNT(*) FILTER (WHERE intent='complaint') complaints,
                       ROUND(AVG(sentiment)::numeric,2) avg_sentiment
                FROM cases WHERE created_at > NOW() - INTERVAL '7 days'
            """)
            snap["last_7_days"] = {k: (float(v) if isinstance(v, float) else int(v)) if v is not None else 0
                                   for k, v in (cur.fetchone() or {}).items()}
            cur.execute("""
                SELECT service, COUNT(*) n, ROUND(AVG(sentiment)::numeric,2) sent
                FROM cases WHERE created_at > NOW() - INTERVAL '7 days'
                GROUP BY service ORDER BY n DESC
            """)
            snap["by_service"] = [{"service": r["service"], "cases": int(r["n"]),
                                   "avg_sentiment": float(r["sent"]) if r["sent"] is not None else None}
                                  for r in cur.fetchall()]
            cur.execute("""
                SELECT channel, COUNT(*) n FROM cases
                WHERE created_at > NOW() - INTERVAL '7 days' GROUP BY channel ORDER BY n DESC
            """)
            snap["by_channel"] = [{"channel": r["channel"], "cases": int(r["n"])} for r in cur.fetchall()]
            # week-over-week sentiment
            cur.execute("""
                SELECT ROUND(AVG(sentiment) FILTER (WHERE created_at > NOW() - INTERVAL '7 days')::numeric,2) this_week,
                       ROUND(AVG(sentiment) FILTER (WHERE created_at BETWEEN NOW() - INTERVAL '14 days' AND NOW() - INTERVAL '7 days')::numeric,2) last_week
                FROM cases
            """)
            snap["sentiment_wow"] = {k: float(v) if v is not None else None for k, v in (cur.fetchone() or {}).items()}
            cur.execute("""
                SELECT ROUND(AVG(csat)::numeric,2) avg_csat, ROUND(AVG(ces)::numeric,2) avg_ces, COUNT(*) n
                FROM case_feedback WHERE submitted_at > NOW() - INTERVAL '30 days'
            """)
            fb = cur.fetchone() or {}
            snap["feedback_30d"] = {"avg_csat": float(fb["avg_csat"]) if fb.get("avg_csat") is not None else None,
                                    "avg_ces": float(fb["avg_ces"]) if fb.get("avg_ces") is not None else None,
                                    "responses": int(fb.get("n") or 0)}
    except Exception as e:
        snap["error"] = str(e)
    return snap


_ADVISOR_SYSTEM = (
    "You are the MOEI AI Leadership Advisor, briefing a Ministry executive. You are given a "
    "live operational snapshot (JSON) and a question. Answer ONLY from the data. Be concise, "
    "specific, and decision-oriented. If the data doesn't support a claim, say so. "
    "Return: a direct answer, the most likely root causes, and 2-4 concrete recommended actions."
)


@router.post("/advisor")
async def leadership_advisor(payload: dict = Body(...)) -> dict:
    """Natural-language operational Q&A for leadership, grounded in live metrics."""
    question = (payload.get("question") or "").strip()
    if not question:
        return {"error": "question required"}
    snapshot = _ops_snapshot()

    try:
        from hassan.llm import LLMRole, get_llm_with_fallback
        from pydantic import BaseModel, Field

        class AdvisorAnswer(BaseModel):
            answer: str = Field(description="Direct 1-3 sentence answer to the question.")
            root_causes: list[str] = Field(default_factory=list, description="Most likely drivers, from the data.")
            recommended_actions: list[str] = Field(default_factory=list, description="2-4 concrete next steps.")

        llm = get_llm_with_fallback(LLMRole.REASONER, temperature=0.2)
        structured = llm.with_structured_output(AdvisorAnswer)
        result: AdvisorAnswer = await structured.ainvoke([
            ("system", _ADVISOR_SYSTEM),
            ("human", f"Operational snapshot (JSON):\n{json.dumps(snapshot, default=str)}\n\nQuestion: {question}"),
        ])
        return {
            "question": question,
            "answer": result.answer,
            "root_causes": result.root_causes,
            "recommended_actions": result.recommended_actions,
            "snapshot": snapshot,
        }
    except Exception as e:
        # Graceful fallback: return the snapshot with a templated read.
        wow = snapshot.get("sentiment_wow", {})
        delta = None
        if wow.get("this_week") is not None and wow.get("last_week") is not None:
            delta = round((wow["this_week"] - wow["last_week"]) * 100)
        return {
            "question": question,
            "answer": f"Based on the last 7 days: {snapshot.get('last_7_days', {}).get('total', 0)} cases, "
                      f"{snapshot.get('last_7_days', {}).get('complaints', 0)} complaints, "
                      f"average sentiment {snapshot.get('last_7_days', {}).get('avg_sentiment', 'n/a')}."
                      + (f" Sentiment moved {delta:+d}% week-over-week." if delta is not None else ""),
            "root_causes": ["LLM unavailable — showing data summary only."],
            "recommended_actions": ["Review the lowest-sentiment service below.", "Check escalation-risk list."],
            "snapshot": snapshot,
            "degraded": True,
        }
