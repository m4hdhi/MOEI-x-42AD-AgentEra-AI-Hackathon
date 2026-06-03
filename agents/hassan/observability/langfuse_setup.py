"""Langfuse setup — every LLM call, tool call, routing decision becomes a span.

This is the audit trail demo. On stage we open Langfuse, click the trace for the just-completed
turn, walk through Router → Memory → Worker → Critic → Composer with timing and inputs visible.

Pinned to Langfuse SDK v2 to match the self-hosted `langfuse/langfuse:2` server (v3 server
needs ClickHouse + MinIO; not worth the operational weight for a hackathon).
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from loguru import logger


@lru_cache(maxsize=1)
def get_langfuse_client():
    """Return a singleton Langfuse client, or None if not configured (dev-time no-op)."""
    public = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret = os.getenv("LANGFUSE_SECRET_KEY")
    if not (public and secret):
        logger.info("Langfuse keys missing — tracing disabled (set LANGFUSE_*_KEY to enable)")
        return None
    try:
        from langfuse import Langfuse

        client = Langfuse(
            public_key=public,
            secret_key=secret,
            host=os.getenv("LANGFUSE_HOST", "http://localhost:3001"),
        )
        logger.info(f"Langfuse client ready @ {os.getenv('LANGFUSE_HOST')}")
        return client
    except Exception as e:
        logger.warning(f"Langfuse init failed: {e}")
        return None


def get_langfuse_callbacks(
    *,
    session_id: str | None = None,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> list:
    """Build LangChain callback handlers that ship spans to Langfuse.

    Pass the return value as `config={"callbacks": ...}` to graph.ainvoke().
    """
    public = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret = os.getenv("LANGFUSE_SECRET_KEY")
    if not (public and secret):
        return []
    try:
        from langfuse.callback import CallbackHandler

        return [
            CallbackHandler(
                public_key=public,
                secret_key=secret,
                host=os.getenv("LANGFUSE_HOST", "http://localhost:3001"),
                session_id=session_id,
                user_id=user_id,
                metadata=metadata or {},
            )
        ]
    except Exception as e:
        logger.warning(f"Langfuse callback unavailable: {e}")
        return []
