"""CRM cases REST API. Powers /copilot CRM panel + /exec case stats."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Body, HTTPException, Query

from ..core.db import db_cursor

router = APIRouter(prefix="/crm", tags=["crm"])


@router.get("/agent-network")
def agent_network() -> dict:
    """The multi-agent ecosystem: a master supervisor coordinating specialist agents.

    Returns each specialist agent with how many cases it has handled, so the admin
    'Agent Network' view can visualise the architecture (Idea #8 in the challenge guide).
    """
    roster = [
        {"id": "housing", "name": "Housing Agent", "desc": "Sheikh Zayed Housing Programme — loans, rescheduling, hardship", "icon": "home"},
        {"id": "energy", "name": "Energy Agent", "desc": "Electricity & water, tariffs, outages", "icon": "zap"},
        {"id": "transport", "name": "Transport Agent", "desc": "Federal vehicle & driver services", "icon": "car"},
        {"id": "maritime", "name": "Maritime Agent", "desc": "Vessels, ports, seafarer certificates", "icon": "anchor"},
        {"id": "infrastructure", "name": "Infrastructure Agent", "desc": "Roads, public works, geological data", "icon": "construction"},
        {"id": "complaints", "name": "Complaints Agent", "desc": "Grievance de-escalation & resolution", "icon": "alert"},
    ]
    counts: dict[str, int] = {}
    try:
        with db_cursor() as cur:
            cur.execute("SELECT service, COUNT(*) AS n FROM cases GROUP BY service")
            for r in cur.fetchall():
                counts[(r["service"] or "unknown")] = int(r["n"])
            cur.execute("SELECT COUNT(*) AS n FROM cases WHERE intent = 'complaint'")
            counts["complaints"] = int((cur.fetchone() or {}).get("n") or 0)
    except Exception:
        pass

    for a in roster:
        a["handled"] = counts.get(a["id"], 0)

    total = sum(counts.get(a["id"], 0) for a in roster)
    return {
        "master": {
            "name": "MOEI Supervisor (Master Agent)",
            "desc": "Routes every request, holds cross-channel memory, enforces guardrails, and coordinates the specialist agents.",
            "pipeline": ["Router", "Sentiment", "Memory", "Guardrails", "Dispatcher", "Critic", "Escalation", "Composer", "Next-Best-Action", "Persist"],
            "total_handled": total,
        },
        "agents": roster,
        "support_agents": [
            {"name": "Knowledge Agent", "desc": "RAG retrieval over services, policies, FAQs, crawled MOEI pages"},
            {"name": "Post-Call Analyst", "desc": "Summarises calls, scores quality, detects sentiment trajectory"},
            {"name": "Escalation Predictor", "desc": "ML model flagging complaint/escalation risk before it happens"},
        ],
    }


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
      - channel_deflection_pct       : % of cases handled fully by Agent42 (status != 'escalated')
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


def _digital_twin(cases: list, recordings: list, feedback: list) -> dict:
    """A learning digital representation of the citizen (Challenge guide Idea #1/#6).

    Derives preferred channel, frequent services, satisfaction trend, a predicted next need,
    and a light life-event signal — all from the citizen's own history.
    """
    from collections import Counter

    chan = Counter(c.get("channel") for c in cases if c.get("channel"))
    svc = Counter(c.get("service") for c in cases if c.get("service") and c.get("service") != "unknown")
    preferred_channel = chan.most_common(1)[0][0] if chan else None
    top_services = [s for s, _ in svc.most_common(3)]

    # Satisfaction trend: average sentiment of the most recent 5 cases vs the previous 5.
    sents = [float(c["sentiment"]) for c in cases if c.get("sentiment") is not None]
    trend = "stable"
    if len(sents) >= 4:
        recent = sum(sents[: len(sents) // 2]) / max(1, len(sents) // 2)
        older = sum(sents[len(sents) // 2:]) / max(1, len(sents) - len(sents) // 2)
        if recent - older > 0.08:
            trend = "improving"
        elif older - recent > 0.08:
            trend = "declining"

    open_cases = [c for c in cases if c.get("status") in ("open", "in_progress", "escalated")]
    dominant = top_services[0] if top_services else None

    # Predicted next need — simple, transparent heuristic over history.
    if open_cases:
        oc = open_cases[0]
        predicted = f"Likely to follow up on {oc.get('service','their')} case {oc.get('case_number','')}"
    elif dominant == "housing":
        predicted = "May ask about Sheikh Zayed Housing Programme documents or instalment status"
    elif dominant:
        predicted = f"Likely to need another {dominant} service soon"
    else:
        predicted = "No active need predicted"

    # Light life-event signal from frequent services.
    life_event = None
    if "housing" in top_services:
        life_event = "Housing journey in progress (possible new home / family growth)"
    elif "maritime" in top_services:
        life_event = "Active vessel / maritime licence holder"
    elif "transport" in top_services:
        life_event = "Frequent transport-services user"

    avg_csat = None
    csats = [int(f["csat"]) for f in feedback if f.get("csat") is not None]
    if csats:
        avg_csat = round(sum(csats) / len(csats), 1)

    return {
        "preferred_channel": preferred_channel,
        "frequent_services": top_services,
        "satisfaction_trend": trend,
        "predicted_next_need": predicted,
        "life_event_signal": life_event,
        "calls_recorded": len(recordings),
        "avg_csat": avg_csat,
    }


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

        # Unified cross-channel interaction history (WhatsApp / Voice / Web), keyed by Customer ID.
        # This is what lets any channel retrieve "everything this customer ever did" (challenge Q8/Q20).
        cur.execute(
            """SELECT interaction_id, channel, occurred_at, intent, service_category,
                      sub_service, message_sample, sentiment_label, sentiment_score, csat,
                      escalated, resolution_status, case_id
               FROM interactions WHERE customer_id = %s
               ORDER BY occurred_at DESC NULLS LAST LIMIT 80""",
            (user_id,),
        )
        interactions = cur.fetchall()

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

    if not profile and not cases and not activity and not interactions:
        raise HTTPException(404, f"no record for {user_id}")

    # Cross-channel interaction breakdown (the unified-memory headline metric).
    from collections import Counter as _Counter
    _ix_chan = _Counter(i.get("channel") for i in interactions if i.get("channel"))

    twin = _digital_twin(cases, recordings, feedback)

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
            "total_interactions": len(interactions),
            "interaction_channels": dict(_ix_chan),
            "cross_channel": len(_ix_chan) >= 2,
        },
        "twin": twin,
        "cases": [_serialize(r) for r in cases],
        "interactions": [_serialize(r) for r in interactions],
        "activity": [_serialize(r) for r in activity],
        "recordings": [_serialize(r) for r in recordings],
        "feedback": [_serialize(r) for r in feedback],
    }


@router.get("/identify")
def identify(phone: str | None = None, customer_id: str | None = None) -> dict:
    """Resolve a caller to their unified profile from a real-time identifier (challenge Q10).

    Phone number is the primary cross-channel key (present on WhatsApp, voice, and app login,
    no extra step). Returns the unified CRM profile + a compact cross-channel snapshot so any
    channel can greet the customer by name and continue where they left off — without asking
    them to repeat anything (challenge Q8/Q20).
    """
    if not phone and not customer_id:
        raise HTTPException(400, "provide phone or customer_id")

    with db_cursor() as cur:
        if customer_id:
            cur.execute("SELECT * FROM citizens WHERE customer_id = %s OR user_id = %s LIMIT 1", (customer_id, customer_id))
        else:
            norm = "".join(ch for ch in phone if ch.isdigit())[-9:]  # last 9 digits — robust to +971/0 prefixes
            cur.execute("SELECT * FROM citizens WHERE regexp_replace(mobile, '[^0-9]', '', 'g') LIKE %s LIMIT 1", (f"%{norm}",))
        profile = cur.fetchone()
        if not profile:
            return {"found": False, "phone": phone, "customer_id": customer_id}

        cid = profile["customer_id"] or profile["user_id"]
        cur.execute(
            """SELECT channel, occurred_at, intent, service_category, case_id
               FROM interactions WHERE customer_id = %s ORDER BY occurred_at DESC NULLS LAST LIMIT 5""",
            (cid,),
        )
        recent = cur.fetchall()
        cur.execute(
            """SELECT case_number, service, status, priority, sla_met
               FROM cases WHERE user_id = %s AND status NOT IN ('closed','resolved')
               ORDER BY created_at DESC LIMIT 5""",
            (cid,),
        )
        open_cases = cur.fetchall()
        cur.execute("SELECT count(DISTINCT channel) AS ch FROM interactions WHERE customer_id = %s", (cid,))
        nch = (cur.fetchone() or {}).get("ch") or 0

    last = recent[0] if recent else None
    return {
        "found": True,
        "customer_id": cid,
        "name": profile.get("full_name_en"),
        "name_ar": profile.get("full_name_ar"),
        "vip_tier": profile.get("vip_tier"),
        "risk_flag": profile.get("risk_flag"),
        "preferred_channel": profile.get("preferred_channel"),
        "emirate": profile.get("emirate"),
        "language": profile.get("preferred_language"),
        "open_cases": [_serialize(c) for c in open_cases],
        "cross_channel": int(nch) >= 2,
        "channels_seen": int(nch),
        "last_interaction": _serialize(last) if last else None,
        "recent_interactions": [_serialize(r) for r in recent],
        "greeting": _greeting(profile, last, open_cases),
    }


def _greeting(profile: dict, last: dict | None, open_cases: list) -> str:
    """A ready-to-speak opening line the agent/bot can use immediately — no 'please hold'."""
    name = (profile.get("full_name_en") or "").split(" ")[0] or "there"
    if open_cases:
        c = open_cases[0]
        return f"Welcome back, {name}. I can see your {c.get('service','')} case {c.get('case_number','')} is {c.get('status','open')} — would you like an update?"
    if last and last.get("service_category"):
        return f"Welcome back, {name}. Last time you contacted us about {last.get('service_category')} on {last.get('channel')}. How can I help today?"
    return f"Welcome back, {name}. How can I help you today?"


def _sentiment_label(score: float | None) -> str:
    if score is None:
        return "unknown"
    if score < 0.34:
        return "negative"
    if score < 0.66:
        return "neutral"
    return "positive"


def _recommended_action(case: dict, interaction_count: int) -> str:
    """A concrete next step for the human agent picking this case up — derived from its state."""
    status = (case.get("status") or "open").lower()
    sentiment = case.get("sentiment")
    if status == "escalated" or case.get("escalated"):
        return ("Take ownership now — this case is escalated. Call the citizen and resolve "
                "within SLA.")
    if status in ("resolved", "closed"):
        return "Close the loop: send a CSAT survey and confirm the citizen is satisfied."
    if sentiment is not None and float(sentiment) < 0.4:
        return ("Lead with empathy — sentiment is negative. Apologise, give a firm timeline, "
                "and offer a proactive update.")
    if interaction_count >= 2:
        return ("Citizen has reached out on multiple channels — confirm the latest status and the "
                "next milestone (e.g. field visit) so they don't have to ask again.")
    return "Provide a status update and confirm the next concrete milestone for the citizen."


@router.get("/agent-context")
def agent_context(case_id: str = Query(..., description="Case number, e.g. MOEI-CASE-...")) -> dict:
    """Agent-handoff context card: everything a human needs to take over a case in one glance.

    When the AI hands a case to a person (or a person opens one), this is the screen they get:
    who the citizen is, what the case is about, how they feel, the recommended next action, and
    the full cross-channel interaction history — so the agent never makes the citizen repeat
    themselves (challenge Q8/Q20).
    """
    with db_cursor() as cur:
        cur.execute("SELECT * FROM cases WHERE case_number = %s", (case_id,))
        case = cur.fetchone()
        if not case:
            raise HTTPException(404, f"case {case_id} not found")

        user_id = case["user_id"]
        customer_id = case.get("customer_id") or user_id

        # Customer name: prefer the master profile, fall back to the name on the case.
        cur.execute(
            "SELECT full_name_en, full_name_ar, vip_tier, preferred_channel, mobile, emirate "
            "FROM citizens WHERE user_id = %s OR customer_id = %s LIMIT 1",
            (user_id, customer_id),
        )
        profile = cur.fetchone() or {}
        customer_name = profile.get("full_name_en") or case.get("user_name") or user_id

        # Cross-channel interaction history — live supervisor turns from the audit log
        # (one entry per turn, any channel), so the web + WhatsApp turns both show up.
        cur.execute(
            """
            SELECT correlation_id, channel, node, payload, created_at
            FROM audit_log
            WHERE user_id = %s AND node IN ('Request', 'Reply')
            ORDER BY created_at ASC
            """,
            (user_id,),
        )
        rows = cur.fetchall()

        # Also pull any pre-existing/seeded interaction rows for this customer.
        cur.execute(
            """
            SELECT channel, occurred_at, intent, service_category, message_sample
            FROM interactions WHERE customer_id = %s
            ORDER BY occurred_at ASC NULLS LAST
            """,
            (customer_id,),
        )
        seeded = cur.fetchall()

    # Fold the audit rows into one entry per turn (correlation_id), in time order.
    turns: dict[str, dict] = {}
    order: list[str] = []
    for r in rows:
        cid = r["correlation_id"]
        if cid not in turns:
            turns[cid] = {"channel": r["channel"], "at": r["created_at"],
                          "message": None, "reply": None}
            order.append(cid)
        payload = r.get("payload") or {}
        if r["node"] == "Request":
            turns[cid]["message"] = payload.get("message")
            turns[cid]["channel"] = r["channel"] or turns[cid]["channel"]
            turns[cid]["at"] = r["created_at"]
        elif r["node"] == "Reply":
            turns[cid]["reply"] = payload.get("text")

    interaction_history: list[dict] = []
    for cid in order:
        t = turns[cid]
        interaction_history.append({
            "source": "live",
            "channel": t["channel"],
            "at": t["at"].isoformat() if hasattr(t["at"], "isoformat") else t["at"],
            "message": t["message"],
            "agent_reply": t["reply"],
        })
    for s in seeded:
        interaction_history.append({
            "source": "history",
            "channel": s.get("channel"),
            "at": s["occurred_at"].isoformat() if s.get("occurred_at") else None,
            "intent": s.get("intent"),
            "service": s.get("service_category"),
            "message": s.get("message_sample"),
        })

    sentiment = float(case["sentiment"]) if case.get("sentiment") is not None else None
    case_summary = case.get("title") or f"{case.get('service', 'service')} request"
    if case.get("description"):
        case_summary = f"{case_summary} — {case['description']}"

    return {
        "case_id": case_id,
        "case_number": case_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "customer_name_ar": profile.get("full_name_ar"),
        "vip_tier": profile.get("vip_tier"),
        "preferred_channel": profile.get("preferred_channel"),
        "service": case.get("service"),
        "status": case.get("status"),
        "priority": case.get("priority"),
        "case_summary": case_summary,
        "sentiment": sentiment,
        "sentiment_label": _sentiment_label(sentiment),
        "recommended_action": _recommended_action(dict(case), len(interaction_history)),
        "channels_seen": sorted({i["channel"] for i in interaction_history if i.get("channel")}),
        "interaction_history": interaction_history,
    }


@router.get("/citizens/{user_id}/recommendations")
def citizen_recommendations(user_id: str) -> dict:
    """Hyper-personalized service recommendations (challenge Idea #9).

    Derived from the citizen's own history: open cases, frequent services, recent life-event
    signals, and preferred channel. Powers a 'Recommended for you' panel on the citizen surface.
    """
    from collections import Counter
    recs: list[dict] = []
    try:
        with db_cursor() as cur:
            cur.execute("SELECT service, status, case_number, intent FROM cases WHERE user_id=%s ORDER BY created_at DESC LIMIT 50", (user_id,))
            cases = [dict(r) for r in cur.fetchall()]
            cur.execute("""SELECT summary, payload FROM activity_events
                           WHERE user_id=%s AND event_type='life_event' ORDER BY id DESC LIMIT 3""", (user_id,))
            life = [dict(r) for r in cur.fetchall()]
    except Exception:
        cases, life = [], []

    open_cases = [c for c in cases if c.get("status") in ("open", "in_progress", "escalated")]
    svc = Counter(c["service"] for c in cases if c.get("service") and c["service"] != "unknown")

    for oc in open_cases[:2]:
        recs.append({
            "title": f"Track your {oc['service']} request",
            "reason": f"You have an open case ({oc['case_number']})",
            "action": "Check status", "href": "/chat",
        })
    for ev in life:
        rec_text = (ev.get("payload") or {}).get("recommendation") or ev.get("summary", "")
        recs.append({"title": "Based on your situation", "reason": rec_text.replace("🎯 Life-event detected · ", ""),
                     "action": "Explore", "href": "/chat"})
    SVC_REC = {
        "housing": ("Sheikh Zayed Housing Programme", "You often use housing services"),
        "energy": ("Energy & water services", "You often use energy services"),
        "maritime": ("Maritime & vessel services", "You often use maritime services"),
        "transport": ("Transport services", "You often use transport services"),
        "infrastructure": ("Infrastructure services", "You often use infrastructure services"),
    }
    for s, _ in svc.most_common(2):
        if s in SVC_REC and not any(s in r["title"].lower() for r in recs):
            t, why = SVC_REC[s]
            recs.append({"title": t, "reason": why, "action": "Open service", "href": "/chat"})

    if not recs:
        recs.append({"title": "Explore MOEI services", "reason": "Popular this month",
                     "action": "Browse", "href": "/chat"})
    return {"user_id": user_id, "recommendations": recs[:4]}


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
