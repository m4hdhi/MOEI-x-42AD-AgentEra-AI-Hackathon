"""Federal-grade tools. Each tool is deterministic Python — agents call them, never invent."""

from .doc_ocr import doc_ocr
from .risk_score import risk_score
from .szhp_rules import szhp_rules_engine
from .uaepass import uaepass_lookup

__all__ = ["doc_ocr", "risk_score", "szhp_rules_engine", "uaepass_lookup"]
