"""Load country intelligence profiles into Postgres.

  uv run python scripts/import_intel.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
from app.core.db import db_cursor  # type: ignore[import-not-found]

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "data" / "intel" / "countries.json"


def main():
    data = json.loads(FILE.read_text(encoding="utf-8"))
    rows = data.get("countries", [])
    with db_cursor() as cur:
        for c in rows:
            cur.execute(
                """INSERT INTO countries (
                     code, flag, name, name_ar, region, capital, population_m, gdp_usd_b,
                     gdp_per_capita_usd, gdp_growth_pct, uae_trade_usd_b, profile, updated_at
                   ) VALUES (
                     %(code)s,%(flag)s,%(name)s,%(name_ar)s,%(region)s,%(capital)s,%(pop)s,%(gdp)s,
                     %(gdpc)s,%(growth)s,%(trade)s,%(profile)s, NOW()
                   )
                   ON CONFLICT (code) DO UPDATE SET
                     flag=EXCLUDED.flag, name=EXCLUDED.name, region=EXCLUDED.region,
                     population_m=EXCLUDED.population_m, gdp_usd_b=EXCLUDED.gdp_usd_b,
                     gdp_per_capita_usd=EXCLUDED.gdp_per_capita_usd, gdp_growth_pct=EXCLUDED.gdp_growth_pct,
                     uae_trade_usd_b=EXCLUDED.uae_trade_usd_b, profile=EXCLUDED.profile, updated_at=NOW()
                """,
                {
                    "code": c["code"], "flag": c.get("flag"), "name": c["name"],
                    "name_ar": c.get("name_ar"), "region": c.get("region"), "capital": c.get("capital"),
                    "pop": c.get("population_m"), "gdp": c.get("gdp_usd_b"),
                    "gdpc": c.get("gdp_per_capita_usd"), "growth": c.get("gdp_growth_pct"),
                    "trade": (c.get("uae") or {}).get("non_oil_trade_usd_b"),
                    "profile": json.dumps(c, ensure_ascii=False),
                },
            )
    print(f"  ✓ countries loaded: {len(rows)}")


if __name__ == "__main__":
    main()
