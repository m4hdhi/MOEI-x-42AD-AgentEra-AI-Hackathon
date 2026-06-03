"""Case-level CSAT + CES feedback collection.

  POST /feedback   { case_number, csat, ces, comment }   submit a survey response
  GET  /feedback/stats                                   aggregate for the exec dashboard
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Body, HTTPException

from ..core.db import db_cursor

router = APIRouter(prefix="/feedback", tags=["feedback"])


def _ser(row: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, datetime) else (str(v) if hasattr(v, "hex") and not isinstance(v, (bytes, str)) else v)) for k, v in row.items()}


@router.post("")
def submit_feedback(payload: dict = Body(...)) -> dict:
    """Citizen submits CSAT (1–5) and CES (1–5, 1=very easy)."""
    case_number = (payload.get("case_number") or "").strip()
    csat = payload.get("csat")
    ces = payload.get("ces")
    comment = (payload.get("comment") or "").strip() or None

    if csat is None and ces is None:
        raise HTTPException(400, "csat or ces required")
    if csat is not None and (csat < 1 or csat > 5):
        raise HTTPException(400, "csat must be 1..5")
    if ces is not None and (ces < 1 or ces > 5):
        raise HTTPException(400, "ces must be 1..5")

    case_id, user_id = None, None
    if case_number:
        with db_cursor() as cur:
            cur.execute("SELECT id, user_id FROM cases WHERE case_number = %s", (case_number,))
            row = cur.fetchone()
            if row:
                case_id, user_id = row["id"], row["user_id"]

    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO case_feedback (case_id, case_number, user_id, csat, ces, comment)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (case_id, case_number or None, user_id, csat, ces, comment),
        )
        row = cur.fetchone()
        # If high satisfaction → also mark the case as resolved (closes the loop)
        if case_id and csat and csat >= 4:
            cur.execute(
                "UPDATE cases SET status='resolved', resolved_at = COALESCE(resolved_at, NOW()) "
                "WHERE id = %s AND status NOT IN ('resolved','closed')",
                (case_id,),
            )
        # Emit an activity event so the live ticker shows the feedback
        cur.execute(
            """
            INSERT INTO activity_events (user_id, channel, event_type, summary, payload)
            VALUES (%s, 'web', 'feedback_received', %s, %s::jsonb)
            """,
            (user_id, f"CSAT {csat}/5 · CES {ces}/5 for {case_number or '(no case)'}",
             '{"csat":' + str(csat or 'null') + ',"ces":' + str(ces or 'null') + '}'),
        )
    return _ser(row)


@router.get("/stats")
def feedback_stats() -> dict:
    """Aggregate CSAT / CES for the executive dashboard."""
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE submitted_at::date = CURRENT_DATE) AS today,
                AVG(csat) FILTER (WHERE csat IS NOT NULL) AS avg_csat,
                AVG(ces)  FILTER (WHERE ces IS NOT NULL)  AS avg_ces,
                COUNT(*) FILTER (WHERE csat >= 4) AS promoters,
                COUNT(*) FILTER (WHERE csat <= 2) AS detractors,
                COUNT(*) FILTER (WHERE ces <= 2)  AS effortless     -- 1 or 2 = easy
            FROM case_feedback
            WHERE submitted_at > NOW() - INTERVAL '30 days'
            """
        )
        agg = cur.fetchone() or {}
        cur.execute(
            """
            SELECT submitted_at::date AS day,
                   AVG(csat) FILTER (WHERE csat IS NOT NULL) AS avg_csat,
                   AVG(ces)  FILTER (WHERE ces IS NOT NULL)  AS avg_ces,
                   COUNT(*) AS n
            FROM case_feedback
            WHERE submitted_at > NOW() - INTERVAL '14 days'
            GROUP BY day ORDER BY day
            """
        )
        trend = cur.fetchall()
    total = int(agg.get("total") or 0)
    promoters = int(agg.get("promoters") or 0)
    detractors = int(agg.get("detractors") or 0)
    nps_like = round(((promoters - detractors) / total) * 100, 1) if total else 0
    effortless_pct = round((int(agg.get("effortless") or 0) / total) * 100, 1) if total else 0
    return {
        "totals": {
            "responses_30d": total,
            "responses_today": int(agg.get("today") or 0),
            "avg_csat_5": round(float(agg["avg_csat"]), 2) if agg.get("avg_csat") is not None else None,
            "avg_ces_5":  round(float(agg["avg_ces"]),  2) if agg.get("avg_ces")  is not None else None,
            "effortless_pct": effortless_pct,
            "nps_proxy": nps_like,
        },
        "series": [
            {"day": r["day"].isoformat(),
             "avg_csat": round(float(r["avg_csat"]), 2) if r["avg_csat"] is not None else None,
             "avg_ces":  round(float(r["avg_ces"]),  2) if r["avg_ces"]  is not None else None,
             "n": int(r["n"] or 0)}
            for r in trend
        ],
    }
