"""WhatsApp ingress via Twilio Sandbox.

WhatsApp has a hard 15-second webhook timeout — if we hold the request open while the
supervisor reasons (LLM + tools + critic = ~30-60s for the cold path), Twilio drops it
and the citizen never gets a reply.

Strategy: ACK Twilio immediately with empty TwiML, then run the supervisor in the
background and push the actual reply via Twilio REST API as a follow-up message.
"""

from __future__ import annotations

import json
import os
import random
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse
from hassan.supervisor.graph import run_supervisor
from loguru import logger

from ..core import whatsapp_meta
from ..core.db import db_cursor

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

# Reply transport: (to, body) -> None. Lets one supervisor pipeline serve both Twilio and Meta.
SendFn = Callable[[str, str], Awaitable[None]]


# Twilio Sandbox WhatsApp number (the From: when we send back)
_SANDBOX_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")


def _synthetic_emirates_id() -> str:
    """Generate a syntactically-valid synthetic Emirates ID for a demo guest.

    Format: 784-YYYY-NNNNNNN-C. Stamped to make obvious it's not real (year 9999).
    """
    seq = random.randint(1_000_000, 9_999_999)
    check = random.randint(0, 9)
    return f"784-9999-{seq}-{check}"


def _resolve_identity(sender: str, profile_name: str | None) -> tuple[str, str | None, bool]:
    """Map a WhatsApp sender to (user_id, display_name, is_new_guest).

    Looks up whatsapp_identities. If unknown, auto-onboards as a synthetic demo guest so
    judges can chat without us pre-registering their phone number.
    """
    try:
        with db_cursor() as cur:
            cur.execute(
                "SELECT user_id, display_name, is_demo_guest FROM whatsapp_identities WHERE wa_number = %s",
                (sender,),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "UPDATE whatsapp_identities SET last_seen_at = NOW() WHERE wa_number = %s",
                    (sender,),
                )
                return row["user_id"], row["display_name"], False

            user_id = _synthetic_emirates_id()
            display_name = (profile_name or "WhatsApp Guest").strip()[:80]
            cur.execute(
                """
                INSERT INTO whatsapp_identities (wa_number, user_id, display_name, is_demo_guest)
                VALUES (%s, %s, %s, TRUE)
                ON CONFLICT (wa_number) DO NOTHING
                """,
                (sender, user_id, display_name),
            )
            logger.info(f"wa_onboard: new guest {sender} → {user_id} ({display_name})")
            return user_id, display_name, True
    except Exception as e:
        logger.warning(f"wa_identity_lookup_failed: {e}; falling back to raw sender")
        return sender, profile_name, False


def _public_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", ""))
    return f"{proto}://{host}{request.url.path}"


def _verify_signature(public_url: str, params: dict[str, str], sig: str) -> bool:
    auth = os.getenv("TWILIO_AUTH_TOKEN")
    if not auth or os.getenv("TWILIO_SKIP_SIGNATURE_CHECK") == "1":
        return True
    try:
        from twilio.request_validator import RequestValidator

        v = RequestValidator(auth)
        ok = v.validate(public_url, params, sig)
        if not ok:
            logger.warning(f"twilio_sig_fail: url={public_url} sig={sig[:20]}...")
        return ok
    except Exception as e:
        logger.warning(f"twilio_sig_exception: {e}")
        return False


async def _process_and_reply(
    *, sender: str, body: str, sid: str, profile_name: str | None = None, send: SendFn
) -> None:
    """Run the supervisor in the background, then push the reply via ``send`` (Twilio or Meta)."""
    user_id, display_name, is_new_guest = _resolve_identity(sender, profile_name)
    logger.info(f"wa_bg: supervisor for {sender} → {user_id} new_guest={is_new_guest}")
    try:
        result = await run_supervisor(
            user_id=user_id,
            channel="whatsapp",
            session_id=sid,
            language="auto",
            text=body,
            user_name=display_name,
        )
        reply = result.get("reply", "")
        if not reply:
            logger.warning(f"wa_bg: empty reply for sid={sid}")
            return

        if is_new_guest:
            reply = (
                "👋 Welcome to the Ministry of Energy and Infrastructure.\n"
                "You can ask about housing, energy, transport, maritime, or infrastructure services in Arabic or English.\n\n"
                + reply
            )
        await send(sender, reply)
        logger.info(f"wa_bg: sent reply ({len(reply)} chars) to {sender}")
    except Exception as e:
        logger.exception(f"wa_bg: failed for {sender}: {e}")
        # Best-effort error message so the citizen isn't left hanging.
        try:
            await send(
                sender,
                "Sorry — Hassan is having a brief technical issue. "
                "Please try again in a moment, or call 800 6634.",
            )
        except Exception as inner:
            logger.debug(f"wa_bg: error-fallback send failed: {inner}")


async def _send_whatsapp(*, to: str, body: str) -> None:
    """Send an outbound WhatsApp via Twilio REST API."""
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not (sid and token):
        logger.warning("Twilio creds missing — cannot send outbound message")
        return

    import httpx

    url = f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json"
    # WhatsApp caps each message at 1600 chars; trim defensively.
    body = body[:1500]
    data = {"From": _SANDBOX_FROM, "To": to, "Body": body}
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(url, data=data, auth=(sid, token))
        if r.status_code >= 300:
            logger.warning(f"twilio_send_failed: {r.status_code} {r.text[:200]}")


async def _twilio_send(to: str, body: str) -> None:
    """Reply transport for the Twilio sandbox path."""
    await _send_whatsapp(to=to, body=body)


async def _meta_send(to: str, body: str) -> None:
    """Reply transport for the Meta Cloud API path."""
    await whatsapp_meta.send_text(to_wa_id=to, body=body)


@router.get("/sandbox-info")
def sandbox_info() -> dict:
    """Public info for the 'Try on WhatsApp' card on the citizen site.

    Prefers the Meta Cloud API number ("MOEI Assistant (Demo)", no join code) when
    META_WHATSAPP_NUMBER is set; otherwise falls back to the Twilio sandbox join flow.
    """
    from urllib.parse import quote

    meta_number = os.getenv("META_WHATSAPP_NUMBER", "").strip()
    if meta_number:
        digits = "".join(c for c in meta_number if c.isdigit())
        return {
            "number": meta_number,
            "join_code": "",  # Meta needs no sandbox join code
            "wa_link": f"https://wa.me/{digits}",
            "note": "Replies arrive within seconds. Available in Arabic and English.",
        }

    join = os.getenv("TWILIO_SANDBOX_JOIN", "join nose-bell")
    number = os.getenv("TWILIO_SANDBOX_NUMBER", "+14155238886")
    digits = "".join(c for c in number if c.isdigit())
    wa_link = f"https://wa.me/{digits}?text={quote(join)}"
    return {
        "number": number,
        "join_code": join,
        "wa_link": wa_link,
        "note": "Replies arrive within seconds. Free of charge. Available in Arabic and English.",
    }


@router.post("/inbound")
async def twilio_inbound(request: Request, background: BackgroundTasks) -> Response:
    """Receive a Twilio WhatsApp webhook. ACK instantly, do work in background."""
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}
    sig = request.headers.get("X-Twilio-Signature", "")
    public_url = _public_url(request)

    if not _verify_signature(public_url, params, sig):
        logger.warning(f"WA REJECTED url={public_url} keys={list(params)[:6]}")
        raise HTTPException(status_code=403, detail="invalid Twilio signature")

    sender = params.get("From", "")
    body = params.get("Body", "")
    sid = params.get("MessageSid", "wa-unknown")
    profile_name = params.get("ProfileName") or None

    if not body:
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="application/xml",
        )

    logger.info(f"whatsapp_in: from={sender} name={profile_name!r} text={body[:80]!r}")

    # Kick off the actual work in the background. FastAPI runs it after we return.
    background.add_task(
        _process_and_reply,
        sender=sender,
        body=body,
        sid=sid,
        profile_name=profile_name,
        send=_twilio_send,
    )

    # Send a tiny ACK so the citizen sees a typing/received state immediately.
    # Keep this VERY short — anything longer than ~14s round-trip kills the webhook.
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        media_type="application/xml",
    )


@router.get("/webhook")
async def meta_verify(
    hub_mode: str | None = Query(None, alias="hub.mode"),
    hub_verify_token: str | None = Query(None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(None, alias="hub.challenge"),
) -> Response:
    """Meta webhook verification handshake (GET). Echo the challenge when the token matches."""
    challenge = whatsapp_meta.verify_webhook(hub_mode, hub_verify_token, hub_challenge)
    if challenge is None:
        raise HTTPException(status_code=403, detail="verification failed")
    return PlainTextResponse(content=challenge)


@router.post("/webhook")
async def meta_inbound(request: Request, background: BackgroundTasks) -> Response:
    """Meta WhatsApp webhook (POST): validate signature, ACK 200 fast, process in background."""
    raw = await request.body()
    if not whatsapp_meta.verify_signature(raw, request.headers.get("X-Hub-Signature-256")):
        logger.warning("meta_webhook: invalid signature")
        raise HTTPException(status_code=403, detail="invalid signature")

    try:
        payload = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        # ACK malformed bodies so Meta stops retrying.
        return Response(status_code=200)

    for msg in whatsapp_meta.parse_inbound(payload):
        sender = whatsapp_meta.canonical_wa_key(msg.wa_id)
        logger.info(
            f"whatsapp_in(meta): from={sender} name={msg.profile_name!r} text={msg.text[:80]!r}"
        )
        background.add_task(
            _process_and_reply,
            sender=sender,
            body=msg.text,
            sid=msg.message_id,
            profile_name=msg.profile_name,
            send=_meta_send,
        )

    # Always 200 quickly so Meta doesn't retry the delivery.
    return Response(status_code=200)
