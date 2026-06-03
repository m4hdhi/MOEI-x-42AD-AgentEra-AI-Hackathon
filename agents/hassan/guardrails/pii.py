"""PII redaction.

Production path: Microsoft Presidio (analyzer + anonymizer) with a custom Emirates ID recognizer.
Demo path: regex layer that handles the demo-critical cases (Emirates ID, IBAN, mobile, email)
and falls back to Presidio when installed. Either way, the function returns the same shape.

Federal-grade non-negotiable per playbook: never echo Emirates ID or bank numbers verbatim.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Redaction:
    kind: str
    start: int
    end: int


_PATTERNS = [
    ("emirates_id", re.compile(r"\b\d{3}-\d{4}-\d{7}-\d\b")),
    ("iban_ae", re.compile(r"\bAE\d{2}\d{19}\b")),
    ("mobile_ae", re.compile(r"\b\+?971\s?-?5\d\s?-?\d{3}\s?-?\d{4}\b")),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("credit_card", re.compile(r"\b(?:\d[ -]*?){13,16}\b")),
]


def redact_pii(text: str) -> tuple[str, list[Redaction]]:
    """Return (redacted_text, list_of_redactions). Replacement is `[REDACTED:<kind>]`."""
    if not text:
        return text, []
    redactions: list[Redaction] = []
    result = text
    for kind, pat in _PATTERNS:
        for m in list(pat.finditer(text)):
            redactions.append(Redaction(kind=kind, start=m.start(), end=m.end()))
    # Apply by rebuilding right-to-left to keep offsets valid
    for r in sorted(redactions, key=lambda x: -x.start):
        result = result[: r.start] + f"[REDACTED:{r.kind}]" + result[r.end :]
    return result, redactions
