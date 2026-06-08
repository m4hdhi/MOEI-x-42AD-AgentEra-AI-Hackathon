"""CRM worker — auto-creates / updates cases in Postgres for every meaningful supervisor turn.

A "meaningful" turn is anything other than smalltalk / out_of_scope. The case carries:
- a human-readable case number (MOEI-CASE-2026-NNNNN, auto-incremented per day)
- channel of origin
- intent + service from the Router
- priority (derived from sentiment + intent + escalation)
- status (open → in_progress → resolved / escalated)
- sentiment score from the latest turn
- correlation_id linking to the Langfuse trace

The same user_id reuses an open case if one exists for the same service within 24h
(so a multi-turn rescheduling conversation is one case, not 5).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Add apps/api to path so we can import the DB helper from the agents package
_API = Path(__file__).resolve().parents[3] / "apps" / "api"
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

try:
    from app.core.db import db_cursor   # type: ignore[import-not-found]
    _DB_AVAILABLE = True
except Exception:
    _DB_AVAILABLE = False

from loguru import logger


def _priority(intent: str, sentiment: float | None, escalated: bool) -> str:
    if escalated or intent == "complaint":
        if sentiment is not None and sentiment < 0.3:
            return "critical"
        return "high"
    if intent in ("status_check", "service_request"):
        return "medium"
    if intent in ("appreciation", "smalltalk"):
        return "low"
    return "medium"


def _title_for(intent: str, service: str, user_text: str) -> str:
    head = {
        "complaint": "Complaint",
        "suggestion": "Suggestion",
        "appreciation": "Appreciation",
        "service_request": "Service request",
        "status_check": "Status check",
        "document_upload": "Document upload",
        "escalate_to_human": "Human escalation",
    }.get(intent, "Inquiry")
    snippet = user_text.strip().replace("\n", " ")[:80]
    return f"{head} — {service} · {snippet}"


def upsert_case(
    *,
    user_id: str,
    user_name: str | None,
    channel: str,
    intent: str,
    service: str,
    user_text: str,
    sentiment: float | None,
    escalated: bool,
    correlation_id: str | None,
) -> dict[str, Any] | None:
    """Create-or-update a case for the turn. Reuses an open case for the same (user, service)
    within the last 24h; otherwise opens a fresh one with a human-readable number.
    """
    if not _DB_AVAILABLE:
        return None
    # Status checks are reads, not new requests — don't spawn a case for them. Smalltalk/out-of-scope
    # likewise. (A status check that has no service context would otherwise create a junk 'Unknown' case.)
    if intent in ("smalltalk", "out_of_scope", "status_check"):
        return None
    try:
        priority = _priority(intent, sentiment, escalated)
        title = _title_for(intent, service, user_text)
        status = "escalated" if escalated else ("resolved" if intent == "appreciation" else "open")

        with db_cursor() as cur:
            # Try to find an existing open case in the same service within 24h
            cur.execute(
                """
                SELECT id, case_number, status, sentiment FROM cases
                WHERE user_id = %s AND service = %s
                  AND status IN ('open', 'in_progress', 'escalated')
                  AND created_at > NOW() - INTERVAL '24 hours'
                ORDER BY created_at DESC LIMIT 1
                """,
                (user_id, service),
            )
            existing = cur.fetchone()

            if existing:
                # Update the existing case — bump status if needed, refresh sentiment + timestamp
                new_status = "escalated" if escalated else existing["status"]
                cur.execute(
                    """
                    UPDATE cases
                    SET sentiment = COALESCE(%s, sentiment),
                        status = %s,
                        priority = %s,
                        correlation_id = COALESCE(%s, correlation_id),
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, case_number, status, priority, sentiment, created_at, updated_at
                    """,
                    (sentiment, new_status, priority, correlation_id, existing["id"]),
                )
                row = cur.fetchone()
                logger.info(f"crm: updated case {row['case_number']} (status={row['status']})")
                return dict(row)

            # New case — generate a human-readable number
            cur.execute("SELECT COUNT(*) AS n FROM cases WHERE created_at::date = CURRENT_DATE")
            today_count = cur.fetchone()["n"]
            case_number = f"MOEI-CASE-{datetime.utcnow():%Y%m%d}-{today_count + 1:04d}"

            cur.execute(
                """
                INSERT INTO cases (case_number, user_id, user_name, channel, intent, service,
                                   title, description, priority, status, sentiment, correlation_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, case_number, status, priority, sentiment, created_at, updated_at
                """,
                (case_number, user_id, user_name, channel, intent, service,
                 title, user_text[:1000], priority, status, sentiment, correlation_id),
            )
            row = cur.fetchone()
            logger.info(f"crm: created {row['case_number']} ({priority} {status})")
            return dict(row)
    except Exception as e:
        logger.warning(f"crm: upsert_case failed: {e}")
        return None


def emit_activity(
    *,
    event_type: str,
    summary: str,
    user_id: str | None = None,
    user_name: str | None = None,
    channel: str | None = None,
    payload: dict | None = None,
) -> None:
    """Append to activity_events for the live ticker."""
    if not _DB_AVAILABLE:
        return
    try:
        import json
        with db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO activity_events (user_id, user_name, channel, event_type, summary, payload)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                """,
                (user_id, user_name, channel, event_type, summary, json.dumps(payload or {})),
            )
    except Exception as e:
        logger.debug(f"activity: emit failed: {e}")


def resolve_case_autonomously(case_number: str) -> None:
    """Mark a case resolved by the agent with no human intervention (Autonomous Resolution)."""
    if not _DB_AVAILABLE:
        return
    try:
        with db_cursor() as cur:
            cur.execute(
                """UPDATE cases SET status='resolved', resolved_at=NOW(), assigned_to='AI (autonomous)',
                   updated_at=NOW() WHERE case_number=%s AND status NOT IN ('resolved','escalated')""",
                (case_number,),
            )
    except Exception as e:
        logger.debug(f"autonomous resolve failed: {e}")


def write_audit_trail(
    *,
    correlation_id: str,
    user_id: str,
    channel: str,
    events: list[tuple[str, dict]],
) -> None:
    """Record the step-by-step decision trail for one supervisor turn.

    `events` is an ordered list of (node, payload). One row per node, all sharing the
    same correlation_id so the Audit Trail page can replay exactly how a reply was reached
    (UAE PDPL Article 7 — right to explanation).
    """
    if not _DB_AVAILABLE or not correlation_id:
        return
    try:
        import json
        with db_cursor() as cur:
            for step, (node, payload) in enumerate(events):
                body = dict(payload or {})
                body["_step"] = step          # preserves display order (ids are UUIDs)
                cur.execute(
                    """
                    INSERT INTO audit_log (correlation_id, user_id, channel, node, payload)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    """,
                    (correlation_id, user_id, channel, node, json.dumps(body)),
                )
    except Exception as e:
        logger.debug(f"audit: write failed: {e}")
