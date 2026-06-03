"""Prompt-injection defense at the Channel Gateway.

Citizen WhatsApp/voice/web text is untrusted input. We never let it override system prompts.
This is a cheap regex layer; defense-in-depth is the structured-output schema (which makes it
impossible for a citizen message to e.g. force `escalated=True`).
"""

from __future__ import annotations

import re

_PATTERNS = [
    re.compile(r"\bignore (?:all )?(?:previous|prior|above) (?:instructions|prompts?)\b", re.I),
    re.compile(r"\b(?:you are|act as|pretend to be) a (?:different|new) (?:assistant|agent|ai|model)\b", re.I),
    re.compile(r"\bsystem\s*[:>]\s*", re.I),
    re.compile(r"</?(system|assistant|user|tool)>", re.I),
    re.compile(r"\b(?:reveal|show|print|dump) (?:your )?(?:system prompt|instructions|guidelines)\b", re.I),
]


def looks_like_injection(text: str) -> bool:
    if not text:
        return False
    return any(p.search(text) for p in _PATTERNS)
