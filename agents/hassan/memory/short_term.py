"""Redis last-20-turns conversation buffer.

Keyed by user_id (not session_id) so cross-channel hand-off works:
Mariam's WhatsApp turns + voice turns + web turns all share the same buffer.
That's the 90-second demo wow.
"""

from __future__ import annotations

import json
import os
from typing import Literal

import redis.asyncio as redis
from loguru import logger

MAX_TURNS = 20
KEY_PREFIX = "hassan:turns"

Role = Literal["user", "assistant"]


class ShortTermBuffer:
    def __init__(self, url: str | None = None):
        self.url = url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._client: redis.Redis | None = None

    async def _conn(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self.url, decode_responses=True)
        return self._client

    @staticmethod
    def _key(user_id: str) -> str:
        return f"{KEY_PREFIX}:{user_id}"

    async def append(self, user_id: str, role: Role, text: str, channel: str) -> None:
        try:
            r = await self._conn()
            payload = json.dumps({"role": role, "text": text, "channel": channel})
            key = self._key(user_id)
            async with r.pipeline(transaction=True) as pipe:
                await pipe.lpush(key, payload)
                await pipe.ltrim(key, 0, MAX_TURNS - 1)
                await pipe.expire(key, 60 * 60 * 24 * 7)   # 7-day TTL
                await pipe.execute()
        except Exception as e:
            logger.debug(f"Redis append failed (non-fatal): {e}")

    async def recent(self, user_id: str, n: int = MAX_TURNS) -> list[dict]:
        try:
            r = await self._conn()
            raw = await r.lrange(self._key(user_id), 0, n - 1)
            return [json.loads(x) for x in reversed(raw)]
        except Exception as e:
            logger.debug(f"Redis read failed (non-fatal, returning empty): {e}")
            return []


_buffer: ShortTermBuffer | None = None


def get_short_term_buffer() -> ShortTermBuffer:
    global _buffer
    if _buffer is None:
        _buffer = ShortTermBuffer()
    return _buffer
