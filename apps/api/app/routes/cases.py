"""Case-centric actions that aren't tied to the staff CRM console.

Currently: proactive outbound updates on a case (`trigger-update`). This is the "we reach out
to YOU" half of the engagement loop — the agent pushes a status update to the citizen's
preferred channel the moment something changes, rather than waiting for them to ask.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException
from loguru import logger

from ..core.db import db_cursor

router = APIRouter(prefix="/cases", tags=["cases"])


def _ser(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        elif hasattr(v, "hex") and not isinstance(v, (bytes, str)):
            out[k] = str(v)
        else:
            out[k] = v
    return out


@router.post("/{case_number}/trigger-update")
def trigger_update(case_number: str, payload: Annotated[dict, Body(...)]) -> dict:
    """Send a proactive status update to the citizen who owns this case.

    Body: {"message": "Your maintenance request has been assigned — field visit Thursday"}

    Routes to the citizen's preferred channel (falls back to the case's channel of origin),
    records it as a *sent* notification, and drops a line on the activity timeline so the
    co-pilot and exec dashboard see the outbound touch. This is what the demo's "the agent
    reaches out first" moment is built on.
    """
    message = (payload or {}).get("message")
    if not message:
        raise HTTPException(400, "missing field: message")

    with db_cursor() as cur:
        cur.execute(
            "SELECT id, user_id, customer_id, user_name, channel, service, status "
            "FROM cases WHERE case_number = %s",
            (case_number,),
        )
        case = cur.fetchone()
        if not case:
            raise HTTPException(404, f"case {case_number} not found")

        user_id = case["user_id"]

        # Prefer the citizen's stated preferred channel; fall back to the case's origin channel.
        channel = case.get("channel") or "whatsapp"
        try:
            cur.execute(
                "SELECT preferred_channel FROM citizens "
                "WHERE user_id = %s OR customer_id = %s LIMIT 1",
                (user_id, case.get("customer_id") or user_id),
            )
            pref = cur.fetchone()
            if pref and pref.get("preferred_channel"):
                channel = pref["preferred_channel"]
        except Exception as e:
            logger.warning(f"preferred channel lookup failed for {case_number}: {e}")

        # Record as an already-sent proactive notification (immediate push).
        cur.execute(
            """
            INSERT INTO notifications (user_id, case_id, channel, template, payload,
                                       scheduled_at, sent_at, status)
            VALUES (%s, %s, %s, 'status_update', %s::jsonb, NOW(), NOW(), 'sent')
            RETURNING *
            """,
            (
                user_id,
                case["id"],
                channel,
                json.dumps({"message": message, "case_number": case_number}),
            ),
        )
        notification = cur.fetchone()

        cur.execute(
            """
            INSERT INTO activity_events (user_id, user_name, channel, event_type, summary, payload)
            VALUES (%s, %s, %s, 'proactive_update', %s, %s::jsonb)
            """,
            (
                user_id,
                case.get("user_name"),
                channel,
                f"📣 Proactive update sent on {case_number} via {channel}",
                json.dumps({"case_number": case_number, "message": message, "channel": channel}),
            ),
        )

    return {
        "ok": True,
        "case_number": case_number,
        "channel": channel,
        "message": message,
        "notification": _ser(notification),
    }
