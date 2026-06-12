"""Co-pilot console endpoints.

The co-pilot console is a human-agent dashboard showing:
- live transcripts of active citizen sessions (with sentiment + suggested replies)
- session details + audit trail (every supervisor node decision)
- the ability to take over from the agent

For the demo we serve a recent-sessions list pulled from Redis short-term + the audit_log
table. Live updates use a simple long-poll endpoint; production would use WebSocket/SSE.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query
from hassan.memory import get_short_term_buffer

from ..core.db import db_cursor

router = APIRouter(prefix="/copilot", tags=["copilot"])


def _serialize(row: dict | None) -> dict | None:
    if row is None:
        return None
    out = dict(row)
    for key, value in out.items():
        if isinstance(value, datetime):
            out[key] = value.isoformat()
        elif isinstance(value, Decimal):
            out[key] = float(value)
        elif hasattr(value, "hex") and not isinstance(value, (bytes, str)):
            out[key] = str(value)
    return out


def _audit_event(
    node: str,
    payload: dict,
    at: datetime | str | None = None,
    *,
    synthetic: bool = True,
) -> dict:
    if isinstance(at, datetime):
        when = at.isoformat()
    elif isinstance(at, str):
        when = at
    else:
        when = datetime.utcnow().isoformat()
    return {
        "node": node,
        "payload": _serialize(payload) or payload or {},
        "at": when,
        "synthetic": synthetic,
    }


def _case_title(case: dict | None) -> str:
    if not case:
        return "Audit trail"
    return (
        case.get("title")
        or case.get("description")
        or case.get("intent")
        or case.get("case_number")
        or "Case audit"
    )


def _build_case_fallback(cur, case: dict) -> list[dict]:
    events = [
        _audit_event(
            "CaseRecord",
            {
                "case_number": case.get("case_number"),
                "title": case.get("title"),
                "description": case.get("description"),
                "service": case.get("service"),
                "intent": case.get("intent"),
                "channel": case.get("channel"),
                "priority": case.get("priority"),
                "status": case.get("status"),
                "sentiment": case.get("sentiment"),
                "assigned_to": case.get("assigned_to"),
                "correlation_id": case.get("correlation_id"),
            },
            case.get("created_at"),
        )
    ]
    if case.get("assigned_to"):
        events.append(
            _audit_event(
                "OfficerAssignment",
                {
                    "case_number": case.get("case_number"),
                    "assigned_to": case.get("assigned_to"),
                    "priority": case.get("priority"),
                    "status": case.get("status"),
                },
                case.get("updated_at"),
            )
        )
    if case.get("resolved_at"):
        events.append(
            _audit_event(
                "Resolution",
                {
                    "case_number": case.get("case_number"),
                    "status": case.get("status"),
                    "resolved_at": case.get("resolved_at"),
                },
                case.get("resolved_at"),
            )
        )

    cur.execute(
        """
        SELECT channel, event_type, summary, payload, created_at
        FROM activity_events
        WHERE payload->>'case_number' = %s
           OR payload->>'correlation_id' = %s
        ORDER BY created_at ASC
        LIMIT 20
        """,
        (case.get("case_number"), case.get("correlation_id")),
    )
    for row in cur.fetchall():
        events.append(
            _audit_event(
                "Activity",
                {
                    "channel": row.get("channel"),
                    "event_type": row.get("event_type"),
                    "summary": row.get("summary"),
                    "payload": row.get("payload"),
                },
                row.get("created_at"),
            )
        )

    cur.execute(
        """
        SELECT n.channel, n.template, n.payload, n.scheduled_at, n.sent_at,
               n.status, n.created_at
        FROM notifications n
        WHERE n.case_id = %s
        ORDER BY COALESCE(n.sent_at, n.scheduled_at, n.created_at) ASC
        LIMIT 10
        """,
        (case.get("id"),),
    )
    for row in cur.fetchall():
        events.append(
            _audit_event(
                "Notification",
                {
                    "channel": row.get("channel"),
                    "template": row.get("template"),
                    "status": row.get("status"),
                    "payload": row.get("payload"),
                    "scheduled_at": row.get("scheduled_at"),
                    "sent_at": row.get("sent_at"),
                },
                row.get("sent_at") or row.get("scheduled_at") or row.get("created_at"),
            )
        )
    return sorted(events, key=lambda event: event["at"])


def _build_call_fallback(call: dict) -> list[dict]:
    return [
        _audit_event(
            "CallRecording",
            {
                "call_id": call.get("call_id"),
                "user_id": call.get("user_id"),
                "user_name": call.get("user_name"),
                "language": call.get("language"),
                "duration_seconds": call.get("duration_seconds"),
                "summary": call.get("summary"),
                "topics": call.get("topics"),
                "action_items": call.get("action_items"),
                "intent": call.get("intent"),
                "service": call.get("service"),
                "resolved": call.get("resolved"),
                "qa_score": call.get("qa_score"),
                "sentiment_avg": call.get("sentiment_avg"),
                "escalated": call.get("escalated"),
                "case_number": call.get("case_number"),
                "correlation_id": call.get("correlation_id"),
            },
            call.get("created_at"),
        )
    ]


def _build_assessment_fallback(assessment: dict) -> list[dict]:
    return [
        _audit_event(
            "Assessment",
            {
                "reference": assessment.get("reference"),
                "application_id": assessment.get("application_id"),
                "user_id": assessment.get("user_id"),
                "applicant": assessment.get("applicant"),
                "recommendation": assessment.get("recommendation"),
                "approved_request_type": assessment.get("approved_request_type"),
                "confidence": assessment.get("confidence"),
                "status": assessment.get("status"),
                "reasoning": assessment.get("reasoning"),
                "current_salary": assessment.get("current_salary"),
                "arrears": assessment.get("arrears"),
                "current_emi": assessment.get("current_emi"),
                "proposed_emi": assessment.get("proposed_emi"),
                "proposed_term_months": assessment.get("proposed_term_months"),
                "deduction_ratio": assessment.get("deduction_ratio"),
                "rule_20_pass": assessment.get("rule_20_pass"),
                "rule_period_pass": assessment.get("rule_period_pass"),
                "rule_active_pass": assessment.get("rule_active_pass"),
            },
            assessment.get("created_at"),
        )
    ]


def _risk_band(score: int) -> str:
    if score >= 75:
        return "critical"
    if score >= 50:
        return "high"
    if score >= 25:
        return "watch"
    return "normal"


def _sentiment_label(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score < 0.35:
        return "negative"
    if score < 0.65:
        return "neutral"
    return "positive"


def _next_best_action(
    latest_case: dict | None,
    open_cases: int,
    escalated_cases: int,
    high_priority: int,
    avg_sentiment: float | None,
    missing_documents: list[str],
) -> dict:
    if escalated_cases:
        return {
            "type": "take_ownership",
            "label": "Take ownership of escalated case",
            "detail": (
                "Call the citizen, confirm the current blocker, and add a staff "
                "update before the SLA window closes."
            ),
        }
    if high_priority:
        return {
            "type": "priority_update",
            "label": "Send high-priority status update",
            "detail": "Give the citizen a clear next milestone and assign an accountable officer.",
        }
    if missing_documents:
        return {
            "type": "document_request",
            "label": f"Request {missing_documents[0].replace('_', ' ')}",
            "detail": (
                "Send a document reminder and keep the case open until "
                "verification is complete."
            ),
        }
    if avg_sentiment is not None and avg_sentiment < 0.4:
        return {
            "type": "empathy_callback",
            "label": "Offer callback and reassurance",
            "detail": "Sentiment is low. Acknowledge the delay and offer a concrete callback time.",
        }
    if open_cases and latest_case:
        return {
            "type": "case_follow_up",
            "label": "Confirm next milestone",
            "detail": (
                f"Update {latest_case.get('case_number')} and tell the citizen "
                "what happens next."
            ),
        }
    return {
        "type": "no_action",
        "label": "No urgent action",
        "detail": "Citizen has no active high-risk case. Keep monitoring live activity.",
    }


@router.get("/active-users")
def active_users(limit: int = Query(20, ge=1, le=100)) -> dict:
    """Live citizen list for the co-pilot selector, ordered by most recent activity."""
    with db_cursor() as cur:
        cur.execute(
            """
            WITH seen AS (
                SELECT user_id, MAX(user_name) AS user_name, MAX(created_at) AS last_seen
                FROM cases WHERE user_id IS NOT NULL GROUP BY user_id
                UNION ALL
                SELECT user_id, MAX(user_name) AS user_name, MAX(created_at) AS last_seen
                FROM activity_events WHERE user_id IS NOT NULL GROUP BY user_id
                UNION ALL
                SELECT user_id, full_name_en AS user_name, last_seen_at AS last_seen
                FROM citizens WHERE user_id IS NOT NULL
            ),
            uniq AS (
                SELECT user_id, MAX(user_name) AS user_name, MAX(last_seen) AS last_seen
                FROM seen GROUP BY user_id
            )
            SELECT
                u.user_id,
                COALESCE(c.full_name_en, u.user_name, u.user_id) AS name,
                c.full_name_ar,
                c.mobile,
                c.verified,
                c.preferred_language,
                u.last_seen,
                (
                    SELECT COUNT(*) FROM cases ca
                    WHERE ca.user_id = u.user_id
                ) AS total_cases,
                (
                    SELECT COUNT(*) FROM cases ca
                    WHERE ca.user_id = u.user_id
                      AND ca.status IN ('open','in_progress','escalated')
                ) AS open_cases,
                (
                    SELECT COUNT(*) FROM cases ca
                    WHERE ca.user_id = u.user_id
                      AND ca.status = 'escalated'
                ) AS escalated_cases,
                (
                    SELECT AVG(sentiment) FROM cases ca
                    WHERE ca.user_id = u.user_id
                      AND ca.sentiment IS NOT NULL
                ) AS avg_sentiment,
                (
                    SELECT json_agg(DISTINCT ca.channel) FROM cases ca
                    WHERE ca.user_id = u.user_id
                ) AS channels
            FROM uniq u
            LEFT JOIN citizens c ON c.user_id = u.user_id
            WHERE u.user_id IS NOT NULL
            ORDER BY u.last_seen DESC NULLS LAST
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()

    items = []
    for row in rows:
        item = _serialize(row) or {}
        item["total_cases"] = int(item.get("total_cases") or 0)
        item["open_cases"] = int(item.get("open_cases") or 0)
        item["escalated_cases"] = int(item.get("escalated_cases") or 0)
        item["avg_sentiment"] = (
            round(float(item["avg_sentiment"]), 2)
            if item.get("avg_sentiment") is not None
            else None
        )
        item["channels"] = [c for c in (item.get("channels") or []) if c]
        items.append(item)
    return {"count": len(items), "users": items}


@router.get("/context/{user_id}")
async def context(user_id: str, limit: int = Query(40, ge=1, le=120)) -> dict:
    """One live operator context: transcript, CRM, activity, documents, calls, and risk."""
    turns = await get_short_term_buffer().recent(user_id, n=limit)

    with db_cursor() as cur:
        cur.execute("SELECT * FROM citizens WHERE user_id = %s", (user_id,))
        profile = cur.fetchone()

        cur.execute(
            """
            SELECT *
            FROM cases
            WHERE user_id = %s
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 25
            """,
            (user_id,),
        )
        cases = cur.fetchall()

        cur.execute(
            """SELECT id, channel, event_type, summary, payload, created_at
               FROM activity_events WHERE user_id = %s ORDER BY id DESC LIMIT 40""",
            (user_id,),
        )
        activity = cur.fetchall()

        cur.execute(
            """SELECT id, document_type, status, original_name, content_type, file_size,
                      confidence, extracted_fields, signals, case_number, created_at
               FROM customer_documents WHERE user_id = %s ORDER BY created_at DESC LIMIT 20""",
            (user_id,),
        )
        documents = cur.fetchall()

        cur.execute(
            """SELECT id, call_id, language, duration_seconds, summary, service, intent,
                      resolved, qa_score, sentiment_avg, escalated, case_number, created_at
               FROM call_recordings WHERE user_id = %s ORDER BY created_at DESC LIMIT 10""",
            (user_id,),
        )
        recordings = cur.fetchall()

        cur.execute(
            """SELECT n.id, n.channel, n.template, n.payload, n.scheduled_at, n.sent_at,
                      n.status, n.created_at, c.case_number
               FROM notifications n
               LEFT JOIN cases c ON c.id = n.case_id
               WHERE n.user_id = %s
               ORDER BY n.scheduled_at DESC, n.created_at DESC
               LIMIT 20""",
            (user_id,),
        )
        notifications = cur.fetchall()

        cur.execute(
            """SELECT
                 COUNT(*) AS total_cases,
                 COUNT(*) FILTER (WHERE status IN ('open','in_progress','escalated')) AS open_cases,
                 COUNT(*) FILTER (WHERE status='escalated') AS escalated_cases,
                 COUNT(*) FILTER (WHERE priority IN ('high','critical')) AS high_priority,
                 COUNT(*) FILTER (WHERE status='resolved') AS resolved_cases,
                 AVG(sentiment) FILTER (WHERE sentiment IS NOT NULL) AS avg_sentiment,
                 MAX(updated_at) AS last_case_at,
                 json_agg(DISTINCT channel) AS channels
               FROM cases WHERE user_id = %s""",
            (user_id,),
        )
        agg = cur.fetchone() or {}

    profile_out = _serialize(profile)
    case_items = [_serialize(row) or {} for row in cases]
    activity_items = [_serialize(row) or {} for row in activity]
    document_items = [_serialize(row) or {} for row in documents]
    recording_items = [_serialize(row) or {} for row in recordings]
    notification_items = [_serialize(row) or {} for row in notifications]

    open_cases = int(agg.get("open_cases") or 0)
    escalated_cases = int(agg.get("escalated_cases") or 0)
    high_priority = int(agg.get("high_priority") or 0)
    avg_sentiment = float(agg["avg_sentiment"]) if agg.get("avg_sentiment") is not None else None

    has_salary = any(
        d.get("document_type") == "salary_certificate"
        and float(d.get("confidence") or 0) >= 0.7
        for d in document_items
    )
    has_emirates = any(
        d.get("document_type") == "emirates_id"
        and float(d.get("confidence") or 0) >= 0.7
        for d in document_items
    )
    housing_open = any(
        c.get("service") == "housing"
        and c.get("status") not in ("resolved", "closed")
        for c in case_items
    )
    missing_documents: list[str] = []
    if housing_open and not has_salary:
        missing_documents.append("salary_certificate")
    if housing_open and not has_emirates:
        missing_documents.append("emirates_id")

    latest_case = case_items[0] if case_items else None
    risk_score = min(
        100,
        escalated_cases * 35
        + high_priority * 20
        + open_cases * 8
        + len(missing_documents) * 10
        + (20 if avg_sentiment is not None and avg_sentiment < 0.4 else 0),
    )

    return {
        "user_id": user_id,
        "name": (profile_out or {}).get("full_name_en")
        or next((c.get("user_name") for c in case_items if c.get("user_name")), user_id),
        "profile": profile_out,
        "turns": turns,
        "cases": case_items,
        "activity": activity_items,
        "documents": document_items,
        "recordings": recording_items,
        "notifications": notification_items,
        "summary": {
            "total_cases": int(agg.get("total_cases") or 0),
            "open_cases": open_cases,
            "escalated_cases": escalated_cases,
            "high_priority": high_priority,
            "resolved_cases": int(agg.get("resolved_cases") or 0),
            "avg_sentiment": round(avg_sentiment, 2) if avg_sentiment is not None else None,
            "sentiment_label": _sentiment_label(avg_sentiment),
            "channels": [c for c in (agg.get("channels") or []) if c],
            "last_case_at": agg["last_case_at"].isoformat() if agg.get("last_case_at") else None,
        },
        "risk": {
            "score": int(risk_score),
            "band": _risk_band(int(risk_score)),
            "drivers": {
                "open_cases": open_cases,
                "escalated_cases": escalated_cases,
                "high_priority": high_priority,
                "missing_documents": missing_documents,
                "avg_sentiment": round(avg_sentiment, 2) if avg_sentiment is not None else None,
            },
        },
        "next_best_action": _next_best_action(
            latest_case,
            open_cases,
            escalated_cases,
            high_priority,
            avg_sentiment,
            missing_documents,
        ),
        "data_sources": {
            "short_term_memory_turns": len(turns),
            "crm_cases": len(case_items),
            "activity_events": len(activity_items),
            "customer_documents": len(document_items),
            "call_recordings": len(recording_items),
            "notifications": len(notification_items),
            "citizen_profile": bool(profile_out),
        },
        "fetched_at": datetime.utcnow().isoformat(),
    }


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


@router.get("/audit/recent")
def recent_audits(limit: int = Query(20, ge=1, le=80)) -> dict:
    """Recent auditable records for the admin audit console."""
    try:
        with db_cursor() as cur:
            cur.execute(
                """
                SELECT
                    c.case_number AS reference,
                    c.case_number,
                    c.correlation_id,
                    c.user_id,
                    COALESCE(ci.full_name_en, c.user_name, c.user_id) AS user_name,
                    c.title,
                    c.service,
                    c.intent,
                    c.status,
                    c.priority,
                    c.updated_at AS updated_at,
                    COALESCE(a.audit_events, 0) AS audit_events,
                    'case' AS kind
                FROM cases c
                LEFT JOIN citizens ci ON ci.user_id = c.user_id
                LEFT JOIN (
                    SELECT correlation_id, COUNT(*) AS audit_events
                    FROM audit_log
                    GROUP BY correlation_id
                ) a ON a.correlation_id = c.correlation_id
                ORDER BY c.updated_at DESC NULLS LAST, c.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            items = [_serialize(row) or {} for row in cur.fetchall()]

            remaining = max(limit - len(items), 0)
            if remaining:
                cur.execute(
                    """
                    SELECT
                        reference,
                        reference AS correlation_id,
                        user_id,
                        applicant AS user_name,
                        CONCAT(
                            'SZHP assessment: ',
                            COALESCE(recommendation, status, 'in progress')
                        ) AS title,
                        'housing' AS service,
                        'loan_rescheduling' AS intent,
                        status,
                        NULL AS priority,
                        COALESCE(decided_at, created_at) AS updated_at,
                        COALESCE(a.audit_events, 0) AS audit_events,
                        'assessment' AS kind
                    FROM szhp_assessments s
                    LEFT JOIN (
                        SELECT correlation_id, COUNT(*) AS audit_events
                        FROM audit_log
                        GROUP BY correlation_id
                    ) a ON a.correlation_id = s.reference
                    ORDER BY COALESCE(decided_at, created_at) DESC
                    LIMIT %s
                    """,
                    (remaining,),
                )
                items.extend([_serialize(row) or {} for row in cur.fetchall()])

            remaining = max(limit - len(items), 0)
            if remaining:
                cur.execute(
                    """
                    SELECT
                        COALESCE(NULLIF(case_number, ''), CONCAT('call:', id::text)) AS reference,
                        case_number,
                        COALESCE(correlation_id, CONCAT('call:', id::text)) AS correlation_id,
                        user_id,
                        user_name,
                        COALESCE(summary, CONCAT('Voice call ', call_id)) AS title,
                        service,
                        intent,
                        CASE
                            WHEN escalated THEN 'escalated'
                            WHEN resolved THEN 'resolved'
                            ELSE 'analysed'
                        END AS status,
                        CASE WHEN escalated THEN 'high' ELSE 'medium' END AS priority,
                        created_at AS updated_at,
                        COALESCE(a.audit_events, 0) AS audit_events,
                        'call' AS kind
                    FROM call_recordings r
                    LEFT JOIN (
                        SELECT correlation_id, COUNT(*) AS audit_events
                        FROM audit_log
                        GROUP BY correlation_id
                    ) a ON a.correlation_id = COALESCE(
                        r.correlation_id,
                        CONCAT('call:', r.id::text)
                    )
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (remaining,),
                )
                items.extend([_serialize(row) or {} for row in cur.fetchall()])

        items.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
        return {
            "count": len(items[:limit]),
            "items": items[:limit],
            "fetched_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"audit recent query failed: {e}") from e


@router.get("/audit/{correlation_id}")
async def audit(correlation_id: str) -> dict:
    """Audit trail for a case, call, SZHP assessment, or raw correlation id."""
    ref = correlation_id.strip()
    if not ref:
        raise HTTPException(status_code=400, detail="empty audit reference")

    try:
        with db_cursor() as cur:
            resolved = ref
            source = "correlation"
            case = None
            call = None
            assessment = None

            cur.execute(
                """
                SELECT c.*, COALESCE(ci.full_name_en, c.user_name, c.user_id) AS display_user_name
                FROM cases c
                LEFT JOIN citizens ci ON ci.user_id = c.user_id
                WHERE c.case_number = %s OR c.correlation_id = %s
                ORDER BY c.updated_at DESC
                LIMIT 1
                """,
                (ref, ref),
            )
            case = cur.fetchone()
            if case:
                resolved = case.get("correlation_id") or case.get("case_number") or ref
                source = "case"

            if not case:
                call_ref = ref[5:] if ref.startswith("call:") else ref
                cur.execute(
                    """
                    SELECT *
                    FROM call_recordings
                    WHERE id::text = %s
                       OR call_id = %s
                       OR correlation_id = %s
                       OR case_number = %s
                       OR CONCAT('call:', id::text) = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (call_ref, ref, ref, ref, ref),
                )
                call = cur.fetchone()
                if call:
                    resolved = call.get("correlation_id") or f"call:{call.get('id')}"
                    source = "call"
                    if call.get("case_number"):
                        cur.execute(
                            "SELECT * FROM cases WHERE case_number = %s LIMIT 1",
                            (call.get("case_number"),),
                        )
                        case = cur.fetchone()

            if not case and not call:
                cur.execute("SELECT * FROM szhp_assessments WHERE reference = %s LIMIT 1", (ref,))
                assessment = cur.fetchone()
                if assessment:
                    resolved = assessment.get("reference") or ref
                    source = "assessment"

            candidates = [resolved]
            if case:
                candidates.extend([case.get("case_number"), case.get("correlation_id")])
            if call:
                candidates.extend(
                    [
                        call.get("correlation_id"),
                        f"call:{call.get('id')}",
                        call.get("call_id"),
                        call.get("case_number"),
                    ]
                )
            candidates = [c for i, c in enumerate(candidates) if c and c not in candidates[:i]]

            events = []
            for candidate in candidates:
                cur.execute(
                    """
                    SELECT node, payload, created_at
                    FROM audit_log
                    WHERE correlation_id = %s
                    ORDER BY created_at, COALESCE((payload->>'_step')::int, 0)
                    """,
                    (candidate,),
                )
                rows = cur.fetchall()
                if rows:
                    resolved = candidate
                    events = [
                        _audit_event(
                            row.get("node"),
                            row.get("payload") or {},
                            row.get("created_at"),
                            synthetic=False,
                        )
                        for row in rows
                    ]
                    break

            if not events:
                if case:
                    events = _build_case_fallback(cur, case)
                elif call:
                    events = _build_call_fallback(call)
                elif assessment:
                    events = _build_assessment_fallback(assessment)

        if not (events or case or call or assessment):
            raise HTTPException(status_code=404, detail=f"no audit record found for {ref}")

        user_id = (case or call or assessment or {}).get("user_id")
        source_row = case or call or assessment or {}
        user_name = (
            source_row.get("display_user_name")
            or source_row.get("user_name")
            or (assessment or {}).get("applicant")
        )
        title = (
            _case_title(case)
            if case
            else (call or {}).get("summary")
            or (assessment or {}).get("reference")
            or ref
        )
        return {
            "reference": ref,
            "correlation_id": resolved,
            "case_number": (case or call or {}).get("case_number"),
            "user_id": user_id,
            "user_name": user_name,
            "title": title,
            "source": source,
            "source_status": (case or call or assessment or {}).get("status"),
            "events": events,
            "event_count": len(events),
            "fetched_at": datetime.utcnow().isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"audit query failed: {e}") from e
