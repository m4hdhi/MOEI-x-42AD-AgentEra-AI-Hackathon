"""CRM cases REST API. Powers /copilot CRM panel + /exec case stats."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Body, HTTPException, Query

from ..core.db import db_cursor

router = APIRouter(prefix="/crm", tags=["crm"])


def _serialize(row: dict) -> dict:
    out = dict(row)
    for k, v in out.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif hasattr(v, "hex") and not isinstance(v, (bytes, str)):
            # UUID
            out[k] = str(v)
    return out


@router.get("/cases")
def list_cases(
    user_id: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    service: str | None = None,
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    """List recent cases with optional filters."""
    sql = "SELECT * FROM cases WHERE 1=1"
    params: list = []
    if user_id:
        sql += " AND user_id = %s"; params.append(user_id)
    if status:
        sql += " AND status = %s"; params.append(status)
    if priority:
        sql += " AND priority = %s"; params.append(priority)
    if service:
        sql += " AND service = %s"; params.append(service)
    sql += " ORDER BY created_at DESC LIMIT %s"; params.append(limit)
    with db_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {"count": len(rows), "cases": [_serialize(r) for r in rows]}


@router.get("/cases/{case_number}")
def get_case(case_number: str) -> dict:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM cases WHERE case_number = %s", (case_number,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, f"case {case_number} not found")
    return _serialize(row)


@router.get("/kpis")
def operational_kpis() -> dict:
    """Operational KPIs the brief asks for:
      - first_contact_resolution_pct : % of cases resolved without a channel switch and within SLA
      - channel_deflection_pct       : % of cases handled fully by Hassan (status != 'escalated')
      - avg_handle_time_seconds      : avg (resolved_at - created_at) for resolved cases
      - cross_channel_continuity_pct : % of users with multi-channel touches in last 7d
    """
    with db_cursor() as cur:
        # First-Contact Resolution: cases resolved within 1 hour of creation AND only one channel touch
        cur.execute(
            """
            WITH user_channel_counts AS (
                SELECT user_id, COUNT(DISTINCT channel) AS n_channels
                FROM cases
                WHERE created_at > NOW() - INTERVAL '7 days'
                GROUP BY user_id
            )
            SELECT
                COUNT(*) FILTER (
                    WHERE c.status = 'resolved'
                      AND c.resolved_at IS NOT NULL
                      AND c.resolved_at - c.created_at < INTERVAL '1 hour'
                      AND COALESCE(ucc.n_channels, 1) = 1
                ) AS fcr_resolved,
                COUNT(*) AS total_week,
                COUNT(*) FILTER (WHERE c.status != 'escalated') AS not_escalated,
                COUNT(*) FILTER (WHERE c.status = 'resolved') AS total_resolved,
                AVG(EXTRACT(EPOCH FROM (c.resolved_at - c.created_at)))
                    FILTER (WHERE c.resolved_at IS NOT NULL) AS aht_seconds
            FROM cases c
            LEFT JOIN user_channel_counts ucc USING (user_id)
            WHERE c.created_at > NOW() - INTERVAL '7 days'
            """
        )
        agg = cur.fetchone() or {}
        cur.execute(
            """
            SELECT
                COUNT(DISTINCT user_id) FILTER (WHERE channels > 1)::float
                / NULLIF(COUNT(DISTINCT user_id), 0) AS cross_channel_pct
            FROM (
                SELECT user_id, COUNT(DISTINCT channel) AS channels
                FROM cases
                WHERE created_at > NOW() - INTERVAL '7 days'
                GROUP BY user_id
            ) t
            """
        )
        cross = cur.fetchone() or {}

    total = int(agg.get("total_week") or 0)
    fcr = int(agg.get("fcr_resolved") or 0)
    not_esc = int(agg.get("not_escalated") or 0)
    aht = float(agg.get("aht_seconds") or 0)
    cross_pct = float(cross.get("cross_channel_pct") or 0)

    return {
        "first_contact_resolution_pct": round((fcr / total) * 100, 1) if total else 0,
        "channel_deflection_pct": round((not_esc / total) * 100, 1) if total else 0,
        "avg_handle_time_seconds": round(aht, 1),
        "avg_handle_time_minutes": round(aht / 60.0, 1) if aht else 0,
        "cross_channel_continuity_pct": round(cross_pct * 100, 1),
        "window": "last 7 days",
    }


@router.get("/stats")
def case_stats() -> dict:
    """Aggregate counters for the executive dashboard."""
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE created_at::date = CURRENT_DATE) AS today,
                COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') AS week,
                COUNT(*) FILTER (WHERE status = 'open') AS open,
                COUNT(*) FILTER (WHERE status = 'escalated') AS escalated,
                COUNT(*) FILTER (WHERE status = 'resolved') AS resolved,
                COUNT(*) FILTER (WHERE priority IN ('high', 'critical')) AS high_priority,
                AVG(sentiment) FILTER (WHERE sentiment IS NOT NULL) AS avg_sentiment
            FROM cases
            """
        )
        agg = cur.fetchone()

        cur.execute(
            """
            SELECT service, COUNT(*) AS n
            FROM cases WHERE created_at > NOW() - INTERVAL '7 days'
            GROUP BY service ORDER BY n DESC LIMIT 6
            """
        )
        by_service = cur.fetchall()

        cur.execute(
            """
            SELECT channel, COUNT(*) AS n
            FROM cases WHERE created_at > NOW() - INTERVAL '7 days'
            GROUP BY channel ORDER BY n DESC
            """
        )
        by_channel = cur.fetchall()

        cur.execute(
            """
            SELECT intent, COUNT(*) AS n
            FROM cases WHERE created_at > NOW() - INTERVAL '7 days'
            GROUP BY intent ORDER BY n DESC LIMIT 8
            """
        )
        by_intent = cur.fetchall()
    return {
        "totals": {k: int(v or 0) if isinstance(v, (int, float)) else (round(float(v), 2) if v is not None else None) for k, v in agg.items()},
        "by_service": [dict(r) for r in by_service],
        "by_channel": [dict(r) for r in by_channel],
        "by_intent": [dict(r) for r in by_intent],
    }


# ============================ CITIZEN 360 ============================
# A directory of everyone who has interacted (verified UAE PASS citizens AND
# unverified WhatsApp/voice guests, derived from their cases/activity), plus a
# full profile view for staff: details + conversations + cases + activity + calls.

@router.get("/citizens")
def list_citizens(
    q: str | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """Directory of all interacting citizens with aggregate counters."""
    with db_cursor() as cur:
        # Union of identities seen across cases + citizens master, with per-user aggregates.
        cur.execute(
            """
            WITH ids AS (
                SELECT user_id, MAX(user_name) AS user_name FROM cases GROUP BY user_id
                UNION
                SELECT user_id, full_name_en AS user_name FROM citizens
            ),
            uniq AS (SELECT user_id, MAX(user_name) AS user_name FROM ids GROUP BY user_id)
            SELECT
                u.user_id,
                COALESCE(c.full_name_en, u.user_name) AS name,
                c.user_type,
                c.mobile,
                c.email,
                c.verified,
                c.last_seen_at AS profile_last_seen,
                (SELECT COUNT(*) FROM cases ca WHERE ca.user_id = u.user_id) AS total_cases,
                (SELECT COUNT(*) FROM cases ca WHERE ca.user_id = u.user_id AND ca.status = 'open') AS open_cases,
                (SELECT COUNT(*) FROM cases ca WHERE ca.user_id = u.user_id AND ca.status = 'escalated') AS escalated_cases,
                (SELECT AVG(sentiment) FROM cases ca WHERE ca.user_id = u.user_id AND ca.sentiment IS NOT NULL) AS avg_sentiment,
                (SELECT MAX(created_at) FROM cases ca WHERE ca.user_id = u.user_id) AS last_case_at,
                (SELECT json_agg(DISTINCT ca.channel) FROM cases ca WHERE ca.user_id = u.user_id) AS channels
            FROM uniq u
            LEFT JOIN citizens c ON c.user_id = u.user_id
            WHERE u.user_id IS NOT NULL
            ORDER BY GREATEST(
                COALESCE((SELECT MAX(created_at) FROM cases ca WHERE ca.user_id = u.user_id), 'epoch'::timestamptz),
                COALESCE(c.last_seen_at, 'epoch'::timestamptz)
            ) DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()

    items = []
    for r in rows:
        d = _serialize(r)
        if q and q.lower() not in (str(d.get("name") or "") + " " + str(d.get("user_id") or "")).lower():
            continue
        d["total_cases"] = int(d.get("total_cases") or 0)
        d["open_cases"] = int(d.get("open_cases") or 0)
        d["escalated_cases"] = int(d.get("escalated_cases") or 0)
        d["avg_sentiment"] = round(float(d["avg_sentiment"]), 2) if d.get("avg_sentiment") is not None else None
        d["channels"] = [c for c in (d.get("channels") or []) if c]
        items.append(d)
    return {"count": len(items), "citizens": items}


@router.get("/citizens/{user_id}")
def citizen_profile(user_id: str) -> dict:
    """Full 360° profile: master details + cases + activity timeline + call recordings + feedback."""
    with db_cursor() as cur:
        cur.execute("SELECT * FROM citizens WHERE user_id = %s", (user_id,))
        profile = cur.fetchone()

        cur.execute(
            "SELECT * FROM cases WHERE user_id = %s ORDER BY created_at DESC LIMIT 50", (user_id,)
        )
        cases = cur.fetchall()

        cur.execute(
            """SELECT id, channel, event_type, summary, payload, created_at
               FROM activity_events WHERE user_id = %s ORDER BY id DESC LIMIT 60""",
            (user_id,),
        )
        activity = cur.fetchall()

        cur.execute(
            """SELECT id, call_id, duration_seconds, summary, service, resolved, qa_score,
                      sentiment_start, sentiment_end, case_number, created_at
               FROM call_recordings WHERE user_id = %s ORDER BY created_at DESC LIMIT 20""",
            (user_id,),
        )
        recordings = cur.fetchall()

        cur.execute(
            """SELECT csat, ces, comment, case_number, submitted_at
               FROM case_feedback WHERE user_id = %s ORDER BY submitted_at DESC LIMIT 20""",
            (user_id,),
        )
        feedback = cur.fetchall()

        # Derived aggregates
        cur.execute(
            """SELECT
                 COUNT(*) AS total_cases,
                 COUNT(*) FILTER (WHERE status='open') AS open_cases,
                 COUNT(*) FILTER (WHERE status='escalated') AS escalated_cases,
                 COUNT(*) FILTER (WHERE status='resolved') AS resolved_cases,
                 AVG(sentiment) FILTER (WHERE sentiment IS NOT NULL) AS avg_sentiment,
                 MIN(created_at) AS first_contact,
                 MAX(created_at) AS last_contact,
                 json_agg(DISTINCT channel) AS channels
               FROM cases WHERE user_id = %s""",
            (user_id,),
        )
        agg = cur.fetchone() or {}

    if not profile and not cases and not activity:
        raise HTTPException(404, f"no record for {user_id}")

    name = None
    if profile:
        name = profile.get("full_name_en")
    if not name and cases:
        name = next((c.get("user_name") for c in cases if c.get("user_name")), None)

    return {
        "user_id": user_id,
        "profile": _serialize(profile) if profile else None,
        "name": name,
        "verified": bool(profile),
        "summary": {
            "total_cases": int(agg.get("total_cases") or 0),
            "open_cases": int(agg.get("open_cases") or 0),
            "escalated_cases": int(agg.get("escalated_cases") or 0),
            "resolved_cases": int(agg.get("resolved_cases") or 0),
            "avg_sentiment": round(float(agg["avg_sentiment"]), 2) if agg.get("avg_sentiment") is not None else None,
            "first_contact": agg["first_contact"].isoformat() if agg.get("first_contact") else None,
            "last_contact": agg["last_contact"].isoformat() if agg.get("last_contact") else None,
            "channels": [c for c in (agg.get("channels") or []) if c],
        },
        "cases": [_serialize(r) for r in cases],
        "activity": [_serialize(r) for r in activity],
        "recordings": [_serialize(r) for r in recordings],
        "feedback": [_serialize(r) for r in feedback],
    }


@router.post("/cases/{case_number}/action")
def case_action(case_number: str, payload: dict = Body(...)) -> dict:
    """Staff next-action on a case: resolve / escalate / reopen / assign.

    Body: {"action": "resolve"|"escalate"|"reopen"|"assign", "assigned_to": "..."?}
    """
    action = (payload.get("action") or "").lower()
    assigned_to = payload.get("assigned_to")
    valid = {"resolve": "resolved", "escalate": "escalated", "reopen": "open", "assign": None}
    if action not in valid:
        raise HTTPException(400, f"invalid action '{action}'")

    with db_cursor() as cur:
        cur.execute("SELECT id, user_id, user_name, channel, status FROM cases WHERE case_number = %s", (case_number,))
        case = cur.fetchone()
        if not case:
            raise HTTPException(404, f"case {case_number} not found")

        if action == "assign":
            cur.execute(
                "UPDATE cases SET assigned_to = %s, updated_at = NOW() WHERE case_number = %s RETURNING status",
                (assigned_to or "MOEI agent", case_number),
            )
        elif action == "resolve":
            cur.execute(
                "UPDATE cases SET status='resolved', resolved_at=NOW(), updated_at=NOW() WHERE case_number=%s RETURNING status",
                (case_number,),
            )
        else:
            new_status = valid[action]
            cur.execute(
                "UPDATE cases SET status=%s, updated_at=NOW() WHERE case_number=%s RETURNING status",
                (new_status, case_number),
            )
        row = cur.fetchone()

        # Log the staff action to the activity timeline.
        import json as _json
        cur.execute(
            """INSERT INTO activity_events (user_id, user_name, channel, event_type, summary, payload)
               VALUES (%s,%s,%s,'staff_action',%s,%s::jsonb)""",
            (case.get("user_id"), case.get("user_name"), case.get("channel") or "web",
             f"Staff {action} on {case_number}",
             _json.dumps({"action": action, "case_number": case_number, "assigned_to": assigned_to})),
        )

    return {"ok": True, "case_number": case_number, "action": action, "status": row.get("status") if row else None}
