"""Voice channel endpoints.

Two paths:
1. `/voice/token` — issue a LiveKit access token so the web client can join a room and stream audio.
   The actual STT→supervisor→TTS loop runs in agents/voice/livekit_worker.py.
2. `/voice/turn` — text-as-voice fallback. Same supervisor, channel="voice".
   Used in the demo when network/LiveKit credits are flaky; preserves the cross-channel memory claim.
"""

from __future__ import annotations

import os
import time

import httpx
from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from hassan.supervisor.graph import run_supervisor
from hassan.workers.crm import emit_activity
from loguru import logger

from ..core.language import detect_language
from .auth import get_authenticated_user_id, get_authenticated_user_name
from ..schemas.message import AgentResponse, IncomingMessage

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/turn", response_model=AgentResponse)
async def voice_turn(msg: IncomingMessage, request: Request) -> AgentResponse:
    """Text-as-voice fallback. channel='voice' so cross-channel memory still works."""
    msg.channel = "voice"
    if msg.language == "auto":
        msg.language = detect_language(msg.text)  # type: ignore[assignment]
    authed = get_authenticated_user_id(request)
    user_id = authed or msg.user_id
    user_name = get_authenticated_user_name(request)
    result = await run_supervisor(
        user_id=user_id,
        channel="voice",
        session_id=msg.session_id,
        language=msg.language,
        text=msg.text,
        user_name=user_name,
    )
    try:
        snippet = (msg.text or "").strip().replace("\n", " ")
        if len(snippet) > 80:
            snippet = snippet[:77] + "…"
        emit_activity(
            event_type="voice_turn",
            summary=f"📞 Call · {snippet}" if snippet else "📞 Call · (no transcript)",
            user_id=user_id,
            user_name=user_name,
            channel="voice",
            payload={
                "session_id": msg.session_id,
                "service": result.get("service"),
                "intent": result.get("intent"),
                "sentiment": result.get("sentiment"),
                "escalated": result.get("escalated", False),
            },
        )
    except Exception as e:
        logger.debug(f"voice: emit_activity failed: {e}")
    return AgentResponse(
        text=result["reply"],
        language=result["language"],
        service=result.get("service", "unknown"),
        intent=result.get("intent", "service_request"),
        confidence=result.get("confidence", 0.0),
        sentiment=result.get("sentiment"),
        escalated=result.get("escalated", False),
        next_best_action=result.get("next_best_action"),
        correlation_id=getattr(request.state, "correlation_id", msg.correlation_id),
        suggested_replies=result.get("suggested_replies", []),
        citations=result.get("citations", []),
        case_number=result.get("case_number"),
    )


# ---- ElevenLabs TTS proxy -----------------------------------------------

# Free, public-domain voices. These work on the ElevenLabs free tier (10k char/mo).
ELEVEN_VOICE_EN = os.getenv("ELEVENLABS_VOICE_ID_EN", "EXAVITQu4vr4xnSDxMaL")  # "Sarah"
ELEVEN_VOICE_AR = os.getenv("ELEVENLABS_VOICE_ID_AR", "EXAVITQu4vr4xnSDxMaL")  # same voice; supports both


@router.get("/tts/status")
async def tts_status() -> dict:
    """Tell the client whether ElevenLabs is available + how much free quota is left."""
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        return {"provider": "browser", "available": False, "reason": "no api key"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            r = await c.get("https://api.elevenlabs.io/v1/user/subscription",
                            headers={"xi-api-key": api_key})
        if r.status_code != 200:
            return {"provider": "browser", "available": False, "reason": f"HTTP {r.status_code}"}
        sub = r.json()
        used = sub.get("character_count", 0)
        limit = sub.get("character_limit", 0)
        remaining = max(0, limit - used)
        return {
            "provider": "elevenlabs" if remaining > 200 else "browser",
            "available": remaining > 200,
            "remaining_chars": remaining,
            "limit": limit,
        }
    except Exception as e:
        return {"provider": "browser", "available": False, "reason": str(e)}


@router.post("/tts", response_model=None)
async def tts(payload: dict = Body(...)) -> StreamingResponse | JSONResponse:
    """Stream MP3 audio from ElevenLabs. Falls back to 503 if no key/quota; client uses browser TTS."""
    text = (payload.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "text required"}, status_code=400)
    text = text[:1500]   # cap per request — save free credits
    language = payload.get("language", "en")
    voice_id = ELEVEN_VOICE_AR if language == "ar" else ELEVEN_VOICE_EN

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        return JSONResponse({"error": "tts unavailable, use browser tts"}, status_code=503)

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    body = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.75, "style": 0.3},
    }
    headers = {"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"}

    async def gen():
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream("POST", url, json=body, headers=headers) as r:
                    if r.status_code != 200:
                        # Client will fall back to browser TTS on a non-200
                        return
                    async for chunk in r.aiter_bytes():
                        if chunk:
                            yield chunk
        except Exception as e:
            logger.warning(f"elevenlabs tts failed: {e}")
            return

    return StreamingResponse(gen(), media_type="audio/mpeg")


@router.post("/token")
async def livekit_token(body: dict) -> dict:
    """Issue a short-lived LiveKit access token for the web client to join a room.

    Body: {"user_id": "...", "room": "..."}. Returns {"token": "...", "url": "..."}.
    Requires LIVEKIT_API_KEY/SECRET; raises 503 if not configured (demo fallback to /voice/turn).
    """
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    url = os.getenv("LIVEKIT_URL")
    if not (api_key and api_secret and url):
        raise HTTPException(status_code=503, detail="LiveKit not configured")
    try:
        from livekit import api  # type: ignore

        user_id = str(body.get("user_id") or "anonymous")
        room = str(body.get("room") or f"hassan-{int(time.time())}")
        token = (
            api.AccessToken(api_key, api_secret)
            .with_identity(user_id)
            .with_name(user_id)
            .with_grants(api.VideoGrants(room_join=True, room=room))
            .to_jwt()
        )
        return {"token": token, "url": url, "room": room}
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"livekit SDK missing: {e}") from e
