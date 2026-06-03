"""Document OCR + structure extraction.

Production path: Docling (IBM, MIT, federal-clean). Demo path: lazy-import Docling and fall back
to a regex-based salary-slip parser when Docling isn't installed in the smoke environment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class SalarySlip:
    employer: str | None
    employee_name: str | None
    emirates_id: str | None
    monthly_gross_aed: float | None
    monthly_net_aed: float | None
    pay_period: str | None
    raw_text: str


def doc_ocr(file_path: str | None = None, text: str | None = None) -> SalarySlip:
    """Extract structured fields from a salary slip.

    Pass `file_path` for real PDFs (uses Docling), or `text` for synthetic-text shortcut path.
    """
    if file_path and text is None:
        try:
            from docling.document_converter import DocumentConverter

            converter = DocumentConverter()
            doc = converter.convert(file_path).document
            text = doc.export_to_markdown()
        except Exception:
            # Demo: if Docling can't load (heavy dep), fall back to reading file as text
            try:
                with open(file_path, encoding="utf-8") as f:
                    text = f.read()
            except Exception:
                text = ""
    text = text or ""

    return SalarySlip(
        employer=_find(r"(?:Employer|Company)\s*[:\-]\s*(.+)", text),
        employee_name=_find(r"(?:Name|Employee)\s*[:\-]\s*(.+)", text),
        emirates_id=_find(r"\b(\d{3}-\d{4}-\d{7}-\d)\b", text),
        monthly_gross_aed=_amount(r"(?:Gross|Basic).*?AED\s*([\d,]+\.?\d*)", text),
        monthly_net_aed=_amount(r"(?:Net|Take[- ]Home).*?AED\s*([\d,]+\.?\d*)", text),
        pay_period=_find(r"(?:Period|Month)\s*[:\-]\s*(.+)", text),
        raw_text=text[:2000],
    )


def _find(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _amount(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None
