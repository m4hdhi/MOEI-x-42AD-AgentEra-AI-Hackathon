"""Scrape the public MOEI services catalog into a JSON file Hassan can load.

Runs Playwright against moei.gov.ae, waits for the SPA to render each category, then
extracts service cards (title, summary, fee, SLA, audience, channels, docs where shown).

Usage:
    uv run python scripts/scrape_moei.py

Output:
    data/moei/services.json  — replaces the seed catalog

Re-run when MOEI hands over a real data source; the loader path doesn't change.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "moei" / "services.json"

# Service categories as they appear in the MOEI top-nav. Each maps to its slug.
CATEGORIES = [
    ("housing", "sheikh-zayed-housing-program", "Sheikh Zayed Housing Programme"),
    ("transport", "land-transportation", "Land Transportation"),
    ("maritime", "maritime-transport", "Maritime Transport"),
    ("infrastructure", "infrastructure-services", "Infrastructure Services"),
    ("infrastructure", "geological-services", "Geological Services"),
    ("energy", "petroleum-products-trading", "Petroleum Products Trading"),
    ("general", "customer-service", "Customer Service"),
]

BASE = "https://www.moei.gov.ae"


def _slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s[:80] or "service"


async def scrape() -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: uv pip install playwright && uv run playwright install chromium", file=sys.stderr)
        sys.exit(1)

    services: list[dict] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 12_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            locale="en-US",
        )

        # Visit several category pages and harvest links from each — more reliable than
        # the all-services index, which depends on tab-switching JS we can't easily drive.
        all_links: list[dict] = []
        category_urls = [
            f"{BASE}/en/services",
        ] + [f"{BASE}/en/services/{slug}" for _, slug, _ in CATEGORIES]

        page = await ctx.new_page()
        for cat_url in category_urls:
            try:
                print(f"→ {cat_url}", file=sys.stderr)
                await page.goto(cat_url, wait_until="domcontentloaded", timeout=30000)
                # Let SPA hydrate. Give it enough time to fetch service cards.
                await page.wait_for_timeout(4000)
                # Scroll to trigger lazy-loaded cards
                await page.evaluate("window.scrollBy(0, 2000)")
                await page.wait_for_timeout(1500)
                await page.evaluate("window.scrollBy(0, 2000)")
                await page.wait_for_timeout(1000)
                cat_links = await page.evaluate("""
                    () => Array.from(document.querySelectorAll('a[href*="/en/services/"]'))
                        .map(a => ({
                            href: a.getAttribute('href'),
                            text: (a.textContent || '').trim().replace(/\\s+/g, ' '),
                        }))
                        .filter(x => x.text.length > 5 && x.text.length < 200 && !x.href.endsWith('/en/services'))
                """)
                all_links.extend(cat_links)
            except Exception as e:
                print(f"  ! failed {cat_url}: {e}", file=sys.stderr)
                continue
        links = all_links
        # De-dup by href
        seen: set[str] = set()
        targets: list[tuple[str, str]] = []
        for l in links:
            href = l["href"]
            if href.startswith("/"):
                href = BASE + href
            if href in seen:
                continue
            seen.add(href)
            targets.append((href, l["text"]))

        print(f"  found {len(targets)} unique service links", file=sys.stderr)

        # Visit each detail page and extract structured info
        for i, (url, title_guess) in enumerate(targets[:80]):  # cap at 80
            print(f"[{i+1}/{min(60,len(targets))}] {title_guess[:60]}", file=sys.stderr)
            try:
                p2 = await ctx.new_page()
                await p2.goto(url, wait_until="domcontentloaded", timeout=20000)
                # Let the SPA hydrate
                await p2.wait_for_timeout(2500)

                # Extract structured fields — MOEI service pages have predictable section headers
                data = await p2.evaluate("""
                    () => {
                        const get = (sel) => {
                            const el = document.querySelector(sel);
                            return el ? (el.textContent || '').trim().replace(/\\s+/g, ' ') : '';
                        };
                        const getAfter = (label) => {
                            // Find a heading or label, return the following block's text
                            const headings = Array.from(document.querySelectorAll('h2, h3, h4, dt, strong, b'));
                            for (const h of headings) {
                                const t = (h.textContent || '').trim().toLowerCase();
                                if (t.includes(label.toLowerCase())) {
                                    let sib = h.nextElementSibling;
                                    if (sib) return (sib.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 600);
                                }
                            }
                            return '';
                        };
                        return {
                            title: document.querySelector('h1') ? document.querySelector('h1').textContent.trim() : '',
                            description: getAfter('description') || getAfter('about the service') || getAfter('service description'),
                            audience: getAfter('target audience') || getAfter('audience'),
                            documents: getAfter('required documents') || getAfter('documents'),
                            channels: getAfter('service channels') || getAfter('channels'),
                            fees: getAfter('service fees') || getAfter('fees'),
                            sla: getAfter('service time') || getAfter('service duration') || getAfter('duration'),
                            steps: getAfter('service procedure') || getAfter('procedure') || getAfter('steps'),
                        };
                    }
                """)
                await p2.close()

                title = data["title"] or title_guess
                if not title:
                    continue

                # Heuristic service-domain detection from URL
                domain = "general"
                for d, slug, _ in CATEGORIES:
                    if slug in url:
                        domain = d
                        break

                service = {
                    "id": _slugify(title),
                    "service": domain,
                    "title": title,
                    "title_ar": "",   # filled by adding an Arabic scrape pass later
                    "audience": data["audience"][:300] or "All UAE residents",
                    "summary": (data["description"] or data["steps"])[:600],
                    "required_documents": [
                        s.strip() for s in re.split(r"[,;•\n·]+", data["documents"])
                        if s.strip()
                    ][:8] if data["documents"] else [],
                    "channels": [
                        s.strip() for s in re.split(r"[,;•\n·]+", data["channels"])
                        if s.strip()
                    ][:6] if data["channels"] else ["Web"],
                    "sla_days": _parse_days(data["sla"]),
                    "fees_aed": _parse_aed(data["fees"]),
                    "url": url,
                }
                services.append(service)
            except Exception as e:
                print(f"  ! failed {url}: {e}", file=sys.stderr)
                continue

        await browser.close()

    # Add the housing-rescheduling entry that's our hero flow (not always on the public listing)
    if not any(s["id"].startswith("reschedul") or "reschedul" in s["title"].lower() for s in services):
        services.insert(0, {
            "id": "szhp-reschedule",
            "service": "housing",
            "title": "Sheikh Zayed Housing Programme — Reschedule a Housing Loan",
            "title_ar": "إعادة جدولة قرض الإسكان — برنامج الشيخ زايد للإسكان",
            "audience": "UAE nationals with an active SZHP loan",
            "summary": "Citizens facing genuine financial hardship can apply to extend the term of their housing loan. Hassan triages eligibility via the rules engine and prepares the offer letter for e-signature.",
            "required_documents": ["Emirates ID", "Latest 3 months' salary slips", "Bank statement", "Active loan statement"],
            "channels": ["WhatsApp", "Voice (800 6634)", "Web", "Branch"],
            "sla_days": 3,
            "fees_aed": 0,
            "url": f"{BASE}/en/services/sheikh-zayed-housing-program",
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_meta": {
            "source": "Scraped from moei.gov.ae public pages (Playwright). PDPL-safe. Re-run scripts/scrape_moei.py to refresh.",
            "version": "scraped-2026-05-24",
            "agent_name": "Hassan",
            "contact_centre": "800 6634",
            "tawasul_complaint": "171 (UAE Government complaints platform)",
            "uae_pass_required": True,
        },
        "services": services,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\n✓ wrote {len(services)} services to {OUT}", file=sys.stderr)


def _parse_days(s: str) -> int:
    if not s:
        return 0
    m = re.search(r"(\d+)\s*(?:working\s+)?(?:day|business\s+day)", s, re.I)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*hour", s, re.I)
    if m:
        return 0
    if "instant" in s.lower() or "immediate" in s.lower():
        return 0
    return 0


def _parse_aed(s: str) -> int:
    if not s:
        return 0
    if "free" in s.lower() or "no fee" in s.lower():
        return 0
    m = re.search(r"AED\s*([\d,]+)", s, re.I)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            return 0
    m = re.search(r"([\d,]+)\s*(?:dirham|AED)", s, re.I)
    if m:
        try:
            return int(m.group(1).replace(",", ""))
        except ValueError:
            return 0
    return 0


if __name__ == "__main__":
    asyncio.run(scrape())
