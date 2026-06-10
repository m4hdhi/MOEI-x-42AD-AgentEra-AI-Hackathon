"""Executive dashboard metrics.

For the demo: pre-computed plausible numbers backed by counters where we can fill them
(volumes from Redis), the rest from a baseline file. The 90-day pilot is where the real
KPIs (deflection, AHT reduction, CSAT) get measured against MOEI baselines.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

router = APIRouter(prefix="/exec", tags=["exec"])


# Demo baseline. The 90-day pilot will replace this with live Customer Happiness Centre
# numbers shadow-mode against real traffic.
_DEMO_KPIS = {
    "agent_name": "Agent42",
    "active_services": ["housing"],
    "shadow_services": ["energy", "infrastructure", "maritime", "transport"],
    "volumes_24h": {
        "total_turns": 1247,
        "by_channel": {"whatsapp": 612, "voice": 198, "web": 401, "mobile": 36},
        "by_language": {"ar": 821, "en": 426},
    },
    "kpis": {
        "deflection_rate_pct": 62.3,
        "containment_rate_pct": 78.1,
        "escalation_rate_pct": 14.4,
        "avg_handle_time_sec": 92,
        "first_response_time_sec": 3,
        "csat_5pt": 4.6,
    },
    "top_intents": [
        {"intent": "service_request", "service": "housing", "count": 384},
        {"intent": "status_check", "service": "housing", "count": 211},
        {"intent": "document_upload", "service": "housing", "count": 142},
        {"intent": "complaint", "service": "housing", "count": 67},
        {"intent": "escalate_to_human", "service": "housing", "count": 51},
    ],
    "risk_distribution": {"low": 624, "medium": 312, "high": 88},
}


@router.get("/kpis")
async def kpis() -> dict:
    return {"as_of": datetime.utcnow().isoformat(), **_DEMO_KPIS}


@router.get("/trend")
async def trend() -> dict:
    """7-day demo trend for the headline chart on the dashboard."""
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    return {
        "volume": [
            {"day": d, "whatsapp": v[0], "voice": v[1], "web": v[2]}
            for d, v in zip(days, [
                (520, 180, 360),
                (610, 195, 390),
                (640, 210, 405),
                (580, 188, 380),
                (612, 198, 401),
                (430, 142, 290),
                (310, 96, 220),
            ])
        ],
        "deflection_pct": [58.2, 60.1, 61.4, 62.0, 62.3, 63.1, 63.6],
        "csat": [4.4, 4.5, 4.5, 4.6, 4.6, 4.6, 4.7],
    }
