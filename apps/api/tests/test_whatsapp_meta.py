"""Unit tests for the Meta WhatsApp Cloud API client (app/core/whatsapp_meta.py).

Covers the security- and parsing-critical pure functions: webhook verification, request-signature
validation, identity canonicalization, and inbound-payload parsing. Outbound ``send_text`` makes a
network call and is exercised end-to-end against Meta instead.
"""

from __future__ import annotations

import hashlib
import hmac

from app.core import whatsapp_meta as wm


def test_canonical_wa_key_matches_twilio_format():
    assert wm.canonical_wa_key("971501234567") == "whatsapp:+971501234567"
    # Tolerates a leading + and stray spaces (so it keys the same identity row).
    assert wm.canonical_wa_key("+971 50 123 4567") == "whatsapp:+971501234567"
    # No digits → fall back to the raw value rather than emit a bare "whatsapp:+".
    assert wm.canonical_wa_key("") == ""


def test_verify_webhook_echoes_challenge_on_match(monkeypatch):
    monkeypatch.setenv("META_WHATSAPP_VERIFY_TOKEN", "s3cret")
    assert wm.verify_webhook("subscribe", "s3cret", "CHALLENGE123") == "CHALLENGE123"


def test_verify_webhook_rejects_bad_token_or_mode(monkeypatch):
    monkeypatch.setenv("META_WHATSAPP_VERIFY_TOKEN", "s3cret")
    assert wm.verify_webhook("subscribe", "wrong", "CHALLENGE123") is None
    assert wm.verify_webhook("unsubscribe", "s3cret", "CHALLENGE123") is None


def test_verify_signature_accepts_valid_hmac(monkeypatch):
    monkeypatch.delenv("META_SKIP_SIGNATURE_CHECK", raising=False)
    monkeypatch.setenv("META_APP_SECRET", "appsecret")
    body = b'{"hello":"world"}'
    digest = hmac.new(b"appsecret", body, hashlib.sha256).hexdigest()
    assert wm.verify_signature(body, f"sha256={digest}") is True


def test_verify_signature_rejects_tampered_or_missing(monkeypatch):
    monkeypatch.delenv("META_SKIP_SIGNATURE_CHECK", raising=False)
    monkeypatch.setenv("META_APP_SECRET", "appsecret")
    body = b'{"hello":"world"}'
    digest = hmac.new(b"appsecret", body, hashlib.sha256).hexdigest()
    assert wm.verify_signature(b'{"hello":"tampered"}', f"sha256={digest}") is False
    assert wm.verify_signature(body, None) is False
    assert wm.verify_signature(body, "garbage") is False


def test_verify_signature_dev_escape_hatches(monkeypatch):
    # No app secret configured → allow (local dev), mirroring the Twilio path's posture.
    monkeypatch.delenv("META_APP_SECRET", raising=False)
    monkeypatch.delenv("META_SKIP_SIGNATURE_CHECK", raising=False)
    assert wm.verify_signature(b"x", None) is True
    # Explicit skip flag → allow even when a secret is set.
    monkeypatch.setenv("META_APP_SECRET", "appsecret")
    monkeypatch.setenv("META_SKIP_SIGNATURE_CHECK", "1")
    assert wm.verify_signature(b"x", "sha256=deadbeef") is True


def _sample_payload(text="مرحبا", wa_id="971501234567", name="Aisha"):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA_ID",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "contacts": [{"profile": {"name": name}, "wa_id": wa_id}],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": "wamid.ABC",
                                    "timestamp": "1700000000",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def test_parse_inbound_extracts_text_message():
    msgs = wm.parse_inbound(_sample_payload())
    assert len(msgs) == 1
    m = msgs[0]
    assert m.wa_id == "971501234567"
    assert m.text == "مرحبا"
    assert m.message_id == "wamid.ABC"
    assert m.profile_name == "Aisha"


def test_parse_inbound_ignores_status_callbacks_and_non_text():
    # Delivery-status callbacks carry `statuses`, not `messages`.
    status_payload = {"entry": [{"changes": [{"value": {"statuses": [{"status": "delivered"}]}}]}]}
    assert wm.parse_inbound(status_payload) == []

    # Non-text message types (e.g. image) are skipped — no text body for the supervisor.
    img = _sample_payload()
    img["entry"][0]["changes"][0]["value"]["messages"][0]["type"] = "image"
    assert wm.parse_inbound(img) == []

    # Empty / malformed payloads must not raise.
    assert wm.parse_inbound({}) == []
    assert wm.parse_inbound({"entry": [{}]}) == []
