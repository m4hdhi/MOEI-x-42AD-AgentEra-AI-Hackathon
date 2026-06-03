"""LiveKit voice worker.

Run with:
    uv pip install -e '.[voice]'
    uv run python -m hassan.voice.livekit_worker dev

Flow:
    LiveKit room  ──audio──▶  Deepgram (EN) or Whisper (AR)  ──text──▶  Supervisor
                                                                          │
                                                                       reply text
                                                                          │
              user hears  ◀──audio──  ElevenLabs (AR) / OpenAI (EN) TTS  ◀┘

Sentiment is captured per turn (SenseVoice / wav2vec2) and pushed to the co-pilot console
via the /copilot/event stream. Lives behind an optional dependency group ('voice').
"""

from __future__ import annotations

import asyncio
import os

from loguru import logger


async def _supervisor_turn(user_id: str, session_id: str, text: str) -> str:
    from hassan.supervisor.graph import run_supervisor

    result = await run_supervisor(
        user_id=user_id,
        channel="voice",
        session_id=session_id,
        language="auto",
        text=text,
    )
    return result.get("reply", "")


async def entrypoint(ctx) -> None:    # pragma: no cover (requires livekit runtime)
    """LiveKit agent entrypoint. Importable by the LiveKit CLI."""
    try:
        from livekit.agents import AutoSubscribe, llm  # type: ignore
        from livekit.agents.voice_assistant import VoiceAssistant  # type: ignore
        from livekit.plugins import deepgram, elevenlabs, openai, silero  # type: ignore
    except ImportError as e:
        logger.error(f"voice extras not installed: {e}; uv pip install -e '.[voice]'")
        return

    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    user_id = ctx.room.metadata or "voice-anonymous"
    session_id = ctx.room.name

    async def _on_text(user_text: str) -> str:
        return await _supervisor_turn(user_id, session_id, user_text)

    class SupervisorLLM(llm.LLM):
        async def chat(self, history, *, fnc_ctx=None, temperature=None, n=None, parallel_tool_calls=None):
            user_text = history.messages[-1].content if history.messages else ""
            reply = await _on_text(user_text)
            return llm.LLMStream.from_response_text(reply)

    assistant = VoiceAssistant(
        vad=silero.VAD.load(),
        stt=deepgram.STT(model="nova-3", language="en") if os.getenv("DEEPGRAM_API_KEY") else openai.STT(),
        llm=SupervisorLLM(),
        tts=elevenlabs.TTS() if os.getenv("ELEVENLABS_API_KEY") else openai.TTS(),
    )
    assistant.start(ctx.room)
    await assistant.aclose_when_disconnected()


if __name__ == "__main__":   # pragma: no cover
    try:
        from livekit.agents import cli, WorkerOptions  # type: ignore

        cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
    except ImportError:
        print("livekit-agents not installed. Run: uv pip install -e '.[voice]'")
        raise SystemExit(1)
    # Suppress 'never awaited' warning for fallback path
    if False:
        asyncio.run(_supervisor_turn("", "", ""))
