"""Voice call recordings + post-call analytics.

Flow:
  1. Browser records the call audio (MediaRecorder) and keeps the live transcript.
  2. On hang-up it POSTs both here (multipart: audio file + transcript JSON).
  3. We persist the row immediately (so the recording appears in admin instantly),
     then run the Post-Call Analyst agent in the background to fill summary, topics,
     action items, sentiment trajectory, QA score, and to auto-create a case.

Audio is stored on disk under apps/api/recordings/ and streamed back for playback.
This makes the voice channel feel like a real contact centre: searchable recordings,
AI summaries, and quality scores — not just a chat that happens to use a microphone.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Form, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from loguru import logger

from ..core.db import db_cursor

router = APIRouter(prefix="/recordings", tags=["recordings"])

_REC_DIR = Path(__file__).resolve().parent.parent.parent / "recordings"
_REC_DIR.mkdir(parents=True, exist_ok=True)


def _row_to_dict(r: dict) -> dict:
    return {
        "id": str(r["id"]),
        "call_id": r.get("call_id"),
        "user_id": r.get("user_id"),
        "user_name": r.get("user_name"),
        "language": r.get("language"),
        "channel": r.get("channel"),
        "duration_seconds": r.get("duration_seconds") or 0,
        "audio_mime": r.get("audio_mime"),
        "has_audio": bool(r.get("audio_path")),
        "transcript": r.get("transcript") or [],
        "turn_count": r.get("turn_count") or 0,
        "summary": r.get("summary"),
        "topics": r.get("topics") or [],
        "action_items": r.get("action_items") or [],
        "intent": r.get("intent"),
        "service": r.get("service"),
        "sentiment_start": float(r["sentiment_start"]) if r.get("sentiment_start") is not None else None,
        "sentiment_end": float(r["sentiment_end"]) if r.get("sentiment_end") is not None else None,
        "sentiment_avg": float(r["sentiment_avg"]) if r.get("sentiment_avg") is not None else None,
        "resolved": r.get("resolved"),
        "qa_score": r.get("qa_score"),
        "escalated": r.get("escalated"),
        "case_number": r.get("case_number"),
        "analysed": r.get("analysed"),
        "created_at": r["created_at"].isoformat() if isinstance(r.get("created_at"), datetime) else r.get("created_at"),
    }


@router.post("")
async def upload_recording(
    background: BackgroundTasks,
    call_id: str = Form(...),
    transcript: str = Form(...),                  # JSON string
    language: str = Form("en"),
    user_id: str = Form("anonymous"),
    user_name: str = Form(""),
    duration_seconds: int = Form(0),
    audio: UploadFile | None = File(None),
) -> JSONResponse:
    """Store a finished call + kick off analysis."""
    try:
        turns = json.loads(transcript) if transcript else []
        if not isinstance(turns, list):
            turns = []
    except Exception:
        turns = []

    rec_id = uuid.uuid4()
    audio_path = None
    audio_mime = "audio/webm"
    if audio is not None:
        ext = ".webm"
        ct = (audio.content_type or "").lower()
        if "mp4" in ct or "m4a" in ct:
            ext = ".mp4"
        elif "ogg" in ct:
            ext = ".ogg"
        elif "wav" in ct:
            ext = ".wav"
        audio_mime = audio.content_type or "audio/webm"
        fname = f"{rec_id}{ext}"
        fpath = _REC_DIR / fname
        try:
            data = await audio.read()
            fpath.write_bytes(data)
            audio_path = fname
        except Exception as e:
            logger.warning(f"recordings: failed to save audio: {e}")

    try:
        with db_cursor() as cur:
            cur.execute(
                """
                INSERT INTO call_recordings
                  (id, call_id, user_id, user_name, language, channel,
                   audio_path, audio_mime, duration_seconds, transcript, turn_count)
                VALUES (%s,%s,%s,%s,%s,'voice',%s,%s,%s,%s::jsonb,%s)
                """,
                (str(rec_id), call_id, user_id, user_name or None, language,
                 audio_path, audio_mime, duration_seconds,
                 json.dumps(turns), len(turns)),
            )
    except Exception as e:
        logger.exception(f"recordings: insert failed: {e}")
        raise HTTPException(status_code=500, detail="could not store recording")

    # Analyse in the background so the client gets an instant response.
    background.add_task(_analyse_recording, str(rec_id), turns, language, user_id, user_name)

    return JSONResponse({"id": str(rec_id), "status": "stored", "turn_count": len(turns)})


async def _analyse_recording(rec_id: str, turns: list, language: str, user_id: str, user_name: str) -> None:
    """Run the Post-Call Analyst, persist results, auto-create a case, emit activity."""
    try:
        from hassan.workers.postcall import analyse_call
        from hassan.workers.crm import upsert_case, emit_activity
    except Exception as e:
        logger.warning(f"recordings: analyst import failed: {e}")
        return

    try:
        analysis = await analyse_call(turns, language=language)
    except Exception as e:
        logger.warning(f"recordings: analysis failed: {e}")
        return

    sentiment_avg = round((analysis.sentiment_start + analysis.sentiment_end) / 2, 2)

    # Auto-create / update a case from the call.
    case_number = None
    try:
        first_citizen = next((t.get("text", "") for t in turns if t.get("role") == "citizen"), "")
        case = upsert_case(
            user_id=user_id,
            user_name=user_name or None,
            channel="voice",
            intent=analysis.intent,
            service=analysis.service,
            user_text=first_citizen or analysis.summary,
            sentiment=sentiment_avg,
            escalated=False,
            correlation_id=f"call:{rec_id}",
        )
        if case:
            case_number = case.get("case_number")
    except Exception as e:
        logger.debug(f"recordings: case creation skipped: {e}")

    try:
        with db_cursor() as cur:
            cur.execute(
                """
                UPDATE call_recordings SET
                  summary=%s, topics=%s::jsonb, action_items=%s::jsonb,
                  intent=%s, service=%s,
                  sentiment_start=%s, sentiment_end=%s, sentiment_avg=%s,
                  resolved=%s, qa_score=%s, escalated=%s,
                  case_number=%s, analysed=TRUE
                WHERE id=%s
                """,
                (analysis.summary, json.dumps(analysis.topics), json.dumps(analysis.action_items),
                 analysis.intent, analysis.service,
                 analysis.sentiment_start, analysis.sentiment_end, sentiment_avg,
                 analysis.resolved, analysis.qa_score, analysis.escalated,
                 case_number, rec_id),
            )
    except Exception as e:
        logger.warning(f"recordings: update analysis failed: {e}")

    try:
        emit_activity(
            event_type="call_recorded",
            summary=f"📞 Call analysed · {analysis.summary[:70]}",
            user_id=user_id,
            user_name=user_name or None,
            channel="voice",
            payload={
                "recording_id": rec_id,
                "service": analysis.service,
                "resolved": analysis.resolved,
                "qa_score": analysis.qa_score,
                "case_number": case_number,
            },
        )
    except Exception as e:
        logger.debug(f"recordings: emit_activity failed: {e}")


@router.get("")
def list_recordings(limit: int = Query(50, ge=1, le=200)) -> dict:
    with db_cursor() as cur:
        cur.execute(
            "SELECT * FROM call_recordings ORDER BY created_at DESC LIMIT %s", (limit,)
        )
        rows = cur.fetchall()
    return {"count": len(rows), "items": [_row_to_dict(r) for r in rows]}


@router.get("/stats")
def recording_stats() -> dict:
    """Aggregate KPIs for the exec dashboard voice card."""
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT
              COUNT(*)                                            AS total,
              COUNT(*) FILTER (WHERE created_at::date = NOW()::date) AS today,
              COALESCE(AVG(qa_score) FILTER (WHERE analysed), 0)  AS avg_qa,
              COALESCE(AVG(duration_seconds), 0)                  AS avg_duration,
              COALESCE(AVG(CASE WHEN resolved THEN 1.0 ELSE 0.0 END) FILTER (WHERE analysed), 0) AS resolution_rate,
              COALESCE(AVG(sentiment_avg) FILTER (WHERE analysed), 0) AS avg_sentiment
            FROM call_recordings
            """
        )
        r = cur.fetchone() or {}
    return {
        "total": int(r.get("total") or 0),
        "today": int(r.get("today") or 0),
        "avg_qa": round(float(r.get("avg_qa") or 0)),
        "avg_duration": round(float(r.get("avg_duration") or 0)),
        "resolution_rate": round(float(r.get("resolution_rate") or 0) * 100),
        "avg_sentiment": round(float(r.get("avg_sentiment") or 0) * 100),
    }


@router.get("/{rec_id}")
def get_recording(rec_id: str) -> dict:
    with db_cursor() as cur:
        cur.execute("SELECT * FROM call_recordings WHERE id = %s", (rec_id,))
        r = cur.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="recording not found")
    return _row_to_dict(r)


@router.get("/{rec_id}/audio")
def get_recording_audio(rec_id: str):
    with db_cursor() as cur:
        cur.execute("SELECT audio_path, audio_mime FROM call_recordings WHERE id = %s", (rec_id,))
        r = cur.fetchone()
    if not r or not r.get("audio_path"):
        raise HTTPException(status_code=404, detail="no audio for this recording")
    fpath = _REC_DIR / r["audio_path"]
    if not fpath.exists():
        raise HTTPException(status_code=404, detail="audio file missing")
    return FileResponse(str(fpath), media_type=r.get("audio_mime") or "audio/webm")
