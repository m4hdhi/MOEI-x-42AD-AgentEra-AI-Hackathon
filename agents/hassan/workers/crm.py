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
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# Add apps/api to path so we can import the DB helper from the agents package
_API = Path(__file__).resolve().parents[3] / "apps" / "api"
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

try:
    from app.core.db import db_cursor  # type: ignore[import-not-found]

    _DB_AVAILABLE = True
except Exception:
    _DB_AVAILABLE = False

from loguru import logger

# 3-tier SLA: how many days a freshly opened case has before its deadline.
_SLA_DAYS = {"urgent": 1, "medium": 3, "normal": 5}


def sla_deadline_for(priority_tier: str, now: datetime | None = None) -> datetime:
    """SLA deadline for a priority tier — urgent=1d, medium=3d, normal=5d from open time.

    Equivalent to Postgres `NOW() + INTERVAL` but computed in Python so it's a single,
    deterministic, testable source of truth. Unknown tiers fall back to 'normal'.
    """
    now = now or datetime.now(UTC)
    return now + timedelta(days=_SLA_DAYS.get(priority_tier, _SLA_DAYS["normal"]))


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
    escalation_reason: str | None = None,
    priority_tier: str = "normal",
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
                        escalated = %s,
                        escalation_reason = COALESCE(%s, escalation_reason),
                        correlation_id = COALESCE(%s, correlation_id),
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, case_number, status, priority, sentiment, created_at, updated_at
                    """,
                    (
                        sentiment,
                        new_status,
                        priority,
                        escalated,
                        escalation_reason,
                        correlation_id,
                        existing["id"],
                    ),
                )
                row = cur.fetchone()
                logger.info(f"crm: updated case {row['case_number']} (status={row['status']})")
                return dict(row)

            # New case — generate a human-readable number
            cur.execute("SELECT COUNT(*) AS n FROM cases WHERE created_at::date = CURRENT_DATE")
            today_count = cur.fetchone()["n"]
            case_number = f"MOEI-CASE-{datetime.utcnow():%Y%m%d}-{today_count + 1:04d}"

            sla_deadline = sla_deadline_for(priority_tier)
            cur.execute(
                """
                INSERT INTO cases (case_number, user_id, user_name, channel, intent, service,
                                   title, description, priority, status, sentiment, escalated,
                                   escalation_reason, correlation_id, priority_tier, sla_deadline)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id, case_number, status, priority, priority_tier, sla_deadline,
                          sentiment, created_at, updated_at
                """,
                (
                    case_number,
                    user_id,
                    user_name,
                    channel,
                    intent,
                    service,
                    title,
                    user_text[:1000],
                    priority,
                    status,
                    sentiment,
                    escalated,
                    escalation_reason,
                    correlation_id,
                    priority_tier,
                    sla_deadline,
                ),
            )
            row = cur.fetchone()
            logger.info(
                f"crm: created {row['case_number']} ({priority} {status}; "
                f"tier={priority_tier} sla={sla_deadline:%Y-%m-%d})"
            )
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


def auto_resolve_case(case_number: str) -> None:
    """Close a case the citizen resolved themselves via a direct FAQ/knowledge answer.

    Sets status='resolved', resolution_type='self_served', resolved_at=NOW(). Never triggers
    escalation, and skips cases already escalated/resolved/closed so we never override a human
    handoff or an existing resolution.
    """
    if not _DB_AVAILABLE:
        return
    try:
        with db_cursor() as cur:
            cur.execute(
                """UPDATE cases
                   SET status='resolved', resolution_type='self_served', resolved_at=NOW(),
                       assigned_to=COALESCE(assigned_to, 'AI (self-service)'), updated_at=NOW()
                   WHERE case_number=%s AND status NOT IN ('resolved', 'escalated', 'closed')""",
                (case_number,),
            )
    except Exception as e:
        logger.debug(f"auto_resolve_case failed: {e}")


# Positive closure phrases ("it's fixed", "working now", "تم الإصلاح") that signal the citizen
# is confirming their issue is resolved. Paired with a negation guard so "it's NOT fixed yet"
# never closes a case.
_RESOLUTION_PHRASES_EN = (
    "fixed it",
    "is fixed",
    "has been fixed",
    "was fixed",
    "all fixed",
    "got fixed",
    "came and fixed",
    "came and repaired",
    "repaired it",
    "is repaired",
    "has been repaired",
    "is resolved",
    "has been resolved",
    "now resolved",
    "problem solved",
    "issue is solved",
    "working now",
    "works now",
    "is working again",
    "sorted now",
    "all sorted",
    "all good now",
    "no longer an issue",
    "no more problem",
    "everything works",
)
_RESOLUTION_PHRASES_AR = (
    "تم الإصلاح",
    "تم الاصلاح",
    "تم إصلاح",
    "تم اصلاح",
    "تم الحل",
    "تمت المعالجة",
    "تم التصليح",
    "اشتغل",
    "تشتغل الآن",
    "يعمل الآن",
    "تم حل المشكلة",
    "خلصت المشكلة",
    "ما عاد في مشكلة",
    "ما في مشكلة الآن",
)
_NEGATION_GUARD_EN = (
    "not ",
    "n't",
    "still not",
    "isn't",
    "hasn't",
    "wasn't",
    "haven't",
    "didn't",
    "no fix",
    "not yet",
    "still broken",
    "still not working",
)
_NEGATION_GUARD_AR = ("لم يتم", "لم", "ما زال", "ما زالت", "لسه", "لسا", "مو", "ليس", "غير")


def is_resolution_confirmation(text: str) -> bool:
    """True when the message is the citizen confirming their issue is now resolved.

    Deliberately conservative: requires an explicit positive-closure phrase AND no negation
    nearby, so ordinary thanks or complaints never auto-close a case.
    """
    if not text:
        return False
    low = text.lower()
    if any(g in low for g in _NEGATION_GUARD_EN) or any(g in text for g in _NEGATION_GUARD_AR):
        return False
    return any(p in low for p in _RESOLUTION_PHRASES_EN) or any(
        p in text for p in _RESOLUTION_PHRASES_AR
    )


def confirm_resolution_for_user(
    user_id: str, *, resolution_type: str = "agent_resolved"
) -> dict[str, Any] | None:
    """Close the citizen's most recent live case after they confirm it's resolved.

    Resolves the newest open / in_progress case for this user (any service), recording
    `resolution_type` (default 'agent_resolved' — a field agent/technician did the work).
    Returns the closed case row, or None if they had no open case.
    """
    if not _DB_AVAILABLE:
        return None
    try:
        with db_cursor() as cur:
            cur.execute(
                """
                UPDATE cases
                SET status='resolved', resolution_type=%s, resolved_at=NOW(),
                    date_closed=NOW(), sla_met=COALESCE(sla_met, 'Yes'), updated_at=NOW(),
                    assigned_to=COALESCE(assigned_to, 'AI (citizen-confirmed)')
                WHERE id = (
                    SELECT id FROM cases
                    WHERE user_id=%s AND status IN ('open','in_progress')
                    ORDER BY created_at DESC LIMIT 1
                )
                RETURNING id, case_number, status, resolution_type, service
                """,
                (resolution_type, user_id),
            )
            row = cur.fetchone()
            if row:
                logger.info(
                    f"crm: citizen-confirmed resolution on {row['case_number']} "
                    f"(resolution_type={row['resolution_type']})"
                )
            return dict(row) if row else None
    except Exception as e:
        logger.debug(f"confirm_resolution_for_user failed: {e}")
        return None


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
                body["_step"] = step  # preserves display order (ids are UUIDs)
                cur.execute(
                    """
                    INSERT INTO audit_log (correlation_id, user_id, channel, node, payload)
                    VALUES (%s, %s, %s, %s, %s::jsonb)
                    """,
                    (correlation_id, user_id, channel, node, json.dumps(body)),
                )
    except Exception as e:
        logger.debug(f"audit: write failed: {e}")
