"""MOEI services catalog loader.

Reads `data/moei/services.json` (or whatever path MOEI provides later). Pure-Python search —
no embedding index needed for ~14 services; if the real catalog grows past 200 services we
swap to Qdrant. The function signatures stay the same so callers don't change.

When MOEI delivers their catalog: drop a JSON file matching `services.json`'s shape at the
path in HASSAN_MOEI_CATALOG (env var) and restart. That's the entire ingest path.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from loguru import logger

_DEFAULT_PATH = Path(__file__).resolve().parents[3] / "data" / "moei" / "services.json"


@lru_cache(maxsize=1)
def _load() -> dict[str, Any]:
    path = Path(os.getenv("HASSAN_MOEI_CATALOG", _DEFAULT_PATH))
    if not path.exists():
        logger.warning(f"MOEI catalog not found at {path}; using empty list")
        return {"_meta": {}, "services": []}
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    logger.info(f"MOEI catalog loaded: {len(data.get('services', []))} services from {path}")
    return data


def all_services() -> list[dict]:
    return _load().get("services", [])


def get_service(service_id: str) -> dict | None:
    for s in all_services():
        if s["id"] == service_id:
            return s
    return None


def find_services(*, domain: str | None = None) -> list[dict]:
    """Filter by top-level service domain (housing, energy, transport, maritime, infrastructure, general)."""
    services = all_services()
    if domain:
        services = [s for s in services if s.get("service") == domain]
    return services


def search_services(query: str, *, limit: int = 5) -> list[dict]:
    """Cheap keyword search over title/title_ar/summary. Returns ranked hits."""
    q = query.lower().strip()
    if not q:
        return []
    scored: list[tuple[int, dict]] = []
    for s in all_services():
        haystack = " ".join([
            s.get("title", "").lower(),
            s.get("title_ar", ""),
            s.get("summary", "").lower(),
            s.get("audience", "").lower(),
        ])
        # Score: 3 for title hit, 1 for any hit
        score = 0
        for term in q.split():
            if term in s.get("title", "").lower() or term in s.get("title_ar", ""):
                score += 3
            elif term in haystack:
                score += 1
        if score > 0:
            scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    return [s for _, s in scored[:limit]]


def catalog_meta() -> dict:
    return _load().get("_meta", {})
