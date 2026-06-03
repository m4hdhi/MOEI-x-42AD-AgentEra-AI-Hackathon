"""Language detection at the gateway.

Cheap, deterministic, ~free. We only need ar/en classification for routing — the LLM Router
will re-verify. Done with Unicode range checks; no model dependency, no startup cost.
"""

from __future__ import annotations


def detect_language(text: str) -> str:
    """Return 'ar' if >= 20% of chars are Arabic, else 'en'."""
    if not text:
        return "en"
    arabic = sum(1 for c in text if "؀" <= c <= "ۿ" or "ݐ" <= c <= "ݿ")
    return "ar" if arabic / max(len(text), 1) > 0.2 else "en"
