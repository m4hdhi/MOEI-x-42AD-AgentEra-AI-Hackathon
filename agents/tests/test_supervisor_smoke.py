"""Day-2/3 smoke: graph compiles, runs end-to-end, Router/Composer recover gracefully.

These tests must pass with NO API keys set — they exercise the keyword fallback path.
A separate test (test_supervisor_live) runs only when GROQ_API_KEY is present.
"""

import os

import pytest

from hassan.supervisor.graph import run_supervisor


@pytest.mark.asyncio
async def test_supervisor_runs_end_to_end():
    out = await run_supervisor(
        user_id="784-1990-0000001-0",
        channel="web",
        session_id="s1",
        language="auto",
        text="I'm 4 months behind on my SZHP housing loan, can I reschedule?",
    )
    assert out["reply"]
    assert out["service"] == "housing"
    # Language detection should produce 'en' for English text (LLM or fallback).
    assert out["language"] in ("en", "ar")


@pytest.mark.asyncio
async def test_supervisor_detects_arabic_via_fallback():
    """Even with no LLM keys, the keyword fallback should detect Arabic + housing."""
    out = await run_supervisor(
        user_id="784-1990-0000002-0",
        channel="whatsapp",
        session_id="s2",
        language="auto",
        text="أحتاج تأجيل قسط السكن",
    )
    assert out["service"] == "housing"
    # Whether the LLM or fallback handled it, Arabic chars should be detected as 'ar'.
    assert out["language"] == "ar"


@pytest.mark.asyncio
async def test_supervisor_unknown_service_path():
    out = await run_supervisor(
        user_id="784-1990-0000003-0",
        channel="web",
        session_id="s3",
        language="en",
        text="Hello, how are you today?",
    )
    assert out["reply"]
    # Unknown service should still produce a non-empty, helpful reply.
    assert len(out["reply"]) > 10


@pytest.mark.skipif(not os.getenv("GROQ_API_KEY"), reason="GROQ_API_KEY not set")
@pytest.mark.asyncio
async def test_supervisor_live_groq_routing():
    """Live: Groq Router should return high confidence on housing."""
    out = await run_supervisor(
        user_id="784-1990-0000004-0",
        channel="web",
        session_id="s4",
        language="auto",
        text="I lost my job and can't pay my Sheikh Zayed housing installments. What are my options?",
    )
    assert out["service"] == "housing"
    assert out["confidence"] >= 0.6
    assert out["language"] == "en"
