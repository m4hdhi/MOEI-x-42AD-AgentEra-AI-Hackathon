"""Notifications API + scheduler. Powers the 'Outbound Engagement' panel on /exec."""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Body, HTTPException, Query

from ..core.db import db_cursor

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _ser(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        out[k] = v.isoformat() if isinstance(v, datetime) else (str(v) if hasattr(v, "hex") and not isinstance(v, (bytes, str)) else v)
    return out


@router.get("")
def list_notifications(
    status: str | None = None,
    user_id: str | None = None,
    upcoming: bool = Query(False, description="Only scheduled in the future"),
    limit: int = Query(50, ge=1, le=500),
) -> dict:
    sql = "SELECT * FROM notifications WHERE 1=1"
    params: list = []
    if status:
        sql += " AND status = %s"; params.append(status)
    if user_id:
        sql += " AND user_id = %s"; params.append(user_id)
    if upcoming:
        sql += " AND scheduled_at > NOW()"
    sql += " ORDER BY scheduled_at ASC LIMIT %s"; params.append(limit)
    with db_cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return {"count": len(rows), "items": [_ser(r) for r in rows]}


@router.post("")
def schedule_notification(payload: dict = Body(...)) -> dict:
    """Schedule a proactive notification.

    Body:
      {
        "user_id": "784-...", "case_number": "MOEI-...",
        "channel": "whatsapp",
        "template": "status_update" | "doc_reminder" | "csat_survey" | "proactive_tip",
        "scheduled_in_hours": 24,  // OR scheduled_at ISO
        "data": {...}
      }
    """
    required = ("user_id", "channel", "template")
    for k in required:
        if k not in payload:
            raise HTTPException(400, f"missing field: {k}")
    scheduled_at: datetime
    if "scheduled_at" in payload:
        scheduled_at = datetime.fromisoformat(payload["scheduled_at"].replace("Z", "+00:00"))
    else:
        hrs = float(payload.get("scheduled_in_hours", 24))
        scheduled_at = datetime.utcnow() + timedelta(hours=hrs)

    case_id = None
    if "case_number" in payload:
        with db_cursor() as cur:
            cur.execute("SELECT id FROM cases WHERE case_number = %s", (payload["case_number"],))
            row = cur.fetchone()
            if row:
                case_id = row["id"]

    with db_cursor() as cur:
        cur.execute(
            """
            INSERT INTO notifications (user_id, case_id, channel, template, payload, scheduled_at)
            VALUES (%s, %s, %s, %s, %s::jsonb, %s)
            RETURNING *
            """,
            (payload["user_id"], case_id, payload["channel"], payload["template"],
             json.dumps(payload.get("data", {})), scheduled_at),
        )
        row = cur.fetchone()

        # Reachability: honest signal for the UI about how/whether this will actually deliver.
        delivery = {"channel": payload["channel"], "reachable": False, "to": None, "mode": "queued"}
        if payload["channel"] in ("whatsapp", "sms"):
            cur.execute(
                "SELECT wa_number FROM whatsapp_identities WHERE user_id = %s ORDER BY last_seen_at DESC LIMIT 1",
                (payload["user_id"],),
            )
            wa = cur.fetchone()
            if wa and wa.get("wa_number"):
                to = wa["wa_number"].replace("whatsapp:", "")
                twilio_live = bool(os.getenv("TWILIO_ACCOUNT_SID") and os.getenv("TWILIO_AUTH_TOKEN"))
                delivery = {
                    "channel": payload["channel"],
                    "reachable": True,
                    "to": to,
                    "mode": "live" if twilio_live else "simulated",
                }

    result = _ser(row)
    result["delivery"] = delivery
    return result


@router.get("/stats")
def notification_stats() -> dict:
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'scheduled' AND scheduled_at > NOW()) AS upcoming,
                COUNT(*) FILTER (WHERE status = 'sent' AND sent_at::date = CURRENT_DATE) AS sent_today,
                COUNT(*) FILTER (WHERE status = 'sent' AND sent_at > NOW() - INTERVAL '7 days') AS sent_week,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed
            FROM notifications
            """
        )
        agg = cur.fetchone()
        cur.execute(
            """
            SELECT template, COUNT(*) AS n
            FROM notifications WHERE created_at > NOW() - INTERVAL '7 days'
            GROUP BY template ORDER BY n DESC
            """
        )
        by_template = cur.fetchall()
    return {
        "totals": {k: int(v or 0) for k, v in agg.items()},
        "by_template": [dict(r) for r in by_template],
    }
