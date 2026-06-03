"""Bias / sensitive-content detector.

Demo path: keyword + pattern rules covering nationality, gender, age, religion bias triggers.
Production path: dedicated classifier (e.g. fine-tuned mDeBERTa) — interface stays the same.

The scripted demo moment: a deliberately biased phrase enters as a draft, check_bias flags it,
the supervisor blocks it, and the audit trail shows the rejection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class BiasFinding:
    category: str
    snippet: str
    severity: str   # "low" | "medium" | "high"


_RULES: list[tuple[str, str, str]] = [
    ("nationality_stereotype", r"\b(all|most|every)\s+(emiratis|expats|indians|filipinos|pakistanis|bangladeshis)\s+\w+", "high"),
    ("gender_stereotype", r"\b(women|men)\s+(can'?t|cannot|should not|always|never)\b", "high"),
    ("age_stereotype", r"\b(old|young)\s+people\s+(can'?t|are unable|always|never)\b", "medium"),
    ("religion_stereotype", r"\b(muslims|christians|hindus|sikhs)\s+(always|never|all)\b", "high"),
    ("disability_stereotype", r"\b(disabled|handicapped)\s+people\s+(can'?t|cannot)\b", "high"),
]


def check_bias(text: str) -> list[BiasFinding]:
    if not text:
        return []
    findings: list[BiasFinding] = []
    for cat, pat, sev in _RULES:
        for m in re.finditer(pat, text, flags=re.IGNORECASE):
            findings.append(BiasFinding(category=cat, snippet=m.group(0), severity=sev))
    return findings
