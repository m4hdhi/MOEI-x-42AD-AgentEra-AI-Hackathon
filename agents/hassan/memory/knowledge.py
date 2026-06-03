"""Knowledge layer — Qdrant for semantic chunks of past resolved cases + SZHP rules text.

Graceful no-op when Qdrant isn't reachable; the demo flow does not depend on it but the
"agent quotes policy with citation" demo moment does. Citation strings are still produced
by the rules engine itself (deterministic), so policy quoting works without Qdrant.
"""

from __future__ import annotations

import os

from loguru import logger


class KnowledgeStore:
    """Thin Qdrant client wrapper with no-op semantics if unreachable."""

    def __init__(self) -> None:
        self._client = None
        self._embed = None
        self._init()

    def _init(self) -> None:
        try:
            from qdrant_client import QdrantClient

            self._client = QdrantClient(
                url=os.getenv("QDRANT_URL", "http://localhost:6333"),
                api_key=os.getenv("QDRANT_API_KEY"),
                timeout=3.0,
            )
            self._client.get_collections()
            logger.info("Qdrant client ready")
        except Exception as e:
            logger.debug(f"Qdrant unavailable: {e}")
            self._client = None

    async def search(self, *, collection: str, query: str, limit: int = 3) -> list[str]:
        if not self._client:
            return []
        # Day-7 stub: real embedding flow comes online once we wire OpenAI/Ollama embed.
        # The demo uses the rules engine's own citations, not Qdrant, for the "show your work" moment.
        return []
