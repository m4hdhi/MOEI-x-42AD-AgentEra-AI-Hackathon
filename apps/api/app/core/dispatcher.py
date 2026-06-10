"""Background notification dispatcher.

Wakes every NOTIF_TICK_SECONDS, finds notifications whose scheduled_at has passed,
sends them via the appropriate channel (Twilio for WhatsApp/SMS, log-only for email/push
in this demo), and updates their status to 'sent' or 'failed'.

Started from FastAPI lifespan in main.py.
"""

from __future__ import annotations

import asyncio
import json
import os

from loguru import logger

from .db import db_cursor

TICK_SECONDS = int(os.getenv("NOTIF_TICK_SECONDS", "30"))
BATCH = 25

# Second loop: scan for SLA breaches and proactively apologise. Runs far less often than the
# notification drain — 15 min is plenty of resolution for day-scale SLA deadlines.
SLA_SCAN_SECONDS = int(os.getenv("SLA_SCAN_SECONDS", "900"))
SLA_BREACH_BATCH = 100


# Templated message bodies. Citizens see these as outbound WhatsApp/SMS.
_TEMPLATES_EN = {
    "status_update": (
        "MOEI Agent42: Update on your case {case_number} — current status is {status}. "
        "Reply STATUS for details or call 800 6634."
    ),
    "doc_reminder": (
        "MOEI Agent42: We're waiting on documents for case {case_number}. "
        "Please upload your latest salary slip via WhatsApp or moei.gov.ae."
    ),
    "csat_survey": (
        "MOEI Agent42: How was your recent service experience for case {case_number}? "
        "Rate us at https://han-ringleted-dubitatively.ngrok-free.dev/csat?case={case_number} "
        "or reply 1-5 here (5 = excellent). Your feedback helps us improve."
    ),
    "proactive_tip": (
        "MOEI Agent42: Based on your housing rescheduling, you may also be eligible for "
        "the SZHP Hardship Programme. Reply INFO to learn more."
    ),
}


def _render(template: str, case_number: str | None, status: str | None) -> str:
    body = _TEMPLATES_EN.get(template, "MOEI Agent42: We have an update for you. Call 800 6634.")
    return body.format(case_number=case_number or "(no case)", status=status or "open")


def _lookup_wa_number(user_id: str) -> str | None:
    try:
        with db_cursor() as cur:
            cur.execute(
                "SELECT wa_number FROM whatsapp_identities WHERE user_id = %s "
                "ORDER BY last_seen_at DESC LIMIT 1",
                (user_id,),
            )
            row = cur.fetchone()
            if row:
                return row["wa_number"]
    except Exception as e:
        logger.warning(f"[notif] wa lookup failed for {user_id}: {e}")
    return None


def _lookup_case(case_id) -> tuple[str | None, str | None]:
    try:
        with db_cursor() as cur:
            cur.execute("SELECT case_number, status FROM cases WHERE id = %s", (case_id,))
            row = cur.fetchone()
            if row:
                return row["case_number"], row["status"]
    except Exception as e:
        logger.warning(f"[notif] case lookup failed for {case_id}: {e}")
    return None, None


async def _send_one(notif: dict) -> tuple[bool, str | None]:
    """Send one notification. Returns (sent_ok, error_message_or_None)."""
    channel = notif.get("channel")
    user_id = notif.get("user_id")

    case_number = None
    status = None
    if notif.get("case_id"):
        case_number, status = await asyncio.to_thread(_lookup_case, notif["case_id"])

    body = _render(notif["template"], case_number, status)

    if channel in ("whatsapp", "sms"):
        return await _send_twilio(channel, user_id, body)
    if channel in ("email", "push"):
        logger.info(f"[notif] (would send via {channel}) → {user_id}: {body[:80]}")
        return True, None
    return False, f"unknown channel {channel}"


async def _send_twilio(channel: str, user_id: str, body: str) -> tuple[bool, str | None]:
    """Send WhatsApp or SMS via Twilio REST API."""
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not (sid and token):
        # Demo: dry-run when credentials missing
        logger.info(f"[notif:dry-run] {channel} → {user_id}: {body[:80]}")
        return True, None

    # Reverse-lookup Emirates ID → WhatsApp number via the whatsapp_identities table.
    # Citizens who self-onboarded via WhatsApp inbound are reachable; synthetic seed users aren't.
    to = await asyncio.to_thread(_lookup_wa_number, user_id)
    if not to:
        logger.info(f"[notif:dry-run] no WhatsApp mapping for {user_id}, dropping")
        return True, "no_mapping_dry_run"

    sandbox_from = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
    body = body[:1500]
    try:
        import httpx

        url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                url, data={"From": sandbox_from, "To": to, "Body": body}, auth=(sid, token)
            )
            if r.status_code >= 300:
                return False, f"twilio {r.status_code}: {r.text[:200]}"
        return True, None
    except Exception as e:
        return False, f"twilio_exception: {e}"


def _fetch_due_notifications() -> list[dict]:
    try:
        with db_cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, case_id, channel, template, payload, scheduled_at
                FROM notifications
                WHERE status = 'scheduled' AND scheduled_at <= NOW()
                ORDER BY scheduled_at ASC
                LIMIT %s
                """,
                (BATCH,),
            )
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.warning(f"[notif] could not query due notifications: {e}")
        return []


def _mark_sent(notification_id, user_id, channel, template) -> None:
    try:
        with db_cursor() as cur:
            cur.execute(
                "UPDATE notifications SET status = 'sent', sent_at = NOW() WHERE id = %s",
                (notification_id,),
            )
            cur.execute(
                """
                INSERT INTO activity_events (user_id, channel, event_type, summary, payload)
                VALUES (%s, %s, 'notification_sent', %s, %s::jsonb)
                """,
                (
                    user_id,
                    channel,
                    f"{template} sent via {channel}",
                    json.dumps({"notification_id": str(notification_id), "template": template}),
                ),
            )
    except Exception as e:
        logger.warning(f"[notif] mark_sent failed: {e}")


def _mark_failed(notification_id) -> None:
    try:
        with db_cursor() as cur:
            cur.execute(
                "UPDATE notifications SET status = 'failed' WHERE id = %s",
                (notification_id,),
            )
    except Exception as e:
        logger.warning(f"[notif] mark_failed update failed: {e}")


async def _drain_due_notifications() -> int:
    """Process one batch of due notifications. Returns the number processed."""
    due = await asyncio.to_thread(_fetch_due_notifications)
    if not due:
        return 0

    sent_count = 0
    for n in due:
        ok, err = await _send_one(n)
        if ok:
            await asyncio.to_thread(_mark_sent, n["id"], n["user_id"], n["channel"], n["template"])
            sent_count += 1
        else:
            await asyncio.to_thread(_mark_failed, n["id"])
            logger.warning(f"[notif] send failed for {n['id']}: {err}")
    return sent_count


# ============================ SLA BREACH SCAN ============================
# Every SLA_SCAN_SECONDS we look for cases that have blown their `sla_deadline` while still
# unresolved/unescalated. Each is flagged (sla_met = 'No'), the citizen gets a proactive
# WhatsApp apology, and the breach is recorded in Langfuse. The `sla_met IS DISTINCT FROM 'No'`
# guard means a given case is only notified once, no matter how many scans it lives through.

_SLA_APOLOGY = (
    "MOEI Agent42: We apologize for the delay on your request {case_number}. "
    "A senior agent will contact you within 24 hours."
)


def _fetch_sla_breaches() -> list[dict]:
    try:
        with db_cursor() as cur:
            cur.execute(
                """
                SELECT id, case_number, user_id, channel, priority_tier, sla_deadline
                FROM cases
                WHERE sla_deadline IS NOT NULL
                  AND sla_deadline < NOW()
                  AND status NOT IN ('resolved', 'escalated')
                  AND sla_met IS DISTINCT FROM 'No'
                ORDER BY sla_deadline ASC
                LIMIT %s
                """,
                (SLA_BREACH_BATCH,),
            )
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.warning(f"[sla-scan] could not query breaches (migration applied?): {e}")
        return []


def _mark_breached(case_id) -> None:
    try:
        with db_cursor() as cur:
            cur.execute(
                "UPDATE cases SET sla_met = 'No', updated_at = NOW() WHERE id = %s", (case_id,)
            )
    except Exception as e:
        logger.warning(f"[sla-scan] mark_breached failed for {case_id}: {e}")


def _log_breach_to_langfuse(case: dict) -> None:
    try:
        from hassan.observability.langfuse_setup import get_langfuse_client

        lf = get_langfuse_client()
        if lf is None:
            return
        lf.trace(
            name="sla_breach",
            user_id=case.get("user_id"),
            metadata={
                "case_number": case.get("case_number"),
                "channel": case.get("channel"),
                "priority_tier": case.get("priority_tier"),
                "sla_deadline": case["sla_deadline"].isoformat()
                if case.get("sla_deadline")
                else None,
            },
            tags=["sla_breach"],
        )
        lf.flush()
    except Exception as e:
        logger.warning(f"[sla-scan] langfuse log failed: {e}")


async def _handle_breach(case: dict) -> None:
    """Flag the case, send the proactive WhatsApp apology, and log to Langfuse."""
    await asyncio.to_thread(_mark_breached, case["id"])

    body = _SLA_APOLOGY.format(case_number=case.get("case_number") or "(no case)")
    wa_number = await asyncio.to_thread(_lookup_wa_number, case.get("user_id"))
    if wa_number:
        try:
            from .whatsapp_meta import send_text

            ok = await send_text(to_wa_id=wa_number, body=body)
            if not ok:
                logger.warning(
                    f"[sla-scan] WhatsApp apology not delivered for {case.get('case_number')}"
                )
        except Exception as e:
            logger.warning(f"[sla-scan] WhatsApp send error for {case.get('case_number')}: {e}")
    else:
        logger.info(
            f"[sla-scan:dry-run] no WhatsApp mapping for {case.get('user_id')}, skipping send"
        )

    await asyncio.to_thread(_log_breach_to_langfuse, case)


async def _scan_sla_breaches() -> int:
    """Process one batch of SLA breaches. Returns the number handled."""
    breaches = await asyncio.to_thread(_fetch_sla_breaches)
    for case in breaches:
        await _handle_breach(case)
    return len(breaches)


_task: asyncio.Task | None = None
_sla_task: asyncio.Task | None = None


async def _loop() -> None:
    logger.info(f"[notif-dispatcher] starting, tick={TICK_SECONDS}s")
    while True:
        try:
            n = await _drain_due_notifications()
            if n:
                logger.info(f"[notif-dispatcher] sent {n} notifications")
        except Exception as e:
            logger.exception(f"[notif-dispatcher] loop error: {e}")
        await asyncio.sleep(TICK_SECONDS)


async def _sla_loop() -> None:
    logger.info(f"[sla-scan] starting, tick={SLA_SCAN_SECONDS}s")
    while True:
        try:
            n = await _scan_sla_breaches()
            if n:
                logger.info(f"[sla-scan] flagged + notified {n} SLA breaches")
        except Exception as e:
            logger.exception(f"[sla-scan] loop error: {e}")
        await asyncio.sleep(SLA_SCAN_SECONDS)


def start_dispatcher_background() -> None:
    global _task, _sla_task
    loop = asyncio.get_event_loop()
    if _task is None or _task.done():
        _task = loop.create_task(_loop())
    if _sla_task is None or _sla_task.done():
        _sla_task = loop.create_task(_sla_loop())


def stop_dispatcher_background() -> None:
    global _task, _sla_task
    if _task and not _task.done():
        _task.cancel()
    if _sla_task and not _sla_task.done():
        _sla_task.cancel()
