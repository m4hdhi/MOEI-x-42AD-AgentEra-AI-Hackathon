"""Mem0 episodic memory — user-scoped facts that persist across channels and sessions.

This is what powers the demo-wow "Agent42 greets Mariam by name on channel switch":
on the WhatsApp turn we add(text) → Mem0 extracts entities → on the voice turn search(user_id)
returns "Mariam is 4 months behind on her SZHP loan; medical emergency".

Graceful no-op if MEM0_API_KEY isn't set — the buffer in short_term.py still carries
recent turns, so cross-channel still works for the demo, just without long-term recall.
"""

from __future__ import annotations

import os
from functools import lru_cache

from loguru import logger


class EpisodicMemory:
    def __init__(self) -> None:
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        if not os.getenv("MEM0_API_KEY"):
            return
        try:
            from mem0 import MemoryClient

            self._client = MemoryClient(api_key=os.getenv("MEM0_API_KEY"))
            logger.info("Mem0 client ready")
        except Exception as e:
            logger.warning(f"Mem0 unavailable: {e}")
            self._client = None

    async def add(self, *, user_id: str, text: str, metadata: dict | None = None) -> None:
        if not self._client:
            return
        try:
            self._client.add(text, user_id=user_id, metadata=metadata or {})
        except Exception as e:
            logger.debug(f"Mem0 add failed (non-fatal): {e}")

    async def search(self, *, user_id: str, query: str, limit: int = 5) -> list[str]:
        if not self._client:
            return []
        try:
            results = self._client.search(query=query, user_id=user_id, limit=limit)
            if isinstance(results, dict):
                results = results.get("results", [])
            return [r.get("memory", "") for r in results if isinstance(r, dict)]
        except Exception as e:
            logger.debug(f"Mem0 search failed (non-fatal): {e}")
            return []


@lru_cache(maxsize=1)
def get_episodic_memory() -> EpisodicMemory:
    return EpisodicMemory()
