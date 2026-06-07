import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from hassan.supervisor.graph import run_supervisor

from ..core.language import detect_language
from .auth import get_authenticated_user_id, get_authenticated_user_name
from ..schemas.message import AgentResponse, IncomingMessage

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/web", response_model=AgentResponse)
async def chat_web(msg: IncomingMessage, request: Request) -> AgentResponse:
    """Web channel ingress — synchronous JSON response. Prefers the UAE PASS session user_id."""
    if msg.language == "auto":
        msg.language = detect_language(msg.text)  # type: ignore[assignment]

    # If the citizen logged in via UAE PASS, use that verified Emirates ID over whatever
    # the client posted — never trust unauthenticated user_id claims for cross-channel memory.
    authed = get_authenticated_user_id(request)
    user_id = authed or msg.user_id
    user_name = get_authenticated_user_name(request)
    correlation_id = getattr(request.state, "correlation_id", msg.correlation_id)

    result = await run_supervisor(
        user_id=user_id,
        channel=msg.channel,
        session_id=msg.session_id,
        language=msg.language,
        text=msg.text,
        user_name=user_name,
        correlation_id=correlation_id,
    )
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
        trace_url=result.get("trace_url"),
        suggested_replies=result.get("suggested_replies", []),
        citations=result.get("citations", []),
        case_number=result.get("case_number"),
        escalation_risk=result.get("escalation_risk", {}),
        emotion=result.get("emotion"),
        urgency=result.get("urgency"),
        life_events=result.get("life_events", []),
        autonomous=result.get("autonomous", False),
    )


@router.post("/web/stream")
async def chat_web_stream(msg: IncomingMessage, request: Request) -> StreamingResponse:
    """Server-sent events stream. Emits progress events so the UI feels instant:
      data: {"event":"router","service":"housing","confidence":0.9}
      data: {"event":"dispatcher","tool":"szhp_rules_engine"}
      data: {"event":"reply","text":"...","suggested_replies":[...]}
      data: {"event":"done"}
    """
    if msg.language == "auto":
        msg.language = detect_language(msg.text)  # type: ignore[assignment]

    correlation_id = getattr(request.state, "correlation_id", msg.correlation_id)
    authed = get_authenticated_user_id(request)
    user_id = authed or msg.user_id
    user_name = get_authenticated_user_name(request)

    async def gen():
        # Phase 1: "thinking" pulse so the UI can render a typing indicator instantly
        yield _sse({"event": "thinking", "correlation_id": correlation_id})
        await asyncio.sleep(0)

        # Phase 2: run the supervisor (this is the heavy part)
        try:
            result = await run_supervisor(
                user_id=user_id,
                channel=msg.channel,
                session_id=msg.session_id,
                language=msg.language,
                text=msg.text,
                user_name=user_name,
                correlation_id=correlation_id,
            )
        except Exception as e:
            yield _sse({"event": "error", "message": str(e), "correlation_id": correlation_id})
            return

        # Phase 3: emit structured progress events (mirrors the graph nodes)
        yield _sse({
            "event": "router",
            "service": result.get("service"),
            "intent": result.get("intent"),
            "confidence": result.get("confidence"),
        })
        yield _sse({
            "event": "dispatcher",
            "tool_calls": [tc.get("tool") for tc in result.get("tool_calls", [])][:5] if isinstance(result.get("tool_calls"), list) else [],
        })

        # Phase 4: stream the reply token-by-token-ish for perceived speed
        reply_text = result.get("reply", "")
        chunk_size = 12
        for i in range(0, len(reply_text), chunk_size):
            yield _sse({"event": "token", "delta": reply_text[i : i + chunk_size]})
            await asyncio.sleep(0.015)   # ~80 tokens/sec perceived

        # Phase 5: final payload
        yield _sse({
            "event": "reply",
            "text": reply_text,
            "language": result.get("language"),
            "service": result.get("service"),
            "intent": result.get("intent"),
            "confidence": result.get("confidence"),
            "escalated": result.get("escalated", False),
            "sentiment": result.get("sentiment"),
            "next_best_action": result.get("next_best_action"),
            "suggested_replies": result.get("suggested_replies", []),
            "citations": result.get("citations", []),
            "escalation_risk": result.get("escalation_risk", {}),
            "emotion": result.get("emotion"),
            "urgency": result.get("urgency"),
            "life_events": result.get("life_events", []),
            "autonomous": result.get("autonomous", False),
            "correlation_id": correlation_id,
        })
        yield _sse({"event": "done"})

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
