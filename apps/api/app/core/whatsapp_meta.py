"""Meta WhatsApp Cloud API client.

The WhatsApp chatbot ("MOEI Assistant (Demo)") runs on Meta's Cloud API. This module is the thin
provider layer the repo previously lacked: webhook verification, request-signature validation,
inbound-JSON parsing, and outbound text sends via the Graph API. Twilio stays for SMS / fallback
(see core/dispatcher.py and routes/whatsapp.py).

Docs: https://developers.facebook.com/docs/whatsapp/cloud-api
"""

from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass

import httpx
from loguru import logger


@dataclass(slots=True)
class InboundMessage:
    """One inbound text message, normalized off a Meta webhook payload."""

    wa_id: str  # sender's bare digits, e.g. "9715xxxxxxx"
    text: str  # message body
    message_id: str  # Meta message id ("wamid....")
    profile_name: str | None = None


def _graph_version() -> str:
    return os.getenv("META_GRAPH_API_VERSION", "v22.0")


def canonical_wa_key(wa_id: str) -> str:
    """Canonical key for the whatsapp_identities table, matching the Twilio format.

    Meta sends bare digits ("9715..."); Twilio stored "whatsapp:+9715...". We canonicalize Meta
    senders to ``whatsapp:+<digits>`` so inbound reuses the same identity rows and the notification
    dispatcher's reverse-lookup keeps working unchanged.
    """
    digits = "".join(c for c in (wa_id or "") if c.isdigit())
    return f"whatsapp:+{digits}" if digits else (wa_id or "")


def verify_webhook(mode: str | None, token: str | None, challenge: str | None) -> str | None:
    """Echo the challenge when the Meta verify token matches."""
    expected = os.getenv("META_WHATSAPP_VERIFY_TOKEN", "")
    if mode == "subscribe" and token and expected and hmac.compare_digest(token, expected):
        return challenge or ""
    logger.warning("meta_webhook_verify_failed: mode={!r} token_present={}", mode, bool(token))
    return None


def verify_signature(raw_body: bytes, header: str | None) -> bool:
    """Validate ``X-Hub-Signature-256`` (HMAC-SHA256 of the raw body keyed by the app secret).

    Mirrors the Twilio path's posture: when no app secret is configured or
    META_SKIP_SIGNATURE_CHECK=1, allow (local dev). When a secret IS set, a missing or invalid
    signature is rejected.
    """
    secret = os.getenv("META_APP_SECRET", "")
    if not secret or os.getenv("META_SKIP_SIGNATURE_CHECK") == "1":
        return True
    if not header or not header.startswith("sha256="):
        logger.warning("meta_sig_missing_or_malformed")
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    provided = header.split("=", 1)[1]
    ok = hmac.compare_digest(expected, provided)
    if not ok:
        logger.warning("meta_sig_mismatch")
    return ok


def parse_inbound(payload: dict) -> list[InboundMessage]:
    """Extract text messages from a Meta webhook payload.

    Ignores status callbacks (sent/delivered/read) and non-text message types — those share the
    same ``messages`` webhook field but carry no ``text.body`` for the supervisor.
    """
    out: list[InboundMessage] = []
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            names: dict[str, str] = {}
            for contact in value.get("contacts", []) or []:
                wa = contact.get("wa_id")
                name = (contact.get("profile") or {}).get("name")
                if wa and name:
                    names[wa] = name
            for msg in value.get("messages", []) or []:
                if msg.get("type") != "text":
                    continue
                wa_id = msg.get("from", "")
                text = (msg.get("text") or {}).get("body", "")
                if not (wa_id and text):
                    continue
                out.append(
                    InboundMessage(
                        wa_id=wa_id,
                        text=text,
                        message_id=msg.get("id", "wamid-unknown"),
                        profile_name=names.get(wa_id),
                    )
                )
    return out


async def send_text(*, to_wa_id: str, body: str) -> bool:
    """Send an outbound WhatsApp text via the Graph API. Returns True on success.

    Freeform text only delivers within 24h of the user's last inbound message; business-initiated
    sends outside that window require an approved template (not handled here).
    """
    token = os.getenv("META_WHATSAPP_ACCESS_TOKEN", "")
    phone_id = os.getenv("META_WHATSAPP_PHONE_NUMBER_ID", "")
    if not (token and phone_id):
        logger.warning("meta_send_skipped: missing META_WHATSAPP_ACCESS_TOKEN/PHONE_NUMBER_ID")
        return False

    to = "".join(c for c in (to_wa_id or "") if c.isdigit())
    # WhatsApp caps each message at 1600 chars; trim defensively (matches the Twilio path).
    body = body[:1500]
    url = f"https://graph.facebook.com/{_graph_version()}/{phone_id}/messages"
    data = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"preview_url": False, "body": body},
    }
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(url, json=data, headers=headers)
        if r.status_code >= 300:
            logger.warning(f"meta_send_failed: {r.status_code} {r.text[:300]}")
            return False
    return True
