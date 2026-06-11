"""Executive dashboard compatibility endpoints backed by live database data.

The richer `/admin/exec` page now reads most data from `/crm/*`, `/analytics/*`,
`/recordings/*`, `/feedback/*`, `/notifications/*`, and `/activity/*`. These `/exec/*`
routes remain for older widgets and smoke tests, but they no longer return fixed demo
numbers.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter

from ..core.db import db_cursor

router = APIRouter(prefix="/exec", tags=["exec"])


@router.get("/kpis")
async def kpis() -> dict:
    """Live executive KPIs from cases, recordings, and feedback."""
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') AS total_turns,
                COUNT(*) FILTER (WHERE channel='whatsapp' AND created_at > NOW() - INTERVAL '24 hours') AS whatsapp,
                COUNT(*) FILTER (WHERE channel='voice' AND created_at > NOW() - INTERVAL '24 hours') AS voice,
                COUNT(*) FILTER (WHERE channel='web' AND created_at > NOW() - INTERVAL '24 hours') AS web,
                COUNT(*) FILTER (WHERE channel='mobile' AND created_at > NOW() - INTERVAL '24 hours') AS mobile,
                COUNT(*) FILTER (WHERE status='escalated' AND created_at > NOW() - INTERVAL '7 days') AS escalated_week,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') AS week,
                COUNT(*) FILTER (WHERE status != 'escalated' AND created_at > NOW() - INTERVAL '7 days') AS not_escalated_week,
                AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)))
                    FILTER (WHERE resolved_at IS NOT NULL AND created_at > NOW() - INTERVAL '7 days') AS avg_handle_time_sec,
                AVG(sentiment) FILTER (WHERE sentiment IS NOT NULL AND created_at > NOW() - INTERVAL '7 days') AS avg_sentiment
            FROM cases
            """
        )
        case = cur.fetchone() or {}
        cur.execute(
            """
            SELECT intent, service, COUNT(*) AS count
            FROM cases
            WHERE created_at > NOW() - INTERVAL '7 days'
            GROUP BY intent, service
            ORDER BY count DESC
            LIMIT 8
            """
        )
        top_intents = [dict(r) for r in cur.fetchall()]
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE risk_score < 0.4) AS low,
                COUNT(*) FILTER (WHERE risk_score >= 0.4 AND risk_score < 0.7) AS medium,
                COUNT(*) FILTER (WHERE risk_score >= 0.7) AS high
            FROM (
                SELECT user_id,
                       LEAST(1.0, (
                           COUNT(*) FILTER (WHERE priority IN ('high','critical')) * 0.25
                           + COUNT(*) FILTER (WHERE status IN ('open','in_progress','escalated')) * 0.10
                           + COALESCE((1 - AVG(sentiment)) * 0.35, 0.15)
                       )) AS risk_score
                FROM cases
                WHERE created_at > NOW() - INTERVAL '14 days'
                GROUP BY user_id
            ) r
            """
        )
        risk = cur.fetchone() or {}
        cur.execute(
            """
            SELECT AVG(csat) AS csat
            FROM case_feedback
            WHERE submitted_at > NOW() - INTERVAL '30 days'
            """
        )
        feedback = cur.fetchone() or {}

    week = int(case.get("week") or 0)
    not_escalated = int(case.get("not_escalated_week") or 0)
    escalated = int(case.get("escalated_week") or 0)
    avg_sentiment = case.get("avg_sentiment")
    csat = feedback.get("csat")
    return {
        "as_of": datetime.now(UTC).isoformat(),
        "agent_name": "Agent42",
        "active_services": ["housing", "energy", "infrastructure", "maritime", "transport"],
        "shadow_services": [],
        "source": "live database",
        "volumes_24h": {
            "total_turns": int(case.get("total_turns") or 0),
            "by_channel": {
                "whatsapp": int(case.get("whatsapp") or 0),
                "voice": int(case.get("voice") or 0),
                "web": int(case.get("web") or 0),
                "mobile": int(case.get("mobile") or 0),
            },
            "by_language": {"ar": 0, "en": 0},
        },
        "kpis": {
            "deflection_rate_pct": round((not_escalated / week) * 100, 1) if week else 0,
            "containment_rate_pct": round((not_escalated / week) * 100, 1) if week else 0,
            "escalation_rate_pct": round((escalated / week) * 100, 1) if week else 0,
            "avg_handle_time_sec": round(float(case.get("avg_handle_time_sec") or 0), 1),
            "first_response_time_sec": 0,
            "csat_5pt": round(float(csat), 1) if csat is not None else (
                round(float(avg_sentiment) * 5, 1) if avg_sentiment is not None else None
            ),
        },
        "top_intents": top_intents,
        "risk_distribution": {k: int(risk.get(k) or 0) for k in ("low", "medium", "high")},
    }


@router.get("/trend")
async def trend() -> dict:
    """Live 7-day trend for older executive dashboard widgets."""
    today = datetime.now(UTC).date()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT created_at::date AS day, channel, COUNT(*) AS n
            FROM cases
            WHERE created_at::date >= CURRENT_DATE - INTERVAL '6 days'
            GROUP BY day, channel
            """
        )
        volume_rows = cur.fetchall()
        cur.execute(
            """
            SELECT created_at::date AS day,
                   COUNT(*) AS total,
                   COUNT(*) FILTER (WHERE status != 'escalated') AS contained,
                   AVG(sentiment) FILTER (WHERE sentiment IS NOT NULL) AS sentiment
            FROM cases
            WHERE created_at::date >= CURRENT_DATE - INTERVAL '6 days'
            GROUP BY day
            """
        )
        kpi_rows = cur.fetchall()

    by_day_channel: dict[tuple[str, str], int] = {
        (r["day"].isoformat(), r["channel"] or "unknown"): int(r["n"]) for r in volume_rows
    }
    by_day_kpi = {r["day"].isoformat(): r for r in kpi_rows}
    return {
        "source": "live database",
        "volume": [
            {
                "day": d.strftime("%a"),
                "whatsapp": by_day_channel.get((d.isoformat(), "whatsapp"), 0),
                "voice": by_day_channel.get((d.isoformat(), "voice"), 0),
                "web": by_day_channel.get((d.isoformat(), "web"), 0),
            }
            for d in days
        ],
        "deflection_pct": [
            round((int((by_day_kpi.get(d.isoformat()) or {}).get("contained") or 0)
                   / max(1, int((by_day_kpi.get(d.isoformat()) or {}).get("total") or 0))) * 100, 1)
            for d in days
        ],
        "csat": [
            round(float((by_day_kpi.get(d.isoformat()) or {}).get("sentiment") or 0) * 5, 1)
            for d in days
        ],
    }
