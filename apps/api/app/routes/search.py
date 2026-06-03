"""Smart search across MOEI services / policies / FAQs / procedures.

Cheap keyword + scored search over the MOEI catalog. Returns matched services with citations.
Production path: swap to Qdrant + embeddings. The endpoint shape stays the same.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from hassan.knowledge import all_services, search_services

router = APIRouter(prefix="/search", tags=["search"])


def _detect_lang(text: str) -> str:
    return "ar" if any("؀" <= c <= "ۿ" for c in text) else "en"


@router.get("")
def search(q: str = Query(..., min_length=2, max_length=200), limit: int = Query(5, ge=1, le=20)) -> dict:
    """Unified smart search across services, policies, FAQs, and procedures.

    Two sources, merged: (1) the MOEI service catalogue, (2) the knowledge base
    (curated facts + crawled moei.gov.ae pages). Each result is tagged with `type`.
    """
    hits = search_services(q, limit=limit)
    if not hits and len(q) >= 3:
        ql = q.lower()
        hits = [s for s in all_services() if ql in s.get("title", "").lower() or ql in s.get("summary", "").lower()][:limit]

    results = [
        {
            "type": "service",
            "id": s["id"],
            "title": s["title"],
            "title_ar": s.get("title_ar", ""),
            "summary": s.get("summary", "")[:280],
            "service": s.get("service"),
            "audience": s.get("audience"),
            "channels": s.get("channels", []),
            "fee_aed": s.get("fees_aed", 0),
            "sla_days": s.get("sla_days", 0),
            "url": s.get("url"),
            "required_documents": s.get("required_documents", []),
        }
        for s in hits
    ]

    # Knowledge base: policies, FAQs, procedures, and crawled official pages.
    try:
        from hassan.workers.knowledge import search as kb_search

        for k in kb_search(q, lang=_detect_lang(q), top_k=limit):
            results.append({
                "type": "policy" if k.get("source") == "curated" else "page",
                "id": (k.get("url") or k.get("title") or "kb"),
                "title": k.get("title") or "MOEI information",
                "title_ar": "",
                "summary": (k.get("snippet") or "")[:280],
                "service": k.get("section"),
                "channels": [],
                "url": k.get("url"),
                "required_documents": [],
            })
    except Exception:
        pass

    return {"query": q, "count": len(results), "results": results}
