"""Knowledge retriever — grounded answers from curated facts + crawled MOEI pages.

Two-tier retrieval:
  1. `knowledge_facts` — hand-curated, high-stakes facts (call centre, hours, mission).
     ALWAYS checked first. A hit here outranks any crawled chunk.
  2. `knowledge_documents` — pages crawled from moei.gov.ae via scripts/crawl_moei.py.
     Postgres FTS (English + Arabic configs) for cheap, fast retrieval.

Each result carries its source URL so the composer can render citations like
  More info → https://www.moei.gov.ae/en/about-ministry
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any

_API = Path(__file__).resolve().parents[3] / "apps" / "api"
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

try:
    from app.core.db import db_cursor  # type: ignore[import-not-found]
    _DB_AVAILABLE = True
except Exception:
    _DB_AVAILABLE = False

from loguru import logger


# Strip punctuation that breaks ts_query. Keep word chars, spaces, and the Arabic
# + Arabic Supplement Unicode blocks (U+0600..U+06FF, U+0750..U+077F).
_TSQ_SAFE = re.compile(r"[^\w\s؀-ۿݐ-ݿ]")
# Stop words we drop before forming a ts_query — they match too much and dilute ranking.
_EN_STOP = {
    "the","a","an","and","or","of","to","for","in","on","at","by","with","is","are","be","was",
    "were","do","does","did","i","you","he","she","it","we","they","this","that","my","your",
    "what","when","where","who","why","how","can","could","should","would","please","tell","me",
    "about","there","their","its","into","over","under","than","then","also","but","not","no",
}


def _to_tsquery(text: str, lang: str) -> str:
    cleaned = _TSQ_SAFE.sub(" ", text or "").lower()
    words = [w for w in cleaned.split() if len(w) >= 2]
    if lang == "en":
        words = [w for w in words if w not in _EN_STOP]
    if not words:
        return ""
    # Use prefix match (':*') and OR for forgiveness on plurals/case/typos.
    return " | ".join(f"{w}:*" for w in words[:12])


def search(query: str, lang: str = "en", top_k: int = 3) -> list[dict[str, Any]]:
    """Return ranked knowledge hits as [{source, title, snippet, url, score}, ...]."""
    if not _DB_AVAILABLE or not query.strip():
        return []
    lang = "ar" if lang == "ar" else "en"
    tsq = _to_tsquery(query, lang)
    if not tsq:
        return []
    cfg = "simple" if lang == "ar" else "english"

    results: list[dict[str, Any]] = []
    try:
        with db_cursor() as cur:
            # 1) Curated facts. Score boosted by +5 so they always lead.
            cur.execute(
                f"""
                SELECT title, answer AS content, source_url AS url, topic AS section,
                       'curated' AS source,
                       ts_rank_cd(tsv, to_tsquery(%s, %s)) + 5.0 AS score
                FROM knowledge_facts
                WHERE lang = %s AND tsv @@ to_tsquery(%s, %s)
                ORDER BY score DESC LIMIT %s
                """,
                (cfg, tsq, lang, cfg, tsq, top_k),
            )
            for r in cur.fetchall():
                results.append(_format(r, snippet_len=400))

            # 2) Crawled pages.
            cur.execute(
                f"""
                SELECT title, content, url, section, 'crawled' AS source,
                       ts_rank_cd(tsv, to_tsquery(%s, %s)) AS score
                FROM knowledge_documents
                WHERE lang = %s AND tsv @@ to_tsquery(%s, %s)
                ORDER BY score DESC LIMIT %s
                """,
                (cfg, tsq, lang, cfg, tsq, top_k),
            )
            for r in cur.fetchall():
                results.append(_format(r, snippet_len=300))
    except Exception as e:
        logger.warning(f"knowledge.search failed: {e}")
        return []

    # Re-sort and de-dupe by URL.
    results.sort(key=lambda x: x["score"], reverse=True)
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for r in results:
        key = (r.get("url") or "").strip().lower() or r["title"]
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
        if len(deduped) >= top_k:
            break
    return deduped


def _format(row: dict[str, Any], snippet_len: int) -> dict[str, Any]:
    content = (row.get("content") or "").strip()
    snippet = content[:snippet_len].rstrip()
    if len(content) > snippet_len:
        snippet += "…"
    return {
        "source": row.get("source", "kb"),
        "section": row.get("section"),
        "title": row.get("title") or "",
        "snippet": snippet,
        "url": row.get("url") or "",
        "score": float(row.get("score") or 0),
    }


def format_for_prompt(hits: list[dict[str, Any]]) -> str:
    """Render hits as a compact context block the composer can paste into its prompt."""
    if not hits:
        return ""
    lines = ["KNOWLEDGE_BASE (from moei.gov.ae, cite the URL if you use a fact):"]
    for i, h in enumerate(hits, 1):
        url = h.get("url") or "(no url)"
        title = h.get("title") or "(untitled)"
        snippet = (h.get("snippet") or "").replace("\n", " ")
        lines.append(f"[{i}] {title} — {url}\n    {snippet}")
    return "\n".join(lines)
