"""Load the official MOEI service catalogue into the knowledge base.

The hackathon workbook ships a "List of Ministry Services" sheet — the ministry's real,
Arabic-language catalogue of ~130 services grouped by sector and department. This script turns
each service into one Arabic (`lang='ar'`) row in `knowledge_documents` (`section='services'`),
so it is retrievable through the exact same Postgres full-text search the agents already use
(`hassan.workers.knowledge.search`) and the citizen `/search` endpoint already queries.

This *complements* the curated `data/moei/services.json` (the 18 rich, bilingual services that
drive the deep demo flows): the JSON gives polished service cards for the headline journeys,
while these rows give grounded coverage of the long tail of official services for Arabic
smart-search. Re-runnable: rows upsert on (url, lang).

The sheet's sector column is merged in Excel (only the first row of each group carries a value),
so we forward-fill it down each group.

Usage:
  uv run python scripts/import_services_catalog.py
  uv run python scripts/import_services_catalog.py --file "/path/to/dataset.xlsx"
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
from app.core.db import db_cursor  # type: ignore[import-not-found]  # noqa: E402

SHEET = "List of Ministry Services"
# Stable services hub on moei.gov.ae; a per-row fragment keeps the UNIQUE(url, lang) key happy.
SERVICES_URL = "https://www.moei.gov.ae/ar/services"
DEFAULT_FILES = [
    ROOT / "docs" / "MOEI_Omnichannel_AI_Dataset_Hackathon (1) (2).xlsx",
    ROOT / "data" / "moei" / "MOEI_Omnichannel_AI_Dataset.xlsx",
    ROOT / "MOEI_Omnichannel_AI_Dataset_Hackathon (1) (2).xlsx",
]


def _hash(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def _resolve(path_arg: str | None) -> Path:
    if path_arg:
        p = Path(path_arg)
        if not p.exists():
            raise SystemExit(f"file not found: {p}")
        return p
    for cand in DEFAULT_FILES:
        if cand.exists():
            return cand
    raise SystemExit("dataset workbook not found in default locations; pass --file")


def _col(df: pd.DataFrame, *needles: str) -> str | None:
    """Find a column whose (stripped) header contains any of the Arabic needles."""
    for c in df.columns:
        cs = str(c).strip()
        if any(n in cs for n in needles):
            return c
    return None


def load_services(path: Path) -> list[dict]:
    # Header is on the second row (index 1): م. | القطاع | الإدارة | اسم الخدمة
    df = pd.read_excel(path, sheet_name=SHEET, header=1)
    sector_col = _col(df, "قطاع")
    dept_col = _col(df, "دارة")          # الإدارة
    name_col = _col(df, "خدمة")          # اسم الخدمة
    if not (sector_col and name_col):
        raise SystemExit(f"could not locate catalogue columns in sheet '{SHEET}'")

    df[sector_col] = df[sector_col].ffill()  # merged-cell sector → forward-fill
    out: list[dict] = []
    for _, row in df.iterrows():
        name = str(row.get(name_col) or "").strip()
        if not name or name.lower() == "nan":
            continue
        out.append({
            "name": name,
            "sector": str(row.get(sector_col) or "").strip(),
            "dept": str(row.get(dept_col) or "").strip() if dept_col else "",
        })
    return out


def _content(svc: dict) -> str:
    parts = [
        svc["name"],
        f"الخدمة: {svc['name']}",
    ]
    if svc["dept"]:
        parts.append(f"الإدارة: {svc['dept']}")
    if svc["sector"]:
        parts.append(f"القطاع: {svc['sector']}")
    parts.append("خدمة حكومية رسمية تقدمها وزارة الطاقة والبنية التحتية.")
    return "\n".join(parts)


def import_catalogue(path: Path) -> dict[str, int]:
    services = load_services(path)
    stats = {"inserted": 0, "updated": 0, "skipped": 0}
    with db_cursor() as cur:
        for seq, svc in enumerate(services, start=1):
            url = f"{SERVICES_URL}#svc-{seq}"
            content = _content(svc)
            h = _hash(content)
            cur.execute(
                "SELECT content_hash FROM knowledge_documents WHERE url=%s AND lang='ar'",
                (url,),
            )
            existing = cur.fetchone()
            if existing and existing["content_hash"] == h:
                stats["skipped"] += 1
                continue
            cur.execute(
                """
                INSERT INTO knowledge_documents
                    (url, lang, title, section, content, content_hash, fetched_at)
                VALUES (%s, 'ar', %s, 'services', %s, %s, NOW())
                ON CONFLICT (url, lang) DO UPDATE
                  SET title=EXCLUDED.title, section=EXCLUDED.section,
                      content=EXCLUDED.content, content_hash=EXCLUDED.content_hash, fetched_at=NOW()
                """,
                (url, svc["name"][:500], content[:30000], h),
            )
            stats["updated" if existing else "inserted"] += 1
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Load the MOEI service catalogue into the KB.")
    ap.add_argument("--file", help="path to the dataset workbook (.xlsx)")
    args = ap.parse_args()

    path = _resolve(args.file)
    print(f"[catalogue] reading '{SHEET}' from {path}")
    stats = import_catalogue(path)
    total = sum(stats.values())
    print(f"[catalogue] {total} official services → "
          f"{stats['inserted']} inserted, {stats['updated']} updated, {stats['skipped']} unchanged")


if __name__ == "__main__":
    main()
