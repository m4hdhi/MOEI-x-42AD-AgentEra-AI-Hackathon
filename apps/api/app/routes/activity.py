"""Live omnichannel activity stream.

  GET /activity              → JSON list of the last N events
  GET /activity/stream       → SSE — every new activity_events row is pushed live

The ticker on /exec subscribes to /activity/stream and renders rows as they arrive,
producing the "live customer engagement" feeling the brief asks for.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Query
from sse_starlette.sse import EventSourceResponse

from ..core.db import db_cursor

router = APIRouter(prefix="/activity", tags=["activity"])


def _row(r: dict) -> dict:
    return {
        "id": int(r["id"]),
        "user_id": r.get("user_id"),
        "user_name": r.get("user_name"),
        "channel": r.get("channel"),
        "event_type": r.get("event_type"),
        "summary": r.get("summary"),
        "payload": r.get("payload") or {},
        "at": r["created_at"].isoformat() if isinstance(r.get("created_at"), datetime) else r.get("created_at"),
    }


@router.get("")
def list_activity(limit: int = Query(50, ge=1, le=500)) -> dict:
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM activity_events ORDER BY id DESC LIMIT %s", (limit,)
        )
        rows = cur.fetchall()
    return {"count": len(rows), "items": [_row(r) for r in rows]}


@router.get("/stream")
async def stream_activity(since_id: int = Query(0, ge=0)):
    """Server-Sent Events: pushes every new activity_events row.

    Poll-based (every 1.5s); fine for the dashboard's needs and avoids LISTEN/NOTIFY plumbing.
    """

    async def gen():
        last_id = since_id
        # Send a snapshot of recent rows first
        with db_cursor() as cur:
            cur.execute("SELECT * FROM activity_events ORDER BY id DESC LIMIT 20")
            initial = list(reversed(cur.fetchall()))
        for r in initial:
            last_id = max(last_id, int(r["id"]))
            yield {"event": "activity", "data": json.dumps(_row(r))}

        while True:
            await asyncio.sleep(1.5)
            with db_cursor() as cur:
                cur.execute(
                    "SELECT * FROM activity_events WHERE id > %s ORDER BY id ASC LIMIT 100",
                    (last_id,),
                )
                new_rows = cur.fetchall()
            for r in new_rows:
                last_id = max(last_id, int(r["id"]))
                yield {"event": "activity", "data": json.dumps(_row(r))}
            # heartbeat so the connection stays open
            yield {"event": "ping", "data": str(int(asyncio.get_event_loop().time()))}

    return EventSourceResponse(gen())
