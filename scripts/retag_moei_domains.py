"""Post-process the scraped MOEI catalog to assign correct service domains based on title keywords."""

import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "data" / "moei" / "services.json"
data = json.loads(PATH.read_text())

DOMAIN_KEYWORDS = {
    "housing": ["housing", "szhp", "sheikh zayed"],
    "transport": ["transportation", "vehicle permit", "land transport", "driver", "fleet"],
    "maritime": ["pleasure boat", "navigation license", "vessel", "ship", "seafarer", "maritime", "port"],
    "energy": ["petroleum", "petrol", "energy", "electricity", "water", "tariff", "gas"],
    "infrastructure": ["infrastructure", "geological", "geophysical", "construction permit", "road permit"],
}

for s in data["services"]:
    title_l = s["title"].lower()
    matched = False
    for domain, kws in DOMAIN_KEYWORDS.items():
        if any(kw in title_l for kw in kws):
            s["service"] = domain
            matched = True
            break
    if not matched:
        s["service"] = "general"

PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))
print(f"Re-tagged {len(data['services'])} services. Distribution:")
from collections import Counter
c = Counter(s["service"] for s in data["services"])
for k, v in c.most_common():
    print(f"  {k:15s} {v}")
