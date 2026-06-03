"""Predictive analytics + workforce planning for the executive dashboard.

Includes:
  - /analytics/volume-forecast  : 7-day demand forecast (seasonal-naive)
  - /analytics/sentiment-trend  : daily sentiment over the last 30 days
  - /analytics/escalation-risk  : top-N users currently at risk of escalation
  - /analytics/heatmap          : day-of-week × hour-of-day demand heatmap + headcount rec
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from fastapi import APIRouter, Query

from ..core.db import db_cursor

router = APIRouter(prefix="/analytics", tags=["analytics"])

# Empirical: each agent handles ~6 chats / hr or ~4 calls / hr → use 5 as a middle
CASES_PER_AGENT_HOUR = 5.0


@router.get("/volume-forecast")
def volume_forecast(days: int = Query(7, ge=1, le=30)) -> dict:
    """Seasonal-naive forecast: predicted demand for the next N days = same weekday last week.

    Falls back to the median when there isn't enough history.
    """
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT created_at::date AS day, COUNT(*) AS n
            FROM cases WHERE created_at > NOW() - INTERVAL '60 days'
            GROUP BY day ORDER BY day
            """
        )
        history = cur.fetchall()
    history_by_day = {r["day"]: int(r["n"]) for r in history}
    if not history:
        history_by_day = {}

    # Median for fallback
    counts = list(history_by_day.values())
    median = int(sorted(counts)[len(counts) // 2]) if counts else 50

    today = datetime.utcnow().date()
    actual = []
    for i in range(14, 0, -1):
        d = today - timedelta(days=i)
        actual.append({"day": d.isoformat(), "value": history_by_day.get(d, 0), "kind": "actual"})

    forecast = []
    for i in range(1, days + 1):
        d = today + timedelta(days=i)
        # Look 7 days back
        ref = d - timedelta(days=7)
        if ref in history_by_day:
            base = history_by_day[ref]
        else:
            base = median
        # Add a small 5% upward trend bias
        forecast.append({"day": d.isoformat(), "value": int(round(base * 1.05)), "kind": "forecast"})

    return {
        "as_of": today.isoformat(),
        "method": "seasonal-naive (lag-7) + 5% trend",
        "history": actual,
        "forecast": forecast,
    }


@router.get("/sentiment-trend")
def sentiment_trend(days: int = Query(14, ge=1, le=60)) -> dict:
    # `days` is server-validated via Query(ge=1, le=60), so safe to interpolate
    safe_days = int(days)
    with db_cursor() as cur:
        cur.execute(
            f"""
            SELECT created_at::date AS day,
                   AVG(sentiment) FILTER (WHERE sentiment IS NOT NULL) AS avg,
                   COUNT(*) FILTER (WHERE sentiment < 0.4) AS negative,
                   COUNT(*) AS total
            FROM cases
            WHERE created_at > NOW() - INTERVAL '{safe_days} days'
            GROUP BY day ORDER BY day
            """
        )
        rows = cur.fetchall()
    return {
        "days": days,
        "series": [
            {
                "day": r["day"].isoformat(),
                "avg": round(float(r["avg"]), 2) if r["avg"] is not None else None,
                "negative_count": int(r["negative"] or 0),
                "total": int(r["total"] or 0),
            }
            for r in rows
        ],
    }


@router.get("/escalation-risk")
def escalation_risk(limit: int = Query(10, ge=1, le=50)) -> dict:
    """Top users at risk: many open cases + low sentiment + high-priority cases."""
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT user_id, MAX(user_name) AS user_name,
                   COUNT(*) FILTER (WHERE status IN ('open','in_progress','escalated')) AS open_cases,
                   AVG(sentiment) FILTER (WHERE sentiment IS NOT NULL) AS avg_sentiment,
                   COUNT(*) FILTER (WHERE priority IN ('high','critical')) AS high_priority,
                   MAX(updated_at) AS last_touched
            FROM cases
            WHERE created_at > NOW() - INTERVAL '14 days'
            GROUP BY user_id
            HAVING COUNT(*) FILTER (WHERE status IN ('open','in_progress','escalated')) > 0
            ORDER BY (
                COUNT(*) FILTER (WHERE priority IN ('high','critical')) * 3
                + COUNT(*) FILTER (WHERE status IN ('open','in_progress','escalated')) * 1
                + COALESCE((1 - AVG(sentiment)) * 4, 1)
            ) DESC
            LIMIT %s
            """,
            (limit,),
        )
        rows = cur.fetchall()
    return {
        "items": [
            {
                "user_id": r["user_id"],
                "user_name": r["user_name"] or "(unknown)",
                "open_cases": int(r["open_cases"] or 0),
                "high_priority": int(r["high_priority"] or 0),
                "avg_sentiment": round(float(r["avg_sentiment"]), 2) if r["avg_sentiment"] is not None else None,
                "last_touched": r["last_touched"].isoformat() if r["last_touched"] else None,
                "risk_score": round(
                    (int(r["high_priority"] or 0) * 3
                     + int(r["open_cases"] or 0)
                     + (1.0 - float(r["avg_sentiment"] or 0.5)) * 4),
                    1,
                ),
            }
            for r in rows
        ]
    }


@router.get("/heatmap")
def heatmap() -> dict:
    """Demand heatmap: hour-of-day × day-of-week, plus recommended headcount per slot."""
    with db_cursor() as cur:
        cur.execute(
            """
            SELECT
                EXTRACT(DOW FROM created_at)::int AS dow,
                EXTRACT(HOUR FROM created_at)::int AS hour,
                COUNT(*) AS n
            FROM cases
            WHERE created_at > NOW() - INTERVAL '28 days'
            GROUP BY dow, hour
            ORDER BY dow, hour
            """
        )
        rows = cur.fetchall()

    # PG DOW: 0=Sun..6=Sat
    day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    cell_avg: dict[tuple[int, int], float] = {}
    for r in rows:
        # cases over 4 weeks → avg per weekday occurrence is /4
        cell_avg[(int(r["dow"]), int(r["hour"]))] = float(r["n"]) / 4.0

    cells = []
    for dow in range(7):
        for hour in range(24):
            avg = cell_avg.get((dow, hour), 0.0)
            headcount = max(1, math.ceil(avg / CASES_PER_AGENT_HOUR))
            cells.append({
                "day": day_names[dow],
                "dow": dow,
                "hour": hour,
                "avg_cases": round(avg, 1),
                "recommended_agents": headcount,
            })

    # Workforce summary: agents needed at peak hour
    peak = max(cells, key=lambda c: c["avg_cases"]) if cells else None

    return {
        "cells": cells,
        "peak": peak,
        "model": "avg over last 28d, threshold 5 cases/agent/hr (configurable)",
    }
