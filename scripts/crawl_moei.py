"""Crawl moei.gov.ae (EN + AR) and populate the knowledge_documents table.

Usage:
    uv run python scripts/crawl_moei.py                      # full bilingual crawl (capped)
    uv run python scripts/crawl_moei.py --lang en --max 100  # narrow run
    uv run python scripts/crawl_moei.py --resume             # skip URLs already in DB

Politeness:
  - Respects robots.txt (lazy fetch + parse)
  - Hard cap per language (default 250)
  - 0.5s delay between pages
  - One Chromium tab, requests Origin: moei.gov.ae only
  - Skips non-HTML (PDFs/images) — these need a separate doc pipeline

Storage: each crawled page is one row in knowledge_documents with:
  url, lang, title, section (about/services/branches/news/other), content (text only),
  content_hash (sha256 of cleaned content — dedupe key).
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
import re
import sys
import time
from collections import deque
from pathlib import Path
from typing import Set
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.robotparser import RobotFileParser

_API = Path(__file__).resolve().parents[1] / "apps" / "api"
if str(_API) not in sys.path:
    sys.path.insert(0, str(_API))

from app.core.db import db_cursor  # type: ignore

ROOT = "https://www.moei.gov.ae"
SEEDS = {
    "en": [
        f"{ROOT}/en",
        f"{ROOT}/en/about-ministry",
        f"{ROOT}/en/services",
        f"{ROOT}/en/contact-us",
        f"{ROOT}/en/media-centre",
    ],
    "ar": [
        f"{ROOT}/ar",
        f"{ROOT}/ar/about-ministry",
        f"{ROOT}/ar/services",
        f"{ROOT}/ar/contact-us",
        f"{ROOT}/ar/media-centre",
    ],
}

# Anything under these paths we don't want — too noisy, breaks search relevance.
SKIP_PATTERNS = (
    "/login", "/sign-in", "/forgot-password", "/captcha",
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".doc", ".docx", ".xls", ".xlsx", ".zip",
    "?print=", "/print/",
)

DEFAULT_CAP_PER_LANG = 250
PAGE_DELAY_S = 0.5
PAGE_TIMEOUT_MS = 20000


def _section_for(url: str) -> str:
    p = urlparse(url).path.lower()
    if "/about" in p:
        return "about"
    if "/services" in p or "/service" in p:
        return "services"
    if "/contact" in p or "/branch" in p or "/location" in p:
        return "branches"
    if "/news" in p or "/media" in p:
        return "news"
    return "other"


def _hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _normalize(url: str) -> str:
    url, _ = urldefrag(url)
    if url.endswith("/"):
        url = url[:-1]
    return url


def _same_site(url: str) -> bool:
    p = urlparse(url)
    return p.netloc in ("www.moei.gov.ae", "moei.gov.ae")


def _allowed_lang(url: str, lang: str) -> bool:
    p = urlparse(url).path
    return p.startswith(f"/{lang}/") or p == f"/{lang}"


def _skip(url: str) -> bool:
    low = url.lower()
    return any(s in low for s in SKIP_PATTERNS)


def _existing_urls(lang: str) -> Set[str]:
    try:
        with db_cursor() as cur:
            cur.execute("SELECT url FROM knowledge_documents WHERE lang=%s", (lang,))
            return {r["url"] for r in cur.fetchall()}
    except Exception:
        return set()


def _upsert(url: str, lang: str, title: str, section: str, content: str) -> str:
    """Insert or replace one document. Returns 'inserted' / 'updated' / 'skipped'."""
    h = _hash(content)
    try:
        with db_cursor() as cur:
            cur.execute(
                "SELECT content_hash FROM knowledge_documents WHERE url=%s AND lang=%s",
                (url, lang),
            )
            existing = cur.fetchone()
            if existing and existing["content_hash"] == h:
                return "skipped"
            cur.execute(
                """
                INSERT INTO knowledge_documents (url, lang, title, section, content, content_hash, fetched_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (url, lang) DO UPDATE
                  SET title=EXCLUDED.title, section=EXCLUDED.section,
                      content=EXCLUDED.content, content_hash=EXCLUDED.content_hash,
                      fetched_at=NOW()
                """,
                (url, lang, title[:500], section, content[:30000], h),
            )
            return "updated" if existing else "inserted"
    except Exception as e:
        print(f"[crawl] DB upsert failed for {url}: {e}", file=sys.stderr)
        return "skipped"


def _build_robots() -> RobotFileParser:
    rp = RobotFileParser()
    rp.set_url(f"{ROOT}/robots.txt")
    try:
        rp.read()
    except Exception:
        pass
    return rp


async def _crawl_lang(lang: str, cap: int, resume: bool) -> tuple[int, int]:
    from playwright.async_api import async_playwright

    rp = _build_robots()
    seen: Set[str] = set()
    if resume:
        seen.update(_existing_urls(lang))
        print(f"[crawl/{lang}] resume mode: {len(seen)} URLs already in DB will be skipped")
    queue: deque[str] = deque(_normalize(u) for u in SEEDS[lang] if u not in seen)
    processed = 0
    inserted = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (MOEI-Agent42-Crawler/1.0; +hassan-demo)",
            locale="en-AE" if lang == "en" else "ar-AE",
        )
        page = await ctx.new_page()

        while queue and processed < cap:
            url = queue.popleft()
            if url in seen:
                continue
            seen.add(url)
            if not _same_site(url) or not _allowed_lang(url, lang) or _skip(url):
                continue
            if not rp.can_fetch("*", url):
                continue

            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS)
                if not resp or resp.status >= 400:
                    continue
                ctype = (resp.headers or {}).get("content-type", "")
                if "html" not in ctype:
                    continue

                title = (await page.title()) or url

                # Pull visible text from <main>, fall back to <body>. Strip nav, footer, scripts.
                content = await page.evaluate("""
                    () => {
                        const drop = ['nav','header','footer','script','style','noscript','svg','iframe'];
                        drop.forEach(t => document.querySelectorAll(t).forEach(n => n.remove()));
                        const main = document.querySelector('main') || document.body;
                        return (main.innerText || '').replace(/[ \\t]+/g, ' ').replace(/\\n{3,}/g, '\\n\\n').trim();
                    }
                """)

                if content and len(content) > 80:
                    section = _section_for(url)
                    status = _upsert(url, lang, title, section, content)
                    if status in ("inserted", "updated"):
                        inserted += 1
                    print(f"[crawl/{lang}] {processed+1:>4} {status:8s} {section:9s} {url}")

                # Enqueue same-lang internal links
                links = await page.evaluate("""
                    () => Array.from(document.querySelectorAll('a[href]')).map(a => a.href)
                """)
                for h in links:
                    if not h:
                        continue
                    n = _normalize(h)
                    if n in seen or not _same_site(n) or not _allowed_lang(n, lang) or _skip(n):
                        continue
                    queue.append(n)

                processed += 1
                await asyncio.sleep(PAGE_DELAY_S)
            except Exception as e:
                msg = str(e).splitlines()[0][:120]
                print(f"[crawl/{lang}] FAIL {url}: {msg}")

        await browser.close()

    print(f"[crawl/{lang}] done. processed={processed} inserted_or_updated={inserted} queue_remaining={len(queue)}")
    return processed, inserted


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", choices=["en", "ar", "both"], default="both")
    ap.add_argument("--max", type=int, default=DEFAULT_CAP_PER_LANG, help="page cap per language")
    ap.add_argument("--resume", action="store_true", help="skip URLs already in knowledge_documents")
    args = ap.parse_args()

    langs = ["en", "ar"] if args.lang == "both" else [args.lang]
    start = time.time()
    total_processed = 0
    total_inserted = 0
    for lang in langs:
        p, i = await _crawl_lang(lang, cap=args.max, resume=args.resume)
        total_processed += p
        total_inserted += i
    elapsed = time.time() - start
    print(f"\n[crawl] ALL DONE in {elapsed:.0f}s · processed={total_processed} inserted_or_updated={total_inserted}")


if __name__ == "__main__":
    asyncio.run(main())
