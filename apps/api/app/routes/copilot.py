"""Co-pilot console endpoints.

The co-pilot console is a human-agent dashboard showing:
- live transcripts of active citizen sessions (with sentiment + suggested replies)
- session details + audit trail (every supervisor node decision)
- the ability to take over from the agent

For the demo we serve a recent-sessions list pulled from Redis short-term + the audit_log
table. Live updates use a simple long-poll endpoint; production would use WebSocket/SSE.
"""

from __future__ import annotations

import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from hassan.memory import get_short_term_buffer

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.get("/sessions/{user_id}/transcript")
async def transcript(user_id: str, limit: int = Query(40, ge=1, le=200)) -> dict:
    """Recent turns for a user across all channels — the cross-channel memory view."""
    buf = get_short_term_buffer()
    turns = await buf.recent(user_id, n=limit)
    return {
        "user_id": user_id,
        "fetched_at": datetime.utcnow().isoformat(),
        "turns": turns,
    }


@router.get("/audit/{correlation_id}")
async def audit(correlation_id: str) -> dict:
    """Audit trail for a single supervisor run, sourced from Langfuse + the audit_log table.

    For the demo we read from Postgres directly when available; otherwise return
    the supervisor's own emitted trace events from Redis.
    """
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=503, detail="audit DB not configured")
    try:
        import psycopg

        ref = correlation_id.strip()
        resolved = ref
        case_number = None
        conn_str = db_url.replace("postgresql+psycopg://", "postgresql://")
        with psycopg.connect(conn_str, autocommit=True) as conn, conn.cursor() as cur:
            # Accept a case number (MOEI-CASE-...) and resolve it to that turn's correlation_id.
            if ref.upper().startswith("MOEI-CASE"):
                case_number = ref
                cur.execute("SELECT correlation_id FROM cases WHERE case_number = %s", (ref,))
                row = cur.fetchone()
                if row and row[0]:
                    resolved = row[0]
            order = "ORDER BY created_at, COALESCE((payload->>'_step')::int, 0)"
            cur.execute(
                f"SELECT node, payload, created_at FROM audit_log WHERE correlation_id = %s {order}",
                (resolved,),
            )
            rows = cur.fetchall()
            # Also support pasting a call-recording reference directly.
            if not rows and case_number is None:
                cur.execute(
                    f"SELECT node, payload, created_at FROM audit_log WHERE correlation_id = %s {order}",
                    (f"call:{ref}",),
                )
                rows = cur.fetchall()
        return {
            "correlation_id": resolved,
            "case_number": case_number,
            "events": [
                {"node": r[0], "payload": r[1], "at": r[2].isoformat()} for r in rows
            ],
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"audit query failed: {e}") from e
