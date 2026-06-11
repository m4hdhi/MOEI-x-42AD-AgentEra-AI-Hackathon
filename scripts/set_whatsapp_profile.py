"""One-shot setup: request WhatsApp display name approval + set business profile.

Run once after configuring META_WHATSAPP_* env vars:

    make wa-profile          # or: uv run python scripts/set_whatsapp_profile.py

Meta must review the display name before it shows to recipients (usually 1-3 days).
The business profile (About text, category, website) is applied immediately.
"""

from __future__ import annotations

import os
import re
import sys

import httpx


def _require(name: str) -> str:
    val = os.getenv(name, "").strip()
    if not val:
        print(f"ERROR: {name} is not set in .env", file=sys.stderr)
        sys.exit(1)
    return val


def main() -> None:
    token = _require("META_WHATSAPP_ACCESS_TOKEN")
    phone_id = _require("META_WHATSAPP_PHONE_NUMBER_ID")
    version = os.getenv("META_GRAPH_API_VERSION", "v22.0").strip() or "v22.0"
    base = f"https://graph.facebook.com/{version}/{phone_id}"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    display_name = "MOEI Assistant (Demo)"

    with httpx.Client(timeout=15.0) as client:
        # 1. Display name — there is NO Cloud API edge to request a review.
        #    Show current verified name and point to WhatsApp Manager.
        r = client.get(f"{base}", headers=headers, params={"fields": "verified_name"})
        current = r.json().get("verified_name") if r.status_code < 300 else None
        if current == display_name:
            print(f"[OK] Display name is already '{display_name}'.")
        else:
            print(f"[ACTION] Set the display name in WhatsApp Manager (no API exists):")
            print("         business.facebook.com → WhatsApp Manager → Phone Numbers")
            print(f"         → Edit profile → Display Name = '{display_name}' → Submit")
            if current:
                print(f"         (current verified name: '{current}')")

        # 2. Set business profile (applied immediately, no review needed)
        profile = {
            "messaging_product": "whatsapp",
            "about": "UAE Ministry of Energy and Infrastructure — AI-powered citizen assistant",
            "vertical": "GOVT",
            "websites": ["https://www.moei.gov.ae"],
        }
        r2 = client.post(f"{base}/whatsapp_business_profile", headers=headers, json=profile)
        if r2.status_code < 300:
            print("[OK] Business profile updated (About text, category, website).")
        else:
            print(f"[WARN] Business profile update returned {r2.status_code}: {r2.text[:300]}")


if __name__ == "__main__":
    # Load .env if present (simple fallback — avoids requiring python-dotenv at runtime)
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, val = line.partition("=")
                    # Drop inline comments (whitespace + '#'), then quotes/space.
                    val = re.split(r"\s+#", val, maxsplit=1)[0]
                    os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

    main()
